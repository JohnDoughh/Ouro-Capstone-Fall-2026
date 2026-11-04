"""Team C Sprint 4: intent recovery, survival, agreement and calibration.

Implements the analysis pre-registered in docs/TEAM_C_PREREGISTRATION.md
(sections 5-8, 12). The core, ``summarize``, is a pure function of coded
units, so every number can be checked by hand. ``build_intent_report`` loads
the units from a lab database and adds the hashes and parameters that bind a
report to its inputs.

Agreement always uses the raw codes. A reference code exists only where at
least two coders agree; a disagreement stays ``pending_adjudication`` until a
separate adjudication record exists (not built yet; see
docs/ADJUDICATION_PROPOSAL.md). Nothing here persuades or judges persuasion.
"""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from collections import defaultdict

from .contracts import (
    INTENT_CODING_CONTRACT_VERSION, INTENT_CONTRACT_VERSION, INTENT_FIELDS,
    INTENT_RECOVERY_CODES, INTENT_RESPONSE_CONTRACT_VERSION,
)
from .metrics import bootstrap_alpha_interval, krippendorff_alpha, wilson_interval

INTENT_REPORT_VERSION = "1.0.0"
DEFAULT_SEED = 20261014
DEFAULT_SAMPLES = 2000
MIN_RESPONSES = 3
EXPLORATORY = ("tone",)
PRIMARY = tuple(field for field in INTENT_FIELDS if field not in EXPLORATORY)
ORDINAL_SCALE = ["not_recovered", "partially_recovered", "recovered"]
UNDELIVERED = {"not_intended", "omitted_in_edit"}
DERIVED_VIEW = {
    "problem": "hook", "product": "thesis", "key_benefit": "thesis",
    "support": "proof", "call_to_action": "cta",
}
DISCLAIMER = (
    "Synthetic protocol-pilot output from fictional clips and team dry runs. "
    "Not a research finding and not a claim about Ouro systems or real advertising."
)


def reference_code(codes: dict[str, str]) -> tuple[str | None, str]:
    """The reference code for one (response, component) and why (§5)."""
    values = set(codes.values())
    if not codes:
        return None, "uncoded"
    if len(codes) < 2:
        return None, "single_coded"
    if len(values) == 1:
        return values.pop(), "agreed"
    return None, "pending_adjudication"


def survival_threshold(n: int) -> int:
    return math.ceil(2 * n / 3)


def _rate(count: int, n: int) -> dict:
    return {"count": count, "n": n, "rate": count / n if n else None, "ci95": wilson_interval(count, n)}


def _survival(recovered: int, n: int, statuses: dict[str, int], delivery: str) -> str:
    if delivery == "not_intended":
        return "not_applicable"
    if statuses.get("single_coded") or statuses.get("uncoded"):
        return "incomplete_coding"
    if statuses.get("pending_adjudication"):
        return "pending_adjudication"
    if n < MIN_RESPONSES:
        return "insufficient_responses"
    return "survived" if recovered >= survival_threshold(n) else "not_survived"


