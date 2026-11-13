"""Team C Stage 2 entry: reveal is refused until responses are frozen.

The sealed records here are test-only fictions, not the sponsor's records.
"""
import contextlib
import gc
import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from ouro_eval_lab.cli import main as cli_main
from ouro_eval_lab.contracts import INTENT_DELIVERY_CODES, INTENT_FIELDS
from ouro_eval_lab.reveal import RevealRefused, reveal
from ouro_eval_lab.runner import verify_manifest
from ouro_eval_lab.store import connect, ingest, initialize, record_intent_freeze


@contextlib.contextmanager
def database(path):
    with contextlib.closing(connect(path)) as db:
        with db:
            yield db


class Study:
    """Two synthetic clips, their sealed records, commitments and a lab database."""

    def __init__(self, root: Path):
        self.root = root
        self.clips = root / "clips"
        self.records = root / "revealed"
        self.clips.mkdir()
        self.records.mkdir()
        artifacts = []
        for index, name in enumerate(("clipA", "clipB")):
            body = f"Synthetic intent clip {name}".encode()
            (self.clips / f"{name}.txt").write_bytes(body)
            artifacts.append({
                "artifact_id": f"syn-{name.lower()}", "relative_path": f"{name}.txt",
                "sha256": hashlib.sha256(body).hexdigest(), "byte_length": len(body),
                "mime_type": "text/plain", "modality": "text", "split": "development",
                "defect_family": "none_seeded_intent_recovery_only", "defect_present": False,
                "synthetic": True,
            })
        self.manifest = self.clips / "manifest.json"
        self.manifest.write_text(json.dumps({
            "contract_version": "1.0.0", "benchmark_id": "synthetic-intent-test", "seed": 1,
            "created_at": "2026-10-14T00:00:00Z", "artifacts": artifacts,
        }))
        self.artifacts = artifacts
        self.commitments = root / "commitments.sha256"
        self.db = root / "intent.db"
        ingest(self.db, verify_manifest(self.manifest)["manifest"], self.clips)
        self.seal()

    def record(self, artifact, **overrides):
        """A fictional record in the committed nested envelope; invented values only."""
        record = {
            "artifact_id": artifact["artifact_id"], "relative_path": artifact["relative_path"],
            "salt": "c0ffee" + artifact["artifact_id"][-1],
            "schema": "fictional-intent-record", "record_type": "fictional_intent_record",
            "fictional": True, "frozen_at": "2026-01-01T00:00:00Z", "note": "",
            "delivery_codes": sorted(INTENT_DELIVERY_CODES),
            "intended": {field: f"Fictional {field}" for field in INTENT_FIELDS},
            "delivery": {field: "explicit_text" for field in INTENT_FIELDS},
        }
        record.update(overrides)
        return record

    def seal(self, **overrides):
        lines = []
        for artifact in self.artifacts:
            body = json.dumps(self.record(artifact, **overrides), sort_keys=True).encode()
            name = Path(artifact["relative_path"]).stem + ".intent.json"
            (self.records / name).write_bytes(body)
            lines.append(f"{hashlib.sha256(body).hexdigest()}  {name}")
        self.commitments.write_text("\n".join(lines) + "\n")

    def freeze(self):
        with database(self.db) as db:
            return record_intent_freeze(db, "f" * 64, "json", 2)

    def reveal(self):
        with database(self.db) as db:
            db.execute("BEGIN IMMEDIATE")
            return reveal(db, self.records, self.commitments, self.manifest)

    def count(self, table):
        with database(self.db) as db:
            return db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


class IntentRevealTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.addCleanup(gc.collect)
        self.study = Study(Path(directory))

    def test_reveal_is_refused_until_responses_are_frozen(self):
        with self.assertRaisesRegex(RevealRefused, "run export-intent before any reveal"):
            self.study.reveal()
        self.assertEqual(self.study.count("intent_records"), 0)
        self.assertEqual(self.study.count("intent_reveals"), 0)

    def test_reveal_loads_verified_records_bound_to_the_freeze(self):
        freeze = self.study.freeze()
        result = self.study.reveal()
        self.assertFalse(result["already_revealed"])
        self.assertEqual(result["record_count"], 2)
        with database(self.study.db) as db:
            reveal_row = db.execute("SELECT * FROM intent_reveals").fetchone()
            records = db.execute("SELECT * FROM intent_records ORDER BY relative_path").fetchall()
        self.assertEqual(reveal_row["freeze_id"], freeze["freeze_id"])
        self.assertEqual(reveal_row["freeze_sha256"], freeze["export_sha256"])
        self.assertEqual(reveal_row["commitments_sha256"],
                         hashlib.sha256(self.study.commitments.read_bytes()).hexdigest())
        for row, artifact in zip(records, self.study.artifacts):
            self.assertEqual(row["artifact_sha256"], artifact["sha256"])
            self.assertEqual(row["reveal_id"], reveal_row["reveal_id"])
            self.assertEqual(row["intent_contract_version"], "2.0.0")
            # The stored text is the exact committed bytes.
            self.assertEqual(hashlib.sha256(row["record_json"].encode()).hexdigest(), row["record_sha256"])

    def test_tampered_or_invalid_records_are_refused_after_freeze(self):
        self.study.freeze()
        name = self.study.records / "clipA.intent.json"
        original = name.read_bytes()
        name.write_bytes(original.replace(b"Fictional support", b"Fictional suppory"))
        with self.assertRaisesRegex(RevealRefused, "does not match the commitment"):
            self.study.reveal()
        name.write_bytes(original)
        self.study.seal(campaign="private")
        with self.assertRaisesRegex(RevealRefused, "forbidden/unknown fields: campaign"):
            self.study.reveal()
        self.assertEqual(self.study.count("intent_records"), 0)

    def test_repeat_reveal_is_a_no_op_and_different_records_are_refused(self):
        self.study.freeze()
        self.study.reveal()
        again = self.study.reveal()
        self.assertTrue(again["already_revealed"])
        self.assertEqual(self.study.count("intent_reveals"), 1)
        self.study.seal(note="A different fictional note")
        with self.assertRaisesRegex(RevealRefused, "already revealed"):
            self.study.reveal()
        self.assertEqual(self.study.count("intent_records"), 2)

    def test_revealed_records_are_append_only(self):
        self.study.freeze()
        self.study.reveal()
        for sql in ("UPDATE intent_records SET record_json='{}'", "DELETE FROM intent_records",
                    "UPDATE intent_reveals SET record_count=0", "DELETE FROM intent_reveals"):
            with self.subTest(sql), self.assertRaisesRegex(sqlite3.DatabaseError, "append-only"):
                with database(self.study.db) as db:
                    db.execute(sql)

    def test_clip_missing_from_the_lab_database_is_refused(self):
        # A frozen database whose clips were never ingested.
        other = self.study.root / "other.db"
        initialize(other)
        with database(other) as db:
            record_intent_freeze(db, "f" * 64, "json", 0)
        with database(other) as db:
            db.execute("BEGIN IMMEDIATE")
            with self.assertRaisesRegex(RevealRefused, "not loaded in this lab database"):
                reveal(db, self.study.records, self.study.commitments, self.study.manifest)

    def test_cli_refuses_before_freeze_and_reveals_after(self):
        args = ["reveal", "--db", str(self.study.db), "--records", str(self.study.records),
                "--commitments", str(self.study.commitments), "--manifest", str(self.study.manifest)]
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit):
            cli_main(args)
        self.assertIn("export-intent", stderr.getvalue())
        self.study.freeze()
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(cli_main(args), 0)
        self.assertIn("revealed 2 intent records after freeze " + "f" * 64, stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
