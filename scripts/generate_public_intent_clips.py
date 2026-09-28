#!/usr/bin/env python3
"""Render the four fictional intent-bearing clips in data/public_intent.

Requires FFmpeg with drawtext and the DejaVu Sans font. The committed MP4s can
be used without either. Only the on-screen storyboard lives here; the frozen
creator intent for each clip is held separately by the sponsor and published
only as a SHA-256 commitment (see data/public_intent/README.md).

These are fictional products and a synthetic tone. They are not Ouro media,
AVC inputs or findings, or human research evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import subprocess
import tempfile
import wave
from pathlib import Path

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FPS = 12
SCENE = 3  # seconds per scene
SCENES = 4
SECONDS = SCENE * SCENES
RATE = 16_000
AMPLITUDE = 4_000  # about -18 dBFS: clearly audible bed, no speech
PERIODS = (40, 36, 32, 30)  # 400, 444.4, 500, 533.3 Hz: one pitch per scene

DEFAULT_OUT = Path(__file__).resolve().parents[1] / "data" / "public_intent"

# (heading, subheading, shape) per 3-second scene. Shapes are simple
# placeholders: "dots" = scattered items, "box" = the product, "none".
STORYBOARDS: dict[str, list[tuple[str, str, str]]] = {
    "clip01.mp4": [
        ("Going away for a week?", "Your plants stay home.", "dots"),
        ("Drizzlet", "a fictional slow-drip plant spike", "box"),
        ("Waters one pot for up to 10 days", "Fill it, then push it into the soil", "box"),
        ("Try Drizzlet before your next trip", "Fictional demonstration", "none"),
    ],
    "clip02.mp4": [
        ("Open office.", "Phones. Chatter. Footsteps.", "dots"),
        ("Hushpane", "a fictional folding desk panel", "box"),
        ("Focus, finally.", "", "box"),
        ("Learn more about Hushpane", "Fictional demonstration", "none"),
    ],
    "clip03.mp4": [
        ("A button pops off at the airport.", "", "dots"),
        ("Stitchkin", "a fictional travel sewing kit", "box"),
        ("Needle, thread and 6 buttons", "in a card-sized case", "box"),
        ("Stitchkin", "Fictional demonstration", "none"),
    ],
    "clip04.mp4": [
        ("Crumbvac", "", "dots"),
        ("", "a fictional pocket desk vacuum", "box"),
        ("Clean desk in 10 seconds", "", "none"),
        ("Get Crumbvac", "Fictional demonstration", "none"),
    ],
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _triangle(n: int, period: int) -> int:
    phase = n % period
    if phase < period // 2:
        return -AMPLITUDE + (4 * AMPLITUDE * phase) // period
    return 3 * AMPLITUDE - (4 * AMPLITUDE * phase) // period


def tone_bed(path: Path) -> None:
    total = SECONDS * RATE
    fade = RATE // 100
    frames = bytearray()
    for n in range(total):
        value = _triangle(n, PERIODS[(n // (SCENE * RATE)) % len(PERIODS)])
        if n < fade:
            value = value * n // fade
        elif n >= total - fade:
            value = value * (total - 1 - n) // fade
        frames += struct.pack("<h", value)
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(RATE)
        stream.writeframes(bytes(frames))


def _filters(board: list[tuple[str, str, str]], temp: Path, stem: str) -> str:
    parts = []
    footer = temp / f"{stem}-footer.txt"
    footer.write_text("SYNTHETIC RESEARCH FIXTURE - FICTIONAL PRODUCT")
    for index, (heading, sub, shape) in enumerate(board):
        start, end = index * SCENE, (index + 1) * SCENE
        on = f"enable='between(t,{start},{end - 0.001})'"
        if shape == "dots":
            for i in range(7):
                x, y = 90 + i * 64, 198 + (i % 2) * 20
                parts.append(f"drawbox=x={x}:y={y}:w=42:h=35:color=0xe6aa75:t=fill:{on}")
        elif shape == "box":
            parts.append(f"drawbox=x=150:y=150:w=340:h=130:color=0x45bea7:t=fill:{on}")
            parts.append(f"drawbox=x=165:y=168:w=310:h=94:color=0x15384a:t=fill:{on}")
        for text, size, y, colour in ((heading, 30, 52, "white"), (sub, 20, 100, "0xaabaca")):
            if not text:
                continue
            file = temp / f"{stem}-{index}-{y}.txt"
            file.write_text(text)
            parts.append(
                f"drawtext=fontfile={FONT}:textfile={file}:fontsize={size}:fontcolor={colour}:"
                f"x=(w-text_w)/2:y={y}:{on}"
            )
    parts.append(f"drawtext=fontfile={FONT}:textfile={footer}:fontsize=12:fontcolor=0xaabaca:x=15:y=336")
    return ",".join(parts)


def render(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ouro-intent-fixture-") as directory:
        temp = Path(directory)
        tone_bed(temp / "bed.wav")
        for name, board in STORYBOARDS.items():
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", f"color=c=0x141c2b:s=640x360:r={FPS}:d={SECONDS}",
                "-i", str(temp / "bed.wav"),
                "-vf", _filters(board, temp, Path(name).stem),
                "-t", str(SECONDS), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-preset", "medium", "-crf", "22", "-threads", "1", "-c:a", "aac",
                "-b:a", "64k", "-map_metadata", "-1", "-fflags", "+bitexact",
                "-flags:v", "+bitexact", "-flags:a", "+bitexact",
                "-movflags", "+faststart", str(out / name),
            ], check=True)

    rows = []
    for index, name in enumerate(STORYBOARDS, start=1):
        path = out / name
        rows.append({
            "artifact_id": f"syn-intent-{index:02d}", "relative_path": name,
            "sha256": sha(path), "byte_length": path.stat().st_size,
            "mime_type": "video/mp4", "modality": "video", "split": "development",
            "defect_family": "none_seeded_intent_recovery_only", "defect_present": False,
            "synthetic": True,
        })
    manifest = {
        "contract_version": "1.0.0", "benchmark_id": "fictional-intent-clips-v1",
        "seed": 20260927, "created_at": "2026-09-27T00:00:00Z", "artifacts": rows,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    render(parser.parse_args().out)
