"""Intent output safety, using only invented records and responses."""
import contextlib
import gc
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ouro_eval_lab.cli import main
from tests.test_intent_coding import CodingStudy, fill, read_sheet, write
from tests.test_intent_reveal import database


class IntentOutputSafetyTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.addCleanup(gc.collect)
        self.study = CodingStudy(self.root)
        # Exercise the committed metadata-string envelope through real reveal,
        # coding and report operations, without using any sponsor records.
        self.study.seal(delivery_codes="Fictional delivery vocabulary description.")
        self.study.collect(recall="Fictional caf\u00e9 product")
        self.study.freeze_and_reveal()

    def run_cli(self, command, out, *extra):
        args = [command, "--db", str(self.study.db), "--out", str(out), *extra]
        if command == "intent-coding-sheet":
            args += ["--coder", "safety_coder"]
        if command == "intent-report":
            args += ["--samples", "20", "--code-commit", "1" * 40]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return main(args)

    def add_codes(self):
        for coder in ("coder_a", "coder_b"):
            body = self.study.sheet(coder)["body"]
            self.study.import_codes(write(fill(read_sheet(body))), coder)

    def test_all_outputs_refuse_every_existing_input_before_database_changes(self):
        prior = self.root / "prior-output.json"
        prior.write_bytes(b"Preserve a prior frozen result\n")
        inputs = [self.study.db, self.study.manifest, self.study.commitments,
                  self.study.records / "clipA.intent.json", self.study.clips / "clipA.txt", prior]
        original = {path: path.read_bytes() for path in inputs}
        for command in ("export-intent", "intent-coding-sheet", "intent-report"):
            for destination in inputs:
                with self.subTest(command=command, destination=destination.name):
                    with self.assertRaises(SystemExit) as error:
                        self.run_cli(command, destination)
                    self.assertEqual(error.exception.code, 2)
                    self.assertEqual({path: path.read_bytes() for path in inputs}, original)
        self.assertEqual(self.study.count("intent_coding_sheets"), 0)

    def test_outputs_refuse_hardlink_database_aliases(self):
        alias = self.root / "database-alias"
        try:
            os.link(self.study.db, alias)
        except OSError as exc:
            self.skipTest(f"hard links unavailable: {exc}")
        original = self.study.db.read_bytes()
        for command in ("export-intent", "intent-coding-sheet", "intent-report"):
            with self.assertRaises(SystemExit):
                self.run_cli(command, alias)
            self.assertEqual(self.study.db.read_bytes(), original)

    def test_outputs_refuse_symlinks_including_dangling_links(self):
        alias, dangling = self.root / "alias", self.root / "dangling"
        target = self.root / "not-created"
        try:
            alias.symlink_to(self.study.db)
            dangling.symlink_to(target)
        except OSError as exc:
            self.skipTest(f"symlinks unavailable: {exc}")
        original = self.study.db.read_bytes()
        for command in ("export-intent", "intent-coding-sheet", "intent-report"):
            for destination in (alias, dangling):
                with self.assertRaises(SystemExit):
                    self.run_cli(command, destination)
                self.assertTrue(destination.is_symlink())
                self.assertFalse(target.exists())
                self.assertEqual(self.study.db.read_bytes(), original)

    def test_sheet_write_failure_rolls_back_sheet_and_removes_new_file(self):
        out = self.root / "failed-sheet.csv"
        with patch("ouro_eval_lab.cli._durable_write", side_effect=OSError(28, "No space")):
            with self.assertRaises(SystemExit):
                self.run_cli("intent-coding-sheet", out)
        self.assertFalse(out.exists())
        self.assertEqual(self.study.count("intent_coding_sheets"), 0)
        self.assertEqual(self.run_cli("intent-coding-sheet", out), 0)
        self.assertEqual(self.study.count("intent_coding_sheets"), 1)

    def test_freeze_write_failure_does_not_record_another_freeze(self):
        out = self.root / "failed-freeze.json"
        before = self.study.count("intent_freezes")
        with patch("ouro_eval_lab.cli._durable_write", side_effect=OSError(28, "No space")):
            with self.assertRaises(SystemExit):
                self.run_cli("export-intent", out)
        self.assertFalse(out.exists())
        self.assertEqual(self.study.count("intent_freezes"), before)

    def test_failed_report_does_not_leave_empty_file(self):
        out = self.root / "no-codes.json"
        with self.assertRaises(SystemExit):
            self.run_cli("intent-report", out)
        self.assertFalse(out.exists())

    def test_successful_rebuilds_use_new_paths_and_identical_private_bytes(self):
        first, second = self.root / "sheet-a.csv", self.root / "sheet-b.csv"
        self.run_cli("intent-coding-sheet", first)
        self.run_cli("intent-coding-sheet", second)
        self.assertEqual(first.read_bytes(), second.read_bytes())
        self.assertIn("caf\u00e9".encode(), first.read_bytes())
        self.assertNotIn(b"\r\n", first.read_bytes())
        self.assertEqual(self.study.count("intent_coding_sheets"), 1)
        self.add_codes()
        reports = [self.root / name for name in ("report-a.json", "report-b.json")]
        for out in reports:
            self.run_cli("intent-report", out)
        self.assertEqual(reports[0].read_bytes(), reports[1].read_bytes())
        self.assertTrue(json.loads(reports[0].read_bytes())["synthetic_demo"])
        with database(self.study.db) as db:
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        if os.name == "posix":
            for out in (first, second, *reports):
                self.assertEqual(out.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
