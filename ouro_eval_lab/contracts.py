from __future__ import annotations

import re
from datetime import datetime
from typing import Any

CONTRACT_VERSION = "1.0.0"
ANNOTATION_CONTRACT_VERSION = "2.1.0"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MODALITIES = {"image", "audio", "video", "text"}
SPLITS = {"development", "calibration", "holdout"}
EVALUATOR_VERDICTS = {"PASS", "HOLD"}
HUMAN_VERDICTS = {"PASS", "HOLD", "UNSURE"}
HUMAN_REASON_CODES = {
    "visual_integrity", "audio_integrity", "temporal_integrity", "intent_integrity",
}
NATIVE_AVC_VERSION = "2.0.0-proposed.2"
NATIVE_AVC_PREVIOUS_VERSION = "2.0.0-proposed.1"
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
# Team C intent study. Both contracts are separate from annotation 2.1.0.
# Record 2.0.0 follows the committed envelope of the sealed sponsor records
# (docs/DATA_CONTRACT.md, "Intent fidelity"); the originals are never rewritten.
INTENT_CONTRACT_VERSION = "2.0.0"
INTENT_RESPONSE_CONTRACT_VERSION = "1.0.0"
INTENT_FIELDS = (
    "audience", "problem", "product", "key_benefit", "support", "call_to_action", "tone",
)
INTENT_DELIVERY_CODES = {
    "explicit_text", "implied", "visual_only", "partially_delivered",
    "omitted_in_edit", "not_intended",
}
INTENT_RECORD_KEYS = {
    "artifact_id", "delivery", "delivery_codes", "fictional", "frozen_at", "intended",
    "note", "record_type", "relative_path", "salt", "schema",
}
INTENT_TEXT_MAX = 300
INTENT_LABEL_MAX = 80
INTENT_NOTE_MAX = 500
INTENT_RECALL_MAX = 300
INTENT_OTHER_BEATS_MAX = 500
INTENT_MAX_PLAY_COUNT = 20
_ARTIFACT_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,80}")
_SALT_RE = re.compile(r"[A-Za-z0-9+/=_-]{1,128}")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
# Digit boundaries rather than \b, so "rater_3055550100" is caught too.
_PHONE_RE = re.compile(r"(?:\+\d[\d\s().-]{7,}\d)|(?:(?<!\d)\d{3}[\s.-]?\d{3}[\s.-]?\d{4}(?!\d))")
_URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)


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
    if not isinstance(record, dict):
        raise ContractError("native AVC output must be one JSON object")
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
    string_fields = {
        "schema_version", "audience", "provenance", "evaluator_alias", "evaluated_at",
        "media_sha256", "delivery_decision", "coverage", "defect_assessment",
        "probability_status", "probability_reason",
    }
    for field in sorted(string_fields):
        if not isinstance(record[field], str):
            raise ContractError(f"native AVC {field} must be a string")
    if record["schema_version"] not in {NATIVE_AVC_PREVIOUS_VERSION, NATIVE_AVC_VERSION}:
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
    if type(record["media_bytes"]) is not int or record["media_bytes"] <= 0:
        raise ContractError("native AVC media_bytes must be a positive integer")
    if record["delivery_decision"] not in NATIVE_AVC_DECISIONS:
        raise ContractError("native AVC delivery_decision must be approve, hold, or reject")
    if record["coverage"] not in {"complete", "incomplete"}:
        raise ContractError("native AVC coverage must be complete or incomplete")
    modalities = record["modalities"]
    if not isinstance(modalities, dict) or set(modalities) != NATIVE_AVC_MODALITIES:
        raise ContractError("native AVC modalities must contain exactly the five public modality names")
    if any(not isinstance(value, str) or value not in NATIVE_AVC_MODALITY_STATES
           for value in modalities.values()):
        raise ContractError("native AVC modality states must be covered, failed, or inconclusive")
    allowed_assessments = {"unassessed", "inconclusive"}
    if record["schema_version"] == NATIVE_AVC_VERSION:
        allowed_assessments.add("detected_failure")
    if record["defect_assessment"] not in allowed_assessments:
        raise ContractError("native AVC defect_assessment is unsupported for this version")
    if record["coverage"] == "complete" and "inconclusive" in modalities.values():
        raise ContractError("complete native AVC coverage cannot contain inconclusive modalities")
    failed = "failed" in modalities.values()
    if record["schema_version"] == NATIVE_AVC_VERSION and failed:
        expected_assessment = "detected_failure"
        if record["delivery_decision"] == "approve":
            raise ContractError("native AVC failed modality cannot have approve delivery decision")
    else:
        expected_assessment = "inconclusive" if record["coverage"] == "incomplete" else "unassessed"
    if record["defect_assessment"] != expected_assessment:
        raise ContractError("native AVC defect_assessment contradicts modality failure or coverage")
    if record["probability"] is not None or record["probability_status"] != "unavailable":
        raise ContractError("native AVC probability must remain null/unavailable")
    if record["probability_reason"] != "PROBABILITY_NOT_REPORTED":
        raise ContractError("native AVC probability reason must be PROBABILITY_NOT_REPORTED")
    codes = record["evidence_codes"]
    if not isinstance(codes, list) or not all(isinstance(code, str) for code in codes):
        raise ContractError("native AVC evidence_codes must be a string list")
    if not 4 <= len(codes) <= 5 or len(set(codes)) != len(codes):
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
    allowed = {"verdict", "confidence", "severity", "defect_timestamps", "reason_codes", "note"}
    unknown = sorted(record.keys() - allowed)
    if unknown:
        raise ContractError(f"annotation contains unknown fields: {', '.join(unknown)}")
    _require(record, {"verdict", "confidence", "severity", "reason_codes"}, "annotation")
    if record["verdict"] not in HUMAN_VERDICTS:
        raise ContractError("annotation verdict must be PASS, HOLD, or UNSURE")
    if type(record["confidence"]) is not int or not 1 <= record["confidence"] <= 5:
        raise ContractError("annotation confidence must be an integer from 1 to 5")
    if type(record["severity"]) is not int or not 0 <= record["severity"] <= 3:
        raise ContractError("annotation severity must be an integer from 0 to 3")
    if "defect_timestamps" in record and (
        not isinstance(record["defect_timestamps"], str) or len(record["defect_timestamps"]) > 240
    ):
        raise ContractError("defect_timestamps must be a string of at most 240 characters")
    if not isinstance(record["reason_codes"], list) or not all(isinstance(x, str) for x in record["reason_codes"]):
        raise ContractError("reason_codes must be a string list")
    if any(code not in HUMAN_REASON_CODES for code in record["reason_codes"]):
        raise ContractError("reason_codes contain an unsupported code")
    if len(set(record["reason_codes"])) != len(record["reason_codes"]):
        raise ContractError("reason_codes must be unique")
    if len(str(record.get("note", ""))) > 500:
        raise ContractError("note must be at most 500 characters")


