from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path

from .contracts import validate_evaluator_output, validate_manifest, validate_native_avc_output
from .metrics import bootstrap_kappa_interval, cohens_kappa, evaluator_report


def load_json(path: Path) -> object:
    return json.loads(path.read_text())


def verify_manifest(manifest_path: Path) -> dict:
    manifest = load_json(manifest_path)
    validate_manifest(manifest)
    root = manifest_path.parent.resolve()
    checked = []
    for artifact in manifest["artifacts"]:
        target = (root / artifact["relative_path"]).resolve()
        if root not in target.parents:
            raise ValueError(f"artifact escaped fixture root: {artifact['relative_path']}")
        blob = target.read_bytes()
        digest = hashlib.sha256(blob).hexdigest()
        if digest != artifact["sha256"] or len(blob) != artifact["byte_length"]:
            raise ValueError(f"artifact integrity failure: {artifact['artifact_id']}")
        checked.append(digest)
    return {"benchmark_id": manifest["benchmark_id"], "verified": len(checked), "manifest": manifest}


def run_benchmark(manifest_path: Path, outputs_path: Path) -> dict:
    verified = verify_manifest(manifest_path)
    manifest = verified["manifest"]
    outputs = load_json(outputs_path)
    if not isinstance(outputs, list):
        raise ValueError("evaluator outputs must be a list")
    truth = {row["sha256"]: row for row in manifest["artifacts"]}
    joined = []
    seen = set()
    for output in outputs:
        validate_evaluator_output(output)
        digest = output["artifact_sha256"]
        if digest not in truth:
            raise ValueError(f"output references unknown artifact hash: {digest}")
        if (digest, output["evaluator_alias"]) in seen:
            raise ValueError(f"duplicate output for artifact/evaluator: {digest}")
        seen.add((digest, output["evaluator_alias"]))
        joined.append({**output, **truth[digest]})
    expected = {row["sha256"] for row in manifest["artifacts"]}
    actual = {row["artifact_sha256"] for row in outputs}
    if expected != actual:
        raise ValueError(f"output coverage mismatch: missing={len(expected-actual)}, extra={len(actual-expected)}")
    report = evaluator_report(joined, manifest["seed"])
    report.update({
        "contract_version": manifest["contract_version"],
        "benchmark_id": manifest["benchmark_id"],
        "evaluator_aliases": sorted({row["evaluator_alias"] for row in outputs}),
        "synthetic_demo": all(row["synthetic"] for row in manifest["artifacts"]),
        "disclaimer": "Synthetic pipeline demonstration; not an Ouro performance claim or research finding.",
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "outputs_sha256": hashlib.sha256(outputs_path.read_bytes()).hexdigest(),
    })
    return report



def inspect_native_avc(manifest_path: Path, evaluation_path: Path) -> dict:
    """Inspect one sanitized native AVC result without treating it as v1 truth.

    This intentionally performs no PASS/HOLD mapping, calibration, Brier score,
    ECE, false-pass or false-hold calculation. Those require independent human
    reference labels rather than AVC's operational delivery decision.
    """
    verified = verify_manifest(manifest_path)
    manifest = verified["manifest"]
    evaluation = load_json(evaluation_path)
    if not isinstance(evaluation, dict):
        raise ValueError("native AVC evaluation must be one JSON object")
    validate_native_avc_output(evaluation)
    by_sha = {row["sha256"]: row for row in manifest["artifacts"]}
    digest = evaluation["media_sha256"]
    if digest not in by_sha:
        raise ValueError(f"native AVC output references unknown artifact hash: {digest}")
    artifact = by_sha[digest]
    if artifact["byte_length"] != evaluation["media_bytes"]:
        raise ValueError("native AVC output media byte length does not match manifest")
    genuine = evaluation["provenance"] == "canonical-approved-synthetic"
    return {
        "schema_version": evaluation["schema_version"],
        "benchmark_id": manifest["benchmark_id"],
        "artifact_id": artifact["artifact_id"],
        "media_sha256": digest,
        "evaluator_alias": evaluation["evaluator_alias"],
        "evaluated_at": evaluation["evaluated_at"],
        "provenance": evaluation["provenance"],
        "genuine_avc": genuine,
        "delivery_decision": evaluation["delivery_decision"],
        "coverage": evaluation["coverage"],
        "modalities": evaluation["modalities"],
        "defect_assessment": evaluation["defect_assessment"],
        "probability": None,
        "probability_status": evaluation["probability_status"],
        "probability_reason": evaluation["probability_reason"],
        "evidence_codes": evaluation["evidence_codes"],
        "calibration_eligible": False,
        "defect_confusion_matrix_eligible": False,
        "warning": (
            "Native AVC inspection only. Delivery decisions are not human defect truth; "
            "null probability is excluded from calibration. Preserve blinded human judgments "
            "before revealing evaluator answers."
        ),
    }


EXPORT_FIELDS = [
    "annotation_id", "rater_id", "artifact_sha256", "verdict", "confidence",
    "reason_codes", "note", "started_at", "completed_at",
]


def export_annotations(db, format_name: str = "json") -> str:
    rows = [dict(row) for row in db.execute(
        "SELECT " + ", ".join(EXPORT_FIELDS) + " FROM annotations ORDER BY completed_at, annotation_id"
    )]
    for row in rows:
        unknown = row.keys() - set(EXPORT_FIELDS)
        if unknown:
            raise ValueError(f"export contains unknown fields: {unknown}")
        row["reason_codes"] = json.loads(row["reason_codes"])
    if format_name == "json":
        return json.dumps({"contract_version": "1.0.0", "annotations": rows}, indent=2, sort_keys=True) + "\n"
    if format_name == "csv":
        stream = io.StringIO()
        writer = csv.DictWriter(stream, fieldnames=EXPORT_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, "reason_codes": "|".join(row["reason_codes"])})
        return stream.getvalue()
    raise ValueError("format must be json or csv")


def agreement_report(db, seed: int = 20260825) -> dict:
    records = db.execute(
        "SELECT artifact_sha256, rater_id, verdict FROM annotations WHERE verdict != 'UNSURE' ORDER BY artifact_sha256, rater_id"
    ).fetchall()
    by_artifact: dict[str, list] = {}
    for row in records:
        by_artifact.setdefault(row["artifact_sha256"], []).append(row)
    pairs = [(items[0]["verdict"], items[1]["verdict"]) for items in by_artifact.values() if len(items) >= 2]
    return {
        "pair_count": len(pairs),
        "cohens_kappa": cohens_kappa(pairs),
        "cohens_kappa_95ci": bootstrap_kappa_interval(pairs, seed),
        "note": "Uses the first two pseudonymous raters per artifact; extend to Krippendorff alpha for 3+ raters.",
    }
