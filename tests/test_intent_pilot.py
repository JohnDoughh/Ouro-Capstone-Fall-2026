"""Team C Sprint 5: the synthetic intent pilot and the offline HTML view.

All data are simulated by the pilot from invented probabilities; nothing here
is study data or a research finding.
"""
import contextlib
import gc
import hashlib
import io
import json
import re
import secrets
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from ouro_eval_lab import coding, reveal, store
from ouro_eval_lab.cli import main as cli_main
from ouro_eval_lab.contracts import INTENT_DELIVERY_CODES
from ouro_eval_lab.intent_html import render_intent_html
from ouro_eval_lab.intent_metrics import render_intent_report
from ouro_eval_lab.intent_pilot import CODERS, VIEWERS, run_pilot

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = ROOT / "team_c" / "intent_pilot" / "EXPECTED_SHA256"


class IntentPilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.body = run_pilot()
        cls.report = json.loads(cls.body)

    def test_pilot_is_byte_stable_and_matches_the_recorded_hash(self):
        self.assertEqual(run_pilot(), self.body)
        expected = EXPECTED.read_text().split()[0]
        self.assertEqual(hashlib.sha256(self.body).hexdigest(), expected,
                         "pilot report changed: if intended, update team_c/intent_pilot/EXPECTED_SHA256")

    def test_a_different_seed_gives_a_different_report(self):
        self.assertNotEqual(run_pilot(seed=7, samples=50), run_pilot(samples=50))

    def test_pinned_ids_and_clock_are_restored_after_a_run(self):
        for module in (store, coding, reveal):
            self.assertIs(module.secrets, secrets)
            self.assertIs(module.datetime, datetime)

    def test_report_is_labelled_synthetic_and_exercises_every_stratum(self):
        report = self.report
        self.assertTrue(report["synthetic_demo"])
        self.assertTrue(report["fictional_records"])
        self.assertIn("numbers mean nothing", report["pilot"]["note"])
        self.assertEqual(report["versions"]["code_commit"], "pilot-unbound")
        results = report["results"]
        self.assertEqual(results["responses"], len(VIEWERS) * report["pilot"]["clips"])
        self.assertEqual(report["inputs"]["coders"], len(CODERS))
        deliveries = {cell["delivery"] for cell in results["cells"]}
        self.assertEqual(deliveries, INTENT_DELIVERY_CODES)
        survival = {cell["survival"] for cell in results["cells"]}
        self.assertTrue({"survived", "not_survived", "pending_adjudication", "not_applicable"} <= survival)

    def test_report_carries_no_identities_or_free_text(self):
        text = self.body.decode()
        for secret in (*VIEWERS, *CODERS, "Simulated answer", "pilot outcome"):
            self.assertNotIn(secret, text)

    def test_workdir_keeps_inspectable_files_and_must_be_empty(self):
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.addCleanup(gc.collect)
        body = run_pilot(samples=50, workdir=directory / "run")
        self.assertEqual((directory / "run" / "intent-report.json").read_bytes(), body)
        self.assertTrue((directory / "run" / "pilot.db").is_file())
        with self.assertRaisesRegex(ValueError, "must be empty"):
            run_pilot(samples=50, workdir=directory / "run")


class IntentHtmlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(run_pilot())
        cls.html = render_intent_html(cls.report).decode()

    def test_html_is_deterministic_and_bound_to_its_report(self):
        self.assertEqual(render_intent_html(self.report).decode(), self.html)
        digest = hashlib.sha256(render_intent_report(self.report)).hexdigest()
        self.assertIn(digest, self.html)
        self.assertIn(self.report["inputs"]["response_freeze_sha256"], self.html)

    def test_html_is_offline_and_labelled(self):
        self.assertNotIn("<script", self.html)
        self.assertIsNone(re.search(r"(src|href)=\"?https?:", self.html))
        self.assertNotIn("@import", self.html)
        self.assertIn("Not a research finding", self.html)
        self.assertIn("not available", self.html)  # evaluator comparison
        self.assertIn("exploratory", self.html)

    def test_html_shows_every_cell_and_never_colours_an_undecided_one(self):
        cells = self.report["results"]["cells"]
        self.assertEqual(self.html.count('<td class="c '), len(cells))
        undecided = sum(c["survival"] not in {"survived", "not_survived"} for c in cells)
        self.assertEqual(len(re.findall(r'<td class="c na', self.html)), undecided)

    def test_html_escapes_report_text(self):
        report = json.loads(json.dumps(self.report))
        report["results"]["cells"][0]["clip"] = "<b>x</b>"
        html = render_intent_html(report).decode()
        self.assertNotIn("<b>x</b>", html)
        self.assertIn("&lt;b&gt;x&lt;/b&gt;", html)

    def test_html_carries_no_identities_or_free_text(self):
        for secret in (*VIEWERS, *CODERS, "Simulated answer"):
            self.assertNotIn(secret, self.html)


class IntentPilotCliTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.addCleanup(gc.collect)

    def run_cli(self, *args):
        with contextlib.redirect_stdout(io.StringIO()) as printed:
            code = cli_main(["intent-pilot", "--out", str(self.root / "r.json"), *args])
        return code, printed.getvalue()

    def test_expect_passes_on_the_recorded_hash_and_writes_html(self):
        code, printed = self.run_cli("--expect", str(EXPECTED), "--html", str(self.root / "r.html"))
        self.assertEqual(code, 0, printed)
        self.assertIn("matches", printed)
        self.assertTrue((self.root / "r.html").read_text(encoding="utf-8").startswith("<!doctype html>"))

    def test_expect_fails_on_a_different_hash(self):
        wrong = self.root / "wrong.sha256"
        wrong.write_text("0" * 64 + "  intent-pilot.json\n")
        code, printed = self.run_cli("--samples", "20", "--expect", str(wrong))
        self.assertEqual(code, 1)
        self.assertIn("does not match", printed)


if __name__ == "__main__":
    unittest.main()
