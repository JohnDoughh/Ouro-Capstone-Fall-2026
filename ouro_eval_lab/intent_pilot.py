"""Team C Sprint 5: a seeded, synthetic end-to-end intent pilot.

Runs the whole intent study on invented data, through the same functions the
lab uses: fictional clips and sealed records, blinded viewer responses, the
freeze, the reveal, two coders' sheets and imports, and ``intent-report``.

Everything is synthetic and labelled so. The pilot shows the protocol works
end to end and that its report is byte-stable; it is not a research finding.
The simulated viewers and coders follow fixed probabilities chosen here, so
the report says nothing about how real people understand real clips.

Byte stability: the lab normally stamps rows with random IDs and the current
time. For the length of a pilot run only, those are replaced by values derived
from the seed, so the same seed always gives the same report bytes. Nothing
outside the pilot changes.
"""
from __future__ import annotations

import base64
import contextlib
import csv
import gc
import hashlib
import io
import json
import random
import tempfile
from datetime import datetime as _real_datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from . import coding, reveal as reveal_module, store
from .coding import SHEET_FIELDS, import_codes, issue_sheet
from .contracts import (
    INTENT_DELIVERY_CODES, INTENT_FIELDS, normalize_intent_response,
    validate_intent_response_payload,
)
from .intent_metrics import DEFAULT_SEED, build_intent_report, render_intent_report
from .reveal import reveal
from .runner import export_intent_responses, verify_manifest
from .store import (
    connect, ingest, next_assignment, record_intent_freeze, record_intent_play,
    save_intent_response,
)

PILOT_VERSION = "1.0.0"
PILOT_SAMPLES = 500
PILOT_CODE_COMMIT = "pilot-unbound"
PLAY_LIMIT = 2
CLIPS = 6
VIEWERS = tuple(f"pilot_viewer_{n:02d}" for n in range(1, 6))
CODERS = ("pilot_coder_a", "pilot_coder_b")
CODER_SLIP = 0.05
START = _real_datetime(2026, 1, 1, tzinfo=timezone.utc)

# Chance that a simulated viewer recovers / partly recovers / contradicts a
# component, by delivery code. The rest is not recovered; a third of that is
# "could not tell". Invented for the pilot, not estimates of anything.
VIEWER_OUTCOMES = {
    "explicit_text": (0.80, 0.10, 0.03),
    "implied": (0.45, 0.25, 0.08),
    "visual_only": (0.55, 0.20, 0.05),
    "partially_delivered": (0.30, 0.40, 0.05),
    "omitted_in_edit": (0.10, 0.15, 0.10),
    "not_intended": (0.05, 0.05, 0.05),
}
# A coder's slip moves the code one step on this scale.
SLIP_SCALE = ["contradicted", "not_recovered", "partially_recovered", "recovered"]


class _PinnedClock:
    """Stands in for ``datetime`` in the lab modules: each call is one second later."""

    def __init__(self) -> None:
        self.ticks = 0

    def now(self, tz=None):
        self.ticks += 1
        return START + timedelta(seconds=self.ticks)


@contextlib.contextmanager
def _pinned(seed: int):
    """Replace random IDs and the clock in the lab modules for one pilot run."""
    counter = [0]

    def token(nbytes: int = 12) -> bytes:
        counter[0] += 1
        return hashlib.sha256(f"pilot:{seed}:{counter[0]}".encode()).digest()[:nbytes]

    fake_secrets = SimpleNamespace(
        token_urlsafe=lambda n=12: base64.urlsafe_b64encode(token(n)).rstrip(b"=").decode(),
        token_hex=lambda n=12: token(n).hex(),
    )
    clock = _PinnedClock()
    modules = (store, coding, reveal_module)
    saved = [(module, module.secrets, module.datetime) for module in modules]
    try:
        for module in modules:
            module.secrets, module.datetime = fake_secrets, clock
        yield
    finally:
        for module, secrets_module, datetime_class in saved:
            module.secrets, module.datetime = secrets_module, datetime_class


@contextlib.contextmanager
def _db(path: Path):
    with contextlib.closing(connect(path)) as db:
        with db:
            yield db


