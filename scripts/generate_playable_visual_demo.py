#!/usr/bin/env python3
"""Produce fictional, playable visual fixtures without contacting Ouro or a provider.

Requires Pillow and FFmpeg locally. The committed MP4s can be used without either.
This is an independent public lab demonstration, not an AVC input or result.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import subprocess
import tempfile
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FPS = 12
SECONDS = 8
RATE = 16000


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frame(second: float, defect: bool) -> Image.Image:
    im = Image.new("RGB", (640, 360), "#141c2b")
    d = ImageDraw.Draw(im)
    heading = ImageFont.truetype(FONT, 34)
    small = ImageFont.truetype(FONT, 22)
    if second < 2:
        d.text((66, 52), "Your desk gets messy.", font=heading, fill="#ffffff")
        for i in range(7):
            d.rounded_rectangle((90 + i * 64, 198 + (i % 2) * 20,
                                 132 + i * 64, 233 + (i % 2) * 20),
                                radius=6, fill="#e6aa75")
    elif second < 4:
        d.text((64, 52), "Meet a fictional desk tray.", font=heading, fill="#ffffff")
        d.rounded_rectangle((130, 143, 510, 287), radius=24, fill="#45bea7")
        d.rounded_rectangle((145, 163, 495, 267), radius=12, fill="#15384a")
        # Exactly one label defect from 2.5 through 3.5 seconds; the
        # positioning, canvas and every other frame are identical.
        label = "ORBIT TRY" if defect and 2.5 <= second < 3.5 else "ORBIT TRAY"
        d.text((236, 201), label, font=small, fill="#ffffff")
    elif second < 6:
        d.text((62, 52), "Keep small items in one place.", font=heading, fill="#ffffff")
        d.rounded_rectangle((130, 143, 510, 287), radius=24, fill="#45bea7")
        d.ellipse((230, 175, 270, 215), fill="#e6aa75")
        d.ellipse((300, 185, 340, 225), fill="#e6aa75")
    else:
        d.text((65, 74), "Explore Orbit Tray", font=heading, fill="#ffffff")
        d.text((67, 152), "Fictional demonstration", font=small, fill="#aabaca")
    d.text((15, 333), "SYNTHETIC RESEARCH FIXTURE", font=ImageFont.truetype(FONT, 12), fill="#aabaca")
    return im


def tone(path: Path) -> None:
    # Low-level, nonverbal synthetic audio; this cannot evaluate speech,
    # captions, pronunciation, lip-sync, or any natural-language intent.
    with wave.open(str(path), "wb") as wav:
        wav.setparams((1, 2, RATE, 0, "NONE", "not compressed"))
        for n in range(SECONDS * RATE):
            t = n / RATE
            active = 0.1 <= (t % 2) < 0.35
            value = int(700 * math.sin(2 * math.pi * 440 * t)) if active else 0
            wav.writeframesraw(struct.pack("<h", value))


def render(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ouro-public-fixture-") as temp:
        root = Path(temp)
        tone(root / "tone.wav")
        for defect, name in [(False, "clean.mp4"), (True, "label_defect.mp4")]:
            for number in range(FPS * SECONDS):
                frame(number / FPS, defect).save(root / f"frame_{number:03d}.png")
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-framerate", str(FPS),
                "-i", str(root / "frame_%03d.png"), "-i", str(root / "tone.wav"),
                "-t", str(SECONDS), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-preset", "medium", "-crf", "22", "-threads", "1", "-c:a", "aac",
                "-b:a", "64k", "-map_metadata", "-1", "-movflags", "+faststart", str(out / name),
            ], check=True)
        frame(2.0, False).save(out / "fictional_reference.png")

    rows = []
    for filename, present in [("clean.mp4", False), ("label_defect.mp4", True)]:
        p = out / filename
        rows.append({
            "artifact_id": "syn-orbit-label-defect" if present else "syn-orbit-clean",
            "relative_path": filename, "sha256": sha(p), "byte_length": p.stat().st_size,
            "mime_type": "video/mp4", "modality": "video", "split": "development",
            "defect_family": "fictional_product_label_mismatch", "defect_present": present,
            "synthetic": True,
        })
    manifest = {
        "contract_version": "1.0.0", "benchmark_id": "orbit-playable-synthetic-v1",
        "seed": 20260923, "created_at": "2026-09-23T00:00:00Z", "artifacts": rows,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    (out / "reference.sha256").write_text(sha(out / "fictional_reference.png") + "  fictional_reference.png\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    render(parser.parse_args().out)
