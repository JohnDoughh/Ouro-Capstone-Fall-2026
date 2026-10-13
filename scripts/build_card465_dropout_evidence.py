#!/usr/bin/env python3
"""Build the public-safe, deterministic evidence package for Sprint 3 card #465."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

EXPECTED_ARTIFACT_ID = "syn-tone-b"
EXPECTED_SHA256 = "9f4f1593b2b5c7f24495f9e1f12d55920cde80d8608916bbb5d70d72e8d10478"
EXPECTED_BYTES = 336044


def load_object(path: Path) -> dict:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return value


def require_artifact(record: dict, label: str) -> None:
    if record.get("artifact_id") != EXPECTED_ARTIFACT_ID:
        raise ValueError(f"{label} has the wrong artifact_id")
    if record.get("artifact_sha256") != EXPECTED_SHA256:
        raise ValueError(f"{label} has the wrong artifact_sha256")


def validate_human(annotation: dict) -> None:
    require_artifact(annotation, "human annotation")
    if annotation.get("confidence_scale") != "1-5" or type(annotation.get("confidence")) is not int:
        raise ValueError("human confidence must use the integer 1-5 scale")
    if not 1 <= annotation["confidence"] <= 5:
        raise ValueError("human confidence is outside the 1-5 scale")
    if type(annotation.get("severity")) is not int or not 0 <= annotation["severity"] <= 3:
        raise ValueError("human severity is outside the 0-3 scale")
    if not annotation.get("defect_timestamps"):
        raise ValueError("human annotation must preserve a defect timestamp")
    if annotation.get("verdict") not in {"PASS", "HOLD", "UNSURE"}:
        raise ValueError("human annotation has an unsupported verdict")


def validate_simulated(output: dict) -> None:
    require_artifact(output, "simulated evaluator output")
    if output.get("provenance") != "simulated-test-only":
        raise ValueError("evaluator output must remain explicitly simulated")
    if output.get("verdict") not in {"PASS", "HOLD"}:
        raise ValueError("simulated evaluator output has an unsupported verdict")
    confidence = output.get("confidence")
    if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        raise ValueError("simulated evaluator confidence must be between 0 and 1")


def build(package_root: Path, artifact: Path, output_dir: Path) -> None:
    blob = artifact.read_bytes()
    digest = hashlib.sha256(blob).hexdigest()
    if digest != EXPECTED_SHA256 or len(blob) != EXPECTED_BYTES:
        raise ValueError("dropout.wav does not match the pinned artifact identity")

    annotation = load_object(package_root / "human_annotation.json")
    evaluator = load_object(package_root / "simulated_evaluator_output.json")
    validate_human(annotation)
    validate_simulated(evaluator)

    comparison = {
        "artifact_id": EXPECTED_ARTIFACT_ID,
        "artifact_sha256": EXPECTED_SHA256,
        "comparison_version": "1.0.0",
        "human_annotation_id": annotation["annotation_id"],
        "human_verdict": annotation["verdict"],
        "simulated_evaluator_alias": evaluator["evaluator_alias"],
        "simulated_evaluator_verdict": evaluator["verdict"],
        "verdict_match": annotation["verdict"] == evaluator["verdict"],
        "synthetic_demo": True,
        "disclaimer": "Synthetic pipeline demonstration; not an Ouro performance claim or research finding."
    }
    export = {
        "package_version": "1.0.0",
        "artifact": {
            "artifact_id": EXPECTED_ARTIFACT_ID,
            "artifact_sha256": EXPECTED_SHA256,
            "byte_length": EXPECTED_BYTES,
            "relative_path": "../public_audio/dropout.wav"
        },
        "human_annotation": annotation,
        "simulated_evaluator_output": evaluator,
        "comparison": comparison
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    comparison_path = output_dir / "comparison.json"
    export_path = output_dir / "dropout-evidence-package.json"
    comparison_path.write_text(json.dumps(comparison, indent=2, sort_keys=True) + "\n")
    export_path.write_text(json.dumps(export, indent=2, sort_keys=True) + "\n")
    checksums = []
    for path in (comparison_path, export_path):
        checksums.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}")
    (output_dir / "SHA256SUMS").write_text("\n".join(checksums) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, default=Path("data/card465_dropout_evidence"))
    parser.add_argument("--artifact", type=Path, default=Path("data/public_audio/dropout.wav"))
    parser.add_argument("--out", type=Path, default=Path("data/card465_dropout_evidence/exports"))
    args = parser.parse_args()
    build(args.package_root, args.artifact, args.out)
    print(f"wrote reproducible card #465 evidence to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
