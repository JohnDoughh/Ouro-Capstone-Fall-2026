from __future__ import annotations

import re
from datetime import datetime
from typing import Any

CONTRACT_VERSION = "1.0.0"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MODALITIES = {"image", "audio", "video", "text"}
SPLITS = {"development", "calibration", "holdout"}
EVALUATOR_VERDICTS = {"PASS", "HOLD"}
HUMAN_VERDICTS = {"PASS", "HOLD", "UNSURE"}
NATIVE_AVC_VERSION = "2.0.0-proposed.1"
NATIVE_AVC_DECISIONS = {"approve", "hold", "reject"}
NATIVE_AVC_PROVENANCE = {"canonical-approved-synthetic", "simulated-test-only"}
NATIVE_AVC_MODALITIES = {
    "signal_scan", "transcription", "audio_perceptual", "video_motion", "audiovisual_sync",
}
NATIVE_AVC_MODALITY_STATES = {"covered", "failed", "inconclusive"}
NATIVE_AVC_EVIDENCE_CODES = {
    "EXACT_BYTES_VERIFIED", "CANONICAL_RECORD_BOUND", "COMPLETED_JOB_BOUND",
    "COVERAGE_INCOMPLETE", "DEFECT_MAPPING_UNAVAILABLE",
}


class ContractError(ValueError):
    pass


def _require(record: dict[str, Any], fields: set[str], context: str) -> None:
    missing = sorted(fields - record.keys())
    if missing:
        raise ContractError(f"{context} missing fields: {', '.join(missing)}")


def _utc(value: str, field: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError) as exc:
        raise ContractError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ContractError(f"{field} must include a timezone")


def validate_artifact(record: dict[str, Any]) -> None:
    required = {
        "artifact_id", "relative_path", "sha256", "byte_length", "mime_type",
        "modality", "split", "defect_family", "defect_present", "synthetic",
    }
    _require(record, required, "artifact")
    if not SHA256_RE.fullmatch(record["sha256"]):
        raise ContractError("artifact sha256 must be 64 lowercase hex characters")
    if record["modality"] not in MODALITIES:
        raise ContractError(f"unsupported modality: {record['modality']}")
    if record["split"] not in SPLITS:
        raise ContractError(f"unsupported split: {record['split']}")
    if not isinstance(record["defect_present"], bool):
        raise ContractError("defect_present must be boolean")
    if record["synthetic"] is not True:
        raise ContractError("public scaffold accepts synthetic artifacts only")
    if not isinstance(record["byte_length"], int) or record["byte_length"] < 0:
        raise ContractError("byte_length must be a nonnegative integer")
    path = record["relative_path"]
    if path.startswith(("/", "\\")) or ".." in path.replace("\\", "/").split("/"):
        raise ContractError("relative_path must remain inside the fixture root")


def validate_manifest(record: dict[str, Any]) -> None:
    _require(record, {"contract_version", "benchmark_id", "seed", "created_at", "artifacts"}, "manifest")
    if record["contract_version"] != CONTRACT_VERSION:
        raise ContractError(f"unsupported contract version: {record['contract_version']}")
    _utc(record["created_at"], "created_at")
    if not isinstance(record["seed"], int):
        raise ContractError("seed must be an integer")
    if not isinstance(record["artifacts"], list) or not record["artifacts"]:
        raise ContractError("artifacts must be a nonempty list")
    seen_ids: set[str] = set()
    seen_hashes: set[str] = set()
    for artifact in record["artifacts"]:
        validate_artifact(artifact)
        if artifact["artifact_id"] in seen_ids:
            raise ContractError(f"duplicate artifact_id: {artifact['artifact_id']}")
        if artifact["sha256"] in seen_hashes:
            raise ContractError(f"duplicate artifact sha256: {artifact['sha256']}")
        seen_ids.add(artifact["artifact_id"])
        seen_hashes.add(artifact["sha256"])


def validate_evaluator_output(record: dict[str, Any]) -> None:
    allowed = {
        "artifact_sha256", "evaluator_alias", "verdict", "confidence",
        "evidence_codes", "evaluated_at", "contract_version",
    }
    _require(record, allowed, "evaluator output")
    unknown = sorted(record.keys() - allowed)
    if unknown:
        raise ContractError(f"evaluator output contains forbidden/unknown fields: {', '.join(unknown)}")
    if not SHA256_RE.fullmatch(record["artifact_sha256"]):
        raise ContractError("invalid evaluator artifact_sha256")
    if record["verdict"] not in EVALUATOR_VERDICTS:
        raise ContractError("evaluator verdict must be PASS or HOLD")
    if not isinstance(record["confidence"], (int, float)) or not 0 <= record["confidence"] <= 1:
        raise ContractError("confidence must be between 0 and 1")
    if not re.fullmatch(r"eval-[a-z0-9-]{1,40}", record["evaluator_alias"]):
        raise ContractError("evaluator_alias must be anonymous, such as eval-alpha")
    if record["contract_version"] != CONTRACT_VERSION:
        raise ContractError("unsupported evaluator contract version")
    if not isinstance(record["evidence_codes"], list) or not all(isinstance(x, str) for x in record["evidence_codes"]):
        raise ContractError("evidence_codes must be a string list")
    _utc(record["evaluated_at"], "evaluated_at")