def _cell(clip: str, component: str, units: list[dict]) -> dict:
    deliveries = {unit["delivery"] for unit in units}
    if len(deliveries) != 1:
        raise ValueError("one (clip, component) cell must have one delivery code")
    delivery = deliveries.pop()
    status_counts: dict[str, int] = defaultdict(int)
    code_counts = {code: 0 for code in sorted(INTENT_RECOVERY_CODES)}
    multi, disagree = 0, 0
    for unit in units:
        code, status = reference_code(unit["codes"])
        status_counts[status] += 1
        if code is not None:
            code_counts[code] += 1
        if len(unit["codes"]) >= 2:
            multi += 1
            disagree += len(set(unit["codes"].values())) > 1
    eligible = sum(count for code, count in code_counts.items() if code != "not_applicable")
    recovered, partial = code_counts["recovered"], code_counts["partially_recovered"]
    survival = _survival(recovered, eligible, status_counts, delivery)
    decidable = survival in {"survived", "not_survived"}
    viewers_split = (
        recovered / eligible > 1 / 3 and recovered < survival_threshold(eligible)
        if decidable else None
    )
    coders_split = multi > 0 and disagree >= multi / 2
    return {
        "clip": clip,
        "component": component,
        "role": "exploratory" if component in EXPLORATORY else "primary",
        "derived_view": DERIVED_VIEW.get(component),
        "delivery": delivery,
        "responses": len(units),
        "reference_status": dict(sorted(status_counts.items())),
        "reference_codes": code_counts,
        "recovery": _rate(recovered, eligible),
        "contradicted": _rate(code_counts["contradicted"], eligible),
        "survival": survival,
        "survival_threshold": survival_threshold(eligible) if decidable else None,
        "survival_counting_partial_exploratory": (
            ("survived" if recovered + partial >= survival_threshold(eligible) else "not_survived")
            if decidable else survival
        ),
        "coder_disagreement": {"multi_coded": multi, "disagreed": disagree},
        "ambiguity": {
            "viewers_split": viewers_split,
            "coders_split": coders_split,
            "ambiguous": bool(viewers_split) or coders_split,
        },
    }


def _pooled(units: list[dict], key) -> dict:
    groups: dict[str, list[str]] = defaultdict(list)
    for unit in units:
        code, _ = reference_code(unit["codes"])
        if code is not None and code != "not_applicable":
            groups[key(unit)].append(code)
    return {
        name: {
            "recovery": _rate(codes.count("recovered"), len(codes)),
            "contradicted": _rate(codes.count("contradicted"), len(codes)),
        }
        for name, codes in sorted(groups.items())
    }


def _agreement(units: list[dict], components: tuple[str, ...], seed: int, samples: int,
               order: list[str] | None = None) -> dict:
    """Alpha over raw codes; not_intended units are excluded (their code is forced)."""
    clusters: dict[str, list[list[str]]] = defaultdict(list)
    clip_of: dict[str, str] = {}
    for unit in units:
        if unit["component"] in components and unit["delivery"] != "not_intended":
            clusters[unit["response_id"]].append([unit["codes"][c] for c in sorted(unit["codes"])])
            clip_of[unit["response_id"]] = unit["clip"]
    keys = sorted(clusters)
    flat = [unit for key in keys for unit in clusters[key]]
    pairable = [unit for unit in flat if len(unit) >= 2]
    alpha = krippendorff_alpha(flat, order)
    interval = bootstrap_alpha_interval(
        [clusters[key] for key in keys], seed, samples, order, [clip_of[key] for key in keys],
    ) if alpha is not None else [None, None]
    return {"alpha": alpha, "ci95": interval, "pairable_units": len(pairable),
            "coders_per_unit_max": max((len(unit) for unit in flat), default=0)}


def _interpretation(alpha: float | None) -> str:
    if alpha is None:
        return "undefined"
    if alpha >= 0.80:
        return "reliable"
    if alpha >= 0.667:
        return "tentative_only"
    return "revise_codebook_before_reporting_recovery"


def _calibration(units: list[dict]) -> dict:
    by_code: dict[str, list[dict]] = defaultdict(list)
    for unit in units:
        code, _ = reference_code(unit["codes"])
        if code is not None and code != "not_applicable" and unit["component"] in PRIMARY:
            by_code[code].append(unit)
    result = {}
    for code in sorted(by_code):
        items = by_code[code]
        certainties = [u["certainty"] for u in items if u["certainty"] is not None]
        result[code] = {
            "n": len(items),
            "could_not_tell": sum(u["could_not_tell"] for u in items),
            "mean_certainty": sum(certainties) / len(certainties) if certainties else None,
            "certainty_counts": {str(level): certainties.count(level) for level in range(1, 6)},
        }
    contradicted = [u["certainty"] for u in by_code.get("contradicted", []) if u["certainty"] is not None]
    return {
        "by_reference_code": result,
        "confidently_wrong": {
            "definition": "contradicted with viewer certainty 4 or 5",
            **_rate(sum(c >= 4 for c in contradicted), len(by_code.get("contradicted", []))),
        },
    }


