import tempfile
import unittest
from pathlib import Path

from ouro_eval_lab.fixtures import generate
from ouro_eval_lab.runner import run_benchmark


class RunnerTests(unittest.TestCase):
    def test_benchmark_is_reproducible_and_labeled_synthetic(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest, outputs = generate(Path(directory), 20260825)
            first = run_benchmark(manifest, outputs)
            second = run_benchmark(manifest, outputs)
            self.assertEqual(first, second)
            self.assertTrue(first["synthetic_demo"])
            self.assertEqual(first["n"], 16)
            self.assertIn("false_pass", first["confusion"])
            self.assertEqual(len(first["risk_coverage"]), 6)


if __name__ == "__main__":
    unittest.main()
