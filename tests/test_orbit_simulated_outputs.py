import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from ouro_eval_lab.contracts import ContractError, validate_evaluator_output
from ouro_eval_lab.runner import run_benchmark

ROOT = Path(__file__).resolve().parents[1]
PLAYABLE = ROOT / "data" / "public_playable"
MANIFEST = PLAYABLE / "manifest.json"
OUTPUTS = PLAYABLE / "simulated_evaluator_outputs.json"
DIGEST = PLAYABLE / "simulated_evaluator_outputs.sha256"
# Frozen before any blinded rating of the Orbit pair; never regenerate.
FROZEN_SHA256 = "baf609996dc1ee5c88e307b66193994f466cd4f079f98e0673787ca41be94c90"


def _outputs() -> list[dict]:
    return json.loads(OUTPUTS.read_text())


class OrbitSimulatedOutputTests(unittest.TestCase):
    def test_outputs_match_the_frozen_digest(self):
        pinned, name = DIGEST.read_text().split()
        self.assertEqual((pinned, name), (FROZEN_SHA256, OUTPUTS.name))
        self.assertEqual(hashlib.sha256(OUTPUTS.read_bytes()).hexdigest(), FROZEN_SHA256)

    def test_every_output_passes_the_evaluator_contract(self):
        outputs = _outputs()
        self.assertTrue(outputs)
        for output in outputs:
            validate_evaluator_output(output)

    def test_every_output_is_labeled_simulated_not_avc(self):
        for output in _outputs():
            self.assertIn("simulated-test-only", output["evidence_codes"])
            self.assertTrue(output["evaluator_alias"].startswith("eval-sim"))

    def test_outputs_cover_the_orbit_manifest_exactly(self):
        manifest = json.loads(MANIFEST.read_text())
        expected = [row["sha256"] for row in manifest["artifacts"]]
        actual = [row["artifact_sha256"] for row in _outputs()]
        self.assertEqual(len(actual), len(set(actual)), "duplicate output hash")
        self.assertCountEqual(actual, expected)

    def test_benchmark_runs_on_the_orbit_pair(self):
        report = run_benchmark(MANIFEST, OUTPUTS)
        self.assertEqual(report["benchmark_id"], "orbit-playable-synthetic-v1")
        self.assertTrue(report["synthetic_demo"])
        self.assertEqual(report["evaluator_aliases"], ["eval-sim-orbit"])
        self.assertEqual(report["outputs_sha256"], FROZEN_SHA256)

    def test_benchmark_rejects_an_output_for_an_unknown_hash(self):
        outputs = _outputs()
        outputs[0] = {**outputs[0], "artifact_sha256": "0" * 64}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "outputs.json"
            path.write_text(json.dumps(outputs))
            with self.assertRaisesRegex(ValueError, "unknown artifact hash"):
                run_benchmark(MANIFEST, path)

    def test_contract_rejects_a_private_field(self):
        leaked = {**_outputs()[0], "model_routing": "simulated"}
        with self.assertRaisesRegex(ContractError, "forbidden/unknown fields: model_routing"):
            validate_evaluator_output(leaked)


if __name__ == "__main__":
    unittest.main()
