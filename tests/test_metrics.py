import unittest

from ouro_eval_lab.metrics import brier_score, bootstrap_kappa_interval, cohens_kappa, confusion, expected_calibration_error, risk_coverage


class MetricTests(unittest.TestCase):
    def test_confusion_names_false_pass_as_missed_defect(self):
        rows = [
            {"defect_present": True, "verdict": "PASS"},
            {"defect_present": False, "verdict": "HOLD"},
            {"defect_present": True, "verdict": "HOLD"},
            {"defect_present": False, "verdict": "PASS"},
        ]
        result = confusion(rows)
        self.assertEqual(result["false_pass"], 1)
        self.assertEqual(result["false_hold"], 1)
        self.assertEqual(result["false_pass_rate"], 0.5)

    def test_perfect_probabilities_have_zero_brier_and_ece(self):
        rows = [
            {"defect_present": True, "verdict": "HOLD", "confidence": 1.0},
            {"defect_present": False, "verdict": "PASS", "confidence": 1.0},
        ]
        self.assertEqual(brier_score(rows), 0.0)
        self.assertEqual(expected_calibration_error(rows), 0.0)

    def test_risk_coverage_abstains_below_threshold(self):
        rows = [
            {"defect_present": True, "verdict": "PASS", "confidence": 0.55},
            {"defect_present": True, "verdict": "HOLD", "confidence": 0.95},
        ]
        point = risk_coverage(rows, [0.9])[0]
        self.assertEqual(point["coverage"], 0.5)
        self.assertEqual(point["selective_risk"], 0.0)

    def test_kappa(self):
        self.assertEqual(cohens_kappa([("PASS", "PASS"), ("HOLD", "HOLD")]), 1.0)

    def test_kappa_is_unavailable_for_single_category_agreement(self):
        for label in ("PASS", "HOLD"):
            for size in (1, 3):
                with self.subTest(label=label, size=size):
                    self.assertIsNone(cohens_kappa([(label, label)] * size))

    def test_kappa_handles_empty_and_disagreeing_pairs(self):
        self.assertIsNone(cohens_kappa([]))
        self.assertEqual(cohens_kappa([("PASS", "HOLD"), ("HOLD", "PASS")]), -1.0)
        self.assertEqual(cohens_kappa([("PASS", "PASS"), ("PASS", "HOLD")]), 0.0)

    def test_bootstrap_does_not_turn_undefined_samples_into_perfect_agreement(self):
        self.assertEqual(bootstrap_kappa_interval([("PASS", "PASS")] * 3, seed=7), [None, None])
        self.assertEqual(bootstrap_kappa_interval([("HOLD", "HOLD")] * 3, seed=7), [None, None])
        self.assertEqual(bootstrap_kappa_interval([("PASS", "PASS"), ("HOLD", "HOLD")], seed=7), [1.0, 1.0])


if __name__ == "__main__":
    unittest.main()
