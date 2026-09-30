import hashlib
import importlib.util
import json
import unittest
from pathlib import Path

from ouro_eval_lab.runner import verify_manifest

ROOT = Path(__file__).resolve().parents[1]
PAIR = ROOT / "data" / "public_visual_pair"
MANIFEST = PAIR / "manifest.json"
TRUTH = PAIR / "seeded_truth.json"


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "generate_visual_continuity_pair", ROOT / "scripts" / "generate_visual_continuity_pair.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class VisualPairContractTests(unittest.TestCase):
    def test_manifest_verifies_one_clean_one_defective(self):
        verified = verify_manifest(MANIFEST)
        self.assertEqual(verified["verified"], 2)
        artifacts = verified["manifest"]["artifacts"]
        self.assertEqual(sorted(a["defect_present"] for a in artifacts), [False, True])
        self.assertEqual({a["defect_family"] for a in artifacts}, {"product_visual_continuity"})
        self.assertTrue(all(a["modality"] == "video" and a["synthetic"] for a in artifacts))

    def test_truth_binds_to_the_defective_artifact(self):
        truth = json.loads(TRUTH.read_text())
        manifest = json.loads(MANIFEST.read_text())
        defective = [a for a in manifest["artifacts"] if a["defect_present"]]
        self.assertEqual(len(defective), 1)
        self.assertEqual(truth["defective_sha256"], defective[0]["sha256"])
        self.assertEqual(truth["defective_artifact_id"], defective[0]["artifact_id"])
        self.assertEqual(truth["seed"], manifest["seed"])
        self.assertTrue(truth["synthetic"])

    def test_nothing_a_rater_sees_names_the_defect(self):
        # The lab shows raters the artifact_id; the path is served behind an
        # opaque assignment URL but is kept neutral too.
        manifest = json.loads(MANIFEST.read_text())
        for artifact in manifest["artifacts"]:
            for field in ("artifact_id", "relative_path"):
                value = artifact[field].lower()
                for word in ("defect", "clean", "bad", "good", "band", "error"):
                    self.assertNotIn(word, value, field)
        # The README is operator-facing but must not spoil the answer either.
        readme = (PAIR / "README.md").read_text().lower()
        for word in ("band", "stripe", "grip", "00:06", "00:09", "6.000", "9.000", "6 s", "third shot"):
            self.assertNotIn(word, readme)
        # Both clips may be named, but never one more often than the other.
        by_truth = {a["defect_present"]: a for a in manifest["artifacts"]}
        for field in ("artifact_id", "relative_path"):
            self.assertEqual(readme.count(by_truth[True][field].lower()),
                             readme.count(by_truth[False][field].lower()), field)


class VisualPairFrameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gen = _load_generator()
        cls.truth = json.loads(TRUTH.read_text())

    def test_source_frames_reproduce_pinned_digests(self):
        manifest = json.loads(MANIFEST.read_text())
        pinned = self.truth["source_frames"]["sha256"]
        for artifact in manifest["artifacts"]:
            name = artifact["relative_path"]
            self.assertEqual(self.gen.frames_digest(artifact["defect_present"]), pinned[name], name)
        self.assertEqual(self.gen.defective_clip(), next(
            a["relative_path"] for a in manifest["artifacts"] if a["defect_present"]))

    def test_defect_is_confined_to_the_window_and_the_product(self):
        first, end = self.truth["defect_window_frames"]
        fps = self.truth["source_frames"]["fps"]
        self.assertEqual(self.truth["defect_window_seconds"], [first / fps, end / fps])
        width = self.gen.WIDTH
        total = width * self.gen.HEIGHT
        for index in range(self.gen.FRAMES):
            clean, box = self.gen.render_frame(index, False)
            defect, defect_box = self.gen.render_frame(index, True)
            self.assertEqual(box, defect_box, index)
            if not first <= index < end:
                self.assertEqual(clean, defect, index)
                continue
            changed = [p for p in range(total) if clean[3 * p:3 * p + 3] != defect[3 * p:3 * p + 3]]
            self.assertTrue(changed, index)
            x0, y0, x1, y1 = box
            for p in changed:
                x, y = p % width, p // width
                self.assertTrue(x0 <= x < x1 and y0 <= y < y1, (index, x, y))
            # Small enough that a rater must look at the product, not just
            # notice that something flashed.
            self.assertLess(len(changed) / total, 0.02, index)

    def test_defect_window_matches_a_whole_shot(self):
        first, end = self.truth["defect_window_frames"]
        self.assertEqual(first % self.gen.SCENE_FRAMES, 0)
        self.assertEqual(end - first, self.gen.SCENE_FRAMES)
        self.assertGreater(first, 0)
        self.assertLess(end, self.gen.FRAMES)


class VisualPairBytesTests(unittest.TestCase):
    def test_media_are_mp4(self):
        for artifact in json.loads(MANIFEST.read_text())["artifacts"]:
            body = (PAIR / artifact["relative_path"]).read_bytes()
            self.assertEqual(body[4:8], b"ftyp")
            self.assertEqual(hashlib.sha256(body).hexdigest(), artifact["sha256"])


if __name__ == "__main__":
    unittest.main()
