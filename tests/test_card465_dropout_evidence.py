import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_card465_dropout_evidence import EXPECTED_SHA256, build, validate_simulated


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "data" / "card465_dropout_evidence"
ARTIFACT = ROOT / "data" / "public_audio" / "dropout.wav"


class Card465DropoutEvidenceTests(unittest.TestCase):
    def test_simulated_confidence_rejects_json_booleans(self):
        baseline = json.loads((PACKAGE / "simulated_evaluator_output.json").read_text())
        for value in (True, False):
            with self.subTest(confidence=value):
                output = dict(baseline)
                output["confidence"] = value
                with self.assertRaisesRegex(ValueError, "confidence must be between 0 and 1"):
                    validate_simulated(output)

    def test_package_is_reproducible_and_bound_to_one_artifact(self):
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = Path(first_dir)
            second = Path(second_dir)
            build(PACKAGE, ARTIFACT, first)
            build(PACKAGE, ARTIFACT, second)
            for name in ("comparison.json", "dropout-evidence-package.json", "SHA256SUMS"):
                self.assertEqual((first / name).read_bytes(), (second / name).read_bytes())

            package = json.loads((first / "dropout-evidence-package.json").read_text())
            records = [
                package["artifact"],
                package["human_annotation"],
                package["simulated_evaluator_output"],
                package["comparison"],
            ]
            self.assertTrue(all(record["artifact_sha256"] == EXPECTED_SHA256 for record in records))
            self.assertEqual(package["human_annotation"]["confidence_scale"], "1-5")
            self.assertEqual(package["human_annotation"]["severity"], 3)
            self.assertEqual(package["human_annotation"]["defect_timestamps"], "00:04-00:05")
            self.assertEqual(package["simulated_evaluator_output"]["provenance"], "simulated-test-only")


if __name__ == "__main__":
    unittest.main()
