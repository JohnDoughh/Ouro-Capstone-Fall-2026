"""Team C drift anchors: a frozen set of coded examples for checking coders.

An anchor is one invented (component, intended text, viewer answer) example
with the code the frozen codebook expects. Coders re-code the anchors blind
from time to time; comparing their codes with the expected ones shows whether
coding has drifted from the codebook. Anchor codes are practice data: they are
never written to the lab database and never pooled with study codes.

An anchor set is bound to one codebook version and to the SHA-256 of the
codebook text, so anchors written for one version cannot silently be used
with another. The codebook hash is taken over its text with line endings
normalized to LF, because Git may check the codebook out with CRLF on Windows
and LF elsewhere; every machine then computes the same hash.

Anchors must be invented, never taken from the study set, so a coder or viewer
who sees them learns nothing about the study clips.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from pathlib import Path
from typing import Any

from .contracts import (
    INTENT_CODEBOOK_VERSION, INTENT_DELIVERY_CODES, INTENT_FIELDS, INTENT_RECALL_MAX,
    INTENT_TEXT_MAX, ContractError, _validate_record_text, validate_intent_code,
)

INTENT_ANCHORS_CONTRACT_VERSION = "1.0.0"
ANCHOR_SCHEMA = "team-c-intent-anchors"
ANCHOR_SET_KEYS = {
    "schema", "contract_version", "anchor_set_version", "codebook_version",
    "codebook_sha256", "fictional", "anchors",
}
ANCHOR_KEYS = {
    "anchor_id", "component", "delivery", "intended_text", "viewer_text",
    "viewer_could_not_tell", "expected_code", "rationale",
}
ANCHOR_MAX = 200
ANCHOR_RATIONALE_MAX = 300
ANCHOR_SHEET_FIELDS = [
    "anchor_id", "component", "delivery", "intended_text", "viewer_text",
    "viewer_could_not_tell", "code", "confidence", "note",
]
_ANCHOR_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,40}")
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
DEFAULT_CODEBOOK = Path(__file__).resolve().parents[1] / "docs" / "INTENT_CODEBOOK.md"


class AnchorRefused(ValueError):
    """An anchor set or coder check that must not be used."""


def codebook_sha256(path: Path) -> str:
    """SHA-256 of the codebook text with CRLF and CR normalized to LF."""
    text = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(text).hexdigest()


def validate_anchor_set(document: Any) -> None:
    """Validate an anchor set (anchors contract 1.0.0).

    Errors name keys and anchor IDs, never the example text.
    """
    if not isinstance(document, dict):
        raise ContractError("anchor set must be one JSON object")
    missing = sorted(ANCHOR_SET_KEYS - document.keys())
    if missing:
        raise ContractError(f"anchor set missing fields: {', '.join(missing)}")
    unknown = sorted(document.keys() - ANCHOR_SET_KEYS)
    if unknown:
        raise ContractError(f"anchor set contains unknown fields: {', '.join(unknown)}")
    if document["schema"] != ANCHOR_SCHEMA:
        raise ContractError(f"anchor set schema must be {ANCHOR_SCHEMA}")
    if document["contract_version"] != INTENT_ANCHORS_CONTRACT_VERSION:
        raise ContractError(f"anchor set contract_version must be {INTENT_ANCHORS_CONTRACT_VERSION}")
    if document["fictional"] is not True:
        raise ContractError("anchor set must be fictional: anchors are invented, never study items")
    for field in ("anchor_set_version", "codebook_version"):
        value = document[field]
        if not isinstance(value, str) or not value.strip() or len(value) > 40:
            raise ContractError(f"anchor set {field} must be a short non-empty string")
    if not isinstance(document["codebook_sha256"], str) or not _SHA256_RE.fullmatch(document["codebook_sha256"]):
        raise ContractError("anchor set codebook_sha256 must be 64 lowercase hex characters")
    anchors = document["anchors"]
    if not isinstance(anchors, list) or not anchors or len(anchors) > ANCHOR_MAX:
        raise ContractError(f"anchor set anchors must be a list of 1 to {ANCHOR_MAX} anchors")
    seen: set[str] = set()
    for index, anchor in enumerate(anchors):
        context = f"anchor {index + 1}"
        if not isinstance(anchor, dict) or set(anchor) != ANCHOR_KEYS:
            raise ContractError(f"{context} must contain exactly: {', '.join(sorted(ANCHOR_KEYS))}")
        anchor_id = anchor["anchor_id"]
        if not isinstance(anchor_id, str) or not _ANCHOR_ID_RE.fullmatch(anchor_id):
            raise ContractError(f"{context} anchor_id must be 1-40 letters, numbers, - or _")
        context = f"anchor {anchor_id}"
        if anchor_id in seen:
            raise ContractError(f"{context} is duplicated")
        seen.add(anchor_id)
        if anchor["component"] not in INTENT_FIELDS:
            raise ContractError(f"{context} component must be one of: {', '.join(INTENT_FIELDS)}")
        delivery = anchor["delivery"]
        if delivery not in INTENT_DELIVERY_CODES:
            raise ContractError(f"{context} delivery must be a controlled delivery code")
        if not isinstance(anchor["viewer_could_not_tell"], bool):
            raise ContractError(f"{context} viewer_could_not_tell must be true or false")
        _validate_record_text(
            anchor["intended_text"], f"{context} intended_text", INTENT_TEXT_MAX,
            required=delivery != "not_intended",
        )
        _validate_record_text(
            anchor["viewer_text"], f"{context} viewer_text", INTENT_RECALL_MAX,
            required=not anchor["viewer_could_not_tell"],
        )
        _validate_record_text(anchor["rationale"], f"{context} rationale", ANCHOR_RATIONALE_MAX)
        expected = anchor["expected_code"]
        try:
            # Same rules the coders' import enforces; the rationale stands in for the note.
            validate_intent_code(expected, 3, anchor["rationale"], delivery)
        except ContractError as exc:
            raise ContractError(f"{context} expected_code: {exc}") from None
        if anchor["viewer_could_not_tell"] and expected not in {"not_recovered", "not_applicable"}:
            raise ContractError(f"{context}: a could-not-tell answer is not_recovered (codebook rule 5)")


def load_anchor_set(path: Path, codebook: Path = DEFAULT_CODEBOOK, pinned: Path | None = None) -> dict:
    """Load, validate and bind an anchor set; refuse it if anything does not match.

    Checks, in order: the file's SHA-256 against ``pinned`` (when given), the
    contract, the codebook version in force, and the codebook text's hash.
    """
    if not path.is_file():
        raise AnchorRefused(f"anchor set not found: {path}")
    body = path.read_bytes()
    digest = hashlib.sha256(body).hexdigest()
    if pinned is not None:
        tokens = pinned.read_text().split() if pinned.is_file() else []
        if not tokens or tokens[0] != digest:
            raise AnchorRefused(
                f"anchor set SHA-256 {digest} does not match the pinned value in {pinned}"
            )
    try:
        document = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise AnchorRefused("anchor set is not valid UTF-8 JSON") from None
    try:
        validate_anchor_set(document)
    except ContractError as exc:
        raise AnchorRefused(str(exc)) from None
    if document["codebook_version"] != INTENT_CODEBOOK_VERSION:
        raise AnchorRefused(
            f"anchor set is for codebook {document['codebook_version']}, "
            f"but codebook {INTENT_CODEBOOK_VERSION} is in force"
        )
    if not codebook.is_file():
        raise AnchorRefused(f"codebook not found: {codebook}")
    actual = codebook_sha256(codebook)
    if actual != document["codebook_sha256"]:
        raise AnchorRefused(
            "codebook text has changed since the anchor set was bound "
            f"(codebook SHA-256 {actual}); re-bind and re-freeze the anchors deliberately"
        )
    return {"document": document, "sha256": digest, "codebook_sha256": actual}


def _cell(text: str) -> str:
    # Keep spreadsheet programs from running a cell as a formula.
    return "'" + text if text[:1] in {"=", "+", "-", "@"} else text


def render_anchor_sheet(document: dict) -> bytes:
    """A blind re-coding sheet: the examples without their expected codes."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=ANCHOR_SHEET_FIELDS, lineterminator="\n")
    writer.writeheader()
    for anchor in document["anchors"]:
        writer.writerow({
            "anchor_id": anchor["anchor_id"], "component": anchor["component"],
            "delivery": anchor["delivery"], "intended_text": _cell(anchor["intended_text"]),
            "viewer_text": _cell(anchor["viewer_text"]),
            "viewer_could_not_tell": "yes" if anchor["viewer_could_not_tell"] else "no",
            "code": "", "confidence": "", "note": "",
        })
    return buffer.getvalue().encode()


