import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ouro_eval_lab.cli import bootstrap_demo
from ouro_eval_lab.contracts import (
    ContractError, NATIVE_AVC_PREVIOUS_VERSION, NATIVE_AVC_VERSION,
    validate_evaluator_output, validate_native_avc_output,
)
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
            "schema_version": NATIVE_AVC_VERSION,
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
            evaluation.write_text(json.dumps(output))
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
            native.write_text(json.dumps([self._native_avc_output(artifact)]))
            with self.assertRaisesRegex(ContractError, "evaluator output missing fields"):
                run_benchmark(manifest, native)
            # Existing v1 seeded benchmark remains valid and unchanged.
            self.assertEqual(run_benchmark(manifest, outputs)["contract_version"], "1.0.0")

    def test_native_avc_rejects_contradictory_coverage(self):
        baseline = self._native_avc_output({"sha256": "a" * 64, "byte_length": 100})
        cases = []
        output = copy.deepcopy(baseline)
        output["modalities"]["video_motion"] = "inconclusive"
        cases.append(output)
        output = copy.deepcopy(baseline)
        output["defect_assessment"] = "inconclusive"
        cases.append(output)
        output = copy.deepcopy(baseline)
        output["coverage"] = "incomplete"
        output["evidence_codes"].append("COVERAGE_INCOMPLETE")
        cases.append(output)
        for output in cases:
            with self.subTest(output=output), self.assertRaises(ContractError):
                validate_native_avc_output(output)

    def test_native_avc_rejects_malformed_json_types(self):
        baseline = self._native_avc_output({"sha256": "a" * 64, "byte_length": 100})
        for field, value in [("media_bytes", True), ("media_sha256", None),
                             ("delivery_decision", []), ("provenance", {}),
                             ("evidence_codes", [[], {}, 1, None])]:
            output = copy.deepcopy(baseline)
            output[field] = value
            with self.subTest(field=field), self.assertRaises(ContractError):
                validate_native_avc_output(output)

    def test_native_avc_incomplete_coverage_preserves_operational_decisions(self):
        for decision in ("approve", "hold", "reject"):
            output = self._native_avc_output({"sha256": "a" * 64, "byte_length": 100})
            output.update(delivery_decision=decision, coverage="incomplete",
                          defect_assessment="inconclusive", provenance="simulated-test-only")
            output["evidence_codes"].append("COVERAGE_INCOMPLETE")
            # Completion can be unavailable even when modality states are covered.
            validate_native_avc_output(output)
            output["modalities"]["video_motion"] = "inconclusive"
            validate_native_avc_output(output)
        output = self._native_avc_output({"sha256": "a" * 64, "byte_length": 100})
        output["modalities"]["video_motion"] = "failed"
        output["defect_assessment"] = "detected_failure"
        validate_native_avc_output(output)  # A checked failure does not make coverage incomplete.

    def test_native_avc_detected_failure_preserves_unsupported_checks_and_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest, _ = generate(Path(directory), 7)
            artifact = load_json(manifest)["artifacts"][0]
            output = self._native_avc_output(artifact)
            output["provenance"] = "simulated-test-only"
            output["coverage"] = "incomplete"
            output["modalities"]["video_motion"] = "failed"
            output["modalities"]["transcription"] = "inconclusive"
            output["defect_assessment"] = "detected_failure"
            output["evidence_codes"].append("COVERAGE_INCOMPLETE")
            evaluation = Path(directory) / "native-avc.json"
            evaluation.write_text(json.dumps(output))
            inspected = inspect_native_avc(manifest, evaluation)
            self.assertFalse(inspected["genuine_avc"])
            self.assertEqual(inspected["defect_assessment"], "detected_failure")
            self.assertEqual(inspected["coverage"], "incomplete")
            self.assertEqual(inspected["modalities"], output["modalities"])
            self.assertEqual(inspected["evidence_codes"], output["evidence_codes"])
            self.assertFalse(inspected["defect_confusion_matrix_eligible"])
            cli_output = Path(directory) / "inspection.json"
            command = subprocess.run(
                [sys.executable, "-m", "ouro_eval_lab.cli", "inspect-avc",
                 "--manifest", str(manifest), "--evaluation", str(evaluation),
                 "--out", str(cli_output)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(command.returncode, 0, command.stderr)
            self.assertEqual(json.loads(cli_output.read_text()), inspected)

    def test_native_avc_failure_cannot_be_erased_or_approved(self):
        baseline = self._native_avc_output({"sha256": "a" * 64, "byte_length": 100})
        baseline["modalities"]["video_motion"] = "failed"
        for assessment in ("unassessed", "inconclusive"):
            output = copy.deepcopy(baseline)
            output["defect_assessment"] = assessment
            with self.subTest(assessment=assessment), self.assertRaises(ContractError):
                validate_native_avc_output(output)
        baseline["defect_assessment"] = "detected_failure"
        baseline["delivery_decision"] = "approve"
        with self.assertRaisesRegex(ContractError, "cannot have approve"):
            validate_native_avc_output(baseline)
        baseline["delivery_decision"] = "reject"
        validate_native_avc_output(baseline)

    def test_native_avc_previous_version_remains_readable_without_redefinition(self):
        previous = self._native_avc_output({"sha256": "a" * 64, "byte_length": 100})
        previous["schema_version"] = NATIVE_AVC_PREVIOUS_VERSION
        validate_native_avc_output(previous)
        previous["modalities"]["video_motion"] = "failed"
        validate_native_avc_output(previous)  # Original .1 meaning remains unchanged.
        previous["defect_assessment"] = "detected_failure"
        with self.assertRaisesRegex(ContractError, "unsupported for this version"):
            validate_native_avc_output(previous)

    def test_native_avc_inspection_rejects_media_hash_and_byte_mismatches(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest, _ = generate(Path(directory), 7)
            artifact = load_json(manifest)["artifacts"][0]
            output = self._native_avc_output(artifact)
            evaluation = Path(directory) / "native-avc.json"
            output["media_sha256"] = "f" * 64
            evaluation.write_text(json.dumps(output))
            with self.assertRaisesRegex(ValueError, "unknown artifact hash"):
                inspect_native_avc(manifest, evaluation)
            output["media_sha256"] = artifact["sha256"]
            output["media_bytes"] = artifact["byte_length"] + 1
            evaluation.write_text(json.dumps(output))
            with self.assertRaisesRegex(ValueError, "byte length does not match"):
                inspect_native_avc(manifest, evaluation)
            output["media_bytes"] = artifact["byte_length"]
            evaluation.write_text(json.dumps(output))
            media = Path(directory) / artifact["relative_path"]
            original = media.read_bytes()
            media.write_bytes(bytes([original[0] ^ 1]) + original[1:])
            with self.assertRaisesRegex(ValueError, "integrity failure"):
                inspect_native_avc(manifest, evaluation)

    def test_private_evaluator_fields_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            _, outputs = generate(Path(directory), 7)
            output = copy.deepcopy(load_json(outputs)[0])
            output["prompt"] = "must never cross boundary"
            with self.assertRaisesRegex(ContractError, "forbidden/unknown"):
                validate_evaluator_output(output)


if __name__ == "__main__":
    unittest.main()
