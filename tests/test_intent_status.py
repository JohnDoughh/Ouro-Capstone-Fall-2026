"""Team C Sprint 5: the read-only intent-status check and the empty-database guard on serve.

Uses the synthetic pilot and the fictional public intent clips only.
"""
import contextlib
import gc
import hashlib
import io
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ouro_eval_lab.cli import main as cli_main
from ouro_eval_lab.intent_pilot import CODERS, VIEWERS, run_pilot
from ouro_eval_lab.intent_status import intent_status
from ouro_eval_lab.runner import verify_manifest
from ouro_eval_lab.store import connect, ingest, initialize, next_assignment

ROOT = Path(__file__).resolve().parents[1]
INTENT_MANIFEST = ROOT / "data" / "public_intent" / "manifest.json"


def run_cli(*args):
    with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()) as err:
        try:
            code = cli_main(list(args))
        except SystemExit as exit_:
            code = exit_.code
    return code, out.getvalue() + err.getvalue()


class IntentStatusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.pilot = Path(cls.directory.name) / "pilot"
        run_pilot(samples=20, workdir=cls.pilot)

    @classmethod
    def tearDownClass(cls):
        gc.collect()
        cls.directory.cleanup()

    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.addCleanup(gc.collect)

    def status(self, path):
        with connect(path) as db:
            return intent_status(db, path)

    def test_empty_database_says_to_ingest(self):
        path = self.root / "empty.db"
        initialize(path)
        status = self.status(path)
        self.assertEqual(status["stage"], "empty")
        self.assertIn("ingest", status["next"])

    def test_ingested_database_is_collecting_and_warns_below_the_minimum(self):
        path = self.root / "intent.db"
        ingest(path, verify_manifest(INTENT_MANIFEST)["manifest"], INTENT_MANIFEST.parent)
        status = self.status(path)
        self.assertEqual(status["stage"], "collecting")
        self.assertEqual(status["clips"], 4)
        self.assertIn("export-intent", status["next"])
        self.assertTrue(any("at least 3 viewers per clip" in w for w in status["warnings"]))

    def test_viewers_count_only_people_who_responded(self):
        path = self.root / "intent.db"
        ingest(path, verify_manifest(INTENT_MANIFEST)["manifest"], INTENT_MANIFEST.parent)
        with connect(path) as db:
            next_assignment(db, "opened_page_only", repeats=False)
        self.assertEqual(self.status(path)["viewers"], 0)

    def test_a_fully_coded_pilot_points_to_the_report(self):
        status = self.status(self.pilot / "pilot.db")
        self.assertEqual(status["stage"], "coded")
        self.assertEqual(status["coders"], len(CODERS))
        self.assertEqual(status["viewers"], len(VIEWERS))
        self.assertEqual(status["items_coded"], status["items_issued"])
        self.assertTrue(status["frozen"] and status["revealed"])
        self.assertIn("intent-report", status["next"])
        self.assertEqual(status["warnings"], [])

    def test_foreign_database_is_recognized(self):
        path = self.root / "other.db"
        sqlite3.connect(path).close()
        db = sqlite3.connect(path)
        try:
            self.assertEqual(intent_status(db, path)["stage"], "not_an_intent_database")
        finally:
            db.close()

    def test_cli_is_read_only_and_prints_no_identities(self):
        path = self.pilot / "pilot.db"
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        code, printed = run_cli("intent-status", "--db", str(path))
        self.assertEqual(code, 0, printed)
        self.assertIn("stage: coded", printed)
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)
        for secret in (*VIEWERS, *CODERS, "Simulated answer"):
            self.assertNotIn(secret, printed)

    def test_cli_refuses_a_missing_database_without_creating_it(self):
        path = self.root / "missing.db"
        code, printed = run_cli("intent-status", "--db", str(path))
        self.assertEqual(code, 2)
        self.assertIn("no database", printed)
        self.assertFalse(path.exists())


class ServeGuardTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.addCleanup(gc.collect)

    def test_intent_serve_refuses_a_database_with_no_clips(self):
        with mock.patch("ouro_eval_lab.cli.serve") as serve:
            code, printed = run_cli("serve", "--db", str(self.root / "fresh.db"), "--study", "intent")
        self.assertEqual(code, 2)
        self.assertIn("no clips", printed)
        serve.assert_not_called()

    def test_intent_serve_starts_once_clips_are_ingested(self):
        path = self.root / "intent.db"
        ingest(path, verify_manifest(INTENT_MANIFEST)["manifest"], INTENT_MANIFEST.parent)
        with mock.patch("ouro_eval_lab.cli.serve") as serve:
            code, printed = run_cli("serve", "--db", str(path), "--study", "intent")
        self.assertEqual(code, 0, printed)
        serve.assert_called_once()


if __name__ == "__main__":
    unittest.main()