def _deliveries(rng: random.Random) -> list[dict[str, str]]:
    """One delivery map per clip. Every code appears, so every stratum is exercised."""
    codes = sorted(INTENT_DELIVERY_CODES)
    weights = [4 if code == "explicit_text" else 2 if code in {"implied", "visual_only"} else 1
               for code in codes]
    maps = [{field: rng.choices(codes, weights)[0] for field in INTENT_FIELDS} for _ in range(CLIPS)]
    for index, code in enumerate(codes):  # Guarantee each code at least once.
        maps[index % CLIPS][INTENT_FIELDS[(index * 3) % (len(INTENT_FIELDS) - 1)]] = code
    return maps


def _write_study(root: Path, rng: random.Random) -> dict:
    """Fictional clips, sealed fictional records, their commitments and a manifest."""
    clips, records = root / "clips", root / "sealed"
    clips.mkdir()
    records.mkdir()
    artifacts, lines = [], []
    for index, delivery in enumerate(_deliveries(rng), start=1):
        name = f"pilot{index:02d}"
        body = f"Fictional pilot clip {name}. Synthetic stand-in, not a real advertisement.".encode()
        (clips / f"{name}.txt").write_bytes(body)
        artifact = {
            "artifact_id": f"syn-{name}", "relative_path": f"{name}.txt",
            "sha256": hashlib.sha256(body).hexdigest(), "byte_length": len(body),
            "mime_type": "text/plain", "modality": "text", "split": "development",
            "defect_family": "none_seeded_intent_recovery_only", "defect_present": False,
            "synthetic": True,
        }
        artifacts.append(artifact)
        record = {
            "artifact_id": artifact["artifact_id"], "relative_path": artifact["relative_path"],
            "salt": hashlib.sha256(f"salt:{name}".encode()).hexdigest()[:16],
            "schema": "fictional-intent-record", "record_type": "fictional_intent_record",
            "fictional": True, "frozen_at": "2026-01-01T00:00:00Z",
            "note": "Synthetic pilot record. Invented values only.",
            "delivery_codes": sorted(set(delivery.values())),
            "intended": {field: f"Fictional {field.replace('_', ' ')} of pilot clip {index}"
                         for field in INTENT_FIELDS},
            "delivery": delivery,
        }
        sealed = json.dumps(record, sort_keys=True).encode()
        (records / f"{name}.intent.json").write_bytes(sealed)
        lines.append(f"{hashlib.sha256(sealed).hexdigest()}  {name}.intent.json")
    manifest = clips / "manifest.json"
    manifest.write_bytes(json.dumps({
        "contract_version": "1.0.0", "benchmark_id": "synthetic-intent-pilot", "seed": 0,
        "created_at": "2026-01-01T00:00:00Z", "artifacts": artifacts,
    }, sort_keys=True).encode())
    commitments = root / "commitments.sha256"
    # Bytes, not text: a text write would use CRLF on Windows and change the hash.
    commitments.write_bytes(("\n".join(lines) + "\n").encode())
    return {"clips": clips, "records": records, "manifest": manifest, "commitments": commitments,
            "delivery": {a["sha256"]: json.loads((records / f"{Path(a['relative_path']).stem}.intent.json")
                                                 .read_bytes())["delivery"] for a in artifacts}}


def _viewer_answer(rng: random.Random, delivery: dict[str, str], serial: list[int]) -> dict:
    """A simulated response. The recall text carries the simulated outcome so the
    simulated coders, who see only the sheet, can code it."""
    components = {}
    for field in INTENT_FIELDS:
        recovered, partial, contradicted = VIEWER_OUTCOMES[delivery[field]]
        draw = rng.random()
        if draw < recovered:
            outcome = "recovered"
        elif draw < recovered + partial:
            outcome = "partially_recovered"
        elif draw < recovered + partial + contradicted:
            outcome = "contradicted"
        else:
            outcome = "could_not_tell" if rng.random() < 1 / 3 else "not_recovered"
        if outcome == "could_not_tell":
            components[field] = {"recall": "", "certainty": None, "could_not_tell": True}
            continue
        serial[0] += 1
        certainty = {"recovered": 4, "partially_recovered": 3, "contradicted": 4,
                     "not_recovered": 2}[outcome] + rng.choice((-1, 0, 1))
        components[field] = {
            "recall": f"Simulated answer {serial[0]} (pilot outcome: {outcome})",
            "certainty": max(1, min(5, certainty)),
            "could_not_tell": False,
        }
    return {"components": components, "other_beats": "", "play_count": 0}


