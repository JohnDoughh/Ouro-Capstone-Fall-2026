from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from .api import serve
from .contracts import validate_manifest
from .fixtures import generate
from .runner import (
    agreement_report, export_annotations, export_intent_responses, inspect_native_avc,
    load_json, run_benchmark, verify_manifest,
)
from .coding import DEFAULT_SHEET_SEED, CodingRefused, import_codes, issue_sheet
from .intent_metrics import (
    DEFAULT_SAMPLES as INTENT_SAMPLES, DEFAULT_SEED as INTENT_SEED, build_intent_report,
    render_intent_report,
)
from .reveal import DEFAULT_DIR as INTENT_DIR, RevealRefused, reveal
from .store import STUDIES, connect, ingest, initialize, record_intent_freeze, study_conflict


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def bootstrap_demo(root: Path, db_path: Path, seed: int) -> tuple[Path, Path, int]:
    """Create or verify the deterministic public demo and ingest it idempotently."""
    manifest_path = root / "manifest.json"
    outputs_path = root / "evaluator_outputs.json"
    if manifest_path.exists() and outputs_path.exists():
        verified = verify_manifest(manifest_path)
    else:
        manifest_path, outputs_path = generate(root, seed)
        verified = verify_manifest(manifest_path)
    initialize(db_path)
    count = ingest(db_path, verified["manifest"], manifest_path.parent)
    return manifest_path, outputs_path, count


