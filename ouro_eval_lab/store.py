from __future__ import annotations

import json
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


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
  reason_codes TEXT NOT NULL, note TEXT NOT NULL, started_at TEXT NOT NULL,
  completed_at TEXT NOT NULL, FOREIGN KEY(assignment_id) REFERENCES assignments(assignment_id)
);
CREATE TABLE IF NOT EXISTS adjudications (
  adjudication_id TEXT PRIMARY KEY, artifact_sha256 TEXT NOT NULL, adjudicator_id TEXT NOT NULL,
  verdict TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL
);
"""


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


def ensure_assignments(db: sqlite3.Connection, rater_id: str, seed: int = 20260825) -> None:
    exists = db.execute("SELECT 1 FROM assignments WHERE rater_id = ? LIMIT 1", (rater_id,)).fetchone()
    if exists:
        return
    import random

    artifacts = [row["sha256"] for row in db.execute("SELECT sha256 FROM artifacts ORDER BY sha256")]
    rng = random.Random(f"{seed}:{rater_id}")
    rng.shuffle(artifacts)
    repeats = artifacts[: max(1, len(artifacts) // 8)]
    sequence = artifacts + repeats
    rng.shuffle(sequence)
    repeat_groups = {value: secrets.token_hex(6) for value in repeats}
    for index, artifact_hash in enumerate(sequence):
        db.execute(
            "INSERT INTO assignments VALUES (?, ?, ?, ?, ?, NULL, NULL)",
            (secrets.token_urlsafe(12), rater_id, artifact_hash, index, repeat_groups.get(artifact_hash)),
        )


def next_assignment(db: sqlite3.Connection, rater_id: str, seed: int = 20260825) -> dict | None:
    ensure_assignments(db, rater_id, seed)
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
        """INSERT INTO annotations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            annotation_id, assignment_id, rater_id, assignment["artifact_sha256"], payload["verdict"],
            payload["confidence"], json.dumps(payload["reason_codes"]), payload.get("note", ""),
            assignment["started_at"], completed_at,
        ),
    )
    db.execute("UPDATE assignments SET completed_at = ? WHERE assignment_id = ?", (completed_at, assignment_id))
    return {"annotation_id": annotation_id, "completed_at": completed_at}


def progress(db: sqlite3.Connection, rater_id: str) -> dict[str, int]:
    ensure_assignments(db, rater_id)
    row = db.execute(
        "SELECT COUNT(*) total, SUM(CASE WHEN completed_at IS NOT NULL THEN 1 ELSE 0 END) completed FROM assignments WHERE rater_id = ?",
        (rater_id,),
    ).fetchone()
    return {"total": row["total"], "completed": row["completed"] or 0}
