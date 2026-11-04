"""Exercise actual Git checkout conversion, including benchmark provenance."""
import hashlib
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from ouro_eval_lab.runner import run_benchmark

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ("public_playable", "public_audio", "public_intent")


@unittest.skipUnless(shutil.which("git"), "Git is required for checkout verification")
class CheckoutBytesTests(unittest.TestCase):
    def test_autocrlf_checkout_preserves_frozen_bytes_and_benchmark(self):
        original = ROOT / "data/public_playable"
        baseline = run_benchmark(original / "manifest.json", original / "simulated_evaluator_outputs.json")
        with tempfile.TemporaryDirectory() as directory:
            checkout = Path(directory)
            shutil.copyfile(ROOT / ".gitattributes", checkout / ".gitattributes")
            for name in PUBLIC:
                shutil.copytree(ROOT / "data" / name, checkout / "data" / name)
            def git(*args):
                return subprocess.run(
                    ["git", "-c", "core.autocrlf=false", *args], cwd=checkout,
                    check=True, capture_output=True,
                )
            git("init", "-q")
            git("add", ".")
            # Remove every indexed file so checkout-index must materialize it.
            # Git falls back to the indexed attributes while .gitattributes is absent.
            files = git("ls-files", "-z").stdout.decode().split("\0")[:-1]
            for name in files:
                (checkout / name).unlink()
            subprocess.run(
                ["git", "-c", "core.autocrlf=true", "checkout-index", "--all"],
                cwd=checkout, check=True, capture_output=True,
            )
            for name in PUBLIC:
                for source in (ROOT / "data" / name).iterdir():
                    if source.name == "manifest.json" or source.suffix == ".sha256":
                        actual = checkout / source.relative_to(ROOT)
                        with self.subTest(path=str(source.relative_to(ROOT))):
                            self.assertEqual(actual.read_bytes(), source.read_bytes())
            restored = checkout / "data/public_playable"
            outputs = restored / "simulated_evaluator_outputs.json"
            self.assertEqual(
                hashlib.sha256(outputs.read_bytes()).hexdigest(),
                "baf609996dc1ee5c88e307b66193994f466cd4f079f98e0673787ca41be94c90",
            )
            self.assertEqual(
                run_benchmark(restored / "manifest.json", outputs), baseline,
                "checkout conversion must not change report provenance or results",
            )
