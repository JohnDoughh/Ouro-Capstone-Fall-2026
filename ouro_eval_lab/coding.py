"""Stage 2 independent coding: coder sheets and code import (Team C).

A coder sheet lists one item per (frozen viewer response, intent component),
next to the revealed record's text and delivery code for that component. It
is built only after the reveal, and it never carries viewer IDs, viewer
certainty, artifact IDs, evaluator output or any other coder's codes. A coder
never receives items for a clip they were assigned as a viewer.

Imported codes are append-only. Each one is bound to the SHA-256 of the exact
stored response, the revealed record and the clip, so a code can never drift
onto a different response. Disagreement is kept; it is resolved only through
separate adjudication records.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import random
import secrets
import sqlite3
from datetime import datetime, timezone

from .contracts import (
    INTENT_CODEBOOK_VERSION, INTENT_CODING_CONTRACT_VERSION, INTENT_FIELDS, ContractError,
    intent_coding_units, validate_intent_code, validate_pseudonymous_id,
)

# Pre-registered seed (docs/TEAM_C_PREREGISTRATION.md); sheets record the one used.
DEFAULT_SHEET_SEED = 20261014
SHEET_FIELDS = [
    "item", "item_id", "component", "delivery", "intended_text",
    "viewer_recall", "viewer_could_not_tell", "code", "confidence", "note",
]
CODE_FIELDS = {"item_id", "code", "confidence", "note"}
_RESPONSE_COLUMNS = (
    "response_id", "assignment_id", "rater_id", "artifact_sha256", "response_contract_version",
    "components", "other_beats", "play_count", "play_limit", "started_at", "completed_at",
)


class CodingRefused(ValueError):
    """A sheet or import that would break blinding, order or append-only codes."""


def response_sha256(row: sqlite3.Row | dict) -> str:
    """SHA-256 of one stored response in canonical JSON (every stored column).

    Anyone holding the frozen export can recompute it, and a code bound to it
    cannot silently move to a different or altered response.
    """
    canonical = {column: row[column] for column in _RESPONSE_COLUMNS}
    canonical["components"] = json.loads(canonical["components"])
    body = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(body.encode()).hexdigest()


def _latest_reveal(db: sqlite3.Connection) -> sqlite3.Row:
    reveal = db.execute(
        "SELECT reveal_id FROM intent_reveals ORDER BY revealed_at DESC, reveal_id LIMIT 1"
    ).fetchone()
    if reveal is None:
        raise CodingRefused("no intent records are revealed; run export-intent and reveal first")
    return reveal


def coding_items(db: sqlite3.Connection, coder_id: str, reveal_id: str, seed: int) -> list[dict]:
    """Return this coder's items in their seeded order.

    Item IDs are derived from the reveal ID (a random token coders never see),
    the coder and the unit, so the same sheet can be rebuilt and checked.
    """
    records = {
        row["artifact_sha256"]: row for row in db.execute(
            "SELECT record_sha256, artifact_sha256, record_json FROM intent_records WHERE reveal_id = ?",
            (reveal_id,),
        )
    }
    # Any assignment counts: a coder may have seen a clip without finishing it.
    watched = {row[0] for row in db.execute(
        "SELECT DISTINCT artifact_sha256 FROM assignments WHERE rater_id = ?", (coder_id,),
    )}
    items = []
    for row in db.execute(
        "SELECT " + ", ".join(_RESPONSE_COLUMNS) + " FROM intent_responses ORDER BY response_id"
    ):
        if row["artifact_sha256"] in watched:
            continue
        record = records.get(row["artifact_sha256"])
        if record is None:
            raise CodingRefused("a frozen response has no revealed intent record for its clip")
        units = intent_coding_units(json.loads(record["record_json"]))
        components = json.loads(row["components"])
        digest = response_sha256(row)
        for component in INTENT_FIELDS:
            key = f"{reveal_id}|{coder_id}|{row['response_id']}|{component}"
            items.append({
                "item_id": hashlib.sha256(key.encode()).hexdigest()[:24],
                "response_id": row["response_id"],
                "response_sha256": digest,
                "record_sha256": record["record_sha256"],
                "artifact_sha256": row["artifact_sha256"],
                "component": component,
                "delivery": units[component]["delivery"],
                "intended_text": units[component]["text"],
                "viewer_recall": components[component]["recall"],
                "viewer_could_not_tell": components[component]["could_not_tell"],
            })
    random.Random(f"{seed}:{coder_id}").shuffle(items)
    return items


def _cell(text: str) -> str:
    # Spreadsheet apps run cells that start like a formula. These columns are
    # display-only (import never reads them back), so the guard is harmless.
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def render_sheet(items: list[dict]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=SHEET_FIELDS, lineterminator="\n")
    writer.writeheader()
    for position, item in enumerate(items, start=1):
        writer.writerow({
            "item": position, "item_id": item["item_id"], "component": item["component"],
            "delivery": item["delivery"], "intended_text": _cell(item["intended_text"]),
            "viewer_recall": _cell(item["viewer_recall"]),
            "viewer_could_not_tell": "yes" if item["viewer_could_not_tell"] else "no",
            "code": "", "confidence": "", "note": "",
        })
    return stream.getvalue().encode()


def issue_sheet(db: sqlite3.Connection, coder_id: str, seed: int = DEFAULT_SHEET_SEED) -> dict:
    """Build (or rebuild) one coder's sheet and record it once.

    Each coder gets exactly one sheet. Asking again with the same seed returns
    the identical bytes; a different seed is refused so a coder never sees a
    second ordering.
    """
    coder_id = validate_pseudonymous_id(coder_id, "coder")
    existing = db.execute("SELECT * FROM intent_coding_sheets WHERE coder_id = ?", (coder_id,)).fetchone()
    reveal_id = existing["reveal_id"] if existing else _latest_reveal(db)["reveal_id"]
    if existing and existing["seed"] != seed:
        raise CodingRefused(
            f"coder already has a sheet built with seed {existing['seed']}; one sheet per coder"
        )
    items = coding_items(db, coder_id, reveal_id, seed)
    if not items:
        raise CodingRefused("no items for this coder: no frozen responses, or the coder viewed every clip")
    body = render_sheet(items)
    digest = hashlib.sha256(body).hexdigest()
    if existing:
        if existing["sheet_sha256"] != digest:
            raise CodingRefused("rebuilt sheet does not match the recorded sheet SHA-256")
        return {"body": body, "sheet_sha256": digest, "item_count": len(items),
                "sheet_id": existing["sheet_id"], "reissued": True}
    sheet_id = secrets.token_urlsafe(12)
    db.execute(
        """INSERT INTO intent_coding_sheets
           (sheet_id, coder_id, reveal_id, seed, item_count, sheet_sha256, codebook_version,
            coding_contract_version, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (sheet_id, coder_id, reveal_id, seed, len(items), digest, INTENT_CODEBOOK_VERSION,
         INTENT_CODING_CONTRACT_VERSION, datetime.now(timezone.utc).isoformat()),
    )
    return {"body": body, "sheet_sha256": digest, "item_count": len(items),
            "sheet_id": sheet_id, "reissued": False}