def check_coder(document: dict, body: bytes) -> dict:
    """Compare one coder's blind anchor codes with the expected codes.

    Every anchor must be coded, with the same validation as a study import.
    Returns counts and the mismatching anchor IDs; no example text.
    """
    try:
        text = body.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise AnchorRefused("anchor codes must be UTF-8 CSV") from None
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or not {"anchor_id", "code", "confidence", "note"} <= set(reader.fieldnames):
        raise AnchorRefused("anchor codes need anchor_id, code, confidence and note columns")
    anchors = {anchor["anchor_id"]: anchor for anchor in document["anchors"]}
    given: dict[str, str] = {}
    for line, row in enumerate(reader, start=2):
        anchor_id = (row.get("anchor_id") or "").strip()
        if anchor_id not in anchors:
            raise AnchorRefused(f"row {line}: unknown anchor_id")
        if anchor_id in given:
            raise AnchorRefused(f"row {line}: anchor {anchor_id} is coded twice")
        try:
            stored = validate_intent_code(
                row.get("code"), row.get("confidence"), row.get("note") or "",
                anchors[anchor_id]["delivery"],
            )
        except ContractError as exc:
            raise AnchorRefused(f"row {line} (anchor {anchor_id}): {exc}") from None
        given[anchor_id] = stored["code"]
    missing = sorted(set(anchors) - set(given))
    if missing:
        raise AnchorRefused(f"{len(missing)} anchors not coded: {', '.join(missing)}")
    mismatches = [
        {"anchor_id": anchor_id, "expected": anchors[anchor_id]["expected_code"], "given": code}
        for anchor_id, code in sorted(given.items())
        if code != anchors[anchor_id]["expected_code"]
    ]
    return {
        "anchors": len(anchors),
        "matching": len(anchors) - len(mismatches),
        "mismatches": mismatches,
        "codes_sha256": hashlib.sha256(body).hexdigest(),
    }