def summarize(units: list[dict], seed: int = DEFAULT_SEED, samples: int = DEFAULT_SAMPLES) -> dict:
    """All pre-registered intent metrics for a list of coded units.

    Each unit: ``response_id``, ``clip``, ``component``, ``delivery``,
    ``certainty`` (1-5 or None), ``could_not_tell`` and ``codes`` mapping
    coder ID to that coder's raw code.
    """
    cells: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for unit in units:
        cells[(unit["clip"], unit["component"])].append(unit)
    order = {field: index for index, field in enumerate(INTENT_FIELDS)}
    cell_rows = [_cell(clip, component, cells[(clip, component)])
                 for clip, component in sorted(cells, key=lambda k: (k[0], order[k[1]]))]
    primary = [u for u in units if u["component"] in PRIMARY]
    delivered = [u for u in primary if u["delivery"] not in UNDELIVERED]
    delivered_codes = [code for code, _ in (reference_code(u["codes"]) for u in delivered)
                       if code is not None]
    agreement = _agreement(units, PRIMARY, seed, samples)
    statuses: dict[str, int] = defaultdict(int)
    for unit in units:
        statuses[reference_code(unit["codes"])[1]] += 1
    ambiguous = [[c["clip"], c["component"]] for c in cell_rows
                 if c["ambiguity"]["ambiguous"] and c["role"] == "primary"]
    return {
        "units": len(units),
        "responses": len({u["response_id"] for u in units}),
        "reference_status": dict(sorted(statuses.items())),
        "agreement": {
            "primary_nominal": {**agreement, "interpretation": _interpretation(agreement["alpha"])},
            "exploratory_ordinal": _agreement(units, PRIMARY, seed, samples, ORDINAL_SCALE),
            "exploratory_tone_nominal": _agreement(units, EXPLORATORY, seed, samples),
            "by_component_nominal": {
                field: krippendorff_alpha(
                    [list(u["codes"].values()) for u in units
                     if u["component"] == field and u["delivery"] != "not_intended"]
                )
                for field in INTENT_FIELDS
            },
        },
        "cells": cell_rows,
        "by_component": _pooled(units, lambda u: u["component"]),
        "by_delivery_primary": _pooled(primary, lambda u: u["delivery"]),
        "comprehension_disruption_primary": {
            "definition": "delivered components coded not_recovered or contradicted",
            **_rate(sum(code in {"not_recovered", "contradicted"} for code in delivered_codes),
                    len(delivered_codes)),
        },
        "viewer_calibration": _calibration(units),
        "ambiguity": {"count": len(ambiguous), "cells": ambiguous},
    }


def _canonical_sha256(value: object) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(body.encode()).hexdigest()


def load_units(db: sqlite3.Connection) -> list[dict]:
    """One unit per (frozen response, component) with every coder's raw code."""
    codes: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)
    for row in db.execute("SELECT response_id, component, coder_id, code FROM intent_codings"):
        codes[(row["response_id"], row["component"])][row["coder_id"]] = row["code"]
    units = []
    for row in db.execute(
        """SELECT r.response_id, r.components, x.artifact_id, rec.record_json
           FROM intent_responses r
           JOIN artifacts x ON x.sha256 = r.artifact_sha256
           JOIN intent_records rec ON rec.artifact_sha256 = r.artifact_sha256
           ORDER BY r.response_id"""
    ):
        answers = json.loads(row["components"])
        delivery = json.loads(row["record_json"])["delivery"]
        for component in INTENT_FIELDS:
            units.append({
                "response_id": row["response_id"],
                "clip": row["artifact_id"],
                "component": component,
                "delivery": delivery[component],
                "certainty": answers[component]["certainty"],
                "could_not_tell": answers[component]["could_not_tell"],
                "codes": codes.get((row["response_id"], component), {}),
            })
    return units


