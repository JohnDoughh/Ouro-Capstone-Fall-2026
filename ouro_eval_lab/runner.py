from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path

from .contracts import (
    ANNOTATION_CONTRACT_VERSION, HUMAN_VERDICTS, INTENT_FIELDS, INTENT_RESPONSE_CONTRACT_VERSION,
    validate_evaluator_output, validate_manifest, validate_native_avc_output,
)
from .metrics import bootstrap_kappa_interval, cohens_kappa, evaluator_report


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


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


COMPARE_LIMITATIONS = [
    "Evaluator outputs are simulated test data, not AVC output.",
    "Responses are a teammate practice rating, not research data.",
    "Compares human vs evaluator only; not a measure of evaluator accuracy against ground truth.",
    "Counts are annotation comparisons, not independent reviewers; repeated ratings remain separate rows.",
    "An empty or partial response export does not establish complete study coverage.",
]


def _outcome(human: str, evaluator: str) -> str:
    """
    Determines the outcome of a comparison between a human verdict and an evaluator verdict.
    Returns a string representing the type of agreement or disagreement.

    Args:
        human (str): The human verdict.
        evaluator (str): The evaluator verdict.

    Returns:
        str: A string representing the type of agreement or disagreement.
    """
    if human == "UNSURE":
        return "human_unsure"
    elif evaluator == "UNSURE":
        # Unreachable today: validate_evaluator_output only allows PASS/HOLD.
        return "evaluator_unsure"
    elif human == evaluator:
        return "agree"
    elif human == "PASS" and evaluator == "HOLD":
        return "false_hold"
    elif human == "HOLD" and evaluator == "PASS":
        return "false_pass"
    else:
        raise ValueError(f"unexpected human/evaluator verdict pair: {human}/{evaluator}")


def compare_responses(manifest_path: Path, outputs_path: Path, responses_path: Path) -> dict:
    """
    Compares the responses between the evaluator and the human responses to check human vs simulated evaluator agreement.
    This function will analyze the outputs and provide a summary of the agreement between the two sets of responses.
    """
    verified = verify_manifest(manifest_path)
    manifest = verified["manifest"]
    by_hash = {row["sha256"]: row for row in manifest["artifacts"]}

    outputs = load_json(outputs_path)
    if not isinstance(outputs, list):
        raise ValueError("evaluator outputs must be a list")

    # Checks that the outputs are valid and correspond to the artifacts in the manifest
    outputs_by_hash = {}
    seen = set()
    for output in outputs:
        validate_evaluator_output(output)
        digest = output["artifact_sha256"]
        if digest not in by_hash:
            raise ValueError(f"output references unknown artifact hash: {digest}")
        if (digest, output["evaluator_alias"]) in seen:
            raise ValueError(f"duplicate output for artifact/evaluator: {digest}")
        seen.add((digest, output["evaluator_alias"]))
        outputs_by_hash.setdefault(digest, []).append(output)

    # Checks that the responses are valid and correspond to the artifacts in the manifest
    responses = load_json(responses_path)
    if not isinstance(responses, dict):
        raise ValueError("human responses must be a dictionary")
    if "annotations" not in responses:
        raise ValueError("human responses must contain an 'annotations' key")
    if not isinstance(responses["annotations"], list):
        raise ValueError("human responses 'annotations' must be a list")

    comparison = []
    for response in responses["annotations"]:
        if not isinstance(response, dict):
            raise ValueError("human response must be an object")
        artifact_sha256 = response.get("artifact_sha256")
        if not isinstance(artifact_sha256, str):
            raise ValueError(f"invalid artifact_sha256 in human response: {artifact_sha256}")
        if artifact_sha256 not in by_hash:
            raise ValueError(f"response references unknown artifact hash: {artifact_sha256}")
        if artifact_sha256 not in outputs_by_hash:
            raise ValueError(f"response references artifact hash not present in outputs: {artifact_sha256}")
        verdict = response.get("verdict")
        if not isinstance(verdict, str) or verdict not in HUMAN_VERDICTS:
            raise ValueError(f"invalid verdict in human response: {verdict}")
        rater_id = response.get("rater_id")
        if not isinstance(rater_id, str) or not rater_id:
            raise ValueError(f"invalid rater_id in human response: {rater_id}")

        # Matching the human response with the corresponding evaluator output
        evaluator_output = outputs_by_hash[artifact_sha256]
        for output in evaluator_output:
            # Implements the comparison logic between the human response and the evaluator output
            comparison.append({
                "artifact_sha256": artifact_sha256,
                "human_verdict": verdict,
                "evaluator_verdict": output["verdict"],
                "rater_id": rater_id,
                "evaluator_alias": output["evaluator_alias"],
                "outcome": _outcome(verdict, output["verdict"])
            })

    # Summary of the agreement between human responses and evaluator outputs
    comparison.sort(key=lambda row: (row["artifact_sha256"], row["rater_id"], row["evaluator_alias"]))

    counts = {name: 0 for name in ("agree", "false_pass", "false_hold", "human_unsure", "evaluator_unsure")}
    for row in comparison:
        counts[row["outcome"]] += 1

    return {
        "benchmark_id": manifest["benchmark_id"],
        "annotation_contract_version": responses.get("annotation_contract_version"),
        "synthetic_demo": all(row["synthetic"] for row in manifest["artifacts"]),
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "outputs_sha256": hashlib.sha256(outputs_path.read_bytes()).hexdigest(),
        "responses_sha256": hashlib.sha256(responses_path.read_bytes()).hexdigest(),
        "rows": comparison,
        "counts": counts,
        "limitations": COMPARE_LIMITATIONS,
    }


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
    "confidence_scale", "severity", "defect_timestamps",
    "rubric_version", "defect_family_id", "region", "reference_id", "evidence_description",
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
        return json.dumps({
            "contract_version": "1.0.0",
            "annotation_contract_version": ANNOTATION_CONTRACT_VERSION,
            "annotations": rows,
        }, indent=2, sort_keys=True) + "\n"
    if format_name == "csv":
        stream = io.StringIO()
        writer = csv.DictWriter(stream, fieldnames=EXPORT_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, "reason_codes": "|".join(row["reason_codes"])})
        return stream.getvalue()
    raise ValueError("format must be json or csv")


