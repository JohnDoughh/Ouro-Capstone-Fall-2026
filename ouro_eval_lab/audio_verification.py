"""Offline evidence for Team B's synthetic audio save/export check.

Run after reviewing; never expose this report in the blinded reviewer interface.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sqlite3
import subprocess
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from .contracts import validate_annotation_payload
from .runner import EXPORT_FIELDS, export_annotations, verify_manifest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/public_audio/manifest.json"
INPUT_FIELDS = ("verdict", "reason_codes", "defect_timestamps", "severity", "confidence", "note")


def compare_export(saved: list[dict], content: str, format_name: str) -> list[dict]:
    """Compare every exported field, preserving CSV's documented representation."""
    exported = (json.loads(content)["annotations"] if format_name == "json"
                else list(csv.DictReader(io.StringIO(content))))
    checks = [{"field": "row_count", "expected": len(saved), "actual": len(exported),
               "ok": len(saved) == len(exported)}]
    ids = [row.get("annotation_id") for row in exported]
    checks.append({"field": "annotation_ids", "ok":
                   len(ids) == len(set(ids)) and set(ids) == {r["annotation_id"] for r in saved}})
    by_id = {row.get("annotation_id"): row for row in exported}
    for row in saved:
        actual = by_id.get(row["annotation_id"], {})
        checks.append({"annotation_id": row["annotation_id"], "field": "export_fields",
                       "ok": set(actual) == set(EXPORT_FIELDS)})
        for field in EXPORT_FIELDS:
            expected = row[field]
            if format_name == "csv":
                expected = ("|".join(expected) if field == "reason_codes"
                            else "" if expected is None else str(expected))
            checks.append({"annotation_id": row["annotation_id"], "field": field,
                           "expected": expected, "actual": actual.get(field),
                           "ok": field in actual and expected == actual[field]})
    return checks


