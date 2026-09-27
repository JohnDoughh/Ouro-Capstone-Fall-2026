import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from ouro_eval_lab.runner import verify_manifest

ROOT = Path(__file__).resolve().parents[1]
INTENT = ROOT / "data" / "public_intent"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PublicIntentClipTests(unittest.TestCase):
    def test_manifest_verifies_and_reveals_no_intent(self):
        self.assertEqual(verify_manifest(INTENT / "manifest.json")["verified"], 4)
        text = (INTENT / "manifest.json").read_text().lower()
        for word in ("audience", "benefit", "call_to_action", "intended"):
            self.assertNotIn(word, text)

    def test_only_commitments_are_public(self):
        reveal = _load("verify_intent_reveal")
        commitments = reveal.read_commitments(INTENT / "intent_commitments.sha256")
        clips = {a["relative_path"] for a in json.loads((INTENT / "manifest.json").read_text())["artifacts"]}
        self.assertEqual(set(commitments), {Path(c).stem + ".intent.json" for c in clips})
        self.assertEqual(list(INTENT.glob("*.intent.json")), [])

    def test_reveal_check_accepts_exact_bytes_and_rejects_changes(self):
        reveal = _load("verify_intent_reveal")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"artifacts": [{"relative_path": "clipX.mp4", "artifact_id": "syn-x"}]}))
            body = json.dumps({"artifact_id": "syn-x", "relative_path": "clipX.mp4", "salt": "00"}).encode()
            (root / "clipX.intent.json").write_bytes(body)
            commitments = root / "c.sha256"
            commitments.write_text(f"{hashlib.sha256(body).hexdigest()}  clipX.intent.json\n")
            self.assertEqual(reveal.verify(commitments, root, manifest), [])
            (root / "clipX.intent.json").write_bytes(body + b" ")
            self.assertEqual(len(reveal.verify(commitments, root, manifest)), 1)
            (root / "clipX.intent.json").write_bytes(body)
            # Every manifest clip must be committed and revealed; nothing extra.
            commitments.write_text("")
            self.assertEqual(len(reveal.verify(commitments, root, manifest)), 1)
            commitments.write_text(
                f"{hashlib.sha256(body).hexdigest()}  clipX.intent.json\n"
                f"{hashlib.sha256(b'x').hexdigest()}  clipY.intent.json\n"
            )
            self.assertEqual(len(reveal.verify(commitments, root, manifest)), 2)


if __name__ == "__main__":
    unittest.main()
