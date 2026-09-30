#!/usr/bin/env python3
"""Render the fictional clean/seeded-defect visual pair in data/public_visual_pair.

Frames are drawn with the standard library only (integer geometry, no fonts,
no Pillow), so the source frames are byte-reproducible everywhere and tests can
inspect them without FFmpeg. FFmpeg is needed only to encode the MP4s; the
committed MP4s can be used without it.

The two clips tell the same wordless story about a fictional water bottle. One
clip carries a single seeded product-continuity defect that a rater can only
find by looking at the product across shots. Which clip that is, and what the
defect is, is recorded in seeded_truth.json and must stay away from raters.

This is a fictional public teaching fixture. It is not Ouro media, not an AVC
input or finding, and not human research evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import subprocess
from pathlib import Path

SEED = 20260930
WIDTH, HEIGHT = 640, 360
FPS = 12
SCENE_FRAMES = 3 * FPS  # four 3-second shots
SCENES = 4
FRAMES = SCENE_FRAMES * SCENES  # 144 frames, 12.000 s
RENDERER_VERSION = "1"

# The seeded defect: during the whole third shot the bottle shows two grip
# bands instead of three, re-spaced evenly over the same span so there is no
# obvious gap. Every other pixel of every frame is identical between clips.
DEFECT_SCENE = 2
DEFECT_FIRST_FRAME = DEFECT_SCENE * SCENE_FRAMES  # 72 -> 6.000 s
DEFECT_END_FRAME = DEFECT_FIRST_FRAME + SCENE_FRAMES  # 108 -> 9.000 s (exclusive)
CLEAN_BANDS, DEFECT_BANDS = 3, 2

DEFAULT_OUT = Path(__file__).resolve().parents[1] / "data" / "public_visual_pair"
BENCHMARK_ID = "fictional-visual-continuity-v1"
DEFECT_FAMILY = "product_visual_continuity"

Color = tuple[int, int, int]
BG_ROOM: Color = (29, 36, 51)
DESK: Color = (122, 86, 58)
DESK_EDGE: Color = (96, 66, 44)
LAMP: Color = (200, 196, 180)
LAMP_GLOW: Color = (245, 214, 140)
NOTEBOOK: Color = (70, 96, 150)
BG_HERO: Color = (38, 52, 70)
BG_HERO_LOW: Color = (48, 64, 84)
BAG: Color = (58, 58, 66)
BAG_FLAP: Color = (74, 74, 84)
BG_END: Color = (18, 60, 64)
DISC: Color = (30, 88, 92)
BOTTLE: Color = (43, 179, 163)
BOTTLE_SHADE: Color = (32, 150, 137)
HIGHLIGHT: Color = (120, 214, 202)
NECK: Color = (34, 140, 128)
CAP: Color = (236, 128, 52)
BAND: Color = (240, 244, 242)


class Canvas:
    def __init__(self, color: Color) -> None:
        self.pixels = bytearray(bytes(color) * (WIDTH * HEIGHT))

    def rect(self, x0: int, y0: int, x1: int, y1: int, color: Color) -> None:
        """Fill the half-open box [x0, x1) x [y0, y1), clipped to the frame."""
        x0, x1 = max(0, x0), min(WIDTH, x1)
        y0, y1 = max(0, y0), min(HEIGHT, y1)
        if x0 >= x1 or y0 >= y1:
            return
        run = bytes(color) * (x1 - x0)
        for y in range(y0, y1):
            start = (y * WIDTH + x0) * 3
            self.pixels[start:start + len(run)] = run

    def ellipse(self, cx: int, cy: int, rx: int, ry: int, color: Color) -> None:
        for dy in range(-ry, ry + 1):
            # Integer half-width of the ellipse row: rx * sqrt(1 - (dy/ry)^2).
            half = math.isqrt(rx * rx * (ry * ry - dy * dy) // (ry * ry))
            self.rect(cx - half, cy + dy, cx + half + 1, cy + dy + 1, color)


def lerp(a: int, b: int, t_num: int, t_den: int) -> int:
    return a + (b - a) * t_num // t_den


def bottle(canvas: Canvas, cx: int, base: int, scale_pct: int, bands: int) -> tuple[int, int, int, int]:
    """Draw the fictional bottle; return its bounding box (x0, y0, x1, y1)."""
    def s(value: int) -> int:
        return value * scale_pct // 100

    w, h = s(64), s(176)
    x0, y0, x1 = cx - w // 2, base - h, cx - w // 2 + w
    canvas.rect(x0, y0, x1, base, BOTTLE)
    canvas.rect(x1 - s(12), y0, x1, base, BOTTLE_SHADE)
    canvas.rect(x0 + s(10), y0 + s(14), x0 + s(18), y0 + s(70), HIGHLIGHT)
    neck_w, neck_h = s(36), s(14)
    canvas.rect(cx - neck_w // 2, y0 - neck_h, cx - neck_w // 2 + neck_w, y0, NECK)
    cap_w, cap_h = s(44), s(26)
    cap_y0 = y0 - neck_h - cap_h
    canvas.rect(cx - cap_w // 2, cap_y0, cx - cap_w // 2 + cap_w, y0 - neck_h, CAP)
    # Grip bands sit evenly inside the same vertical span whatever their count.
    span_top, span_bottom = y0 + h * 45 // 100, y0 + h * 82 // 100
    band_h = max(3, s(8))
    for i in range(bands):
        centre = span_top + (span_bottom - span_top) * (2 * i + 1) // (2 * bands)
        canvas.rect(x0, centre - band_h // 2, x1, centre - band_h // 2 + band_h, BAND)
    return (x0, cap_y0, x1, base)  # the cap is narrower than the body


def render_frame(index: int, defect: bool) -> tuple[bytes, tuple[int, int, int, int]]:
    """Return one RGB24 frame and the bottle's bounding box in that frame."""
    scene, step = divmod(index, SCENE_FRAMES)
    last = SCENE_FRAMES - 1
    bands = DEFECT_BANDS if defect and DEFECT_FIRST_FRAME <= index < DEFECT_END_FRAME else CLEAN_BANDS
    if scene == 0:  # wide desk shot, slow push in
        c = Canvas(BG_ROOM)
        c.rect(0, 262, WIDTH, HEIGHT, DESK)
        c.rect(0, 262, WIDTH, 270, DESK_EDGE)
        c.ellipse(150, 120, 46, 30, LAMP_GLOW)
        c.rect(144, 140, 156, 262, LAMP)
        c.rect(116, 254, 184, 262, LAMP)
        c.rect(236, 236, 356, 262, NOTEBOOK)
        box = bottle(c, 470, 262, lerp(66, 76, step, last), bands)
    elif scene == 1:  # close-up, bottle rises into frame
        c = Canvas(BG_HERO)
        c.rect(0, 250, WIDTH, HEIGHT, BG_HERO_LOW)
        box = bottle(c, 320, lerp(372, 344, step, last), 140, bands)
    elif scene == 2:  # packing shot, bottle slides toward an open bag
        c = Canvas(BG_ROOM)
        c.rect(0, 290, WIDTH, HEIGHT, DESK)
        c.rect(380, 150, 590, 300, BAG)
        c.rect(372, 136, 598, 158, BAG_FLAP)
        box = bottle(c, lerp(150, 300, step, last), 300, 100, bands)
    else:  # end card on a backdrop disc
        c = Canvas(BG_END)
        c.ellipse(320, 190, 132, 132, DISC)
        box = bottle(c, 320, 300, lerp(104, 112, step, last), bands)
    return bytes(c.pixels), box