def build_intent_report(
    db: sqlite3.Connection, seed: int = DEFAULT_SEED, samples: int = DEFAULT_SAMPLES,
    code_commit: str = "unrecorded",
) -> dict:
    """Deterministic report: the same database and arguments give the same bytes."""
    reveal = db.execute("SELECT * FROM intent_reveals ORDER BY revealed_at DESC LIMIT 1").fetchone()
    if reveal is None:
        raise ValueError("no intent records are revealed; nothing to report")
    codings = [dict(row) for row in db.execute(
        """SELECT coder_id, response_id, response_sha256, record_sha256, artifact_sha256,
                  component, delivery, code, confidence, note, codebook_version,
                  coding_contract_version
           FROM intent_codings ORDER BY coder_id, response_id, component"""
    )]
    if not codings:
        raise ValueError("no intent codes are imported; nothing to report")
    records = [dict(row) for row in db.execute(
        """SELECT relative_path, record_sha256, artifact_sha256, record_json
           FROM intent_records ORDER BY relative_path"""
    )]
    fictional = all(json.loads(r["record_json"]).get("fictional") is True for r in records)
    units = load_units(db)
    return {
        "report": "team-c-intent-fidelity",
        "intent_report_version": INTENT_REPORT_VERSION,
        "synthetic_demo": True,
        "fictional_records": fictional,
        "disclaimer": DISCLAIMER,
        "versions": {
            "code_commit": code_commit,
            "intent_contract": INTENT_CONTRACT_VERSION,
            "intent_response_contract": INTENT_RESPONSE_CONTRACT_VERSION,
            "intent_coding_contract": INTENT_CODING_CONTRACT_VERSION,
            "codebooks": sorted({c["codebook_version"] for c in codings}),
        },
        "parameters": {
            "seed": seed,
            "bootstrap_samples": samples,
            "bootstrap_resampling": "responses within clip, percentile interval",
            "wilson_z": 1.96,
            "survival_rule": "survived when at least ceil(2n/3) of n eligible reference codes are recovered",
            "min_responses_for_survival": MIN_RESPONSES,
            "primary_components": list(PRIMARY),
            "exploratory_components": list(EXPLORATORY),
            "sheet_seeds": sorted({row[0] for row in db.execute("SELECT seed FROM intent_coding_sheets")}),
        },
        "inputs": {
            "response_freeze_sha256": reveal["freeze_sha256"],
            "commitments_sha256": reveal["commitments_sha256"],
            "revealed_records": [
                # The reveal checked each clip's bytes against the manifest.
                {"relative_path": r["relative_path"], "record_sha256": r["record_sha256"],
                 "artifact_sha256": r["artifact_sha256"]}
                for r in records
            ],
            "codes_sha256": _canonical_sha256(codings),
            "code_import_sha256": sorted(
                row[0] for row in db.execute("SELECT import_sha256 FROM intent_code_imports")
            ),
            "coders": len({c["coder_id"] for c in codings}),
        },
        "exclusions": {
            "excluded_responses": [],
            "not_yet_checkable": [
                "facilitator exposure log (not built): pre-response exposure to records or README",
            ],
            "enforced_at_capture": [
                "every component answered or marked could not tell",
                "server-held play limit",
                "contact details rejected",
            ],
        },
        "evaluator_comparison": {
            "status": "not_available",
            "reason": "no council-approved intent evaluator-output contract and no frozen evaluator outputs",
        },
        "persuasion": {"status": "not_collected", "reason": "excluded unless FIU approves"},
        "results": summarize(units, seed, samples),
    }


def render_intent_report(report: dict) -> bytes:
    return (json.dumps(report, indent=2, sort_keys=True) + "\n").encode()
