from __future__ import annotations

import json
import hashlib
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .contracts import ContractError, validate_annotation_payload
from .store import connect, next_assignment, progress, save_annotation


WEB_ROOT = Path(__file__).parent / "web"


def parse_byte_range(header: str | None, size: int) -> tuple[int, int] | str | None:
    """Parse a single ``bytes=`` range.

    Returns ``None`` to serve the whole body (no header, or a form this lab
    does not support, which RFC 9110 allows a server to ignore), an inclusive
    ``(start, end)`` pair, or ``"unsatisfiable"`` for a range outside the body.
    """
    if not header:
        return None
    unit, _, spec = header.strip().partition("=")
    if unit.strip().lower() != "bytes" or "," in spec:
        return None
    first, dash, last = spec.strip().partition("-")
    if not dash or not (first.isdigit() or first == "") or not (last.isdigit() or last == ""):
        return None
    if first == "" and last == "":
        return None
    if size == 0:
        return "unsatisfiable"
    if first == "":
        length = int(last)
        if length == 0:
            return "unsatisfiable"
        return (max(size - length, 0), size - 1)
    start = int(first)
    if start >= size:
        return "unsatisfiable"
    end = size - 1 if last == "" else min(int(last), size - 1)
    if end < start:
        return None
    return (start, end)


class LabHandler(BaseHTTPRequestHandler):
    db_path: Path

    def _json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, sort_keys=True).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; media-src 'self'; img-src 'self' data:")
        self.end_headers()
        self.wfile.write(body)

    def _rater(self, query: dict[str, list[str]]) -> str:
        value = query.get("rater", [""])[0].strip()
        if not value or len(value) > 80 or not all(ch.isalnum() or ch in "-_" for ch in value):
            raise ValueError("rater must be a pseudonymous ID using letters, numbers, - or _")
        return value

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        try:
            if parsed.path == "/api/health":
                return self._json(200, {"status": "ok", "synthetic_demo": True})
            if parsed.path == "/api/next":
                rater = self._rater(query)
                with connect(self.db_path) as db:
                    assignment = next_assignment(db, rater)
                    state = progress(db, rater)
                if assignment:
                    assignment["media_url"] = f"/api/media/{assignment['assignment_id']}?rater={rater}"
                    for hidden in ("relative_path", "fixture_root", "sha256"):
                        assignment.pop(hidden, None)
                return self._json(200, {"assignment": assignment, "progress": state})
            if parsed.path.startswith("/api/media/"):
                assignment_id = parsed.path.rsplit("/", 1)[-1]
                rater = self._rater(query)
                with connect(self.db_path) as db:
                    row = db.execute(
                        """SELECT x.fixture_root, x.relative_path, x.mime_type, x.sha256, x.byte_length FROM assignments a
                           JOIN artifacts x ON x.sha256=a.artifact_sha256
                           WHERE a.assignment_id=? AND a.rater_id=?""",
                        (assignment_id, rater),
                    ).fetchone()
                if not row:
                    return self._json(404, {"error": "not found"})
                root = Path(row["fixture_root"]).resolve()
                target = (root / row["relative_path"]).resolve()
                if root not in target.parents:
                    return self._json(403, {"error": "invalid artifact path"})
                body = target.read_bytes()
                if len(body) != row["byte_length"] or hashlib.sha256(body).hexdigest() != row["sha256"]:
                    return self._json(409, {"error": "artifact integrity failure"})
                # Safari and iOS refuse to play <audio>/<video> unless the
                # server answers byte-range requests. Integrity is always
                # checked over the whole file before any slice is served.
                span = parse_byte_range(self.headers.get("Range"), len(body))
                if span == "unsatisfiable":
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{len(body)}")
                    self.send_header("Content-Length", "0")
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    return None
                chunk = body if span is None else body[span[0]:span[1] + 1]
                self.send_response(200 if span is None else 206)
                self.send_header("Content-Type", row["mime_type"] or mimetypes.guess_type(target.name)[0] or "application/octet-stream")
                self.send_header("Content-Length", str(len(chunk)))
                self.send_header("Accept-Ranges", "bytes")
                if span is not None:
                    self.send_header("Content-Range", f"bytes {span[0]}-{span[1]}/{len(body)}")
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                return self.wfile.write(chunk)
            return self._static(parsed.path)
        except (ValueError, ContractError) as exc:
            return self._json(400, {"error": str(exc)})
        except FileNotFoundError:
            return self._json(404, {"error": "artifact not found"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        try:
            if not parsed.path.startswith("/api/annotations/"):
                return self._json(404, {"error": "not found"})
            rater = self._rater(query)
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 8192:
                raise ValueError("invalid request size")
            payload = json.loads(self.rfile.read(length))
            validate_annotation_payload(payload)
            assignment_id = parsed.path.rsplit("/", 1)[-1]
            with connect(self.db_path) as db:
                result = save_annotation(db, assignment_id, rater, payload)
            return self._json(HTTPStatus.CREATED, result)
        except (ValueError, ContractError, json.JSONDecodeError) as exc:
            return self._json(400, {"error": str(exc)})

    def _static(self, path: str) -> None:
        name = "index.html" if path == "/" else path.lstrip("/")
        if name not in {"index.html", "app.js", "styles.css", "annotation-scales.css"}:
            return self._json(404, {"error": "not found"})
        target = WEB_ROOT / name
        body = target.read_bytes()
        mime = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8"}[target.suffix]
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        print(f"lab-api {self.address_string()} {format % args}")


def serve(db_path: Path, host: str, port: int) -> None:
    handler = type("ConfiguredLabHandler", (LabHandler,), {"db_path": db_path})
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Evaluation Lab listening on http://{host}:{port}")
    server.serve_forever()
