from __future__ import annotations

import hashlib
import json
import math
import random
import struct
import wave
from datetime import datetime, timezone
from pathlib import Path

from .contracts import CONTRACT_VERSION


def _write_wave(path: Path, defect: bool, index: int) -> None:
    rate = 8000
    frames = bytearray()
    fixture_index = index
    for sample_index in range(rate // 4):
        signal = 0.25 * math.sin(2 * math.pi * (420 + fixture_index * 10) * sample_index / rate)
        if defect and 750 <= sample_index < 820:
            signal = 0.95
        frames.extend(struct.pack("<h", int(signal * 32767)))
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(rate)
        stream.writeframes(frames)


def _content(modality: str, defect: bool, index: int) -> tuple[str, bytes]:
    label = "DEFECT" if defect else "CONTROL"
    if modality == "image":
        color = "#ff4d6d" if defect else "#41d6a3"
        body = f'''<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360"><rect width="640" height="360" fill="#121826"/><rect x="90" y="70" width="460" height="220" rx="24" fill="{color}"/><text x="320" y="190" text-anchor="middle" fill="#081018" font-family="sans-serif" font-size="42">SYNTHETIC {label} {index}</text></svg>'''
        return "image/svg+xml", body.encode()
    if modality == "text":
        body = f"Synthetic campaign card {index}. " + ("Call to action is missing." if defect else "Call to action: learn more.")
        return "text/plain", body.encode()
    if modality == "video":
        payload = {
            "synthetic": True,
            "kind": "frame-sequence-placeholder",
            "index": index,
            "frames": ["opening", "product", "closing" if not defect else "abrupt_cut"],
        }
        return "application/json", json.dumps(payload, sort_keys=True, indent=2).encode()
    raise ValueError(modality)


def generate(root: Path, seed: int = 20260825) -> tuple[Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    plan = [
        ("image", "visual_corruption"),
        ("audio", "audio_discontinuity"),
        ("video", "temporal_discontinuity"),
        ("text", "intent_omission"),
    ]
    artifacts = []
    outputs = []
    for modality, family in plan:
        for local_index in range(4):
            defect = local_index % 2 == 1
            artifact_id = f"syn-{modality}-{local_index + 1:02d}"
            suffix = {"image": ".svg", "audio": ".wav", "video": ".json", "text": ".txt"}[modality]
            path = root / f"{artifact_id}{suffix}"
            if modality == "audio":
                _write_wave(path, defect, local_index + 1)
                mime = "audio/wav"
            else:
                mime, content = _content(modality, defect, local_index + 1)
                path.write_bytes(content)
            blob = path.read_bytes()
            digest = hashlib.sha256(blob).hexdigest()
            split = ["development", "calibration", "holdout", "calibration"][local_index]
            artifacts.append({
                "artifact_id": artifact_id,
                "relative_path": path.name,
                "sha256": digest,
                "byte_length": len(blob),
                "mime_type": mime,
                "modality": modality,
                "split": split,
                "defect_family": family,
                "defect_present": defect,
                "synthetic": True,
            })
            # Seeded demo output: intentionally imperfect so failure analysis is exercised.
            correct = rng.random() > 0.18
            predicted_defect = defect if correct else not defect
            outputs.append({
                "artifact_sha256": digest,
                "evaluator_alias": "eval-alpha",
                "verdict": "HOLD" if predicted_defect else "PASS",
                "confidence": round(rng.uniform(0.56, 0.96), 3),
                "evidence_codes": [family],
                "evaluated_at": "2026-08-25T00:00:00Z",
                "contract_version": CONTRACT_VERSION,
            })
    created = datetime(2026, 8, 25, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    manifest = {
        "contract_version": CONTRACT_VERSION,
        "benchmark_id": f"synthetic-fixtures-{seed}",
        "seed": seed,
        "created_at": created,
        "artifacts": artifacts,
    }
    manifest_path = root / "manifest.json"
    outputs_path = root / "evaluator_outputs.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    outputs_path.write_text(json.dumps(outputs, indent=2, sort_keys=True) + "\n")
    return manifest_path, outputs_path
