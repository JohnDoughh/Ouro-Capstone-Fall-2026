import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from ouro_eval_lab.cli import main
from ouro_eval_lab.family4_check import family4_check, parse_timestamps
from ouro_eval_lab.runner import compare_responses

ROOT = Path(__file__).resolve().parents[1]
ORBIT = ROOT / "data" / "public_playable"
MANIFEST = ORBIT / "manifest.json"
OUTPUTS = ORBIT / "simulated_evaluator_outputs.json"
REFERENCE = ORBIT / "reference.sha256"

ARTIFACTS = json.loads(MANIFEST.read_text(encoding="utf-8"))["artifacts"]
DEFECT = next(row["sha256"] for row in ARTIFACTS if row["defect_present"])
CLEAN = next(row["sha256"] for row in ARTIFACTS if not row["defect_present"])
APPROVED = REFERENCE.read_text(encoding="utf-8").split()[0]
OTHER = "0" * 64


def row(annotation_id, artifact, verdict="HOLD", timestamps="00:03", reference=None, **extra):
    record = {
        "annotation_id": annotation_id, "rater_id": "constructed-rater", "artifact_sha256": artifact,
        "verdict": verdict, "confidence": 4, "confidence_scale": "ordinal-1-5", "severity": 2,
        "defect_timestamps": timestamps, "rubric_version": None, "defect_family_id": None,
        "region": None, "reference_id": reference, "evidence_description": None,
        "reason_codes": [], "note": "constructed test row", "started_at": None, "completed_at": None,
    }
    if reference is not None:
        record.update(rubric_version="v0.1", defect_family_id=4)
    record.update(extra)
    return record


