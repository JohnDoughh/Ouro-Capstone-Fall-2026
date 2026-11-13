import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.build_card465_dropout_evidence import MediaIdentityError
from scripts.build_dropout_agreement_report import build_report, write_report


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "data" / "card465_dropout_evidence"


class DropoutAgreementReportTests(unittest.TestCase):
    def setUp(self):
        self.annotation = json.loads((PACKAGE / "fictional_annotation.json").read_text())
        self.evaluation = json.loads((PACKAGE / "simulated_evaluator_output.json").read_text())

    def test_default_fixture_reports_agreement_and_unavailable_error_metrics(self):
        report = build_report(self.annotation, self.evaluation)
        self.assertEqual(report["artifact"]["artifact_sha256"], self.annotation["artifact_sha256"])
        self.assertEqual(report["artifact"]["artifact_version"], self.annotation["artifact_version"])
        self.assertEqual(report["inputs"]["evaluator_provenance"], "simulated-test-only")
        metrics = report["metrics"]
        self.assertEqual(metrics["agreement_count"], 1)
        self.assertEqual(metrics["disagreement_count"], 0)
        self.assertEqual(metrics["uncertain_count"], 0)
        self.assertEqual(metrics["coverage"], 1.0)
        false_metrics = metrics["false_passes_and_holds"]
        self.assertEqual(false_metrics["status"], "unavailable")
        self.assertIsNone(false_metrics["false_pass_count"])
        self.assertIsNone(false_metrics["false_hold_count"])

    def test_false_metrics_require_an_explicit_independent_reference(self):
        reference = {**self.annotation, "reference_role": "independent_reference"}
        report = build_report(reference, {**self.evaluation, "verdict": "PASS"})
        false_metrics = report["metrics"]["false_passes_and_holds"]
        self.assertEqual(false_metrics["status"], "available")
        self.assertEqual(false_metrics["false_pass_count"], 1)
        self.assertEqual(false_metrics["false_hold_count"], 0)

    def test_hash_mismatch_is_rejected_even_with_the_same_version(self):
        changed = {**self.evaluation, "artifact_sha256": "0" * 64}
        with self.assertRaisesRegex(MediaIdentityError, "mismatched artifact_sha256"):
            build_report(self.annotation, changed)

    def test_version_mismatch_is_rejected_even_with_the_same_hash(self):
        changed = {**self.evaluation, "artifact_version": "v2"}
        with self.assertRaisesRegex(MediaIdentityError, "mismatched artifact_version"):
            build_report(self.annotation, changed)

    def test_two_unversioned_records_cannot_match(self):
        annotation = self.annotation.copy()
        evaluation = self.evaluation.copy()
        del annotation["artifact_version"]
        del evaluation["artifact_version"]
        with self.assertRaisesRegex(MediaIdentityError, "must declare artifact_version"):
            build_report(annotation, evaluation)

    def test_native_provenance_cannot_enter_simulated_metrics_even_with_matching_media(self):
        native = {**self.evaluation, "provenance": "canonical-approved-synthetic"}
        with self.assertRaisesRegex(ValueError, "must remain explicitly simulated"):
            build_report(self.annotation, native)

    def test_cli_rejects_mismatches_without_writing_a_report(self):
        for field, value in (("artifact_sha256", "0" * 64), ("artifact_version", "v2")):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                evaluation = Path(directory) / "evaluation.json"
                evaluation.write_text(json.dumps({**self.evaluation, field: value}))
                out = Path(directory) / "report.json"
                result = subprocess.run(
                    [
                        sys.executable,
                        str(ROOT / "scripts" / "build_dropout_agreement_report.py"),
                        "--annotation",
                        str(PACKAGE / "fictional_annotation.json"),
                        "--evaluation",
                        str(evaluation),
                        "--out",
                        str(out),
                    ],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn(f"mismatched {field}", result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertFalse(out.exists())

    def test_command_output_is_reproducible(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.json"
            second = Path(directory) / "second.json"
            annotation = PACKAGE / "fictional_annotation.json"
            evaluation = PACKAGE / "simulated_evaluator_output.json"
            write_report(annotation, evaluation, first)
            write_report(annotation, evaluation, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())


if __name__ == "__main__":
    unittest.main()