def import_codes(db: sqlite3.Connection, coder_id: str, body: bytes) -> dict:
    """Validate a filled sheet and append its codes, all or nothing.

    Rows left blank are uncoded and skipped, so a coder may import in parts.
    Re-importing an identical code is a no-op; a different code for an item
    already coded is refused: codes are never updated.
    """
    coder_id = validate_pseudonymous_id(coder_id, "coder")
    sheet = db.execute("SELECT * FROM intent_coding_sheets WHERE coder_id = ?", (coder_id,)).fetchone()
    if sheet is None:
        raise CodingRefused("no coding sheet was issued to this coder; run intent-coding-sheet first")
    items = coding_items(db, coder_id, sheet["reveal_id"], sheet["seed"])
    if hashlib.sha256(render_sheet(items)).hexdigest() != sheet["sheet_sha256"]:
        raise CodingRefused("the coder's items no longer match the recorded sheet SHA-256")
    by_id = {item["item_id"]: item for item in items}
    try:
        text = body.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise CodingRefused("codes file must be UTF-8 CSV") from None
    reader = csv.DictReader(io.StringIO(text, newline=""))
    missing = CODE_FIELDS - set(reader.fieldnames or [])
    if missing:
        raise CodingRefused(f"codes file is missing columns: {', '.join(sorted(missing))}")
    saved = {
        row["item_id"]: (row["code"], row["confidence"], row["note"]) for row in db.execute(
            "SELECT item_id, code, confidence, note FROM intent_codings WHERE coder_id = ?", (coder_id,),
        )
    }
    errors, seen, new, unchanged, uncoded = [], set(), [], 0, 0
    for line, row in enumerate(reader, start=2):
        item_id = (row.get("item_id") or "").strip()
        values = [(row.get(key) or "").strip() for key in ("code", "confidence", "note")]
        if not item_id and not any(values):
            continue
        if item_id not in by_id:
            errors.append(f"line {line}: item_id is not on this coder's sheet")
            continue
        if item_id in seen:
            errors.append(f"line {line}: item_id appears more than once")
            continue
        seen.add(item_id)
        if not any(values):
            uncoded += 1
            continue
        item = by_id[item_id]
        try:
            code = validate_intent_code(values[0], values[1], values[2], item["delivery"])
        except ContractError as exc:
            errors.append(f"line {line} ({item['component']}): {exc}")
            continue
        if item_id in saved:
            if saved[item_id] == (code["code"], code["confidence"], code["note"]):
                unchanged += 1
            else:
                errors.append(f"line {line}: item already has a different code; codes are append-only")
            continue
        new.append({**item, **code})
    if errors:
        shown = errors[:20] + ([f"... and {len(errors) - 20} more"] if len(errors) > 20 else [])
        raise CodingRefused("codes not imported: " + "; ".join(shown))
    result = {"coded": len(new), "unchanged": unchanged, "uncoded": uncoded,
              "import_sha256": hashlib.sha256(body).hexdigest()}
    if not new:
        return {**result, "import_id": None}
    import_id = secrets.token_urlsafe(12)
    imported_at = datetime.now(timezone.utc).isoformat()
    db.execute(
        """INSERT INTO intent_code_imports
           (import_id, sheet_id, coder_id, import_sha256, coded_count, unchanged_count, imported_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (import_id, sheet["sheet_id"], coder_id, result["import_sha256"], len(new), unchanged, imported_at),
    )
    for item in new:
        db.execute(
            """INSERT INTO intent_codings
               (coding_id, item_id, import_id, sheet_id, coder_id, response_id, response_sha256,
                record_sha256, artifact_sha256, component, delivery, code, confidence, note,
                codebook_version, coding_contract_version, coded_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (secrets.token_urlsafe(12), item["item_id"], import_id, sheet["sheet_id"], coder_id,
             item["response_id"], item["response_sha256"], item["record_sha256"],
             item["artifact_sha256"], item["component"], item["delivery"], item["code"],
             item["confidence"], item["note"], sheet["codebook_version"],
             INTENT_CODING_CONTRACT_VERSION, imported_at),
        )
    return {**result, "import_id": import_id}
