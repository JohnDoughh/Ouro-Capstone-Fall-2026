import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from ouro_eval_lab.cli import main
from ouro_eval_lab.runner import load_json
from ouro_eval_lab.runner import compare_responses


ROOT = Path(__file__).resolve().parents[1]


class ComparisonSafetyTests(unittest.TestCase):
    def test_output_aliases_never_modify_frozen_inputs_or_media(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "data/public_playable", root / "media")
            manifest = root / "media/manifest.json"
            outputs = root / "media/simulated_evaluator_outputs.json"
            responses = root / "responses.json"
            responses.write_text(json.dumps({"annotations": []}), encoding="utf-8")
            media = root / "media" / load_json(manifest)["artifacts"][0]["relative_path"]
            inputs = [manifest, outputs, responses, media]
            before = {p: p.read_bytes() for p in inputs}
            aliases = inputs[:]
            symbolic = root / "response-link.json"
            try:
                symbolic.symlink_to(responses)
            except OSError:
                pass  # Windows may require developer mode for symlinks.
            else:
                aliases.append(symbolic)
            hard = root / "response-hardlink.json"
            os.link(responses, hard)
            aliases.append(hard)
            for out in aliases:
                with self.subTest(output=out.name), self.assertRaisesRegex(ValueError, "must not overwrite"):
                    main(["compare", "--manifest", str(manifest), "--outputs", str(outputs),
                          "--responses", str(responses), "--out", str(out)])
                self.assertEqual({p: p.read_bytes() for p in inputs}, before)

    def test_utf8_json_is_independent_of_windows_default_encoding(self):
        original = Path.read_text

        def windows_read_text(path, encoding=None, errors=None, **kwargs):
            return original(path, encoding=encoding or "cp1252", errors=errors, **kwargs)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unicode.json"
            path.write_bytes(json.dumps({"note": "café — naïve"}, ensure_ascii=False).encode("utf-8"))
            with patch.object(Path, "read_text", windows_read_text):
                self.assertEqual(load_json(path), {"note": "café — naïve"})

    def test_duplicate_and_invalid_outputs_are_rejected(self):
        manifest = ROOT / "data/public_playable/manifest.json"
        frozen = load_json(ROOT / "data/public_playable/simulated_evaluator_outputs.json")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            responses = root / "responses.json"
            responses.write_text(json.dumps({"annotations": []}), encoding="utf-8")
            outputs = root / "outputs.json"
            for records in [frozen + [frozen[0]], [{**frozen[0], "verdict": "UNSURE"}]]:
                outputs.write_text(json.dumps(records), encoding="utf-8")
                with self.subTest(records=records), self.assertRaises(ValueError):
                    compare_responses(manifest, outputs, responses)

    def test_response_with_missing_evaluator_output_is_rejected(self):
        manifest = ROOT / "data/public_playable/manifest.json"
        frozen = load_json(ROOT / "data/public_playable/simulated_evaluator_outputs.json")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outputs = root / "outputs.json"
            outputs.write_text(json.dumps(frozen[:1]), encoding="utf-8")
            responses = root / "responses.json"
            responses.write_text(json.dumps({"annotations": [{"rater_id": "rater-a",
                "artifact_sha256": frozen[1]["artifact_sha256"], "verdict": "PASS"}]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not present in outputs"):
                compare_responses(manifest, outputs, responses)

    def test_tie_break_sort_is_stable_across_raters_and_evaluators(self):
        manifest = ROOT / "data/public_playable/manifest.json"
        frozen = load_json(ROOT / "data/public_playable/simulated_evaluator_outputs.json")
        one = frozen[0]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outputs = root / "outputs.json"
            outputs.write_text(json.dumps([{**one, "evaluator_alias": alias}
                                          for alias in ["eval-z", "eval-a"]]), encoding="utf-8")
            rows = [{"artifact_sha256": one["artifact_sha256"], "rater_id": rater, "verdict": "PASS"}
                    for rater in ["rater-z", "rater-a"]]
            responses = root / "responses.json"
            reports = []
            for ordered in [rows, list(reversed(rows))]:
                responses.write_text(json.dumps({"annotations": ordered}), encoding="utf-8")
                reports.append(compare_responses(manifest, outputs, responses)["rows"])
            self.assertEqual(reports[0], reports[1])
            self.assertEqual([(r["rater_id"], r["evaluator_alias"]) for r in reports[0]],
                             [("rater-a", "eval-a"), ("rater-a", "eval-z"),
                              ("rater-z", "eval-a"), ("rater-z", "eval-z")])


if __name__ == "__main__":
    unittest.main()
