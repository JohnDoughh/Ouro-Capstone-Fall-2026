from __future__ import annotations

import math
import random
from collections import defaultdict
from typing import Iterable


def wilson_interval(successes: int, total: int, z: float = 1.96) -> list[float | None]:
    if total == 0:
        return [None, None]
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denominator
    return [max(0.0, center - margin), min(1.0, center + margin)]


def confusion(rows: Iterable[dict]) -> dict[str, int | float | list[float | None]]:
    counts = {"true_hold": 0, "true_pass": 0, "false_hold": 0, "false_pass": 0}
    for row in rows:
        truth_hold = bool(row["defect_present"])
        predicted_hold = row["verdict"] == "HOLD"
        if truth_hold and predicted_hold:
            counts["true_hold"] += 1
        elif truth_hold:
            counts["false_pass"] += 1
        elif predicted_hold:
            counts["false_hold"] += 1
        else:
            counts["true_pass"] += 1
    defect_total = counts["true_hold"] + counts["false_pass"]
    clean_total = counts["true_pass"] + counts["false_hold"]
    counts["false_pass_rate"] = counts["false_pass"] / defect_total if defect_total else 0.0
    counts["false_hold_rate"] = counts["false_hold"] / clean_total if clean_total else 0.0
    counts["false_pass_95ci"] = wilson_interval(counts["false_pass"], defect_total)
    counts["false_hold_95ci"] = wilson_interval(counts["false_hold"], clean_total)
    return counts


def hold_probability(row: dict) -> float:
    confidence = float(row["confidence"])
    return confidence if row["verdict"] == "HOLD" else 1.0 - confidence


def brier_score(rows: list[dict]) -> float:
    if not rows:
        return 0.0
    return sum((hold_probability(row) - float(row["defect_present"])) ** 2 for row in rows) / len(rows)


def expected_calibration_error(rows: list[dict], bins: int = 10) -> float:
    if not rows:
        return 0.0
    buckets: dict[int, list[tuple[float, float]]] = defaultdict(list)
    for row in rows:
        probability = hold_probability(row)
        bucket = min(bins - 1, int(probability * bins))
        buckets[bucket].append((probability, float(row["defect_present"])))
    total = len(rows)
    return sum(
        len(values) / total * abs(
            sum(p for p, _ in values) / len(values) - sum(y for _, y in values) / len(values)
        )
        for values in buckets.values()
    )


def risk_coverage(rows: list[dict], thresholds: Iterable[float] | None = None) -> list[dict[str, float | int]]:
    thresholds = thresholds or [0.5, 0.6, 0.7, 0.8, 0.9, 0.95]
    result = []
    for threshold in thresholds:
        retained = [row for row in rows if float(row["confidence"]) >= threshold]
        errors = sum((row["verdict"] == "HOLD") != bool(row["defect_present"]) for row in retained)
        result.append({
            "threshold": threshold,
            "coverage": len(retained) / len(rows) if rows else 0.0,
            "retained": len(retained),
            "errors": errors,
            "selective_risk": errors / len(retained) if retained else 0.0,
        })
    return result


def cohens_kappa(pairs: list[tuple[str, str]]) -> float | None:
    if not pairs:
        return None
    labels = sorted({value for pair in pairs for value in pair})
    observed = sum(a == b for a, b in pairs) / len(pairs)
    expected = sum(
        (sum(a == label for a, _ in pairs) / len(pairs))
        * (sum(b == label for _, b in pairs) / len(pairs))
        for label in labels
    )
    if expected == 1:
        return 1.0
    return (observed - expected) / (1 - expected)


def bootstrap_kappa_interval(pairs: list[tuple[str, str]], seed: int, samples: int = 1000) -> list[float | None]:
    if len(pairs) < 2:
        return [None, None]
    rng = random.Random(seed)
    values = []
    for _ in range(samples):
        sample = [pairs[rng.randrange(len(pairs))] for _ in pairs]
        value = cohens_kappa(sample)
        if value is not None:
            values.append(value)
    values.sort()
    if not values:
        return [None, None]
    return [values[int(0.025 * (len(values) - 1))], values[int(0.975 * (len(values) - 1))]]


def evaluator_report(rows: list[dict], seed: int) -> dict:
    by_family: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_family[row["defect_family"]].append(row)
    return {
        "n": len(rows),
        "confusion": confusion(rows),
        "brier_score": brier_score(rows),
        "expected_calibration_error": expected_calibration_error(rows),
        "risk_coverage": risk_coverage(rows),
        "by_defect_family": {
            family: {
                "n": len(items),
                "confusion": confusion(items),
                "brier_score": brier_score(items),
            }
            for family, items in sorted(by_family.items())
        },
        "analysis_seed": seed,
    }
