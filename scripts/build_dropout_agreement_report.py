#!/usr/bin/env python3
"""Build a deterministic, public-safe dropout agreement report.

The default inputs are the fictional card #465 annotation and simulated
evaluator output.  They exercise the reporting path without publishing or
replacing a participant judgment.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from scripts.build_card465_dropout_evidence import (
        load_object,
        validate_human,
        validate_simulated,
    )
except ModuleNotFoundError:  # Direct execution adds scripts/, not the repository root.
    from build_card465_dropout_evidence import (  # type: ignore[no-redef]
        load_object,
        validate_human,
        validate_simulated,
    )


def build_report(annotation: dict, evaluation: dict) -> dict:
    validate_human(annotation)
    validate_simulated(evaluation)

    same_artifact = (
        annotation["artifact_id"] == evaluation["artifact_id"]
        and annotation["artifact_sha256"] == evaluation["artifact_sha256"]
    )
    if not same_artifact:
        raise ValueError("annotation and evaluator output must identify the same media bytes")

    human_verdict = annotation["verdict"]
    evaluator_verdict = evaluation["verdict"]
    uncertain = human_verdict == "UNSURE"
    comparable = not uncertain
    agreement = int(comparable and human_verdict == evaluator_verdict)
    disagreement = int(comparable and human_verdict != evaluator_verdict)

    reference_is_independent = annotation.get("reference_role") == "independent_reference"
    false_metrics: dict[str, object]
    if reference_is_independent and comparable:
        false_pass = int(evaluator_verdict == "PASS" and human_verdict == "HOLD")
        false_hold = int(evaluator_verdict == "HOLD" and human_verdict == "PASS")
        false_metrics = {
            "status": "available",
            "false_pass_count": false_pass,
            "false_hold_count": false_hold,
            "comparable_reference_count": 1,
        }
    else:
        false_metrics = {
            "status": "unavailable",
            "reason": (
                "reference judgment is uncertain"
                if uncertain
                else "no explicitly independent comparable reference judgment"
            ),
            "false_pass_count": None,
            "false_hold_count": None,
            "comparable_reference_count": 0,
        }

    return {
        "report_version": "1.0.0",
        "synthetic_demo": True,
        "disclaimer": (
            "Fictional annotation and simulated evaluator demonstration; "
            "not a human-subject result or evaluator performance claim."
        ),
        "artifact": {
            "artifact_id": annotation["artifact_id"],
            "artifact_sha256": annotation["artifact_sha256"],
        },
        "inputs": {
            "annotation_id": annotation["annotation_id"],
            "annotation_provenance": annotation["provenance"],
            "evaluator_alias": evaluation["evaluator_alias"],
            "evaluator_provenance": evaluation["provenance"],
        },
        "metrics": {
            "pair_count": 1,
            "comparable_pair_count": int(comparable),
            "agreement_count": agreement,
            "disagreement_count": disagreement,
            "uncertain_count": int(uncertain),
            "coverage": 1.0,
            "comparable_coverage": float(comparable),
            "false_passes_and_holds": false_metrics,
        },
    }


def write_report(annotation_path: Path, evaluation_path: Path, out: Path) -> None:
    report = build_report(load_object(annotation_path), load_object(evaluation_path))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes((json.dumps(report, indent=2, sort_keys=True) + "\n").encode())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--annotation",
        type=Path,
        default=Path("data/card465_dropout_evidence/fictional_annotation.json"),
    )
    parser.add_argument(
        "--evaluation",
        type=Path,
        default=Path("data/card465_dropout_evidence/simulated_evaluator_output.json"),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/card465_dropout_evidence/exports/agreement-report.json"),
    )
    args = parser.parse_args()
    write_report(args.annotation, args.evaluation, args.out)
    print(f"wrote reproducible dropout agreement report to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
