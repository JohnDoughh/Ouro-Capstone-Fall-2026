"""Team C Sprint 4: intent metrics, agreement and the deterministic report.

Every expected value here is computed by hand or taken from a published
example. All data are invented fictions, not study data.
"""
import contextlib
import gc
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from ouro_eval_lab.cli import main as cli_main
from ouro_eval_lab.coding import coding_items
from ouro_eval_lab.intent_metrics import (
    build_intent_report, reference_code, render_intent_report, summarize, survival_threshold,
)
from ouro_eval_lab.metrics import bootstrap_alpha_interval, krippendorff_alpha
from tests.test_intent_coding import CodingStudy, fill, read_sheet, write
from tests.test_intent_reveal import database

N = None
# Krippendorff (2011), "Computing Krippendorff's alpha-reliability": 4 coders,
# 12 units, values 1-5. Published: nominal 0.743, ordinal 0.815.
KRIPPENDORFF_EXAMPLE = list(zip(
    [1, 2, 3, 3, 2, 1, 4, 1, 2, N, N, N],
    [1, 2, 3, 3, 2, 2, 4, 1, 2, 5, N, 3],
    [N, 3, 3, 3, 2, 3, 4, 2, 2, 5, 1, N],
    [1, 2, 3, 3, 2, 4, 4, 1, 2, 5, 1, N],
))


def unit(response, *codes, clip="clip1", component="product", delivery="explicit_text",
         certainty=3, could_not_tell=False):
    return {
        "response_id": response, "clip": clip, "component": component, "delivery": delivery,
        "certainty": certainty, "could_not_tell": could_not_tell,
        "codes": {f"coder{i}": code for i, code in enumerate(codes)},
    }


def agreed(*codes, **kwargs):
    """One unit per code, both coders agreeing."""
    return [unit(f"r{i}", code, code, **kwargs) for i, code in enumerate(codes)]


def cell(units, clip="clip1", component="product"):
    rows = summarize(units, samples=50)["cells"]
    return next(row for row in rows if row["clip"] == clip and row["component"] == component)


class KrippendorffAlphaTests(unittest.TestCase):
    def test_published_example(self):
        self.assertAlmostEqual(krippendorff_alpha(KRIPPENDORFF_EXAMPLE), 0.743, places=3)
        self.assertAlmostEqual(krippendorff_alpha(KRIPPENDORFF_EXAMPLE, order=[1, 2, 3, 4, 5]), 0.815, places=3)

    def test_two_coder_nominal_by_hand(self):
        # Coincidences: aa=2, ab=ba=1, bb=4; n_a=3, n_b=5, n=8.
        # alpha = 1 - (n-1) * D_o / D_e = 1 - 7 * 2 / (2 * 3 * 5) = 8/15.
        self.assertAlmostEqual(krippendorff_alpha([("a", "a"), ("a", "b"), ("b", "b"), ("b", "b")]), 8 / 15)

    def test_edge_cases(self):
        self.assertEqual(krippendorff_alpha([("a", "a"), ("b", "b")]), 1.0)
        self.assertIsNone(krippendorff_alpha([("a", "a"), ("a", "a")]), "one value used: undefined")
        self.assertIsNone(krippendorff_alpha([("a",), ("b", None)]), "nothing pairable")
        self.assertIsNone(krippendorff_alpha([]))
        # Values outside the ordinal scale are dropped, not ranked.
        self.assertEqual(krippendorff_alpha([("lo", "lo"), ("hi", "hi"), ("x", "lo")], order=["lo", "hi"]), 1.0)

    def test_bootstrap_is_seeded_and_brackets_perfect_agreement(self):
        clusters = [[("a", "a")], [("b", "b")], [("a", "a"), ("b", "b")]]
        self.assertEqual(bootstrap_alpha_interval(clusters, seed=1, samples=200), [1.0, 1.0])
        noisy = [[("a", "b")], [("a", "a")], [("b", "b")], [("b", "a")], [("a", "a")]]
        first = bootstrap_alpha_interval(noisy, seed=7, samples=300, strata=["x", "x", "y", "y", "y"])
        self.assertEqual(first, bootstrap_alpha_interval(noisy, seed=7, samples=300, strata=["x", "x", "y", "y", "y"]))
        self.assertLessEqual(first[0], first[1])
        self.assertEqual(bootstrap_alpha_interval([[("a", "a")]], seed=1), [None, None])


