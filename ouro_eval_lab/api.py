from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .contracts import ContractError, validate_annotation_payload
from .runner import agreement_report
from .store import connect, next_assignment, progress, save_annotation


WEB_ROOT = Path(__file__).parent / "web"


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
            if parsed.path == "/api/agreement":
                with connect(self.db_path) as db:
                    return self._json(200, agreement_report(db))
            if parsed.path.startswith("/api/media/"):
                assignment_id = parsed.path.rsplit("/", 1)[-1]
                rater = self._rater(query)
                with connect(self.db_path) as db:
                    row = db.execute(
                        """SELECT x.fixture_root, x.relative_path, x.mime_type FROM assignments a
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
                self.send_response(200)
                self.send_header("Content-Type", row["mime_type"] or mimetypes.guess_type(target.name)[0] or "application/octet-stream")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                return self.wfile.write(body)
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
        if name not in {"index.html", "app.js", "styles.css"}:
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
