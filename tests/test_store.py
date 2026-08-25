import tempfile
import unittest
from pathlib import Path

from ouro_eval_lab.contracts import validate_manifest
from ouro_eval_lab.fixtures import generate
from ouro_eval_lab.runner import load_json
from ouro_eval_lab.store import connect, ingest, initialize, next_assignment, progress, save_annotation


class StoreTests(unittest.TestCase):
    def test_assignment_is_blinded_and_annotation_is_append_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "fixtures"
            db_path = Path(directory) / "lab.db"
            manifest_path, _ = generate(root, 13)
            manifest = load_json(manifest_path)
            validate_manifest(manifest)
            initialize(db_path)
            ingest(db_path, manifest, root)
            with connect(db_path) as db:
                assignment = next_assignment(db, "rater-a", 13)
                self.assertNotIn("defect_present", assignment)
                self.assertNotIn("repeat_group", assignment)
                self.assertNotIn("defect_family", assignment)
                result = save_annotation(db, assignment["assignment_id"], "rater-a", {
                    "verdict": "PASS", "confidence": 0.8, "reason_codes": ["visual_integrity"], "note": "",
                })
                self.assertIn("annotation_id", result)
                with self.assertRaisesRegex(ValueError, "already completed"):
                    save_annotation(db, assignment["assignment_id"], "rater-a", {
                        "verdict": "HOLD", "confidence": 0.9, "reason_codes": [], "note": "overwrite",
                    })
                self.assertEqual(progress(db, "rater-a")["completed"], 1)


if __name__ == "__main__":
    unittest.main()
