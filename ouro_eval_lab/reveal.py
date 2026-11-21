"""Reveal sealed intent records, only after the viewer responses are frozen.

The checks here are the same ones `scripts/verify_intent_reveal.py` runs.
`reveal` adds the order rule: it refuses unless `export-intent` already
recorded a response freeze, then loads the verified records into append-only
tables bound to that freeze.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .contracts import INTENT_CONTRACT_VERSION, ContractError, validate_intent_record
from .runner import verify_manifest

DEFAULT_DIR = Path(__file__).resolve().parents[1] / "data" / "public_intent"


class RevealRefused(ValueError):
    """The reveal would break the freeze-before-reveal order or its commitments."""


def read_commitments(path: Path) -> dict[str, str]:
    commitments = {}
    for line in path.read_text().splitlines():
        digest, _, name = line.partition("  ")
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest) or not name:
            raise ValueError(f"malformed commitment line: {line!r}")
        if "/" in name or "\\" in name or name in commitments:
            raise ValueError(f"invalid or duplicate record name: {name!r}")
        commitments[name] = digest
    return commitments


def verify(commitments_path: Path, records_dir: Path, manifest_path: Path, schema: bool = True) -> list[str]:
    """Return every problem with the revealed records; an empty list means OK."""
    commitments = read_commitments(commitments_path)
    artifacts = {a["relative_path"]: a["artifact_id"] for a in json.loads(manifest_path.read_text())["artifacts"]}
    problems = []
    expected = {Path(clip).stem + ".intent.json" for clip in artifacts}
    for name in sorted(expected - set(commitments)):
        problems.append(f"{name}: no commitment for a manifest clip")
    for name in sorted(set(commitments) - expected):
        problems.append(f"{name}: commitment for a clip not in the manifest")
    if not expected:
        problems.append("manifest lists no clips")
    for name, digest in commitments.items():
        record_path = records_dir / name
        if not record_path.is_file():
            problems.append(f"{name}: missing")
            continue
        body = record_path.read_bytes()
        if hashlib.sha256(body).hexdigest() != digest:
            problems.append(f"{name}: SHA-256 does not match the commitment")
            continue
        try:
            record = json.loads(body)
        except ValueError:
            problems.append(f"{name}: is not valid JSON")
            continue
        if not isinstance(record, dict):
            problems.append(f"{name}: is not one JSON object")
            continue
        clip = record.get("relative_path")
        if clip not in artifacts or artifacts[clip] != record.get("artifact_id"):
            problems.append(f"{name}: names a clip that is not in the manifest")
        elif name != Path(clip).stem + ".intent.json":
            problems.append(f"{name}: record name does not match its clip")
        elif schema:
            # Only bytes that match their commitment are worth schema-checking.
            try:
                validate_intent_record(record)
            except ContractError as exc:
                problems.append(f"{name}: {exc}")
    return problems


def reveal(db: sqlite3.Connection, records_dir: Path, commitments_path: Path, manifest_path: Path) -> dict:
    """Load verified intent records once, bound to the latest response freeze.

    Revealing the same records again is a no-op. Revealing different records
    is refused: revealed records are append-only, like the responses.
    """
    freeze = db.execute(
        "SELECT freeze_id, export_sha256 FROM intent_freezes ORDER BY created_at DESC, freeze_id LIMIT 1"
    ).fetchone()
    if freeze is None:
        raise RevealRefused("no response freeze is recorded; run export-intent before any reveal")
    problems = verify(commitments_path, records_dir, manifest_path)
    if problems:
        raise RevealRefused("reveal check failed: " + "; ".join(problems))
    by_path = {a["relative_path"]: a for a in verify_manifest(manifest_path)["manifest"]["artifacts"]}
    rows = []
    for name in sorted(read_commitments(commitments_path)):
        body = (records_dir / name).read_bytes()
        record = json.loads(body)
        artifact = by_path[record["relative_path"]]
        if not db.execute("SELECT 1 FROM artifacts WHERE sha256 = ?", (artifact["sha256"],)).fetchone():
            raise RevealRefused(f"{name}: its clip is not loaded in this lab database")
        rows.append({
            "record_sha256": hashlib.sha256(body).hexdigest(),
            "artifact_sha256": artifact["sha256"],
            "artifact_id": record["artifact_id"],
            "relative_path": record["relative_path"],
            "record_json": body.decode(),
        })
    existing = {row[0] for row in db.execute("SELECT record_sha256 FROM intent_records")}
    if existing:
        if existing == {row["record_sha256"] for row in rows}:
            return {"already_revealed": True, "record_count": len(rows), "freeze_sha256": freeze["export_sha256"]}
        raise RevealRefused("different intent records were already revealed; revealed records are append-only")
    reveal_id = secrets.token_urlsafe(12)
    revealed_at = datetime.now(timezone.utc).isoformat()
    db.execute(
        """INSERT INTO intent_reveals
           (reveal_id, freeze_id, freeze_sha256, commitments_sha256, record_count, revealed_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (reveal_id, freeze["freeze_id"], freeze["export_sha256"],
         hashlib.sha256(commitments_path.read_bytes()).hexdigest(), len(rows), revealed_at),
    )
    for row in rows:
        db.execute(
            """INSERT INTO intent_records
               (record_sha256, reveal_id, artifact_sha256, artifact_id, relative_path,
                record_json, intent_contract_version)
               VALUES (:record_sha256, :reveal_id, :artifact_sha256, :artifact_id, :relative_path,
                       :record_json, :intent_contract_version)""",
            {**row, "reveal_id": reveal_id, "intent_contract_version": INTENT_CONTRACT_VERSION},
        )
    return {
        "already_revealed": False, "reveal_id": reveal_id, "record_count": len(rows),
        "freeze_sha256": freeze["export_sha256"], "revealed_at": revealed_at,
    }