def _code_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10,
            cwd=Path(__file__).resolve().parents[1],
        )
    except (OSError, subprocess.SubprocessError):
        return "unrecorded"
    commit = result.stdout.strip()
    return commit if result.returncode == 0 and len(commit) == 40 else "unrecorded"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ouro-eval-lab")
    sub = parser.add_subparsers(dest="command", required=True)
    seed = sub.add_parser("seed")
    seed.add_argument("--root", type=Path, required=True)
    seed.add_argument("--seed", type=int, default=20260825)
    bootstrap = sub.add_parser("bootstrap")
    bootstrap.add_argument("--root", type=Path, required=True)
    bootstrap.add_argument("--db", type=Path, required=True)
    bootstrap.add_argument("--seed", type=int, default=20260825)
    init = sub.add_parser("init-db")
    init.add_argument("--db", type=Path, required=True)
    ingestion = sub.add_parser("ingest")
    ingestion.add_argument("--db", type=Path, required=True)
    ingestion.add_argument("--manifest", type=Path, required=True)
    verification = sub.add_parser("verify")
    verification.add_argument("--manifest", type=Path, required=True)
    benchmark = sub.add_parser("benchmark")
    benchmark.add_argument("--manifest", type=Path, required=True)
    benchmark.add_argument("--outputs", type=Path, required=True)
    benchmark.add_argument("--out", type=Path, required=True)
    export = sub.add_parser("export")
    export.add_argument("--db", type=Path, required=True)
    export.add_argument("--out", type=Path, required=True)
    export.add_argument("--format", choices=["json", "csv"], default="json")
    reveal_cmd = sub.add_parser(
        "reveal", help="verify sealed intent records and load them; refused before export-intent",
    )
    reveal_cmd.add_argument("--db", type=Path, required=True)
    reveal_cmd.add_argument("--records", type=Path, required=True, help="directory of revealed *.intent.json files")
    reveal_cmd.add_argument("--commitments", type=Path, default=INTENT_DIR / "intent_commitments.sha256")
    reveal_cmd.add_argument("--manifest", type=Path, default=INTENT_DIR / "manifest.json")
    export_intent = sub.add_parser(
        "export-intent", help="freeze Stage 1 intent responses before reveal; closes collection",
    )
    export_intent.add_argument("--db", type=Path, required=True)
    export_intent.add_argument("--out", type=Path, required=True)
    export_intent.add_argument("--format", choices=["json", "csv"], default="json")
    sheet_cmd = sub.add_parser(
        "intent-coding-sheet", help="write one coder's blinded Stage 2 coding sheet (CSV); after reveal",
    )
    sheet_cmd.add_argument("--db", type=Path, required=True)
    sheet_cmd.add_argument("--coder", required=True, help="pseudonymous coder ID")
    sheet_cmd.add_argument("--out", type=Path, required=True)
    sheet_cmd.add_argument("--seed", type=int, default=DEFAULT_SHEET_SEED, help="item-order seed (recorded)")
    import_cmd = sub.add_parser(
        "intent-import-codes", help="validate a filled coding sheet and append its codes",
    )
    import_cmd.add_argument("--db", type=Path, required=True)
    import_cmd.add_argument("--coder", required=True, help="pseudonymous coder ID the sheet was issued to")
    import_cmd.add_argument("--codes", type=Path, required=True, help="the filled coding sheet CSV")
    intent_report = sub.add_parser(
        "intent-report", help="write the deterministic intent metrics report (JSON) from coded responses",
    )
    intent_report.add_argument("--db", type=Path, required=True)
    intent_report.add_argument("--out", type=Path, required=True)
    intent_report.add_argument("--seed", type=int, default=INTENT_SEED, help="bootstrap seed (pre-registered)")
    intent_report.add_argument("--samples", type=int, default=INTENT_SAMPLES, help="bootstrap resamples")
    intent_report.add_argument(
        "--code-commit", default=None, help="commit to record; defaults to git HEAD when available",
    )
    agreement = sub.add_parser("agreement", help="write an offline aggregate report from a local lab database")
    agreement.add_argument("--db", type=Path, required=True)
    agreement.add_argument("--out", type=Path, required=True)
    native = sub.add_parser("inspect-avc")
    native.add_argument("--manifest", type=Path, required=True)
    native.add_argument("--evaluation", type=Path, required=True)
    native.add_argument("--out", type=Path, required=True)
    server = sub.add_parser("serve")
    server.add_argument("--db", type=Path, required=True)
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=8080)
    server.add_argument("--study", choices=STUDIES, default="annotation")
    server.add_argument(
        "--play-limit", type=int, default=2,
        help="intent study only: plays allowed per clip (pre-registered value: 2)",
    )
    args = parser.parse_args(argv)

    if args.command == "seed":
        manifest, outputs = generate(args.root, args.seed)
        print(f"generated {manifest} and {outputs}")
    elif args.command == "bootstrap":
        manifest, outputs, count = bootstrap_demo(args.root, args.db, args.seed)
        print(f"ready: {count} verified artifacts, {manifest}, {outputs}, {args.db}")
    elif args.command == "init-db":
        initialize(args.db)
        print(f"initialized {args.db}")
    elif args.command == "ingest":
        verified = verify_manifest(args.manifest)
        count = ingest(args.db, verified["manifest"], args.manifest.parent)
        print(f"ingested {count} verified artifacts")
    elif args.command == "verify":
        result = verify_manifest(args.manifest)
        print(json.dumps({k: v for k, v in result.items() if k != "manifest"}, indent=2))
    elif args.command == "benchmark":
        report = run_benchmark(args.manifest, args.outputs)
        _write(args.out, json.dumps(report, indent=2, sort_keys=True) + "\n")
        print(f"wrote {args.out}")
    elif args.command == "export":
        initialize(args.db)
        with connect(args.db) as db:
            _write(args.out, export_annotations(db, args.format))
        print(f"wrote {args.out}")
    elif args.command == "export-intent":
        if not args.db.is_file():
            parser.error("export-intent requires an existing local lab database")
        with connect(args.db) as db:
            # Hold the write lock from export to freeze so no response can be
            # accepted after the export query but before collection closes.
            db.execute("BEGIN IMMEDIATE")
            body, count = export_intent_responses(db, args.format)
            if count == 0:
                parser.error("no intent responses to freeze")
            digest = hashlib.sha256(body).hexdigest()
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_bytes(body)
            freeze = record_intent_freeze(db, digest, args.format, count)
        print(f"froze {count} intent responses to {args.out}")
        print(f"sha256 {digest}  freeze {freeze['freeze_id']}")
        print("intent collection is now closed; record this SHA-256 before any reveal")
    elif args.command == "reveal":
        if not args.db.is_file():
            parser.error("reveal requires an existing local lab database")
        initialize(args.db)
        try:
            with connect(args.db) as db:
                db.execute("BEGIN IMMEDIATE")
                result = reveal(db, args.records, args.commitments, args.manifest)
        except RevealRefused as exc:
            parser.error(str(exc))
        if result["already_revealed"]:
            print(f"already revealed: the same {result['record_count']} intent records; nothing changed")
        else:
            print(f"revealed {result['record_count']} intent records after freeze {result['freeze_sha256']}")
    elif args.command in {"intent-coding-sheet", "intent-import-codes"}:
        if not args.db.is_file():
            parser.error(f"{args.command} requires an existing local lab database")
        initialize(args.db)
        try:
            with connect(args.db) as db:
                db.execute("BEGIN IMMEDIATE")
                if args.command == "intent-coding-sheet":
                    result = issue_sheet(db, args.coder, args.seed)
                else:
                    result = import_codes(db, args.coder, args.codes.read_bytes())
        except (CodingRefused, ValueError) as exc:
            parser.error(str(exc))
        if args.command == "intent-coding-sheet":
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_bytes(result["body"])
            state = "rebuilt the recorded" if result["reissued"] else "issued a"
            print(f"{state} sheet of {result['item_count']} items to {args.out}")
            print(f"sha256 {result['sheet_sha256']}  seed {args.seed}")
            print("the sheet holds revealed intent text: give it only to this coder")
        else:
            print(f"imported {result['coded']} codes ({result['unchanged']} already stored, "
                  f"{result['uncoded']} left blank)")
            print(f"sha256 {result['import_sha256']}")
    elif args.command == "intent-report":
        if not args.db.is_file():
            parser.error("intent-report requires an existing local lab database")
        if args.samples < 1:
            parser.error("--samples must be at least 1")
        initialize(args.db)
        try:
            with connect(args.db) as db:
                report = build_intent_report(
                    db, args.seed, args.samples, args.code_commit or _code_commit(),
                )
        except ValueError as exc:
            parser.error(str(exc))
        body = render_intent_report(report)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(body)
        print(f"wrote {args.out} (synthetic demo; not a research finding)")
        print(f"sha256 {hashlib.sha256(body).hexdigest()}")
    elif args.command == "agreement":
        if not args.db.is_file():
            parser.error("agreement requires an existing local lab database")
        with connect(args.db) as db:
            _write(args.out, json.dumps(agreement_report(db), indent=2, sort_keys=True) + "\n")
        print(f"wrote {args.out}")
    elif args.command == "inspect-avc":
        report = inspect_native_avc(args.manifest, args.evaluation)
        _write(args.out, json.dumps(report, indent=2, sort_keys=True) + "\n")
        print(f"wrote {args.out}")
    elif args.command == "serve":
        if args.play_limit < 1:
            parser.error("--play-limit must be at least 1")
        initialize(args.db)
        with connect(args.db) as db:
            conflict = study_conflict(db, args.study)
        if conflict:
            parser.error(conflict)
        serve(args.db, args.host, args.port, args.study, args.play_limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
