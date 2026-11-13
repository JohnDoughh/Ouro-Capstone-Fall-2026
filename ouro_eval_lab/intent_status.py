"""Team C operator check: where an intent study database stands, and what to run next.

Read-only. It prints counts, stage flags and recorded SHA-256 values only:
never viewer or coder IDs, free text, artifact IDs or intent text, so its
output can be pasted into a team channel or an issue.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from .intent_metrics import MIN_RESPONSES

# Pre-registration §9 (docs/TEAM_C_PREREGISTRATION.md).
MIN_CODERS = 2
_INTENT_TABLES = ("intent_responses", "intent_freezes", "intent_reveals", "intent_coding_sheets")


def _one(db: sqlite3.Connection, sql: str, params: tuple = ()) -> object:
    return db.execute(sql, params).fetchone()[0]


def intent_status(db: sqlite3.Connection, db_path: Path) -> dict:
    """Summarize the study stage of one intent database and the next command."""
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    if not set(_INTENT_TABLES) <= tables or "artifacts" not in tables:
        return {
            "stage": "not_an_intent_database",
            "warnings": [],
            "next": f"python -m ouro_eval_lab.cli ingest --db {db_path} --manifest data/public_intent/manifest.json",
        }
    status: dict = {"warnings": []}
    warn = status["warnings"].append
    status["clips"] = _one(db, "SELECT COUNT(*) FROM artifacts")
    # Viewers who saved a response; opening the page alone creates assignments too.
    status["viewers"] = _one(db, "SELECT COUNT(DISTINCT rater_id) FROM intent_responses")
    status["responses"] = _one(db, "SELECT COUNT(*) FROM intent_responses")
    per_clip = [
        row[0] for row in db.execute(
            """SELECT COUNT(r.response_id) FROM artifacts a
               LEFT JOIN intent_responses r ON r.artifact_sha256 = a.sha256 GROUP BY a.sha256"""
        )
    ]
    status["fewest_responses_per_clip"] = min(per_clip) if per_clip else 0
    freeze = db.execute(
        "SELECT export_sha256, response_count FROM intent_freezes ORDER BY created_at DESC, rowid DESC LIMIT 1"
    ).fetchone()
    status["frozen"] = freeze is not None
    status["freeze_sha256"] = freeze[0] if freeze else None
    reveal = db.execute(
        "SELECT reveal_id, record_count FROM intent_reveals ORDER BY revealed_at DESC, rowid DESC LIMIT 1"
    ).fetchone()
    status["revealed"] = reveal is not None
    status["records"] = reveal[1] if reveal else 0
    sheets = db.execute("SELECT sheet_id, item_count FROM intent_coding_sheets").fetchall()
    status["coders"] = len(sheets)
    status["items_issued"] = sum(row[1] for row in sheets)
    status["items_coded"] = _one(db, "SELECT COUNT(*) FROM intent_codings")

    if _one(db, "SELECT COUNT(*) FROM annotations"):
        warn("this database also holds PASS/HOLD annotations; the intent study needs its own database")
    if status["frozen"] and status["fewest_responses_per_clip"] < MIN_RESPONSES:
        warn(f"at least one clip has fewer than {MIN_RESPONSES} responses; "
             "its cells will report insufficient_responses")
    if status["revealed"] and status["records"] != status["clips"]:
        warn("the number of revealed records differs from the number of ingested clips")

    serve = f"python -m ouro_eval_lab.cli serve --db {db_path} --study intent --play-limit 2"
    if status["clips"] == 0:
        status["stage"] = "empty"
        status["next"] = f"python -m ouro_eval_lab.cli ingest --db {db_path} --manifest data/public_intent/manifest.json"
    elif not status["frozen"]:
        status["stage"] = "collecting"
        if status["fewest_responses_per_clip"] < MIN_RESPONSES:
            warn(f"pre-registration needs at least {MIN_RESPONSES} viewers per clip before the freeze")
        status["next"] = (
            f"collect responses with: {serve}\n"
            f"then freeze them (closes collection, cannot be undone): "
            f"python -m ouro_eval_lab.cli export-intent --db {db_path} --out data/exports/intent-responses.json"
        )
    elif not status["revealed"]:
        status["stage"] = "frozen"
        status["next"] = (
            "the reveal custodian supplies the revealed records, then: "
            f"python -m ouro_eval_lab.cli reveal --db {db_path} --records <records directory>"
        )
    elif status["coders"] < MIN_CODERS:
        status["stage"] = "revealed"
        status["next"] = (
            f"issue a coding sheet per coder (at least {MIN_CODERS}; a coder never codes a clip they viewed): "
            f"python -m ouro_eval_lab.cli intent-coding-sheet --db {db_path} --coder <coder ID> "
            "--out data/exports/coding/<coder ID>.csv"
        )
    elif status["items_coded"] < status["items_issued"]:
        status["stage"] = "coding"
        status["next"] = (
            f"{status['items_issued'] - status['items_coded']} items still uncoded; each coder imports their sheet: "
            f"python -m ouro_eval_lab.cli intent-import-codes --db {db_path} --coder <coder ID> "
            "--codes data/exports/coding/<coder ID>.csv"
        )
    else:
        status["stage"] = "coded"
        status["next"] = (
            f"python -m ouro_eval_lab.cli intent-report --db {db_path} "
            "--out data/exports/intent-report.json --html data/exports/intent-report.html"
        )
    return status


def render_status(status: dict) -> str:
    lines = [f"stage: {status['stage']}"]
    for key in (
        "clips", "viewers", "responses", "fewest_responses_per_clip", "frozen", "freeze_sha256",
        "revealed", "records", "coders", "items_issued", "items_coded",
    ):
        if key in status:
            value = status[key]
            lines.append(f"{key}: {'yes' if value is True else 'no' if value is False else value if value is not None else '-'}")
    for warning in status["warnings"]:
        lines.append(f"warning: {warning}")
    lines.append("next:")
    lines.extend(f"  {line}" for line in status["next"].splitlines())
    return "\n".join(lines) + "\n"
