from __future__ import annotations

import json
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .contracts import INTENT_RESPONSE_CONTRACT_VERSION


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS artifacts (
  sha256 TEXT PRIMARY KEY, artifact_id TEXT UNIQUE NOT NULL, relative_path TEXT NOT NULL,
  fixture_root TEXT NOT NULL, byte_length INTEGER NOT NULL, mime_type TEXT NOT NULL,
  modality TEXT NOT NULL, split TEXT NOT NULL, defect_family TEXT NOT NULL,
  defect_present INTEGER NOT NULL, synthetic INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS assignments (
  assignment_id TEXT PRIMARY KEY, rater_id TEXT NOT NULL, artifact_sha256 TEXT NOT NULL,
  sequence INTEGER NOT NULL, repeat_group TEXT, started_at TEXT,
  completed_at TEXT, UNIQUE(rater_id, sequence),
  FOREIGN KEY(artifact_sha256) REFERENCES artifacts(sha256)
);
CREATE TABLE IF NOT EXISTS annotations (
  annotation_id TEXT PRIMARY KEY, assignment_id TEXT UNIQUE NOT NULL, rater_id TEXT NOT NULL,
  artifact_sha256 TEXT NOT NULL, verdict TEXT NOT NULL, confidence REAL NOT NULL,
    confidence_scale TEXT NOT NULL DEFAULT '1-5', severity INTEGER, defect_timestamps TEXT,
    reason_codes TEXT NOT NULL, note TEXT NOT NULL, started_at TEXT NOT NULL,
  completed_at TEXT NOT NULL, FOREIGN KEY(assignment_id) REFERENCES assignments(assignment_id)
);
CREATE TABLE IF NOT EXISTS adjudications (
  adjudication_id TEXT PRIMARY KEY, artifact_sha256 TEXT NOT NULL, adjudicator_id TEXT NOT NULL,
  verdict TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS intent_responses (
  response_id TEXT PRIMARY KEY, assignment_id TEXT UNIQUE NOT NULL, rater_id TEXT NOT NULL,
  artifact_sha256 TEXT NOT NULL, response_contract_version TEXT NOT NULL,
  components TEXT NOT NULL, other_beats TEXT NOT NULL, play_count INTEGER NOT NULL,
  play_limit INTEGER, started_at TEXT NOT NULL, completed_at TEXT NOT NULL,
  FOREIGN KEY(assignment_id) REFERENCES assignments(assignment_id)
);
CREATE TABLE IF NOT EXISTS intent_plays (
  play_id TEXT PRIMARY KEY, assignment_id TEXT NOT NULL, rater_id TEXT NOT NULL,
  play_number INTEGER NOT NULL, started_at TEXT NOT NULL, UNIQUE(assignment_id, play_number),
  FOREIGN KEY(assignment_id) REFERENCES assignments(assignment_id)
);
CREATE TABLE IF NOT EXISTS intent_freezes (
  freeze_id TEXT PRIMARY KEY, export_sha256 TEXT NOT NULL, export_format TEXT NOT NULL,
  response_count INTEGER NOT NULL, created_at TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS intent_responses_no_update BEFORE UPDATE ON intent_responses
BEGIN SELECT RAISE(ABORT, 'intent responses are append-only'); END;
CREATE TRIGGER IF NOT EXISTS intent_responses_no_delete BEFORE DELETE ON intent_responses
BEGIN SELECT RAISE(ABORT, 'intent responses are append-only'); END;
CREATE TRIGGER IF NOT EXISTS intent_plays_no_update BEFORE UPDATE ON intent_plays
BEGIN SELECT RAISE(ABORT, 'intent plays are append-only'); END;
CREATE TRIGGER IF NOT EXISTS intent_plays_no_delete BEFORE DELETE ON intent_plays
BEGIN SELECT RAISE(ABORT, 'intent plays are append-only'); END;
CREATE TRIGGER IF NOT EXISTS intent_freezes_no_update BEFORE UPDATE ON intent_freezes
BEGIN SELECT RAISE(ABORT, 'intent freezes are append-only'); END;
CREATE TRIGGER IF NOT EXISTS intent_freezes_no_delete BEFORE DELETE ON intent_freezes
BEGIN SELECT RAISE(ABORT, 'intent freezes are append-only'); END;
"""

STUDIES = ("annotation", "intent")


class CollectionFrozen(Exception):
    """Intent responses were already exported for reveal; collection is closed."""


class PlayRefused(Exception):
    """A play start the server will not record: limit reached, completed, or out of order."""


def connect(path: Path | str) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize(path: Path | str) -> None:
    with connect(path) as db:
        db.executescript(SCHEMA)
        columns = {row["name"] for row in db.execute("PRAGMA table_info(annotations)")}
        if "confidence_scale" not in columns:
            db.execute(
                "ALTER TABLE annotations ADD COLUMN confidence_scale TEXT NOT NULL DEFAULT 'legacy-0-1'"
            )
        if "severity" not in columns:
            db.execute("ALTER TABLE annotations ADD COLUMN severity INTEGER")
        if "defect_timestamps" not in columns:
            db.execute("ALTER TABLE annotations ADD COLUMN defect_timestamps TEXT")


def ingest(path: Path | str, manifest: dict, fixture_root: Path) -> int:
    initialize(path)
    with connect(path) as db:
        for artifact in manifest["artifacts"]:
            db.execute(
                """INSERT OR REPLACE INTO artifacts
                (sha256, artifact_id, relative_path, fixture_root, byte_length, mime_type,
                 modality, split, defect_family, defect_present, synthetic)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    artifact["sha256"], artifact["artifact_id"], artifact["relative_path"], str(fixture_root.resolve()),
                    artifact["byte_length"], artifact["mime_type"], artifact["modality"], artifact["split"],
                    artifact["defect_family"], int(artifact["defect_present"]), int(artifact["synthetic"]),
                ),
            )
    return len(manifest["artifacts"])


def ensure_assignments(
    db: sqlite3.Connection, rater_id: str, seed: int = 20260825, repeats: bool = True,
) -> None:
    exists = db.execute("SELECT 1 FROM assignments WHERE rater_id = ? LIMIT 1", (rater_id,)).fetchone()
    if exists:
        return
    import random

    artifacts = [row["sha256"] for row in db.execute("SELECT sha256 FROM artifacts ORDER BY sha256")]
    rng = random.Random(f"{seed}:{rater_id}")
    rng.shuffle(artifacts)
    # A repeat is a second exposure, which would contaminate intent recall.
    repeated = artifacts[: max(1, len(artifacts) // 8)] if repeats else []
    sequence = artifacts + repeated
    rng.shuffle(sequence)
    repeat_groups = {value: secrets.token_hex(6) for value in repeated}
    for index, artifact_hash in enumerate(sequence):
        db.execute(
            "INSERT INTO assignments VALUES (?, ?, ?, ?, ?, NULL, NULL)",
            (secrets.token_urlsafe(12), rater_id, artifact_hash, index, repeat_groups.get(artifact_hash)),
        )


def next_assignment(
    db: sqlite3.Connection, rater_id: str, seed: int = 20260825, repeats: bool = True,
) -> dict | None:
    ensure_assignments(db, rater_id, seed, repeats)
    row = db.execute(
        """SELECT a.assignment_id, a.sequence, a.started_at, x.sha256, x.artifact_id,
                  x.mime_type, x.modality, x.relative_path, x.fixture_root
           FROM assignments a JOIN artifacts x ON x.sha256 = a.artifact_sha256
           WHERE a.rater_id = ? AND a.completed_at IS NULL ORDER BY a.sequence LIMIT 1""",
        (rater_id,),
    ).fetchone()
    if not row:
        return None
    started_at = row["started_at"] or datetime.now(timezone.utc).isoformat()
    if not row["started_at"]:
        db.execute("UPDATE assignments SET started_at = ? WHERE assignment_id = ?", (started_at, row["assignment_id"]))
    result = dict(row)
    result["started_at"] = started_at
    # Deliberately excludes truth, defect family, split, repeat marker, and evaluator output.
    return result


def save_annotation(db: sqlite3.Connection, assignment_id: str, rater_id: str, payload: dict) -> dict:
    assignment = db.execute(
        "SELECT * FROM assignments WHERE assignment_id = ? AND rater_id = ?",
        (assignment_id, rater_id),
    ).fetchone()
    if not assignment:
        raise ValueError("assignment not found for rater")
    if assignment["completed_at"]:
        raise ValueError("assignment already completed")
    completed_at = datetime.now(timezone.utc).isoformat()
    annotation_id = secrets.token_urlsafe(12)
    db.execute(
        """INSERT INTO annotations
           (annotation_id, assignment_id, rater_id, artifact_sha256, verdict, confidence,
            confidence_scale, severity, defect_timestamps, reason_codes, note, started_at, completed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            annotation_id, assignment_id, rater_id, assignment["artifact_sha256"], payload["verdict"],
            payload["confidence"], "1-5", payload["severity"],
            payload.get("defect_timestamps", "").strip(),
            json.dumps(payload["reason_codes"]), payload.get("note", ""),
            assignment["started_at"], completed_at,
        ),
    )
    db.execute("UPDATE assignments SET completed_at = ? WHERE assignment_id = ?", (completed_at, assignment_id))
    return {"annotation_id": annotation_id, "completed_at": completed_at}


def progress(db: sqlite3.Connection, rater_id: str, repeats: bool = True) -> dict[str, int]:
    ensure_assignments(db, rater_id, repeats=repeats)
    row = db.execute(
        "SELECT COUNT(*) total, SUM(CASE WHEN completed_at IS NOT NULL THEN 1 ELSE 0 END) completed FROM assignments WHERE rater_id = ?",
        (rater_id,),
    ).fetchone()
    return {"total": row["total"], "completed": row["completed"] or 0}


def study_conflict(db: sqlite3.Connection, study: str) -> str | None:
    """Explain why this database cannot serve ``study``, or return None.

    PASS/HOLD annotation and intent recall share the assignment table, so one
    database serves one study. Intent assignments must also have no repeats.
    """
    if study == "intent":
        if db.execute("SELECT 1 FROM annotations LIMIT 1").fetchone():
            return "database already holds PASS/HOLD annotations; use a separate database for the intent study"
        if db.execute("SELECT 1 FROM assignments WHERE repeat_group IS NOT NULL LIMIT 1").fetchone():
            return "database has repeat assignments from an annotation session; use a separate database for the intent study"
    elif db.execute("SELECT 1 FROM intent_responses LIMIT 1").fetchone():
        return "database already holds intent responses; use a separate database for annotation"
    return None


def intent_collection_frozen(db: sqlite3.Connection) -> bool:
    return db.execute("SELECT 1 FROM intent_freezes LIMIT 1").fetchone() is not None


def intent_plays_used(db: sqlite3.Connection, assignment_id: str) -> int:
    return db.execute(
        "SELECT COUNT(*) FROM intent_plays WHERE assignment_id = ?", (assignment_id,),
    ).fetchone()[0]


def record_intent_play(
    db: sqlite3.Connection, assignment_id: str, rater_id: str, play_number: int,
    play_limit: int | None,
) -> dict:
    """Append one play start before the browser plays the clip.

    The durable count is the exposure record: a reload or re-entry restores it,
    and a response must report it exactly. Re-sending a recorded play_number
    replays its receipt, so an interrupted request never counts twice.
    """
    assignment = db.execute(
        "SELECT * FROM assignments WHERE assignment_id = ? AND rater_id = ?",
        (assignment_id, rater_id),
    ).fetchone()
    if not assignment:
        raise ValueError("assignment not found for rater")
    saved = db.execute(
        "SELECT play_id, started_at FROM intent_plays WHERE assignment_id = ? AND play_number = ?",
        (assignment_id, play_number),
    ).fetchone()
    used = intent_plays_used(db, assignment_id)
    if saved:
        return {"play_id": saved["play_id"], "play_number": play_number,
                "plays_used": used, "replayed": True}
    if intent_collection_frozen(db):
        raise CollectionFrozen("intent responses are frozen for reveal; collection is closed")
    if assignment["completed_at"]:
        raise PlayRefused("assignment already completed")
    if play_limit is not None and used >= play_limit:
        raise PlayRefused(f"play limit of {play_limit} reached")
    if play_number != used + 1:
        raise PlayRefused(f"play_number must be {used + 1}, the next play")
    play_id = secrets.token_urlsafe(12)
    db.execute(
        "INSERT INTO intent_plays (play_id, assignment_id, rater_id, play_number, started_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (play_id, assignment_id, rater_id, play_number, datetime.now(timezone.utc).isoformat()),
    )
    return {"play_id": play_id, "play_number": play_number, "plays_used": play_number}


def save_intent_response(
    db: sqlite3.Connection, assignment_id: str, rater_id: str, normalized: dict,
    play_limit: int | None,
) -> dict:
    """Append one normalized Stage 1 response. Never updates an earlier one."""
    assignment = db.execute(
        "SELECT * FROM assignments WHERE assignment_id = ? AND rater_id = ?",
        (assignment_id, rater_id),
    ).fetchone()
    if not assignment:
        raise ValueError("assignment not found for rater")
    if assignment["completed_at"]:
        raise ValueError("assignment already completed")
    if intent_collection_frozen(db):
        raise CollectionFrozen("intent responses are frozen for reveal; collection is closed")
    used = intent_plays_used(db, assignment_id)
    if normalized["play_count"] != used:
        raise ValueError(f"play_count must equal the {used} plays recorded for this assignment")
    completed_at = datetime.now(timezone.utc).isoformat()
    response_id = secrets.token_urlsafe(12)
    db.execute(
        """INSERT INTO intent_responses
           (response_id, assignment_id, rater_id, artifact_sha256, response_contract_version,
            components, other_beats, play_count, play_limit, started_at, completed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            response_id, assignment_id, rater_id, assignment["artifact_sha256"],
            INTENT_RESPONSE_CONTRACT_VERSION, json.dumps(normalized["components"], sort_keys=True),
            normalized["other_beats"], normalized["play_count"], play_limit,
            assignment["started_at"], completed_at,
        ),
    )
    db.execute("UPDATE assignments SET completed_at = ? WHERE assignment_id = ?", (completed_at, assignment_id))
    return {"response_id": response_id, "completed_at": completed_at}


def saved_intent_receipt(
    db: sqlite3.Connection, assignment_id: str, rater_id: str, normalized: dict,
) -> dict | None:
    """Return the original receipt only if the saved response equals ``normalized``."""
    saved = db.execute(
        """SELECT response_id, completed_at, components, other_beats, play_count
           FROM intent_responses WHERE assignment_id=? AND rater_id=?""",
        (assignment_id, rater_id),
    ).fetchone()
    if saved is None or (
        json.loads(saved["components"]), saved["other_beats"], saved["play_count"],
    ) != (normalized["components"], normalized["other_beats"], normalized["play_count"]):
        return None
    return {"response_id": saved["response_id"], "completed_at": saved["completed_at"]}


def record_intent_freeze(db: sqlite3.Connection, export_sha256: str, export_format: str, count: int) -> dict:
    freeze = {
        "freeze_id": secrets.token_urlsafe(12), "export_sha256": export_sha256,
        "export_format": export_format, "response_count": count,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    db.execute(
        """INSERT INTO intent_freezes (freeze_id, export_sha256, export_format, response_count, created_at)
           VALUES (:freeze_id, :export_sha256, :export_format, :response_count, :created_at)""",
        freeze,
    )
    return freeze
