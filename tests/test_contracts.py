import copy
import tempfile
import unittest
from pathlib import Path

from ouro_eval_lab.cli import bootstrap_demo
from ouro_eval_lab.contracts import ContractError, validate_evaluator_output, validate_native_avc_output
from ouro_eval_lab.fixtures import generate
from ouro_eval_lab.runner import inspect_native_avc, load_json, run_benchmark, verify_manifest


class ContractTests(unittest.TestCase):
    def test_bootstrap_is_idempotent_from_empty_data_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "fixtures"
            db_path = Path(directory) / "lab.db"
            first = bootstrap_demo(root, db_path, 20260825)
            first_manifest = first[0].read_bytes()
            second = bootstrap_demo(root, db_path, 20260825)
            self.assertEqual(first[2], second[2])
            self.assertEqual(first_manifest, second[0].read_bytes())

    def test_seed_is_byte_reproducible_and_manifest_verifies(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            manifest_a, outputs_a = generate(Path(first), 7)
            manifest_b, outputs_b = generate(Path(second), 7)
            self.assertEqual(manifest_a.read_bytes(), manifest_b.read_bytes())
            self.assertEqual(outputs_a.read_bytes(), outputs_b.read_bytes())
            self.assertEqual(verify_manifest(manifest_a)["verified"], 16)

    def test_hash_substitution_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest, _ = generate(Path(directory), 7)
            artifact = load_json(manifest)["artifacts"][0]
            (Path(directory) / artifact["relative_path"]).write_text("tampered")
            with self.assertRaisesRegex(ValueError, "integrity failure"):
                verify_manifest(manifest)

    def _native_avc_output(self, artifact):
        return {
            "schema_version": "2.0.0-proposed.1",
            "audience": "sponsor-review-only",
            "import_ready": False,
            "provenance": "canonical-approved-synthetic",
            "evaluator_alias": "evaluator-01",
            "evaluated_at": "2026-09-24T08:00:00Z",
            "media_sha256": artifact["sha256"],
            "media_bytes": artifact["byte_length"],
            "delivery_decision": "hold",
            "coverage": "complete",
            "modalities": {
                "signal_scan": "covered",
                "transcription": "covered",
                "audio_perceptual": "covered",
                "video_motion": "covered",
                "audiovisual_sync": "covered",
            },
            "defect_assessment": "unassessed",
            "probability": None,
            "probability_status": "unavailable",
            "probability_reason": "PROBABILITY_NOT_REPORTED",
            "evidence_codes": [
                "EXACT_BYTES_VERIFIED",
                "CANONICAL_RECORD_BOUND",
                "COMPLETED_JOB_BOUND",
                "DEFECT_MAPPING_UNAVAILABLE",
            ],
        }

    def test_native_avc_contract_preserves_native_semantics(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest, _ = generate(Path(directory), 7)
            artifact = load_json(manifest)["artifacts"][0]
            output = self._native_avc_output(artifact)
            validate_native_avc_output(output)
            evaluation = Path(directory) / "native-avc.json"
            evaluation.write_text(__import__("json").dumps(output))
            report = inspect_native_avc(manifest, evaluation)
            self.assertTrue(report["genuine_avc"])
            self.assertEqual(report["delivery_decision"], "hold")
            self.assertIsNone(report["probability"])
            self.assertFalse(report["calibration_eligible"])
            self.assertFalse(report["defect_confusion_matrix_eligible"])

    def test_native_avc_private_fields_and_fake_probability_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest, _ = generate(Path(directory), 7)
            artifact = load_json(manifest)["artifacts"][0]
            output = self._native_avc_output(artifact)
            private = copy.deepcopy(output)
            private["provider"] = "must-never-cross"
            with self.assertRaisesRegex(ContractError, "forbidden/unknown"):
                validate_native_avc_output(private)
            probability = copy.deepcopy(output)
            probability["probability"] = 0.91
            with self.assertRaisesRegex(ContractError, "probability"):
                validate_native_avc_output(probability)

    def test_native_avc_does_not_enter_v1_benchmark(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest, outputs = generate(Path(directory), 7)
            artifact = load_json(manifest)["artifacts"][0]
            native = Path(directory) / "native-avc.json"
            native.write_text(__import__("json").dumps([self._native_avc_output(artifact)]))
            with self.assertRaisesRegex(ContractError, "evaluator output missing fields"):
                run_benchmark(manifest, native)
            # Existing v1 seeded benchmark remains valid and unchanged.
            self.assertEqual(run_benchmark(manifest, outputs)["contract_version"], "1.0.0")

    def test_private_evaluator_fields_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            _, outputs = generate(Path(directory), 7)
            output = copy.deepcopy(load_json(outputs)[0])
            output["prompt"] = "must never cross boundary"
            with self.assertRaisesRegex(ContractError, "forbidden/unknown"):
                validate_evaluator_output(output)


if __name__ == "__main__":
    unittest.main()
