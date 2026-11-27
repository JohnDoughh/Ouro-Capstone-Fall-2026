"""Family 4 reference and timing check for a frozen Orbit response (card #870).

This is a separate, post-freeze report. It does not change ``cli compare`` or
its report, and it never writes to ``data/public_playable``. It reads the
manifest's hidden truth (``defect_present``) and the documented defect window,
so run it only after the saved response is frozen and never show the report to
someone who has not finished rating.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .contracts import HUMAN_VERDICTS
from .runner import load_json, verify_manifest

ORBIT_BENCHMARK_ID = "orbit-playable-synthetic-v1"
# Documented in data/public_playable/README.md: ORBIT TRAY reads ORBIT TRY
# during [2.500, 3.500) seconds of the defective clip only.
ORBIT_DEFECT_WINDOW_S = (2.5, 3.5)

FAMILY4_CHECK_NOTES = [
    "Separate from cli compare: this report does not change the comparison report or its hash.",
    "A missing reference on a blind response is expected, because the reference stays hidden during blind rating. It is not a failed rating.",
    "Timing overlap is not detection accuracy. It only says whether an entered timestamp touches the documented defect window.",
    "Timestamps are entered in whole seconds, so mm:ss covers that full second and mm:ss-mm:ss runs to the end of the last second.",
    "Uses the hidden defect window and truth from the manifest: run only after the response is frozen and never show this report to a rater.",
    "Responses are a teammate practice rating, not research data.",
]

_SHA256 = re.compile(r"[0-9a-f]{64}")
_TIME = r"\s*(?:(\d+):)?(\d{1,2}):(\d{2}(?:\.\d+)?)\s*"
_POINT = re.compile(rf"^{_TIME}$")
_RANGE = re.compile(rf"^{_TIME}[-–—]{_TIME}$")


def _seconds(hours: str | None, minutes: str, seconds: str) -> tuple[float, bool]:
    """Return (seconds, whole) where whole means no fractional part was typed."""
    if int(minutes) > 59 and hours is not None:
        raise ValueError("minutes out of range")
    whole = "." not in seconds
    if float(seconds) >= 60:
        raise ValueError("seconds out of range")
    return int(hours or 0) * 3600 + int(minutes) * 60 + float(seconds), whole


def parse_timestamps(text: object) -> list[tuple[float, float]] | None:
    """Parse reviewer-entered timestamps into half-open [start, end) intervals.

    Returns None when the text is empty or any segment cannot be parsed. A whole
    second ``mm:ss`` covers [s, s + 1); a range's whole-second end is inclusive.
    """
    if not isinstance(text, str) or not text.strip():
        return None
    intervals = []
    for segment in text.split(";"):
        if not segment.strip():
            return None
        try:
            ranged = _RANGE.match(segment)
            if ranged:
                start, _ = _seconds(*ranged.groups()[:3])
                end, end_whole = _seconds(*ranged.groups()[3:])
                if end < start:
                    return None
                intervals.append((start, end + 1 if end_whole else end))
                continue
            point = _POINT.match(segment)
            if not point:
                return None
            at, whole = _seconds(*point.groups())
            intervals.append((at, at + 1 if whole else at))
        except ValueError:
            return None
    return intervals


def _overlaps(intervals: list[tuple[float, float]], window: tuple[float, float]) -> bool:
    low, high = window
    for start, end in intervals:
        if start == end:  # an exact fractional instant
            if low <= start < high:
                return True
        elif start < high and end > low:
            return True
    return False


def read_approved_reference(reference_file: Path) -> str:
    """Read the approved reference digest and confirm the reference bytes match it."""
    parts = reference_file.read_text(encoding="utf-8").split()
    if len(parts) != 2 or not _SHA256.fullmatch(parts[0]):
        raise ValueError("reference digest file must be '<64 lowercase hex>  <file name>'")
    digest, name = parts
    image = reference_file.parent / name
    if Path(name).name != name or not image.is_file():
        raise ValueError(f"approved reference file is missing: {name}")
    if hashlib.sha256(image.read_bytes()).hexdigest() != digest:
        raise ValueError("approved reference bytes do not match the recorded digest")
    return digest


def family4_check(manifest_path: Path, responses_path: Path, reference_file: Path,
                  window: tuple[float, float] = ORBIT_DEFECT_WINDOW_S) -> dict:
    manifest = verify_manifest(manifest_path)["manifest"]
    if manifest["benchmark_id"] != ORBIT_BENCHMARK_ID:
        raise ValueError(f"family 4 check is scoped to {ORBIT_BENCHMARK_ID}")
    by_hash = {row["sha256"]: row for row in manifest["artifacts"]}
    approved = read_approved_reference(reference_file)

    responses = load_json(responses_path)
    if not isinstance(responses, dict) or not isinstance(responses.get("annotations"), list):
        raise ValueError("responses must be an object with an 'annotations' list")

    rows, skipped = [], 0
    for response in responses["annotations"]:
        if not isinstance(response, dict):
            raise ValueError("each response must be an object")
        digest = response.get("artifact_sha256")
        if digest not in by_hash:
            raise ValueError(f"response references unknown artifact hash: {digest}")
        verdict = response.get("verdict")
        if verdict not in HUMAN_VERDICTS:
            raise ValueError(f"invalid verdict in response: {verdict}")
        annotation_id = response.get("annotation_id")
        if not isinstance(annotation_id, str) or not annotation_id:
            raise ValueError("each response needs an annotation_id")
        if verdict != "HOLD":
            skipped += 1
            continue

        reference_id = response.get("reference_id")
        if reference_id in (None, ""):
            reference = "missing"
        elif reference_id == approved:
            reference = "match"
        else:
            reference = "mismatch"

        if not by_hash[digest]["defect_present"]:
            timing = "no_defect_window"
        else:
            intervals = parse_timestamps(response.get("defect_timestamps"))
            if intervals is None:
                timing = "unparsed"
            else:
                timing = "overlaps" if _overlaps(intervals, window) else "misses"

        rows.append({
            "annotation_id": annotation_id,
            "artifact_sha256": digest,
            "defect_timestamps": response.get("defect_timestamps"),
            "reference": reference,
            "reference_expected_missing": reference == "missing",
            "timing": timing,
        })

    rows.sort(key=lambda row: (row["artifact_sha256"], row["annotation_id"]))
    reference_counts = {name: 0 for name in ("match", "mismatch", "missing")}
    timing_counts = {name: 0 for name in ("overlaps", "misses", "unparsed", "no_defect_window")}
    for row in rows:
        reference_counts[row["reference"]] += 1
        timing_counts[row["timing"]] += 1

    return {
        "benchmark_id": manifest["benchmark_id"],
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "responses_sha256": hashlib.sha256(responses_path.read_bytes()).hexdigest(),
        "approved_reference_sha256": approved,
        "defect_window_s": list(window),
        "holds_checked": len(rows),
        "non_hold_rows_skipped": skipped,
        "reference_counts": reference_counts,
        "timing_counts": timing_counts,
        "rows": rows,
        "notes": FAMILY4_CHECK_NOTES,
    }