class ReferenceAndSurvivalTests(unittest.TestCase):
    def test_reference_code_needs_two_agreeing_coders(self):
        self.assertEqual(reference_code({}), (None, "uncoded"))
        self.assertEqual(reference_code({"c1": "recovered"}), (None, "single_coded"))
        self.assertEqual(reference_code({"c1": "recovered", "c2": "recovered"}), ("recovered", "agreed"))
        self.assertEqual(reference_code({"c1": "recovered", "c2": "contradicted"}),
                         (None, "pending_adjudication"))

    def test_survival_threshold_is_ceil_two_thirds(self):
        self.assertEqual([survival_threshold(n) for n in (3, 4, 5, 6, 9)], [2, 3, 4, 4, 6])

    def test_survival_boundaries(self):
        R, P, X = "recovered", "partially_recovered", "not_recovered"
        self.assertEqual(cell(agreed(R, R, X))["survival"], "survived")
        self.assertEqual(cell(agreed(R, X, X))["survival"], "not_survived")
        self.assertEqual(cell(agreed(R, R, X, X))["survival"], "not_survived", "4 needs 3")
        self.assertEqual(cell(agreed(R, R, R, X))["survival"], "survived")
        self.assertEqual(cell(agreed(R, R))["survival"], "insufficient_responses")
        partial = cell(agreed(R, P, X))
        self.assertEqual(partial["survival"], "not_survived")
        self.assertEqual(partial["survival_counting_partial_exploratory"], "survived")
        self.assertEqual(partial["recovery"]["count"], 1)
        self.assertEqual(partial["recovery"]["n"], 3)

    def test_not_intended_is_not_applicable_and_left_out_of_rates(self):
        row = cell(agreed(*["not_applicable"] * 3, delivery="not_intended"))
        self.assertEqual(row["survival"], "not_applicable")
        self.assertEqual(row["recovery"]["n"], 0)
        self.assertIsNone(row["recovery"]["rate"])

    def test_disagreement_and_single_coding_block_survival(self):
        units = agreed("recovered", "recovered") + [unit("r9", "recovered", "contradicted")]
        row = cell(units)
        self.assertEqual(row["survival"], "pending_adjudication")
        self.assertEqual(row["coder_disagreement"], {"multi_coded": 3, "disagreed": 1})
        units = agreed("recovered", "recovered") + [unit("r9", "recovered")]
        self.assertEqual(cell(units)["survival"], "incomplete_coding")

    def test_ambiguity_reference_class(self):
        R, X = "recovered", "not_recovered"
        split = cell(agreed(R, R, R, X, X))  # 3/5 > 1/3 but below 4: viewers split.
        self.assertEqual(split["ambiguity"], {"viewers_split": True, "coders_split": False, "ambiguous": True})
        clear = cell(agreed(R, X, X))  # exactly 1/3 is not a split.
        self.assertFalse(clear["ambiguity"]["ambiguous"])
        coders = [unit("a", R, X), unit("b", R, R), unit("c", X, R), unit("d", R, R)]
        self.assertTrue(cell(coders)["ambiguity"]["coders_split"], "half the responses disagree")
        summary = summarize(agreed(R, R, R, X, X), samples=20)
        self.assertEqual(summary["ambiguity"], {"count": 1, "cells": [["clip1", "product"]]})


class PooledOutcomeTests(unittest.TestCase):
    def test_comprehension_disruption_counts_only_delivered_components(self):
        units = (
            agreed("not_recovered", "recovered", component="product")
            + [unit("r5", "contradicted", "contradicted", component="problem")]
            + [unit("r6", "not_recovered", "not_recovered", component="support", delivery="omitted_in_edit")]
            + [unit("r7", "not_applicable", "not_applicable", component="audience", delivery="not_intended")]
            + [unit("r8", "not_recovered", "not_recovered", component="tone")]
        )
        disruption = summarize(units, samples=20)["comprehension_disruption_primary"]
        self.assertEqual((disruption["count"], disruption["n"]), (2, 3))

    def test_viewer_calibration_and_confidently_wrong(self):
        units = [
            unit("a", "contradicted", "contradicted", certainty=5),
            unit("b", "contradicted", "contradicted", certainty=2),
            unit("c", "recovered", "recovered", certainty=4),
            unit("d", "not_recovered", "not_recovered", certainty=None, could_not_tell=True),
        ]
        calibration = summarize(units, samples=20)["viewer_calibration"]
        self.assertEqual(calibration["by_reference_code"]["contradicted"]["mean_certainty"], 3.5)
        self.assertEqual(calibration["by_reference_code"]["not_recovered"]["could_not_tell"], 1)
        self.assertIsNone(calibration["by_reference_code"]["not_recovered"]["mean_certainty"])
        self.assertEqual((calibration["confidently_wrong"]["count"], calibration["confidently_wrong"]["n"]), (1, 2))

    def test_delivery_strata_and_agreement_use_raw_codes(self):
        units = [
            unit("a", "recovered", "recovered", delivery="explicit_text"),
            unit("b", "recovered", "not_recovered", clip="clip2", delivery="implied"),
            unit("c", "not_applicable", "not_applicable", component="support", delivery="not_intended"),
        ]
        summary = summarize(units, samples=50)
        self.assertEqual(sorted(summary["by_delivery_primary"]), ["explicit_text"],
                         "pending and not_applicable units have no reference code")
        # Raw codes: (R,R), (R,X); the forced not_intended unit is excluded.
        # Coincidences RR=2, RX=XR=1; n_R=3, n_X=1, n=4: alpha = 1 - 3*2/(2*3*1) = 0.
        self.assertAlmostEqual(summary["agreement"]["primary_nominal"]["alpha"], 0.0)
        self.assertEqual(summary["agreement"]["primary_nominal"]["pairable_units"], 2)
        self.assertEqual(summary["agreement"]["primary_nominal"]["interpretation"],
                         "revise_codebook_before_reporting_recovery")


class IntentReportTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.addCleanup(gc.collect)
        self.root = Path(directory)
        self.study = CodingStudy(self.root)
        self.study.collect(viewers=("viewer_a", "viewer_b", "viewer_c"))
        self.study.freeze_and_reveal()
        for coder in ("coder_1", "coder_2"):
            rows = fill(read_sheet(self.study.sheet(coder)["body"]))
            if coder == "coder_2":
                for row in rows[::4]:
                    row["code"], row["note"] = "partially_recovered", "vaguer than the record"
            self.study.import_codes(write(rows), coder)

    def report(self, **kwargs):
        with database(self.study.db) as db:
            return build_intent_report(db, samples=100, code_commit="0" * 40, **kwargs)

    def test_report_is_byte_identical_on_rerun_and_bound_to_its_inputs(self):
        first, second = render_intent_report(self.report()), render_intent_report(self.report())
        self.assertEqual(first, second)
        report = json.loads(first)
        self.assertTrue(report["synthetic_demo"])
        self.assertIn("Not a research finding", report["disclaimer"])
        with database(self.study.db) as db:
            freeze = db.execute("SELECT export_sha256 FROM intent_freezes").fetchone()[0]
            records = db.execute("SELECT record_sha256 FROM intent_records ORDER BY relative_path").fetchall()
        self.assertEqual(report["inputs"]["response_freeze_sha256"], freeze)
        self.assertEqual([r["record_sha256"] for r in report["inputs"]["revealed_records"]],
                         [r[0] for r in records])
        self.assertEqual(report["inputs"]["coders"], 2)
        self.assertEqual(report["parameters"]["seed"], 20261014)
        self.assertEqual(report["versions"]["codebooks"], ["0.1-draft"])
        results = report["results"]
        self.assertEqual(results["responses"], 6)
        self.assertEqual(len(results["cells"]), 2 * 7)
        self.assertIsNotNone(results["agreement"]["primary_nominal"]["alpha"])

    def test_report_changes_when_a_code_is_added(self):
        before = render_intent_report(self.report())
        rows = fill(read_sheet(self.study.sheet("coder_3")["body"]))
        self.study.import_codes(write(rows), "coder_3")
        after = json.loads(render_intent_report(self.report()))
        self.assertNotEqual(json.loads(before)["inputs"]["codes_sha256"], after["inputs"]["codes_sha256"])
        self.assertEqual(after["inputs"]["coders"], 3)

    def test_report_carries_no_identities_or_free_text(self):
        body = render_intent_report(self.report()).decode()
        for secret in ("viewer_a", "coder_1", "Fictional answer", "vaguer than the record"):
            self.assertNotIn(secret, body)
        with database(self.study.db) as db:
            for row in db.execute("SELECT response_id FROM intent_responses"):
                self.assertNotIn(row[0], body)

    def test_cli_writes_the_same_bytes_twice(self):
        outputs = []
        for name in ("a.json", "b.json"):
            out = self.root / name
            with contextlib.redirect_stdout(io.StringIO()) as printed:
                cli_main(["intent-report", "--db", str(self.study.db), "--out", str(out),
                          "--samples", "100", "--code-commit", "1" * 40])
            self.assertIn(hashlib.sha256(out.read_bytes()).hexdigest(), printed.getvalue())
            outputs.append(out.read_bytes())
        self.assertEqual(outputs[0], outputs[1])

    def test_cli_html_view_is_written_from_the_same_report(self):
        out, html = self.root / "r.json", self.root / "r.html"
        with contextlib.redirect_stdout(io.StringIO()):
            cli_main(["intent-report", "--db", str(self.study.db), "--out", str(out),
                      "--samples", "50", "--code-commit", "1" * 40, "--html", str(html)])
        page = html.read_text(encoding="utf-8")
        self.assertIn(hashlib.sha256(out.read_bytes()).hexdigest(), page)
        for secret in ("viewer_a", "coder_1", "Fictional answer", "vaguer than the record"):
            self.assertNotIn(secret, page)

    def test_report_is_refused_without_codes(self):
        empty = CodingStudy(Path(self.enterContext(tempfile.TemporaryDirectory())))
        self.addCleanup(gc.collect)  # Windows: close stray handles before the directory goes.
        empty.collect()
        empty.freeze_and_reveal()
        with database(empty.db) as db, self.assertRaisesRegex(ValueError, "no intent codes"):
            build_intent_report(db)


if __name__ == "__main__":
    unittest.main()
