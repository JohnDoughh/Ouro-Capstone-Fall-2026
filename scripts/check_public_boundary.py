#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

SKIP = {".git", ".venv", "__pycache__", "data"}
PATTERNS = {
    "private key": re.compile(r"BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY"),
    "generic API key": re.compile(r"(?i)(api[_-]?key|secret[_-]?key)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}"),
    "production URL": re.compile(r"https?://[^\s'\"]*(prod|production)[^\s'\"]*", re.I),
    "customer identifier": re.compile(r"(?i)(customer_email|campaign_id|tenant_id)\s*[:=]"),
}


def main(root: Path) -> int:
    failures = []
    for path in root.rglob("*"):
        if not path.is_file() or any(part in SKIP for part in path.parts):
            continue
        try:
            content = path.read_text()
        except UnicodeDecodeError:
            continue
        for label, pattern in PATTERNS.items():
            if pattern.search(content):
                failures.append(f"{path}: possible {label}")
    if failures:
        print("Public-boundary scan failed:")
        print("\n".join(failures))
        return 1
    print("Public-boundary scan passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1] if len(sys.argv) > 1 else ".")))
