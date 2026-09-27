#!/usr/bin/env python3
"""Check revealed intent records against the pre-published SHA-256 commitments.

Run this only after every blinded viewer response has been recorded and
exported. It proves the revealed records are byte-identical to what was frozen
before viewing, and that each record names the clip it claims to describe.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

DEFAULT_DIR = Path(__file__).resolve().parents[1] / "data" / "public_intent"


def read_commitments(path: Path) -> dict[str, str]:
    commitments = {}
    for line in path.read_text().splitlines():
        digest, _, name = line.partition("  ")
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest) or not name:
            raise ValueError(f"malformed commitment line: {line!r}")
        if "/" in name or "\\" in name or name in commitments:
            raise ValueError(f"invalid or duplicate record name: {name!r}")
        commitments[name] = digest
    return commitments


def verify(commitments_path: Path, records_dir: Path, manifest_path: Path) -> list[str]:
    commitments = read_commitments(commitments_path)
    artifacts = {a["relative_path"]: a["artifact_id"] for a in json.loads(manifest_path.read_text())["artifacts"]}
    problems = []
    expected = {Path(clip).stem + ".intent.json" for clip in artifacts}
    for name in sorted(expected - set(commitments)):
        problems.append(f"{name}: no commitment for a manifest clip")
    for name in sorted(set(commitments) - expected):
        problems.append(f"{name}: commitment for a clip not in the manifest")
    if not expected:
        problems.append("manifest lists no clips")
    for name, digest in commitments.items():
        record_path = records_dir / name
        if not record_path.is_file():
            problems.append(f"{name}: missing")
            continue
        body = record_path.read_bytes()
        if hashlib.sha256(body).hexdigest() != digest:
            problems.append(f"{name}: SHA-256 does not match the commitment")
            continue
        record = json.loads(body)
        clip = record.get("relative_path")
        if clip not in artifacts or artifacts[clip] != record.get("artifact_id"):
            problems.append(f"{name}: names a clip that is not in the manifest")
        elif name != Path(clip).stem + ".intent.json":
            problems.append(f"{name}: record name does not match its clip")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--records", type=Path, required=True, help="directory holding the revealed *.intent.json files")
    parser.add_argument("--commitments", type=Path, default=DEFAULT_DIR / "intent_commitments.sha256")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_DIR / "manifest.json")
    args = parser.parse_args()
    problems = verify(args.commitments, args.records, args.manifest)
    for problem in problems:
        print(f"FAIL {problem}")
    if not problems:
        print(f"OK {len(read_commitments(args.commitments))} revealed intent records match their commitments")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