def looks_like_phone_number(text: str) -> bool:
    return bool(_PHONE_RE.search(text))


def _contains_contact_info(text: str) -> bool:
    return bool(_EMAIL_RE.search(text) or looks_like_phone_number(text))


def _validate_record_text(text: Any, context: str, limit: int, required: bool = True) -> None:
    if not isinstance(text, str) or len(text) > limit:
        raise ContractError(f"{context} must be a string of at most {limit} characters")
    if required and not text.strip():
        raise ContractError(f"{context} must not be empty")
    if _URL_RE.search(text) or _contains_contact_info(text):
        raise ContractError(f"{context} must not contain URLs or contact details")


def _component_map(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != set(INTENT_FIELDS):
        raise ContractError(f"{context} must contain exactly: {', '.join(INTENT_FIELDS)}")
    return value


def validate_intent_record(record: dict[str, Any]) -> None:
    """Validate one revealed intent record in its committed envelope (2.0.0).

    The allow-list is strict on purpose: an unexpected key may be a private
    field (prompt, campaign, customer) and must stop the reveal, not be dropped.
    Errors name keys, never values, so the custodian can run this check on the
    sealed records and share the output without disclosing any intent.
    """
    if not isinstance(record, dict):
        raise ContractError("intent record must be one JSON object")
    _require(record, INTENT_RECORD_KEYS, "intent record")
    unknown = sorted(record.keys() - INTENT_RECORD_KEYS)
    if unknown:
        raise ContractError(f"intent record contains forbidden/unknown fields: {', '.join(unknown)}")
    if record["fictional"] is not True:
        raise ContractError("public scaffold accepts fictional intent records only")
    if not isinstance(record["artifact_id"], str) or not _ARTIFACT_ID_RE.fullmatch(record["artifact_id"]):
        raise ContractError("intent record artifact_id must be 1-80 letters, numbers, - or _")
    path = record["relative_path"]
    if not isinstance(path, str) or not path or "/" in path or "\\" in path or path in {".", ".."}:
        raise ContractError("intent record relative_path must be a bare file name")
    if not isinstance(record["salt"], str) or not _SALT_RE.fullmatch(record["salt"]):
        raise ContractError("intent record salt must be 1-128 URL-safe or base64 characters")
    for field in ("schema", "record_type"):
        _validate_record_text(record[field], f"intent record {field}", INTENT_LABEL_MAX)
    if not isinstance(record["frozen_at"], str):
        raise ContractError("intent record frozen_at must be an ISO-8601 timestamp")
    _utc(record["frozen_at"], "intent record frozen_at")
    _validate_record_text(record["note"], "intent record note", INTENT_NOTE_MAX, required=False)
    codes = record["delivery_codes"]
    if (not isinstance(codes, list) or not codes
            or any(not isinstance(code, str) or code not in INTENT_DELIVERY_CODES for code in codes)
            or len(set(codes)) != len(codes)):
        raise ContractError("intent record delivery_codes must be unique controlled delivery codes")
    intended = _component_map(record["intended"], "intent record intended")
    delivery = _component_map(record["delivery"], "intent record delivery")
    for field in INTENT_FIELDS:
        code = delivery[field]
        if not isinstance(code, str) or code not in codes:
            raise ContractError(f"intent record delivery.{field} is not one of the record's delivery_codes")
        # omitted_in_edit was intended, so only not_intended may leave the text empty.
        _validate_record_text(
            intended[field], f"intent record intended.{field}", INTENT_TEXT_MAX,
            required=code != "not_intended",
        )


def intent_coding_units(record: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Derive the per-component coding view of a verified record.

    Call only after the commitment check and validate_intent_record. The view
    is derived, never written back: the committed bytes stay the record.
    """
    return {
        field: {"text": record["intended"][field], "delivery": record["delivery"][field]}
        for field in INTENT_FIELDS
    }


def validate_intent_response_payload(record: dict[str, Any], play_limit: int | None = None) -> None:
    """Validate one Stage 1 viewer response (intent response contract 1.0.0)."""
    if not isinstance(record, dict):
        raise ContractError("intent response must be one JSON object")
    allowed = {"components", "other_beats", "play_count"}
    unknown = sorted(record.keys() - allowed)
    if unknown:
        raise ContractError(f"intent response contains unknown fields: {', '.join(unknown)}")
    _require(record, {"components", "play_count"}, "intent response")
    components = record["components"]
    if not isinstance(components, dict) or set(components) != set(INTENT_FIELDS):
        raise ContractError(f"components must contain exactly: {', '.join(INTENT_FIELDS)}")
    for field in INTENT_FIELDS:
        item = components[field]
        if not isinstance(item, dict) or set(item) != {"recall", "certainty", "could_not_tell"}:
            raise ContractError(f"{field} must contain exactly recall, certainty and could_not_tell")
        recall, certainty = item["recall"], item["certainty"]
        if type(item["could_not_tell"]) is not bool:
            raise ContractError(f"{field} could_not_tell must be true or false")
        if not isinstance(recall, str) or len(recall) > INTENT_RECALL_MAX:
            raise ContractError(f"{field} recall must be a string of at most {INTENT_RECALL_MAX} characters")
        if item["could_not_tell"]:
            if recall.strip() or certainty is not None:
                raise ContractError(f"{field} marked could not tell must have no recall and no certainty")
        else:
            if not recall.strip():
                raise ContractError(f"{field} recall is required unless could not tell is marked")
            if type(certainty) is not int or not 1 <= certainty <= 5:
                raise ContractError(f"{field} certainty must be an integer from 1 to 5")
        if _contains_contact_info(recall):
            raise ContractError(f"{field} recall must not contain contact details")
    other = record.get("other_beats", "")
    if not isinstance(other, str) or len(other) > INTENT_OTHER_BEATS_MAX:
        raise ContractError(f"other_beats must be a string of at most {INTENT_OTHER_BEATS_MAX} characters")
    if _contains_contact_info(other):
        raise ContractError("other_beats must not contain contact details")
    plays = record["play_count"]
    if type(plays) is not int or not 0 <= plays <= INTENT_MAX_PLAY_COUNT:
        raise ContractError(f"play_count must be an integer from 0 to {INTENT_MAX_PLAY_COUNT}")
    if play_limit is not None and plays > play_limit:
        raise ContractError(f"play_count exceeds the play limit of {play_limit}")


def normalize_intent_response(record: dict[str, Any]) -> dict[str, Any]:
    """Return the stored form of a validated response: trimmed text, fixed keys."""
    return {
        "components": {
            field: {
                "recall": record["components"][field]["recall"].strip(),
                "certainty": record["components"][field]["certainty"],
                "could_not_tell": record["components"][field]["could_not_tell"],
            }
            for field in INTENT_FIELDS
        },
        "other_beats": record.get("other_beats", "").strip(),
        "play_count": record["play_count"],
    }