def defective_clip() -> str:
    """Seeded choice of which file carries the defect, so order is no clue."""
    return random.Random(SEED).choice(["clip_a.mp4", "clip_b.mp4"])


def frames_digest(defect: bool) -> str:
    digest = hashlib.sha256()
    for index in range(FRAMES):
        digest.update(render_frame(index, defect)[0])
    return digest.hexdigest()


def encode(path: Path, defect: bool) -> None:
    process = subprocess.Popen([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{WIDTH}x{HEIGHT}", "-r", str(FPS), "-i", "-",
        "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "18",
        "-threads", "1", "-fflags", "+bitexact", "-flags:v", "+bitexact",
        "-map_metadata", "-1", "-movflags", "+faststart", str(path),
    ], stdin=subprocess.PIPE)
    assert process.stdin is not None
    for index in range(FRAMES):
        process.stdin.write(render_frame(index, defect)[0])
    process.stdin.close()
    if process.wait() != 0:
        raise SystemExit(f"ffmpeg failed for {path}")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ffmpeg_version() -> str:
    first = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, check=True).stdout.split("\n")[0]
    return first.split(" ")[2]


def render(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    bad = defective_clip()
    rows, digests = [], {}
    for name, suffix in (("clip_a.mp4", "a"), ("clip_b.mp4", "b")):
        defect = name == bad
        encode(out / name, defect)
        digests[name] = frames_digest(defect)
        rows.append({
            "artifact_id": f"syn-vis-{suffix}", "relative_path": name,
            "sha256": sha(out / name), "byte_length": (out / name).stat().st_size,
            "mime_type": "video/mp4", "modality": "video", "split": "development",
            "defect_family": DEFECT_FAMILY, "defect_present": defect, "synthetic": True,
        })
    manifest = {
        "contract_version": "1.0.0", "benchmark_id": BENCHMARK_ID, "seed": SEED,
        "created_at": "2026-09-30T00:00:00Z", "artifacts": rows,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    defective = next(row for row in rows if row["defect_present"])
    truth = {
        "benchmark_id": BENCHMARK_ID,
        "synthetic": True,
        "seed": SEED,
        "defective_artifact_id": defective["artifact_id"],
        "defective_sha256": defective["sha256"],
        "defect_family": DEFECT_FAMILY,
        "defect": (
            "During the whole third shot (the bottle sliding toward the bag), the bottle "
            f"shows {DEFECT_BANDS} white grip bands instead of the {CLEAN_BANDS} it shows in "
            "every other shot. The bands are re-spaced evenly, so there is no visible gap."
        ),
        "defect_window_seconds": [DEFECT_FIRST_FRAME / FPS, DEFECT_END_FRAME / FPS],
        "defect_window_frames": [DEFECT_FIRST_FRAME, DEFECT_END_FRAME],
        "window_is_half_open": True,
        "expected_timestamp_entry": "00:06-00:09",
        "source_frames": {
            "renderer_version": RENDERER_VERSION, "width": WIDTH, "height": HEIGHT,
            "fps": FPS, "frames": FRAMES, "pix_fmt": "rgb24",
            "sha256": digests,
        },
        "encoder": {"ffmpeg": ffmpeg_version(), "codec": "libx264", "crf": 18, "preset": "medium"},
    }
    (out / "seeded_truth.json").write_text(json.dumps(truth, indent=2, sort_keys=True) + "\n")
    for name in ("clip_a.mp4", "clip_b.mp4"):
        print(f"{sha(out / name)}  {name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    render(parser.parse_args().out)