def validate_native_avc_output(record: dict[str, Any]) -> None:
    """Validate the separately versioned native AVC inspection contract.

    This contract is intentionally NOT accepted by the v1 benchmark runner.
    Native delivery decisions are not binary defect labels and AVC does not
    report a calibrated final probability for this report version.
    """
    allowed = {
        "schema_version", "audience", "import_ready", "provenance", "evaluator_alias",
        "evaluated_at", "media_sha256", "media_bytes", "delivery_decision", "coverage",
        "modalities", "defect_assessment", "probability", "probability_status",
        "probability_reason", "evidence_codes",
    }
    _require(record, allowed, "native AVC output")
    unknown = sorted(record.keys() - allowed)
    if unknown:
        raise ContractError(f"native AVC output contains forbidden/unknown fields: {', '.join(unknown)}")
    if record["schema_version"] != NATIVE_AVC_VERSION:
        raise ContractError("unsupported native AVC schema version")
    if record["audience"] != "sponsor-review-only" or record["import_ready"] is not False:
        raise ContractError("native AVC output must remain sponsor-review-only and not import-ready")
    if record["provenance"] not in NATIVE_AVC_PROVENANCE:
        raise ContractError("unsupported native AVC provenance")
    if record["evaluator_alias"] != "evaluator-01":
        raise ContractError("native AVC evaluator alias must remain evaluator-01")
    _utc(record["evaluated_at"], "evaluated_at")
    if not SHA256_RE.fullmatch(record["media_sha256"]):
        raise ContractError("invalid native AVC media_sha256")
    if not isinstance(record["media_bytes"], int) or record["media_bytes"] <= 0:
        raise ContractError("native AVC media_bytes must be a positive integer")
    if record["delivery_decision"] not in NATIVE_AVC_DECISIONS:
        raise ContractError("native AVC delivery_decision must be approve, hold, or reject")
    if record["coverage"] not in {"complete", "incomplete"}:
        raise ContractError("native AVC coverage must be complete or incomplete")
    modalities = record["modalities"]
    if not isinstance(modalities, dict) or set(modalities) != NATIVE_AVC_MODALITIES:
        raise ContractError("native AVC modalities must contain exactly the five public modality names")
    if any(value not in NATIVE_AVC_MODALITY_STATES for value in modalities.values()):
        raise ContractError("native AVC modality states must be covered, failed, or inconclusive")
    if record["defect_assessment"] not in {"unassessed", "inconclusive"}:
        raise ContractError("native AVC defect_assessment must be unassessed or inconclusive")
    if record["probability"] is not None or record["probability_status"] != "unavailable":
        raise ContractError("native AVC probability must remain null/unavailable")
    if record["probability_reason"] != "PROBABILITY_NOT_REPORTED":
        raise ContractError("native AVC probability reason must be PROBABILITY_NOT_REPORTED")
    codes = record["evidence_codes"]
    if not isinstance(codes, list) or not 4 <= len(codes) <= 5 or len(set(codes)) != len(codes):
        raise ContractError("native AVC evidence_codes must contain four or five unique codes")
    if any(code not in NATIVE_AVC_EVIDENCE_CODES for code in codes):
        raise ContractError("native AVC evidence_codes contain an unsupported code")
    required_codes = {
        "EXACT_BYTES_VERIFIED", "CANONICAL_RECORD_BOUND", "COMPLETED_JOB_BOUND",
        "DEFECT_MAPPING_UNAVAILABLE",
    }
    if not required_codes.issubset(codes):
        raise ContractError("native AVC evidence_codes are missing required provenance codes")
    if record["coverage"] == "incomplete" and "COVERAGE_INCOMPLETE" not in codes:
        raise ContractError("incomplete native AVC coverage requires COVERAGE_INCOMPLETE")
    if record["coverage"] == "complete" and "COVERAGE_INCOMPLETE" in codes:
        raise ContractError("complete native AVC coverage cannot include COVERAGE_INCOMPLETE")


def validate_annotation_payload(record: dict[str, Any]) -> None:
    allowed = {"verdict", "confidence", "reason_codes", "note"}
    unknown = sorted(record.keys() - allowed)
    if unknown:
        raise ContractError(f"annotation contains unknown fields: {', '.join(unknown)}")
    _require(record, {"verdict", "confidence", "reason_codes"}, "annotation")
    if record["verdict"] not in HUMAN_VERDICTS:
        raise ContractError("annotation verdict must be PASS, HOLD, or UNSURE")
    if not isinstance(record["confidence"], (int, float)) or not 0 <= record["confidence"] <= 1:
        raise ContractError("annotation confidence must be between 0 and 1")
    if not isinstance(record["reason_codes"], list) or not all(isinstance(x, str) for x in record["reason_codes"]):
        raise ContractError("reason_codes must be a string list")
    if len(str(record.get("note", ""))) > 500:
        raise ContractError("note must be at most 500 characters")
