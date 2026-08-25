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
