from __future__ import annotations

import argparse
import json
from pathlib import Path

from .api import serve
from .contracts import validate_manifest
from .fixtures import generate
from .runner import export_annotations, load_json, run_benchmark, verify_manifest
from .store import connect, ingest, initialize


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ouro-eval-lab")
    sub = parser.add_subparsers(dest="command", required=True)
    seed = sub.add_parser("seed")
    seed.add_argument("--root", type=Path, required=True)
    seed.add_argument("--seed", type=int, default=20260825)
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
    server = sub.add_parser("serve")
    server.add_argument("--db", type=Path, required=True)
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=8080)
    args = parser.parse_args(argv)

    if args.command == "seed":
        manifest, outputs = generate(args.root, args.seed)
        print(f"generated {manifest} and {outputs}")
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
        with connect(args.db) as db:
            _write(args.out, export_annotations(db, args.format))
        print(f"wrote {args.out}")
    elif args.command == "serve":
        initialize(args.db)
        serve(args.db, args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
