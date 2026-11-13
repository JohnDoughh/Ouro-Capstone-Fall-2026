import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ouro_eval_lab.agreement import calculate
from ouro_eval_lab.runner import agreement_report
from ouro_eval_lab.store import connect, connect_readonly, initialize

FICTIONAL_TIME = "2026-11-12T00:00:00+00:00"


def build_db(path: Path, assignments: list[tuple]) -> None:
    """assignments: (assignment_id, artifact, rater, sequence, repeat_group, verdict|None)."""
    initialize(path)
    with connect(path) as db:
        for artifact in sorted({item[1] for item in assignments}):
            db.execute(
                """INSERT INTO artifacts (sha256, artifact_id, relative_path, fixture_root, byte_length,
                   mime_type, modality, split, defect_family, defect_present, synthetic)
                   VALUES (?, ?, 'fictional.txt', '.', 1, 'text/plain', 'text', 'practice', 'fictional', 0, 1)""",
                (artifact, f"fictional-{artifact[:6]}"),
            )
        for assignment_id, artifact, rater, sequence, group, verdict in assignments:
            db.execute(
                "INSERT INTO assignments (assignment_id, rater_id, artifact_sha256, sequence, repeat_group, started_at, completed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (assignment_id, rater, artifact, sequence, group, FICTIONAL_TIME,
                 FICTIONAL_TIME if verdict else None),
            )
            if verdict:
                db.execute(
                    """INSERT INTO annotations (annotation_id, assignment_id, rater_id, artifact_sha256, verdict,
                       confidence, confidence_scale, severity, reason_codes, note, started_at, completed_at)
                       VALUES (?, ?, ?, ?, ?, 3, '1-5', 0, '[]', 'Fictional test annotation', ?, ?)""",
                    (f"n-{assignment_id}", assignment_id, rater, artifact, verdict, FICTIONAL_TIME, FICTIONAL_TIME),
                )


def report_for(assignments: list[tuple]) -> dict:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "lab.db"
        build_db(path, assignments)
        with connect_readonly(path) as db:
            return agreement_report(db)


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


A, B, C = "a" * 64, "b" * 64, "c" * 64


class AgreementReportTests(unittest.TestCase):
    def test_same_reviewer_repeat_is_not_inter_reviewer_agreement(self):
        # The previous "first two rows" logic paired fictional-rater-1 with
        # its own repeat here (PASS vs HOLD) and never saw fictional-rater-2.
        report = report_for([
            ("a1", A, "fictional-rater-1", 0, "g1", "PASS"),
            ("a2", A, "fictional-rater-1", 5, "g1", "HOLD"),
            ("a3", A, "fictional-rater-2", 2, None, "PASS"),
        ])
        inter, repeat = report["inter_reviewer_agreement"], report["repeat_consistency"]
        self.assertEqual((inter["pair_count"], inter["agreements"]), (1, 1))
        self.assertEqual((repeat["pair_count"], repeat["disagreements"]), (1, 1))
        self.assertEqual(repeat["agreement_rate"], 0.0)

    def test_three_reviewers_form_all_distinct_pairs(self):
        report = report_for([
            ("a1", A, "fictional-rater-1", 0, None, "PASS"),
            ("a2", A, "fictional-rater-2", 0, None, "PASS"),
            ("a3", A, "fictional-rater-3", 0, None, "HOLD"),
        ])
        inter = report["inter_reviewer_agreement"]
        self.assertEqual((inter["pair_count"], inter["agreements"], inter["disagreements"]), (3, 1, 2))

    def test_unsure_and_missing_are_counted_separately_and_excluded(self):
        report = report_for([
            ("a1", A, "fictional-rater-1", 0, None, "PASS"),
            ("a2", A, "fictional-rater-2", 0, None, "HOLD"),
            ("b1", B, "fictional-rater-1", 1, None, "PASS"),
            ("b2", B, "fictional-rater-2", 1, None, "UNSURE"),
            ("c1", C, "fictional-rater-1", 2, None, "UNSURE"),
            ("c2", C, "fictional-rater-2", 2, None, None),  # missing beats UNSURE
        ])
        inter = report["inter_reviewer_agreement"]
        self.assertEqual(
            (inter["total_candidate_pairs"], inter["pair_count"], inter["unsure_pairs"], inter["missing_pairs"]),
            (3, 1, 1, 1),
        )
        self.assertEqual(inter["agreement_rate"], 0.0)

    def test_zero_eligible_pairs_report_unavailable_metrics(self):
        report = report_for([
            ("a1", A, "fictional-rater-1", 0, None, "PASS"),
            ("a2", A, "fictional-rater-2", 0, None, "UNSURE"),
            ("b1", B, "fictional-rater-1", 1, "g1", "HOLD"),
            ("b2", B, "fictional-rater-1", 2, "g1", None),
        ])
        inter, repeat = report["inter_reviewer_agreement"], report["repeat_consistency"]
        self.assertEqual((inter["pair_count"], repeat["pair_count"], repeat["missing_pairs"]), (0, 0, 1))
        self.assertIsNone(inter["agreement_rate"])
        self.assertIsNone(repeat["agreement_rate"])
        self.assertIsNone(inter["cohens_kappa_exploratory"])
        self.assertEqual(inter["cohens_kappa_status"], "unavailable: no eligible pairs")
        self.assertEqual(inter["cohens_kappa_95ci_exploratory"], [None, None])

    def test_single_category_agreement_keeps_raw_rate_but_kappa_is_unavailable(self):
        # PR #35 edge case: expected agreement is one, so kappa is undefined.
        report = report_for([
            ("a1", A, "fictional-rater-1", 0, None, "HOLD"),
            ("a2", A, "fictional-rater-2", 0, None, "HOLD"),
            ("b1", B, "fictional-rater-1", 1, None, "HOLD"),
            ("b2", B, "fictional-rater-2", 1, None, "HOLD"),
        ])
        inter = report["inter_reviewer_agreement"]
        self.assertEqual((inter["pair_count"], inter["agreement_rate"]), (2, 1.0))
        self.assertIsNone(inter["cohens_kappa_exploratory"])
        self.assertEqual(inter["cohens_kappa_status"], "unavailable: single category (expected agreement = 1)")
        self.assertEqual(inter["cohens_kappa_95ci_exploratory"], [None, None])

    def test_report_json_serializes_unavailable_values_as_null(self):
        text = json.dumps(calculate([]), sort_keys=True)
        self.assertIn('"agreement_rate": null', text)
        self.assertIn('"cohens_kappa_exploratory": null', text)

    def test_unexpected_verdict_is_rejected(self):
        rows = [
            {"assignment_id": "1", "artifact_sha256": A, "rater_id": "r1", "repeat_group": None, "sequence": 0, "verdict": "MAYBE"},
            {"assignment_id": "2", "artifact_sha256": A, "rater_id": "r2", "repeat_group": None, "sequence": 0, "verdict": "PASS"},
        ]
        with self.assertRaises(ValueError):
            calculate(rows)