INTENT_EXPORT_FIELDS = [
    "response_id", "rater_id", "artifact_sha256", "response_contract_version",
    "components", "other_beats", "play_count", "play_limit", "started_at", "completed_at",
]
INTENT_CSV_FIELDS = (
    INTENT_EXPORT_FIELDS[:4]
    + [f"{field}_{part}" for field in INTENT_FIELDS for part in ("recall", "certainty", "could_not_tell")]
    + INTENT_EXPORT_FIELDS[5:]
)


def export_intent_responses(db, format_name: str = "json") -> tuple[bytes, int]:
    """Serialize every Stage 1 response deterministically for the freeze.

    The same database always yields the same bytes, so the freeze SHA-256 can
    be recomputed by anyone holding the export.
    """
    rows = [dict(row) for row in db.execute(
        "SELECT " + ", ".join(INTENT_EXPORT_FIELDS)
        + " FROM intent_responses ORDER BY completed_at, response_id"
    )]
    for row in rows:
        unknown = row.keys() - set(INTENT_EXPORT_FIELDS)
        if unknown:
            raise ValueError(f"export contains unknown fields: {unknown}")
        row["components"] = json.loads(row["components"])
    if format_name == "json":
        body = json.dumps({
            "intent_response_contract_version": INTENT_RESPONSE_CONTRACT_VERSION,
            "responses": rows,
        }, indent=2, sort_keys=True) + "\n"
        return body.encode(), len(rows)
    if format_name == "csv":
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=INTENT_CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            flat = {key: row[key] for key in INTENT_EXPORT_FIELDS if key != "components"}
            for field in INTENT_FIELDS:
                for part in ("recall", "certainty", "could_not_tell"):
                    flat[f"{field}_{part}"] = row["components"][field][part]
            writer.writerow(flat)
        return stream.getvalue().encode(), len(rows)
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
