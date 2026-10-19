from __future__ import annotations

import json
import hashlib
import mimetypes
import sqlite3
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .contracts import (
    INTENT_MAX_PLAY_COUNT, ContractError, looks_like_phone_number, normalize_intent_response,
    validate_annotation_payload, validate_intent_response_payload,
)
from .store import (
    CollectionFrozen, PlayRefused, connect, intent_collection_frozen, intent_plays_used,
    next_assignment, progress, record_intent_play, save_annotation, save_intent_response, saved_intent_receipt,
)


WEB_ROOT = Path(__file__).parent / "web"


class ConflictingAnnotation(ValueError):
    """The assignment has a saved judgment different from this retry."""


def _saved_annotation_receipt(db: sqlite3.Connection, assignment_id: str, rater: str, payload: dict) -> dict | None:
    saved = db.execute(
        """SELECT annotation_id, completed_at, verdict, confidence,
                  confidence_scale, severity, defect_timestamps,
                  reason_codes, note FROM annotations
           WHERE assignment_id=? AND rater_id=?""",
        (assignment_id, rater),
    ).fetchone()
    if saved is None or not _same_saved_annotation(saved, payload):
        return None
    return {"annotation_id": saved["annotation_id"], "completed_at": saved["completed_at"]}


def _same_saved_annotation(row: sqlite3.Row, payload: dict) -> bool:
    """Compare the stored normalized judgment, never replacing its original evidence."""
    return (
        row["confidence_scale"] == "1-5"
        and row["verdict"] == payload["verdict"]
        and row["confidence"] == payload["confidence"]
        and row["severity"] == payload["severity"]
        and (row["defect_timestamps"] or "") == payload.get("defect_timestamps", "").strip()
        and json.loads(row["reason_codes"]) == payload["reason_codes"]
        and row["note"] == payload.get("note", "")
    )


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
    study: str = "annotation"
    play_limit: int | None = None

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
        if looks_like_phone_number(value):
            raise ValueError("rater must be a pseudonymous ID, not a phone number")
        return value

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        try:
            if parsed.path == "/api/health":
                return self._json(200, {"status": "ok", "synthetic_demo": True, "study": self.study})
            if parsed.path == "/api/next":
                rater = self._rater(query)
                repeats = self.study != "intent"
                plays_used = None
                with connect(self.db_path) as db:
                    # After the freeze no assignment is offered: nothing could be saved.
                    closed = self.study == "intent" and intent_collection_frozen(db)
                    assignment = None if closed else next_assignment(db, rater, repeats=repeats)
                    state = progress(db, rater, repeats=repeats)
                    if assignment and self.study == "intent":
                        # Restored on every reload, so re-entry never resets exposure.
                        plays_used = intent_plays_used(db, assignment["assignment_id"])
                if assignment:
                    # Source IDs can encode the answer (for example CLEAN).
                    # Only send presentation fields; preserve canonical identity
                    # and media bindings in storage and offline exports.
                    assignment = {key: assignment[key] for key in (
                        "assignment_id", "sequence", "started_at", "mime_type", "modality",
                    )}
                    assignment["review_label"] = f"Item {assignment['sequence'] + 1:03d}"
                    assignment["media_url"] = f"/api/media/{assignment['assignment_id']}?rater={rater}"
                # The study mode is a server setting, never an artifact field.
                return self._json(200, {
                    "assignment": assignment, "progress": state,
                    "study": self.study, "play_limit": self.play_limit, "plays_used": plays_used,
                    "collection_closed": closed,
                })
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
        # Each server runs one study, so a rater can never complete an
        # assignment through the other study's form.
        if self.study == "intent" and parsed.path.startswith("/api/intent-responses/"):
            return self._post_intent_response(parsed.path, query)
        if self.study == "intent" and parsed.path.startswith("/api/intent-plays/"):
            return self._post_intent_play(parsed.path, query)
        if self.study == "annotation" and parsed.path.startswith("/api/annotations/"):
            return self._post_annotation(parsed.path, query)
        return self._json(404, {"error": "not found"})

    def _read_payload(self, max_bytes: int) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > max_bytes:
            raise ValueError("invalid request size")
        payload = json.loads(self.rfile.read(length))
        if not isinstance(payload, dict):
            raise ContractError("submission must be one JSON object")
        return payload

    def _post_annotation(self, path: str, query: dict[str, list[str]]) -> None:
        def prepare() -> dict:
            payload = self._read_payload(8192)
            validate_annotation_payload(payload)
            if not isinstance(payload.get("note", ""), str):
                raise ContractError("note must be a string")
            return payload

        self._post_with_receipt(
            path, query, prepare, save=save_annotation,
            saved_receipt=_saved_annotation_receipt,
            conflict="assignment already completed with a different annotation",
            retry_hint="retry the exact same annotation",
        )

    def _post_intent_response(self, path: str, query: dict[str, list[str]]) -> None:
        def prepare() -> dict:
            payload = self._read_payload(16384)
            validate_intent_response_payload(payload, self.play_limit)
            return normalize_intent_response(payload)

        def save(db, assignment_id, rater, normalized):
            return save_intent_response(db, assignment_id, rater, normalized, self.play_limit)

        self._post_with_receipt(
            path, query, prepare, save=save, saved_receipt=saved_intent_receipt,
            conflict="assignment already completed with a different response",
            retry_hint="retry the exact same response",
        )

    def _post_intent_play(self, path: str, query: dict[str, list[str]]) -> None:
        """Record one play start before the clip plays.

        201 records a new play, 200 replays an already-recorded play_number,
        409 refuses (limit reached, completed, out of order, or frozen) with the
        durable count, 400 rejects before writing, and 503 has an unknown outcome.
        """
        try:
            rater = self._rater(query)
            payload = self._read_payload(256)
            if set(payload) != {"play_number"}:
                raise ContractError("play request must contain exactly play_number")
            play_number = payload["play_number"]
            if type(play_number) is not int or not 1 <= play_number <= INTENT_MAX_PLAY_COUNT:
                raise ContractError(f"play_number must be an integer from 1 to {INTENT_MAX_PLAY_COUNT}")
            assignment_id = path.rsplit("/", 1)[-1]
            with connect(self.db_path) as db:
                db.execute("BEGIN IMMEDIATE")
                try:
                    result = record_intent_play(db, assignment_id, rater, play_number, self.play_limit)
                except (PlayRefused, CollectionFrozen) as exc:
                    refusal = {"error": str(exc), "plays_used": intent_plays_used(db, assignment_id)}
                    if isinstance(exc, CollectionFrozen):
                        refusal["collection_closed"] = True
                    return self._json(HTTPStatus.CONFLICT, refusal)
            return self._json(HTTPStatus.OK if result.get("replayed") else HTTPStatus.CREATED, result)
        except sqlite3.OperationalError:
            return self._json(HTTPStatus.SERVICE_UNAVAILABLE, {
                "error": "play status unknown; retry the same play_number"
            })
        except (ValueError, ContractError, json.JSONDecodeError) as exc:
            return self._json(400, {"error": str(exc)})

    def _post_with_receipt(self, path, query, prepare, save, saved_receipt, conflict, retry_hint) -> None:
        """Save once per assignment; an exact retry replays the original receipt.

        201 is a new write, 200 an exact replay, 409 a different submission
        for a completed assignment or a frozen collection, 400 a definite
        pre-write rejection, and 503 a storage error with an unknown outcome.
        A frozen collection's 409 sets ``collection_closed``: nothing was
        written and no retry can succeed, so the client may stop retrying.
        """
        try:
            rater = self._rater(query)
            payload = prepare()
            assignment_id = path.rsplit("/", 1)[-1]
            with connect(self.db_path) as db:
                # An aborted browser request does not prove its earlier write
                # rolled back. Serialize the initial write and an exact retry
                # against the same assignment before returning any receipt.
                db.execute("BEGIN IMMEDIATE")
                try:
                    result = save(db, assignment_id, rater, payload)
                    status = HTTPStatus.CREATED
                except ValueError as exc:
                    if str(exc) != "assignment already completed":
                        raise
                    receipt = saved_receipt(db, assignment_id, rater, payload)
                    if receipt is None:
                        raise ConflictingAnnotation(conflict) from exc
                    result = {**receipt, "replayed": True}
                    status = HTTPStatus.OK
            return self._json(status, result)
        except CollectionFrozen as exc:
            return self._json(HTTPStatus.CONFLICT, {"error": str(exc), "collection_closed": True})
        except ConflictingAnnotation as exc:
            return self._json(HTTPStatus.CONFLICT, {"error": str(exc)})
        except sqlite3.OperationalError:
            # A lock, I/O error, or interrupted transaction has an ambiguous
            # outcome from the client's perspective. Only the same frozen
            # payload may be retried; never tell the browser no write occurred.
            return self._json(HTTPStatus.SERVICE_UNAVAILABLE, {
                "error": f"save status unknown; {retry_hint}"
            })
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


def serve(
    db_path: Path, host: str, port: int, study: str = "annotation", play_limit: int | None = None,
) -> None:
    handler = type("ConfiguredLabHandler", (LabHandler,), {
        "db_path": db_path, "study": study,
        "play_limit": play_limit if study == "intent" else None,
    })
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Evaluation Lab ({study} study) listening on http://{host}:{port}")
    server.serve_forever()