def verify_audio_session(db_path: Path, out: Path, rater: str,
                         expected_path: Path | None = None) -> dict:
    # Fixed repository fixture manifest: no external clips or arbitrary ingest.
    manifest = verify_manifest(MANIFEST)["manifest"]
    artifacts = {a["sha256"]: a for a in manifest["artifacts"]}
    if not db_path.is_file():
        raise ValueError("An existing audio test database is required; no database was created")
    with closing(sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        db.execute("BEGIN")  # One consistent read-only snapshot for records and both exports.
        stored_artifacts = [dict(r) for r in db.execute("SELECT * FROM artifacts")]
        if {a["sha256"] for a in stored_artifacts} != set(artifacts):
            raise ValueError("Use a separate database containing exactly the Lab public audio pair")
        for stored in stored_artifacts:
            source = artifacts[stored["sha256"]]
            for field in ("artifact_id", "relative_path", "byte_length", "mime_type", "modality", "synthetic"):
                if stored[field] != source[field]:
                    raise ValueError(f"Artifact metadata mismatch: {field}")
            media = (Path(stored["fixture_root"]) / stored["relative_path"]).resolve()
            if media != (MANIFEST.parent / source["relative_path"]).resolve():
                raise ValueError("Database must reference the repository's existing public audio files")
        raw = [dict(r) for r in db.execute("SELECT * FROM annotations ORDER BY completed_at, annotation_id")]
        assignments = {r["assignment_id"]: dict(r) for r in db.execute("SELECT * FROM assignments")}
        exports = {fmt: export_annotations(db, fmt) for fmt in ("json", "csv")}
    saved = [{field: json.loads(r[field]) if field == "reason_codes" else r[field]
              for field in EXPORT_FIELDS} for r in raw]
    checks = []
    selected = []
    for row, record in zip(raw, saved):
        assignment = assignments.get(row["assignment_id"], {})
        binding_ok = (record["artifact_sha256"] in artifacts
                      and assignment.get("artifact_sha256") == record["artifact_sha256"]
                      and assignment.get("rater_id") == record["rater_id"]
                      and assignment.get("started_at") == record["started_at"]
                      and assignment.get("completed_at") == record["completed_at"])
        checks.append({"annotation_id": row["annotation_id"], "field": "assignment_binding", "ok": binding_ok})
        payload = {f: record[f] for f in INPUT_FIELDS}
        # SQLite stores confidence in a REAL column; 4.0 is the integer scale value 4.
        confidence = payload["confidence"]
        if isinstance(confidence, (float, int)) and confidence in range(1, 6):
            payload["confidence"] = int(confidence)
        try:
            validate_annotation_payload(payload)
            valid = record["confidence_scale"] == "1-5" and isinstance(record["note"], str)
        except (ValueError, TypeError):
            valid = False
        checks.append({"annotation_id": row["annotation_id"], "field": "contract_and_scales", "ok": valid})
        try:
            start, end = (datetime.fromisoformat(record[f]) for f in ("started_at", "completed_at"))
            timing_ok = start.tzinfo is not None and end.tzinfo is not None and start <= end
        except (ValueError, TypeError):
            timing_ok = False
        checks.append({"annotation_id": row["annotation_id"], "field": "review_timestamps", "ok": timing_ok})
        if row["rater_id"] == rater:
            selected.append({**record, "review_label": f"Item {assignment.get('sequence', -1) + 1:03d}"})
    export_checks = {fmt: compare_export(saved, content, fmt) for fmt, content in exports.items()}
    # Acceptance cases are distinct files. This is a disclosed practice fixture, not rater accuracy research.
    cases = {}
    for verdict, defective in (("PASS", False), ("HOLD", True)):
        cases[verdict] = [r["annotation_id"] for r in selected
                         if r["verdict"] == verdict
                         and artifacts.get(r["artifact_sha256"], {}).get("defect_present") is defective
                         and (r["severity"] == 0 if verdict == "PASS" else
                              r["severity"] in (1, 2, 3) and r["note"].strip() and r["defect_timestamps"].strip()
                              and "audio_integrity" in r["reason_codes"])]
    expected_checks = []
    verified_inputs = set()
    if expected_path:
        expected = json.loads(expected_path.read_text())
        if not isinstance(expected, list) or not expected:
            raise ValueError("Expected input must be a nonempty JSON list recorded before submission")
        labels = set()
        for entry in expected:
            label = entry.get("review_label")
            if label in labels or set(entry) != {"review_label", *INPUT_FIELDS}:
                raise ValueError("Expected entries require unique review_label and all six input fields")
            labels.add(label)
            validate_annotation_payload({f: entry[f] for f in INPUT_FIELDS})
            matches = [r for r in selected if r["review_label"] == label]
            expected_checks.append({"review_label": label, "field": "saved_record_exists", "ok": len(matches) == 1})
            if len(matches) == 1:
                match = matches[0]
                for field in INPUT_FIELDS:
                    # The existing save path intentionally strips surrounding timestamp whitespace.
                    value = entry[field].strip() if field == "defect_timestamps" else entry[field]
                    expected_checks.append({"review_label": label, "field": field, "expected": value,
                                            "actual": match[field], "ok": value == match[field]})
                if all(c["ok"] for c in expected_checks if c["review_label"] == label):
                    verified_inputs.add(match["annotation_id"])
    complete = all(set(ids) & verified_inputs for ids in cases.values())
    all_checks = checks + expected_checks + [c for group in export_checks.values() for c in group]
    status = "failed" if any(not c["ok"] for c in all_checks) else "passed" if complete else "pending_manual_review"
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=normal"], cwd=ROOT, capture_output=True, text=True)
    report = {
        "status": status, "synthetic_demo": True,
        "disclaimer": "Synthetic software verification only; not research findings. Manual entries are user-supplied evidence.",
        "generated_at": datetime.now(timezone.utc).isoformat(), "rater_id": rater,
        "code_commit": revision.stdout.strip() if revision.returncode == 0 else None,
        "working_tree_dirty": bool(dirty.stdout.strip()) if dirty.returncode == 0 else None,
        "manifest_sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
        "expected_input_sha256": hashlib.sha256(expected_path.read_bytes()).hexdigest() if expected_path else None,
        "assignment_seed": 20260825, "fixture_seed": manifest["seed"],
        "acceptance_cases": cases, "manual_input_comparison_complete": bool(complete),
        "saved_records": selected, "storage_checks": checks,
        "export_checks": export_checks, "submitted_input_checks": expected_checks,
        "export_sha256": {fmt: hashlib.sha256(content.encode()).hexdigest() for fmt, content in exports.items()},
        "notes": ["PASS may have empty reason_codes and defect_timestamps; these are present fields, not missing data.",
                  "Confidence is stored as SQLite REAL (e.g. 4.0); scale remains integer-valued 1-5.",
                  "Reopened means a fresh read-only database connection, not an edit/reopen browser screen.",
                  "Raw judgments and UNSURE are preserved. Missing acceptance cases remain pending, not coerced."],
    }
    destinations = [out / name for name in ("annotations.json", "annotations.csv", "verification.json")]
    protected = {db_path.resolve(), MANIFEST.resolve(), *( (MANIFEST.parent / a["relative_path"]).resolve() for a in artifacts.values())}
    if expected_path:
        protected.add(expected_path.resolve())
    if any(p.resolve() in protected for p in destinations):
        raise ValueError("Evidence output must not overwrite its input files")
    out.mkdir(parents=True, exist_ok=True)
    for fmt, content in exports.items():
        (out / f"annotations.{fmt}").write_bytes(content.encode())
    (out / "verification.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--rater", required=True)
    parser.add_argument("--expected", type=Path, help="Independent pre-submit notes: JSON list with review_label, verdict, reason_codes, defect_timestamps, severity, confidence, and note")
    args = parser.parse_args(argv)
    try:
        report = verify_audio_session(args.db, args.out, args.rater, args.expected)
    except (ValueError, OSError, sqlite3.Error) as exc:
        parser.error(str(exc))
    print(f"{report['status']}: {args.out / 'verification.json'}")
    return {"passed": 0, "failed": 1, "pending_manual_review": 2}[report["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
