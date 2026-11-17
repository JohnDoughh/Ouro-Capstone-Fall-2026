"""Reviewer agreement and repeat consistency for the offline report workflow.

Integrates the Card #877 pairing rules with the shared PR #35 kappa
convention (Card #1427). The calculations only read rows; they never update,
replace, or adjudicate a stored judgment.

- Inter-reviewer agreement: the earliest assignment (by sequence) for each
  reviewer and artifact, then every distinct-reviewer pair for that artifact.
  A reviewer's repeat assignments never stand in for a second reviewer.
- Repeat consistency: adjacent assignments by the same reviewer for the same
  artifact within one repeat_group.
- Only PASS/HOLD pairs are eligible. A pair with a missing judgment counts as
  missing (taking precedence over UNSURE); otherwise a pair containing UNSURE
  counts as UNSURE. Neither enters a denominator.
- Undefined metrics are reported as null with a status string, never as 0 or 1.
"""
from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from typing import Iterable, Mapping

from .metrics import bootstrap_kappa_interval, cohens_kappa

SCHEMA_VERSION = "agreement-report-v2"
DEFINITIVE = frozenset({"PASS", "HOLD"})
KNOWN_VERDICTS = DEFINITIVE | {"UNSURE"}

AGREEMENT_ROWS_SQL = """
SELECT a.assignment_id, a.artifact_sha256, a.rater_id, a.repeat_group, a.sequence, n.verdict
FROM assignments a
LEFT JOIN annotations n ON n.assignment_id = a.assignment_id
ORDER BY a.artifact_sha256, a.rater_id, a.sequence, a.assignment_id
"""

METHODS = {
    "inter": "Earliest sequence per reviewer and artifact; all distinct-reviewer pairs",
    "repeat": "Adjacent assignments within each rater/artifact/repeat_group",
    "exclusions": "Missing takes precedence over UNSURE; both excluded from denominator",
    "undefined": (
        "Rates are null with zero eligible pairs; kappa is null with zero eligible pairs "
        "or expected agreement of one (PR #35)"
    ),
    "limitations": (
        "Exploratory pairwise statistics. With 3+ reviewers, pairs reuse judgments, so the "
        "bootstrap interval assumes independence it does not have. Preregister a multi-rater "
        "method (for example Krippendorff's alpha) and its interval before research claims."
    ),
}


def kappa_status(pairs: list[tuple[str, str]]) -> str:
    if not pairs:
        return "unavailable: no eligible pairs"
    if cohens_kappa(pairs) is None:
        return "unavailable: single category (expected agreement = 1)"
    return "available"


def _summarize(candidates: list[tuple[str | None, str | None]]) -> tuple[dict, list[tuple[str, str]]]:
    eligible: list[tuple[str, str]] = []
    unsure = missing = 0
    for a, b in candidates:
        for verdict in (a, b):
            if verdict is not None and verdict not in KNOWN_VERDICTS:
                raise ValueError(f"unexpected verdict: {verdict!r}")
        if a is None or b is None:
            missing += 1
        elif a == "UNSURE" or b == "UNSURE":
            unsure += 1
        else:
            eligible.append((a, b))
    agreements = sum(a == b for a, b in eligible)
    return {
        "total_candidate_pairs": len(candidates),
        "pair_count": len(eligible),
        "agreements": agreements,
        "disagreements": len(eligible) - agreements,
        "agreement_rate": agreements / len(eligible) if eligible else None,
        "unsure_pairs": unsure,
        "missing_pairs": missing,
    }, eligible


def _order(row: Mapping) -> tuple:
    return (row["sequence"], row["assignment_id"])


def calculate(rows: Iterable[Mapping], seed: int = 20260825) -> dict:
    """Rows need assignment_id, artifact_sha256, rater_id, repeat_group,
    sequence and verdict (None when the assignment has no annotation)."""
    by_artifact: dict[str, list[dict]] = defaultdict(list)
    by_repeat: dict[tuple, list[dict]] = defaultdict(list)
    for source in rows:
        row = dict(source)
        by_artifact[row["artifact_sha256"]].append(row)
        if row["repeat_group"] is not None:
            by_repeat[(row["rater_id"], row["artifact_sha256"], row["repeat_group"])].append(row)

    inter_candidates = []
    for artifact in sorted(by_artifact):
        earliest: dict[str, dict] = {}
        for row in sorted(by_artifact[artifact], key=_order):
            earliest.setdefault(row["rater_id"], row)
        for a, b in combinations((earliest[rater] for rater in sorted(earliest)), 2):
            inter_candidates.append((a["verdict"], b["verdict"]))

    repeat_candidates = []
    for key in sorted(by_repeat):
        ordered = sorted(by_repeat[key], key=_order)
        repeat_candidates.extend((a["verdict"], b["verdict"]) for a, b in zip(ordered, ordered[1:]))

    inter, inter_pairs = _summarize(inter_candidates)
    repeat, _ = _summarize(repeat_candidates)
    inter["cohens_kappa_exploratory"] = cohens_kappa(inter_pairs)
    inter["cohens_kappa_status"] = kappa_status(inter_pairs)
    inter["cohens_kappa_95ci_exploratory"] = bootstrap_kappa_interval(inter_pairs, seed)
    return {
        "schema_version": SCHEMA_VERSION,
        "data_classification": "synthetic/demo or authorized local database only",
        "analysis_seed": seed,
        "inter_reviewer_agreement": inter,
        "repeat_consistency": repeat,
        "methods": METHODS,
    }


def agreement_rows(db) -> list[dict]:
    return [dict(row) for row in db.execute(AGREEMENT_ROWS_SQL)]
