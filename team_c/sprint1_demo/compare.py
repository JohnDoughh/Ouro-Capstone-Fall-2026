#!/usr/bin/env python3
"""
Team C walking skeleton, Sprint 1.

Runs the smallest possible end-to-end path:
  fixture + intent manifest -> fictional viewer response -> simulated evaluator output
  -> per-beat comparison -> one-row-per-beat scoreboard (CSV)

This does NOT decide whether AVC is right. It only proves the five-step
path connects and produces a reproducible, inspectable artifact.

Usage:
    python3 compare.py
Output:
    scoreboard.csv (also printed to stdout)
"""

import csv
import hashlib
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent

FIXTURE_PATH = BASE / "fixtures" / "fixture_ad_001.md"
MANIFEST_PATH = BASE / "contracts" / "intent_manifest.json"
VIEWER_PATH = BASE / "annotations" / "viewer_response_001.json"
AVC_PATH = BASE / "evaluator_outputs" / "avc_output_001.json"
OUT_PATH = BASE / "scoreboard.csv"


def load(path):
    with open(path, "r") as f:
        return json.load(f)


def beat_recovered(beat_name, beat_manifest, viewer_beat):
    """
    Minimal, transparent recovery rule for the walking skeleton:
    a beat counts as recovered if the viewer's confidence is >= 3
    and they did not flag ambiguity, UNLESS the manifest expects
    'none' to be recovered (e.g. the deliberate proof gap), in which
    case recovery means the viewer correctly found nothing.
    This rule is intentionally simple and is flagged for the team's
    rubric work in later sprints. It is not a finding.
    """
    expected_none = beat_manifest.get("expected_recovery") == "none"
    if expected_none:
        said_nothing = "none" in viewer_beat["recovered_text"].lower() or \
                        "nothing" in viewer_beat["recovered_text"].lower() or \
                        "no " in viewer_beat["recovered_text"].lower()
        return said_nothing
    return viewer_beat["confidence"] >= 3 and not viewer_beat["ambiguity_flag"]


def main():
    manifest = load(MANIFEST_PATH)
    viewer = load(VIEWER_PATH)
    avc = load(AVC_PATH)

    # The manifest is frozen against one exact fixture. Refuse to run if the
    # fixture changed after the manifest was written.
    fixture_sha = hashlib.sha256(FIXTURE_PATH.read_bytes()).hexdigest()
    if fixture_sha != manifest["artifact_sha256"]:
        sys.exit(f"Fixture hash {fixture_sha} does not match the frozen manifest. Stopping.")

    if viewer.get("status") == "FICTIONAL_TEST_RESPONSE":
        print("NOTE: the viewer response is fictional test data, not a real participant.",
              file=sys.stderr)
    if avc.get("status") == "SYNTHETIC_PLACEHOLDER":
        print("NOTE: the evaluator output is simulated, not real AVC output.\n"
              "Results below are a workflow demonstration, not a research finding.\n",
              file=sys.stderr)

    rows = []
    for beat_name, beat_manifest in manifest["beats"].items():
        viewer_beat = viewer["responses"][beat_name]
        avc_beat = avc["beat_judgments"][beat_name]

        human_recovered = beat_recovered(beat_name, beat_manifest, viewer_beat)
        avc_pass = avc_beat["verdict"] == "PASS"

        # Does AVC's PASS/HOLD agree with whether a human actually recovered
        # the beat? This is the core Team C comparison, at its simplest form.
        agreement = (avc_pass and human_recovered) or \
                    (not avc_pass and not human_recovered)

        rows.append({
            "artifact_id": manifest["artifact_id"],
            "beat": beat_name,
            "viewer_confidence": viewer_beat["confidence"],
            "viewer_ambiguity_flag": viewer_beat["ambiguity_flag"],
            "human_recovered": human_recovered,
            "avc_verdict": avc_beat["verdict"],
            "avc_confidence": avc_beat["confidence"],
            "avc_human_agree": agreement,
        })

    with open(OUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {OUT_PATH.name}\n")
    for row in rows:
        print(row)


if __name__ == "__main__":
    main()
