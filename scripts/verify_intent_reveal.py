#!/usr/bin/env python3
"""Check revealed intent records against the pre-published SHA-256 commitments.

Run this only after every blinded viewer response has been recorded and
exported. It proves the revealed records are byte-identical to what was frozen
before viewing, that each record names the clip it claims to describe, and
that each record satisfies the intent-record contract. It only reads files;
`python -m ouro_eval_lab.cli reveal` runs the same checks and loads the records.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ouro_eval_lab.reveal import DEFAULT_DIR, read_commitments, verify  # noqa: E402,F401


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--records", type=Path, required=True, help="directory holding the revealed *.intent.json files")
    parser.add_argument("--commitments", type=Path, default=DEFAULT_DIR / "intent_commitments.sha256")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_DIR / "manifest.json")
    parser.add_argument(
        "--skip-schema", action="store_true",
        help="check commitments only, without the intent-record contract",
    )
    args = parser.parse_args()
    problems = verify(args.commitments, args.records, args.manifest, schema=not args.skip_schema)
    for problem in problems:
        print(f"FAIL {problem}")
    if not problems:
        checked = "match their commitments" + ("" if args.skip_schema else " and the intent-record contract")
        print(f"OK {len(read_commitments(args.commitments))} revealed intent records {checked}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
