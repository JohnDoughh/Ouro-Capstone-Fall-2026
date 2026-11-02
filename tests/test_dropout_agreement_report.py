import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_dropout_agreement_report import build_report, write_report


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "data" / "card465_dropout_evidence"


class DropoutAgreementReportTests(unittest.TestCase):
    def setUp(self):
        self.annotation = json.loads((PACKAGE / "fictional_annotation.json").read_text())
        self.evaluation = json.loads((PACKAGE / "simulated_evaluator_output.json").read_text())

    def test_default_fixture_reports_agreement_and_unavailable_error_metrics(self):
        report = build_report(self.annotation, self.evaluation)
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

    def test_mismatched_media_is_rejected(self):
        changed = {**self.evaluation, "artifact_sha256": "0" * 64}
        with self.assertRaisesRegex(ValueError, "wrong artifact_sha256"):
            build_report(self.annotation, changed)

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
