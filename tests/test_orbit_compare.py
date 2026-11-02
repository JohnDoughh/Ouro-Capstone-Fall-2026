import hashlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from ouro_eval_lab.cli import main
from ouro_eval_lab.contracts import validate_annotation_payload
from ouro_eval_lab.runner import compare_responses, export_annotations, load_json, verify_manifest
from ouro_eval_lab.store import connect, ingest, initialize, next_assignment, save_annotation

ROOT = Path(__file__).resolve().parents[1]
PLAYABLE = ROOT / "data" / "public_playable"
MANIFEST = PLAYABLE / "manifest.json"
OUTPUTS = PLAYABLE / "simulated_evaluator_outputs.json"
DIGEST = PLAYABLE / "simulated_evaluator_outputs.sha256"
# Frozen before any blinded rating of the Orbit pair; never regenerate.
FROZEN_SHA256 = "baf609996dc1ee5c88e307b66193994f466cd4f079f98e0673787ca41be94c90"
RATER = "rater-practice-01"


def _outputs() -> list[dict]:
    return json.loads(OUTPUTS.read_text())


def _hashes() -> dict[str, str]:
    return {row["artifact_id"]: row["sha256"] for row in load_json(MANIFEST)["artifacts"]}


def _response(artifact_sha256: str, verdict: str) -> dict:
    return {"rater_id": RATER, "artifact_sha256": artifact_sha256, "verdict": verdict}


def _write_export(directory: str, annotations: list[dict], annotation_contract_version: str = "2.1.0") -> Path:
    path = Path(directory) / "responses.json"
    path.write_text(json.dumps({
        "contract_version": "1.0.0",
        "annotation_contract_version": annotation_contract_version,
        "annotations": annotations,
    }))
    return path