class Family4CheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def export(self, *rows, **top):
        path = self.dir / f"export-{len(list(self.dir.iterdir()))}.json"
        body = {"annotation_contract_version": "2.2.0", "contract_version": "1.0.0", "annotations": list(rows)}
        body.update(top)
        path.write_text(json.dumps(body), encoding="utf-8")
        return path

    def check(self, *rows):
        return family4_check(MANIFEST, self.export(*rows), REFERENCE)

    # The seven cases named in the #870 acceptance criteria.
    def test_reference_match(self):
        report = self.check(row("a1", DEFECT, reference=APPROVED))
        self.assertEqual(report["rows"][0]["reference"], "match")
        self.assertEqual(report["reference_counts"], {"match": 1, "mismatch": 0, "missing": 0})

    def test_reference_mismatch(self):
        report = self.check(row("a1", DEFECT, reference=OTHER))
        self.assertEqual(report["rows"][0]["reference"], "mismatch")

    def test_missing_reference_on_blind_hold_is_expected(self):
        report = self.check(row("a1", DEFECT, reference=None))
        self.assertEqual(report["rows"][0]["reference"], "missing")
        self.assertTrue(report["rows"][0]["reference_expected_missing"])
        self.assertTrue(any("not a failed rating" in note for note in report["notes"]))

    def test_timing_overlap(self):
        for text in ("00:03 - 00:04", "00:02", "00:03", "00:02-00:03", "00:03–00:04", "00:02.9"):
            with self.subTest(text=text):
                self.assertEqual(self.check(row("a1", DEFECT, timestamps=text))["rows"][0]["timing"], "overlaps")

    def test_timing_miss(self):
        for text in ("00:04", "00:00-00:01", "00:05; 00:07", "00:03.5", "00:01.2"):
            with self.subTest(text=text):
                self.assertEqual(self.check(row("a1", DEFECT, timestamps=text))["rows"][0]["timing"], "misses")

    def test_timing_unparsed(self):
        for text in ("around three seconds", "", None, "00:04-00:02", "00:03;", "3s", "00:75"):
            with self.subTest(text=text):
                self.assertEqual(self.check(row("a1", DEFECT, timestamps=text))["rows"][0]["timing"], "unparsed")

    def test_hold_on_clean_clip_has_no_defect_window(self):
        report = self.check(row("a1", CLEAN, timestamps="00:03"))
        self.assertEqual(report["rows"][0]["timing"], "no_defect_window")
        self.assertEqual(report["timing_counts"]["no_defect_window"], 1)

    # Scope, safety and reproducibility.
    def test_pass_and_unsure_rows_are_skipped(self):
        report = self.check(row("a1", CLEAN, "PASS", ""), row("a2", CLEAN, "UNSURE", ""), row("a3", DEFECT))
        self.assertEqual((report["holds_checked"], report["non_hold_rows_skipped"]), (1, 2))

    def test_saved_review_download_shape_is_accepted_without_leaking_ids(self):
        path = self.export(row("a1", DEFECT, artifact_id="hidden-source-id", review_label="Item 001"),
                           schema_version="saved-review-v1")
        text = json.dumps(family4_check(MANIFEST, path, REFERENCE))
        self.assertNotIn("hidden-source-id", text)
        self.assertNotIn("constructed-rater", text)

    def test_report_states_timing_is_not_detection_accuracy(self):
        notes = " ".join(self.check(row("a1", DEFECT))["notes"])
        self.assertIn("Timing overlap is not detection accuracy", notes)

    def test_unknown_artifact_and_bad_verdict_are_rejected(self):
        with self.assertRaises(ValueError):
            self.check(row("a1", OTHER))
        with self.assertRaises(ValueError):
            self.check(row("a1", DEFECT, verdict="FAIL"))

    def test_tampered_reference_image_is_rejected(self):
        copy = self.dir / "orbit"
        shutil.copytree(ORBIT, copy)
        image = copy / REFERENCE.read_text(encoding="utf-8").split()[1]
        image.write_bytes(image.read_bytes() + b"x")
        with self.assertRaises(ValueError):
            family4_check(MANIFEST, self.export(row("a1", DEFECT)), copy / "reference.sha256")

    def test_cli_report_is_lf_and_identical_twice(self):
        responses = self.export(row("a1", DEFECT, timestamps="00:03 - 00:04"), row("a2", CLEAN, "PASS", ""))
        first, second = self.dir / "out" / "one.json", self.dir / "out" / "two.json"
        for out in (first, second):
            main(["family4-check", "--manifest", str(MANIFEST), "--responses", str(responses),
                  "--reference", str(REFERENCE), "--out", str(out)])
        self.assertEqual(first.read_bytes(), second.read_bytes())
        self.assertNotIn(b"\r\n", first.read_bytes())

    def test_cli_refuses_to_write_into_inputs_or_fixture_directory(self):
        responses = self.export(row("a1", DEFECT))
        for out in (responses, REFERENCE, ORBIT / "family4.json"):
            with self.subTest(out=out), self.assertRaises(ValueError):
                main(["family4-check", "--manifest", str(MANIFEST), "--responses", str(responses),
                      "--reference", str(REFERENCE), "--out", str(out)])
        self.assertFalse((ORBIT / "family4.json").exists())

    def test_compare_report_and_fixture_bytes_are_unchanged(self):
        responses = self.export(row("a1", DEFECT), row("a2", CLEAN, "PASS", ""))
        fixtures = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in ORBIT.iterdir() if p.is_file()}
        before = compare_responses(MANIFEST, OUTPUTS, responses)
        family4_check(MANIFEST, responses, REFERENCE)
        self.assertEqual(compare_responses(MANIFEST, OUTPUTS, responses), before)
        self.assertEqual({p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in ORBIT.iterdir() if p.is_file()}, fixtures)
        self.assertEqual(hashlib.sha256(OUTPUTS.read_bytes()).hexdigest(),
                         "baf609996dc1ee5c88e307b66193994f466cd4f079f98e0673787ca41be94c90")

    def test_parser_intervals(self):
        self.assertEqual(parse_timestamps("00:03"), [(3, 4)])
        self.assertEqual(parse_timestamps("00:02 - 00:03; 00:08"), [(2, 4), (8, 9)])
        self.assertEqual(parse_timestamps("00:02.5-00:03.25"), [(2.5, 3.25)])


if __name__ == "__main__":
    unittest.main()
