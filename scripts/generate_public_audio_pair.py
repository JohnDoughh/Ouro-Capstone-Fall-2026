#!/usr/bin/env python3
"""Generate the public-safe synthetic audio pair in data/public_audio.

The output is byte-reproducible on any platform: it uses only integer
arithmetic (no floating-point sine), the standard-library ``wave`` module and
fixed parameters. Running this script again must produce files whose SHA-256
digests equal the ones pinned in ``data/public_audio/manifest.json``.

The pair is a loading/playback practice fixture. It is not Ouro media, not an
AVC input or finding, not human research evidence, and not any team's own
dropout example.
"""
from __future__ import annotations

import argparse
import hashlib
import struct
import wave
from pathlib import Path

RATE = 16_000  # samples per second, mono, 16-bit PCM
SECONDS_NUM, SECONDS_DEN = 21, 2  # 10.5 seconds
TOTAL = RATE * SECONDS_NUM // SECONDS_DEN  # 168_000 samples
AMPLITUDE = 8_000  # peak about -12.3 dBFS: clearly audible at normal volume
SEGMENT = RATE // 2  # alternate the pitch every 0.5 s
PERIODS = (40, 32)  # 400 Hz and 500 Hz triangle waves; both divide SEGMENT
FADE = RATE // 100  # 10 ms fade in/out avoids clicks at the file edges
DROPOUT_START = 4 * RATE  # 4.000 s
DROPOUT_END = 5 * RATE  # 5.000 s (exclusive), exactly 1.000 s of silence

DEFAULT_OUT = Path(__file__).resolve().parents[1] / "data" / "public_audio"


def _triangle(n: int, period: int) -> int:
    phase = n % period
    half = period // 2
    if phase < half:
        return -AMPLITUDE + (4 * AMPLITUDE * phase) // period
    return 3 * AMPLITUDE - (4 * AMPLITUDE * phase) // period


def samples(dropout: bool) -> list[int]:
    out = []
    for n in range(TOTAL):
        period = PERIODS[(n // SEGMENT) % len(PERIODS)]
        value = _triangle(n, period)
        if n < FADE:
            value = value * n // FADE
        elif n >= TOTAL - FADE:
            value = value * (TOTAL - 1 - n) // FADE
        if dropout and DROPOUT_START <= n < DROPOUT_END:
            value = 0
        out.append(value)
    return out


def write(path: Path, dropout: bool) -> str:
    frames = b"".join(struct.pack("<h", value) for value in samples(dropout))
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(RATE)
        stream.writeframes(frames)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for name, dropout in (("clean.wav", False), ("dropout.wav", True)):
        digest = write(args.out / name, dropout)
        print(f"{digest}  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