class OrbitComparisonTests(unittest.TestCase):
    def test_response_agreement_human_and_evaluator(self):
        hashes = _hashes()
        with tempfile.TemporaryDirectory() as directory:
            responses = _write_export(directory, [
                _response(hashes["syn-orbit-clean"], "PASS"),
                _response(hashes["syn-orbit-label-defect"], "HOLD"),
            ])
            report = compare_responses(MANIFEST, OUTPUTS, responses)
        self.assertEqual([row["outcome"] for row in report["rows"]], ["agree", "agree"])
        self.assertEqual(report["counts"], {
            "agree": 2, "false_pass": 0, "false_hold": 0, "human_unsure": 0, "evaluator_unsure": 0,
        })

    def test_disagreements_follow_the_outcome_rules(self):
        hashes = _hashes()
        with tempfile.TemporaryDirectory() as directory:
            responses = _write_export(directory, [
                _response(hashes["syn-orbit-clean"], "HOLD"),
                _response(hashes["syn-orbit-label-defect"], "PASS"),
            ])
            report = compare_responses(MANIFEST, OUTPUTS, responses)
        outcomes = {row["artifact_sha256"]: row["outcome"] for row in report["rows"]}
        # The labels compare human and evaluator verdicts, never the manifest's defect truth.
        self.assertEqual(outcomes, {
            hashes["syn-orbit-clean"]: "false_pass",
            hashes["syn-orbit-label-defect"]: "false_hold",
        })
        self.assertEqual(report["counts"]["false_pass"], 1)
        self.assertEqual(report["counts"]["false_hold"], 1)

    def test_human_unsure_is_not_counted_as_an_error(self):
        hashes = _hashes()
        with tempfile.TemporaryDirectory() as directory:
            responses = _write_export(directory, [_response(hashes["syn-orbit-clean"], "UNSURE")])
            report = compare_responses(MANIFEST, OUTPUTS, responses)
        self.assertEqual(report["rows"][0]["outcome"], "human_unsure")
        self.assertEqual(report["counts"]["human_unsure"], 1)
        self.assertEqual(report["counts"]["false_pass"], 0)
        self.assertEqual(report["counts"]["false_hold"], 0)

    def test_output_with_unknown_hash_is_rejected(self):
        hashes = _hashes()
        outputs = _outputs()
        outputs[0] = {**outputs[0], "artifact_sha256": "0" * 64}
        with tempfile.TemporaryDirectory() as directory:
            outputs_path = Path(directory) / "outputs.json"
            outputs_path.write_text(json.dumps(outputs))
            responses = _write_export(directory, [_response(hashes["syn-orbit-clean"], "PASS")])
            with self.assertRaisesRegex(ValueError, "output references unknown artifact hash"):
                compare_responses(MANIFEST, outputs_path, responses)

    def test_response_with_unknown_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            responses = _write_export(directory, [_response("0" * 64, "PASS")])
            with self.assertRaisesRegex(ValueError, "response references unknown artifact hash"):
                compare_responses(MANIFEST, OUTPUTS, responses)

    def test_export_with_pr28_evidence_fields_still_works(self):
        hashes = _hashes()
        response = {
            **_response(hashes["syn-orbit-clean"], "PASS"),
            "rubric_version": "fictional-rubric-v0",
            "defect_family_id": "fictional-family",
            "region": "fictional-region",
            "reference_id": "fictional-reference",
            "evidence_description": "Fictional practice note.",
        }
        with tempfile.TemporaryDirectory() as directory:
            responses = _write_export(directory, [response], annotation_contract_version="2.2.0")
            report = compare_responses(MANIFEST, OUTPUTS, responses)
        self.assertEqual(report["rows"][0]["outcome"], "agree")
        self.assertEqual(report["annotation_contract_version"], "2.2.0")
        self.assertEqual(set(report["rows"][0]), {
            "artifact_sha256", "rater_id", "human_verdict",
            "evaluator_verdict", "evaluator_alias", "outcome",
        })

    def test_malformed_responses_are_rejected_with_value_error(self):
        sha = _hashes()["syn-orbit-clean"]
        cases = {
            "missing artifact_sha256": {"rater_id": RATER, "verdict": "PASS"},
            "missing verdict": {"rater_id": RATER, "artifact_sha256": sha},
            "missing rater_id": {"artifact_sha256": sha, "verdict": "PASS"},
            "row is not an object": "not-an-object",
            "artifact_sha256 is a list": {"rater_id": RATER, "artifact_sha256": [], "verdict": "PASS"},
            "verdict is a list": {"rater_id": RATER, "artifact_sha256": sha, "verdict": []},
        }
        for label, row in cases.items():
            with self.subTest(label), tempfile.TemporaryDirectory() as directory:
                responses = _write_export(directory, [row])
                with self.assertRaises(ValueError):
                    compare_responses(MANIFEST, OUTPUTS, responses)

    def test_saved_export_is_unchanged_by_compare(self):
        payload = {
            "verdict": "HOLD", "confidence": 4, "severity": 2,
            "reason_codes": ["visual_integrity"], "note": "Fictional practice note.",
        }
        validate_annotation_payload(payload)
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "lab.db"
            initialize(db_path)
            ingest(db_path, verify_manifest(MANIFEST)["manifest"], MANIFEST.parent)
            with connect(db_path) as db:
                assignment = next_assignment(db, RATER)
                save_annotation(db, assignment["assignment_id"], RATER, payload)
            with connect(db_path) as db:
                before = export_annotations(db, "json")
            responses = Path(directory) / "responses.json"
            responses.write_text(before)
            file_before = responses.read_bytes()
            report = compare_responses(MANIFEST, OUTPUTS, responses)
            with connect(db_path) as db:
                after = export_annotations(db, "json")
            self.assertEqual(before.encode(), after.encode())
            self.assertEqual(responses.read_bytes(), file_before)
        self.assertEqual([row["rater_id"] for row in report["rows"]], [RATER])
        self.assertEqual(report["rows"][0]["artifact_sha256"], assignment["sha256"])

    def test_compare_twice_yields_identical_report_bytes(self):
        hashes = _hashes()
        with tempfile.TemporaryDirectory() as directory:
            responses = _write_export(directory, [
                _response(hashes["syn-orbit-label-defect"], "HOLD"),
                _response(hashes["syn-orbit-clean"], "PASS"),
            ])
            paths = [Path(directory) / name for name in ("first.json", "second.json")]
            for path in paths:
                with redirect_stdout(io.StringIO()):
                    main([
                        "compare", "--manifest", str(MANIFEST), "--outputs", str(OUTPUTS),
                        "--responses", str(responses), "--out", str(path),
                    ])
            first, second = (path.read_bytes() for path in paths)
        self.assertEqual(first, second)
        self.assertNotIn(b"\r\n", first)
        # Artifact IDs can name the seeded clip, and this report may be linked on cards.
        self.assertNotIn(b"artifact_id", first)
        self.assertNotIn(b"syn-orbit", first)
        report = json.loads(first)
        self.assertEqual(report["counts"]["agree"], 2)
        row_hashes = [row["artifact_sha256"] for row in report["rows"]]
        self.assertEqual(row_hashes, sorted(row_hashes))

    def test_frozen_outputs_are_unchanged_after_compare(self):
        hashes = _hashes()
        with tempfile.TemporaryDirectory() as directory:
            responses = _write_export(directory, [_response(hashes["syn-orbit-clean"], "PASS")])
            report = compare_responses(MANIFEST, OUTPUTS, responses)
        pinned, name = DIGEST.read_text().split()
        self.assertEqual((pinned, name), (FROZEN_SHA256, OUTPUTS.name))
        self.assertEqual(hashlib.sha256(OUTPUTS.read_bytes()).hexdigest(), FROZEN_SHA256)
        self.assertEqual(report["outputs_sha256"], FROZEN_SHA256)


if __name__ == "__main__":
    unittest.main()