def _collect(db, rng: random.Random, delivery_by_sha: dict) -> int:
    serial, count = [0], 0
    for viewer in VIEWERS:
        while (assignment := next_assignment(db, viewer, repeats=False)) is not None:
            plays = rng.choice((1, 1, 2))
            for number in range(1, plays + 1):
                record_intent_play(db, assignment["assignment_id"], viewer, number, PLAY_LIMIT)
            payload = _viewer_answer(rng, delivery_by_sha[assignment["sha256"]], serial)
            payload["play_count"] = plays
            validate_intent_response_payload(payload, PLAY_LIMIT)
            save_intent_response(db, assignment["assignment_id"], viewer,
                                 normalize_intent_response(payload), PLAY_LIMIT)
            count += 1
    return count


def _code(row: dict, coder: str, seed: int) -> str:
    """The code a simulated coder gives one sheet row (codebook rules, plus slips)."""
    if row["delivery"] == "not_intended":
        return "not_applicable"
    if row["viewer_could_not_tell"] == "yes":
        return "not_recovered"
    intended = row["viewer_recall"].rsplit("pilot outcome: ", 1)[1].rstrip(")")
    slip = random.Random(f"{seed}:{coder}:{row['component']}:{row['viewer_recall']}")
    if slip.random() >= CODER_SLIP:
        return intended
    position = SLIP_SCALE.index(intended)
    return SLIP_SCALE[position + 1 if position == 0 else position - 1 if position == 3
                      else position + slip.choice((-1, 1))]


def _code_sheet(body: bytes, coder: str, seed: int) -> bytes:
    rows = list(csv.DictReader(io.StringIO(body.decode(), newline="")))
    for row in rows:
        row["code"] = _code(row, coder, seed)
        row["confidence"] = "3"
        row["note"] = "" if row["code"] in {"recovered", "not_recovered", "not_applicable"} else "simulated"
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=SHEET_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode()


def run_pilot(seed: int = DEFAULT_SEED, samples: int = PILOT_SAMPLES, workdir: Path | None = None) -> bytes:
    """Run the synthetic pilot and return the intent report bytes.

    ``workdir`` (empty or missing) keeps the pilot's files and database for
    inspection; by default they go to a temporary directory and are removed.
    """
    with contextlib.ExitStack() as stack:
        if workdir is None:
            root = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        else:
            root = Path(workdir)
            root.mkdir(parents=True, exist_ok=True)
            if any(root.iterdir()):
                raise ValueError("pilot workdir must be empty")
        stack.enter_context(_pinned(seed))
        rng = random.Random(f"intent-pilot:{seed}")
        study = _write_study(root, rng)
        path = root / "pilot.db"
        ingest(path, verify_manifest(study["manifest"])["manifest"], study["clips"])
        with _db(path) as db:
            _collect(db, rng, study["delivery"])
            body, count = export_intent_responses(db, "json")
            (root / "freeze.json").write_bytes(body)
            record_intent_freeze(db, hashlib.sha256(body).hexdigest(), "json", count)
        with _db(path) as db:
            db.execute("BEGIN IMMEDIATE")
            reveal(db, study["records"], study["commitments"], study["manifest"])
        for coder in CODERS:
            with _db(path) as db:
                db.execute("BEGIN IMMEDIATE")
                sheet = issue_sheet(db, coder, seed)
            with _db(path) as db:
                db.execute("BEGIN IMMEDIATE")
                import_codes(db, coder, _code_sheet(sheet["body"], coder, seed))
        with _db(path) as db:
            report = build_intent_report(db, seed, samples, PILOT_CODE_COMMIT)
        report["pilot"] = {
            "pilot_version": PILOT_VERSION,
            "clips": CLIPS, "viewers": len(VIEWERS), "coders": len(CODERS),
            "simulated_viewer_outcomes": {code: list(p) for code, p in sorted(VIEWER_OUTCOMES.items())},
            "simulated_coder_slip_rate": CODER_SLIP,
            "note": "Simulated viewers and coders with invented probabilities. "
                    "Exercises the protocol only; the numbers mean nothing about people or clips.",
        }
        body = render_intent_report(report)
        if workdir is not None:
            (root / "intent-report.json").write_bytes(body)
        # Drop SQLite handles before the temporary directory goes (Windows).
        gc.collect()
        return body
