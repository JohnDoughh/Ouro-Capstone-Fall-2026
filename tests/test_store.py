import json
import tempfile
import unittest
from pathlib import Path

from ouro_eval_lab.cli import main as cli_main
from ouro_eval_lab.contracts import validate_manifest
from ouro_eval_lab.fixtures import generate
from ouro_eval_lab.runner import export_annotations, load_json
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
                    "verdict": "PASS", "confidence": 4, "severity": 1,
                    "defect_timestamps": "00:04-00:05; 00:08",
                    "reason_codes": ["visual_integrity"], "note": "",
                })
                self.assertIn("annotation_id", result)
                saved = db.execute(
                    "SELECT confidence, confidence_scale, severity, defect_timestamps FROM annotations WHERE annotation_id = ?",
                    (result["annotation_id"],),
                ).fetchone()
                self.assertEqual(tuple(saved), (4.0, "1-5", 1, "00:04-00:05; 00:08"))
                exported = json.loads(export_annotations(db))
                self.assertEqual(exported["annotation_contract_version"], "2.1.0")
                self.assertEqual(exported["annotations"][0]["confidence"], 4.0)
                self.assertEqual(exported["annotations"][0]["severity"], 1)
                self.assertEqual(exported["annotations"][0]["defect_timestamps"], "00:04-00:05; 00:08")
                with self.assertRaisesRegex(ValueError, "already completed"):
                    save_annotation(db, assignment["assignment_id"], "rater-a", {
                        "verdict": "HOLD", "confidence": 5, "severity": 3,
                        "reason_codes": [], "note": "overwrite",
                    })
                self.assertEqual(progress(db, "rater-a")["completed"], 1)

    def test_initialize_preserves_legacy_annotations(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "legacy.db"
            with connect(db_path) as db:
                db.execute("""CREATE TABLE annotations (
                    annotation_id TEXT PRIMARY KEY, assignment_id TEXT UNIQUE NOT NULL,
                    rater_id TEXT NOT NULL, artifact_sha256 TEXT NOT NULL,
                    verdict TEXT NOT NULL, confidence REAL NOT NULL, reason_codes TEXT NOT NULL,
                    note TEXT NOT NULL, started_at TEXT NOT NULL, completed_at TEXT NOT NULL
                )""")
                db.execute(
                    "INSERT INTO annotations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    ("old", "assignment", "rater-a", "a" * 64, "PASS", 0.75, "[]", "", "start", "end"),
                )
            export_path = Path(directory) / "annotations.json"
            self.assertEqual(cli_main(["export", "--db", str(db_path), "--out", str(export_path)]), 0)
            exported = json.loads(export_path.read_text())
            self.assertEqual(exported["annotation_contract_version"], "2.1.0")
            self.assertEqual(exported["annotations"][0]["confidence"], 0.75)
            self.assertEqual(exported["annotations"][0]["confidence_scale"], "legacy-0-1")
            self.assertIsNone(exported["annotations"][0]["severity"])
            self.assertIsNone(exported["annotations"][0]["defect_timestamps"])


if __name__ == "__main__":
    unittest.main()