class AgreementPreservesJudgmentsTests(unittest.TestCase):
    ROWS = [
        ("a1", A, "fictional-rater-1", 0, "g1", "PASS"),
        ("a2", A, "fictional-rater-1", 3, "g1", "HOLD"),
        ("a3", A, "fictional-rater-2", 1, None, "UNSURE"),
        ("b1", B, "fictional-rater-2", 2, None, None),
    ]

    def test_cli_report_leaves_database_bytes_and_judgments_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "lab.db"
            out = Path(directory) / "agreement.json"
            build_db(db_path, self.ROWS)
            with connect(db_path) as db:
                before_rows = [tuple(row) for row in db.execute("SELECT * FROM annotations ORDER BY annotation_id")]
            before_digest = file_digest(db_path)
            command = subprocess.run(
                [sys.executable, "-m", "ouro_eval_lab.cli", "agreement", "--db", str(db_path), "--out", str(out)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(command.returncode, 0, command.stderr)
            self.assertEqual(file_digest(db_path), before_digest)
            with connect(db_path) as db:
                after_rows = [tuple(row) for row in db.execute("SELECT * FROM annotations ORDER BY annotation_id")]
            self.assertEqual(after_rows, before_rows)
            report = json.loads(out.read_text())
            self.assertEqual(report["schema_version"], "agreement-report-v2")
            self.assertEqual(report["repeat_consistency"]["disagreements"], 1)

    def test_report_connection_cannot_write(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "lab.db"
            build_db(db_path, self.ROWS)
            with connect_readonly(db_path) as db:
                with self.assertRaises(Exception):
                    db.execute("UPDATE annotations SET verdict = 'PASS'")

    def test_cli_refuses_to_write_report_over_database(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "lab.db"
            build_db(db_path, self.ROWS)
            before_digest = file_digest(db_path)
            command = subprocess.run(
                [sys.executable, "-m", "ouro_eval_lab.cli", "agreement", "--db", str(db_path), "--out", str(db_path)],
                capture_output=True, text=True, check=False,
            )
            self.assertNotEqual(command.returncode, 0)
            self.assertEqual(file_digest(db_path), before_digest)


if __name__ == "__main__":
    unittest.main()
