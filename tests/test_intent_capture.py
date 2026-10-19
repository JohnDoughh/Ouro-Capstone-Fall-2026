"""Team C Stage 1: intent-record contract and blinded viewer response capture.

All records and responses here are synthetic test data, not participant data.
"""
import contextlib
import copy
import gc
import hashlib
import io
import json
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from ouro_eval_lab.api import LabHandler
from ouro_eval_lab.cli import main as cli_main
from ouro_eval_lab.contracts import (
    INTENT_DELIVERY_CODES, INTENT_FIELDS, INTENT_RECORD_KEYS, ContractError, intent_coding_units,
    normalize_intent_response, validate_intent_record, validate_intent_response_payload,
)
from ouro_eval_lab.runner import export_intent_responses
from ouro_eval_lab.store import (
    CollectionFrozen, PlayRefused, connect, ingest, intent_plays_used, next_assignment,
    record_intent_freeze, record_intent_play, save_annotation, save_intent_response, study_conflict,
)


def intent_record(intended=None, delivery=None, **overrides):
    """A fictional record in the committed sponsor envelope (nested intended/delivery).

    The structure matches the sealed records; every value here is invented and
    says nothing about their content.
    """
    record = {
        "artifact_id": "syn-x", "relative_path": "clipX.mp4", "salt": "9f2c41aa",
        "schema": "fictional-intent-record", "record_type": "fictional_intent_record",
        "fictional": True, "frozen_at": "2026-01-01T00:00:00Z",
        "note": "Fictional structural fixture for tests; not a sealed study record.",
        "delivery_codes": sorted(INTENT_DELIVERY_CODES),
        "intended": {field: f"Fictional {field} for the Glimmerbox lamp" for field in INTENT_FIELDS},
        "delivery": {field: "explicit_text" for field in INTENT_FIELDS},
    }
    record["intended"]["tone"] = ""
    record["delivery"]["tone"] = "not_intended"
    record["intended"].update(intended or {})
    record["delivery"].update(delivery or {})
    record.update(overrides)
    return record


def intent_response(**overrides):
    components = {
        field: {"recall": f"Synthetic {field} recall", "certainty": 3, "could_not_tell": False}
        for field in INTENT_FIELDS
    }
    components["tone"] = {"recall": "", "certainty": None, "could_not_tell": True}
    payload = {"components": components, "other_beats": "", "play_count": 1}
    payload.update(overrides)
    return payload


@contextlib.contextmanager
def database(path):
    """Open, commit and always close, so Windows can delete the temp directory."""
    with contextlib.closing(connect(path)) as db:
        with db:
            yield db


@contextlib.contextmanager
def scratch():
    """A temp directory that Windows can delete: the lab's ``with connect()``
    commits but leaves the connection to the garbage collector."""
    with tempfile.TemporaryDirectory() as directory:
        try:
            yield directory
        finally:
            gc.collect()


def ingest_synthetic(root: Path, count: int = 4) -> Path:
    artifacts = []
    for index in range(count):
        body = f"Synthetic intent clip {index}".encode()
        name = f"clip{index:02d}.txt"
        (root / name).write_bytes(body)
        artifacts.append({
            "sha256": hashlib.sha256(body).hexdigest(), "artifact_id": f"SYN-INTENT-{index:02d}",
            "relative_path": name, "byte_length": len(body), "mime_type": "text/plain",
            "modality": "text", "split": "development",
            "defect_family": "none_seeded_intent_recovery_only", "defect_present": 0, "synthetic": 1,
        })
    db_path = root / "intent.db"
    ingest(db_path, {"artifacts": artifacts}, root)
    return db_path


class IntentRecordContractTests(unittest.TestCase):
    def test_accepts_the_committed_nested_envelope(self):
        validate_intent_record(intent_record())
        self.assertEqual(sorted(intent_record()), sorted(INTENT_RECORD_KEYS))

    def test_rejects_the_superseded_top_level_component_shape(self):
        # Sprint 2's provisional 1.0.0 shape: seven top-level {text, delivery} items.
        old = {k: v for k, v in intent_record().items() if k not in {"intended", "delivery"}}
        old.update({field: {"text": "Fictional", "delivery": "implied"} for field in INTENT_FIELDS})
        with self.assertRaises(ContractError):
            validate_intent_record(old)

    def test_rejects_unknown_missing_oversized_and_uncontrolled_values(self):
        record = intent_record()
        del record["intended"]["support"]
        cases = {
            "unknown/private key": intent_record(prompt="internal"),
            "missing envelope key": {k: v for k, v in intent_record().items() if k != "note"},
            "missing component": record,
            "extra component": intent_record(intended={"offer": "Fictional offer"}),
            "component object, not string": intent_record(intended={"support": {"text": "x"}}),
            "bad delivery": intent_record(delivery={"support": "spoken"}),
            "delivery not in record codes": intent_record(
                delivery_codes=["explicit_text", "not_intended"], delivery={"support": "implied"}),
            "uncontrolled delivery_codes": intent_record(delivery_codes=["explicit_text", "spoken"]),
            "duplicate delivery_codes": intent_record(delivery_codes=["implied", "implied"]),
            "oversized text": intent_record(intended={"support": "x" * 301}),
            "delivered but empty": intent_record(intended={"support": " "}),
            "url in text": intent_record(intended={"call_to_action": "Visit https://example.test"}),
            "email in text": intent_record(intended={"audience": "ask a@b.test"}),
            "url in note": intent_record(note="see www.example.test"),
            "not fictional": intent_record(fictional=False),
            "naive frozen_at": intent_record(frozen_at="2026-01-01T00:00:00"),
            "empty schema": intent_record(schema=""),
            "path with folder": intent_record(relative_path="../clipX.mp4"),
            "bad artifact id": intent_record(artifact_id="syn x"),
            "empty salt": intent_record(salt=""),
        }
        for name, record in cases.items():
            with self.subTest(name), self.assertRaises(ContractError):
                validate_intent_record(record)
        with self.assertRaises(ContractError):
            validate_intent_record(["not", "an", "object"])

    def test_errors_name_keys_but_never_record_values(self):
        secret = "Fictional secret benefit 7c1e"
        cases = [
            intent_record(intended={"key_benefit": secret + " https://example.test"}),
            intent_record(intended={"key_benefit": secret * 20}),
            intent_record(delivery={"key_benefit": secret}),
            intent_record(note=secret + " a@b.test"),
        ]
        for record in cases:
            with self.assertRaises(ContractError) as caught:
                validate_intent_record(record)
            self.assertNotIn(secret, str(caught.exception))

    def test_not_intended_and_omitted_in_edit_rules(self):
        validate_intent_record(intent_record(intended={"support": ""}, delivery={"support": "not_intended"}))
        # Omitted in edit was intended, so its intended text must be present.
        validate_intent_record(intent_record(intended={"support": "Lab test"}, delivery={"support": "omitted_in_edit"}))
        with self.assertRaises(ContractError):
            validate_intent_record(intent_record(intended={"support": ""}, delivery={"support": "omitted_in_edit"}))

    def test_coding_units_are_derived_without_changing_the_record(self):
        record = intent_record(delivery={"support": "visual_only"})
        before = json.dumps(record, sort_keys=True)
        units = intent_coding_units(record)
        self.assertEqual(list(units), list(INTENT_FIELDS))
        self.assertEqual(units["support"], {"text": record["intended"]["support"], "delivery": "visual_only"})
        self.assertEqual(units["tone"], {"text": "", "delivery": "not_intended"})
        self.assertEqual(json.dumps(record, sort_keys=True), before)


class IntentResponseContractTests(unittest.TestCase):
    def test_accepts_answers_and_could_not_tell(self):
        validate_intent_response_payload(intent_response())
        validate_intent_response_payload(intent_response(play_count=2), play_limit=2)

    def test_numbers_in_ordinary_recall_are_not_contact_details(self):
        payload = intent_response()
        payload["components"]["support"]["recall"] = "Waters one pot for up to 10 days; 6 buttons"
        payload["components"]["key_benefit"]["recall"] = "Clean desk in 10 seconds, 20% off until 12/31"
        validate_intent_response_payload(payload)

    def test_rejects_malformed_or_inconsistent_responses(self):
        def changed(field, **item):
            payload = intent_response()
            payload["components"][field] = {**payload["components"][field], **item}
            return payload

        missing = intent_response()
        del missing["components"]["support"]
        extra = changed("support", note="x")
        cases = {
            "unknown top-level": intent_response(artifact_id="syn-x"),
            "missing component": missing,
            "extra component key": extra,
            "could not tell with text": changed("tone", recall="calm"),
            "could not tell with certainty": changed("tone", certainty=3),
            "answer without certainty": changed("support", certainty=None),
            "certainty too high": changed("support", certainty=6),
            "certainty bool": changed("support", certainty=True),
            "certainty float": changed("support", certainty=3.0),
            "blank answer": changed("support", recall="   "),
            "oversized answer": changed("support", recall="x" * 301),
            "could_not_tell not bool": changed("support", could_not_tell=0),
            "email": changed("audience", recall="me@example.test"),
            "phone": changed("audience", recall="call 305-555-0100"),
            "international phone": changed("audience", recall="+1 (305) 555 0100"),
            "oversized other beats": intent_response(other_beats="x" * 501),
            "contact in other beats": intent_response(other_beats="viewer@example.test"),
            "negative plays": intent_response(play_count=-1),
            "bool plays": intent_response(play_count=True),
        }
        for name, payload in cases.items():
            with self.subTest(name), self.assertRaises(ContractError):
                validate_intent_response_payload(payload)
        with self.assertRaisesRegex(ContractError, "play limit"):
            validate_intent_response_payload(intent_response(play_count=3), play_limit=2)

    def test_normalization_trims_text_and_fixes_keys(self):
        payload = intent_response(other_beats="  more  ")
        payload["components"]["support"]["recall"] = "  ten days  "
        normalized = normalize_intent_response(payload)
        self.assertEqual(normalized["components"]["support"]["recall"], "ten days")
        self.assertEqual(normalized["other_beats"], "more")
        self.assertEqual(list(normalized["components"]), list(INTENT_FIELDS))


class IntentStoreTests(unittest.TestCase):
    def test_responses_and_freezes_are_append_only(self):
        with scratch() as directory:
            db_path = ingest_synthetic(Path(directory))
            with database(db_path) as db:
                assignment = next_assignment(db, "viewer-a", repeats=False)
                record_intent_play(db, assignment["assignment_id"], "viewer-a", 1, 2)
                save_intent_response(
                    db, assignment["assignment_id"], "viewer-a",
                    normalize_intent_response(intent_response()), 2,
                )
                record_intent_freeze(db, "a" * 64, "json", 1)
            for sql in ("UPDATE intent_responses SET other_beats='changed'",
                        "DELETE FROM intent_responses",
                        "UPDATE intent_plays SET play_number=0",
                        "DELETE FROM intent_plays",
                        "UPDATE intent_freezes SET export_sha256='b'",
                        "DELETE FROM intent_freezes"):
                with self.subTest(sql), self.assertRaisesRegex(sqlite3.DatabaseError, "append-only"):
                    with database(db_path) as db:
                        db.execute(sql)
            with database(db_path) as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM intent_responses").fetchone()[0], 1)

    def test_completed_and_frozen_assignments_are_never_rewritten(self):
        with scratch() as directory:
            db_path = ingest_synthetic(Path(directory))
            normalized = normalize_intent_response(intent_response())
            with database(db_path) as db:
                first = next_assignment(db, "viewer-a", repeats=False)
                record_intent_play(db, first["assignment_id"], "viewer-a", 1, 2)
                save_intent_response(db, first["assignment_id"], "viewer-a", normalized, 2)
                with self.assertRaisesRegex(ValueError, "already completed"):
                    save_intent_response(db, first["assignment_id"], "viewer-a", normalized, 2)
                with self.assertRaisesRegex(ValueError, "not found for rater"):
                    save_intent_response(db, first["assignment_id"], "viewer-b", normalized, 2)
                record_intent_freeze(db, "a" * 64, "json", 1)
                second = next_assignment(db, "viewer-a", repeats=False)
                with self.assertRaises(CollectionFrozen):
                    save_intent_response(db, second["assignment_id"], "viewer-a", normalized, 2)
                # No exposure is recorded after the freeze either.
                with self.assertRaises(CollectionFrozen):
                    record_intent_play(db, second["assignment_id"], "viewer-a", 1, 2)

    def test_play_starts_are_durable_ordered_limited_and_bind_the_response(self):
        with scratch() as directory:
            db_path = ingest_synthetic(Path(directory))
            with database(db_path) as db:
                aid = next_assignment(db, "viewer-a", repeats=False)["assignment_id"]
                with self.assertRaisesRegex(PlayRefused, "must be 1"):
                    record_intent_play(db, aid, "viewer-a", 2, 2)
                first = record_intent_play(db, aid, "viewer-a", 1, 2)
                self.assertEqual(first["plays_used"], 1)
                # A lost reply re-sends the same number: replayed, not counted twice.
                self.assertEqual(record_intent_play(db, aid, "viewer-a", 1, 2),
                                 {**first, "replayed": True})
                record_intent_play(db, aid, "viewer-a", 2, 2)
                with self.assertRaisesRegex(PlayRefused, "limit of 2"):
                    record_intent_play(db, aid, "viewer-a", 3, 2)
                with self.assertRaisesRegex(ValueError, "not found for rater"):
                    record_intent_play(db, aid, "viewer-b", 3, 2)
                self.assertEqual(intent_plays_used(db, aid), 2)
                # The response must report the recorded count, not a browser counter.
                for claimed in (1, 0):
                    with self.subTest(claimed=claimed), self.assertRaisesRegex(ValueError, "2 plays recorded"):
                        save_intent_response(db, aid, "viewer-a", normalize_intent_response(
                            intent_response(play_count=claimed)), 2)
                save_intent_response(db, aid, "viewer-a", normalize_intent_response(
                    intent_response(play_count=2)), 2)
                with self.assertRaisesRegex(PlayRefused, "already completed"):
                    record_intent_play(db, aid, "viewer-a", 3, 5)

    def test_intent_assignments_have_no_repeat_exposures(self):
        with scratch() as directory:
            db_path = ingest_synthetic(Path(directory), count=8)
            with database(db_path) as db:
                next_assignment(db, "viewer-a", repeats=False)
                next_assignment(db, "annotator-a")
                rows = {
                    rater: db.execute(
                        "SELECT COUNT(*), COUNT(DISTINCT artifact_sha256), COUNT(repeat_group) "
                        "FROM assignments WHERE rater_id=?", (rater,),
                    ).fetchone()
                    for rater in ("viewer-a", "annotator-a")
                }
            self.assertEqual(tuple(rows["viewer-a"]), (8, 8, 0))
            self.assertEqual(tuple(rows["annotator-a"]), (9, 8, 2))

    def test_one_database_serves_one_study(self):
        with scratch() as directory:
            root = Path(directory)
            (root / "a").mkdir()
            (root / "b").mkdir()
            annotation_db = ingest_synthetic(root / "a")
            intent_db = ingest_synthetic(root / "b")
            with database(annotation_db) as db:
                assignment = next_assignment(db, "annotator-a")
                save_annotation(db, assignment["assignment_id"], "annotator-a", {
                    "verdict": "PASS", "confidence": 3, "severity": 0, "reason_codes": [], "note": "",
                })
                self.assertIn("separate database", study_conflict(db, "intent"))
                self.assertIsNone(study_conflict(db, "annotation"))
            with database(intent_db) as db:
                assignment = next_assignment(db, "viewer-a", repeats=False)
                record_intent_play(db, assignment["assignment_id"], "viewer-a", 1, 2)
                save_intent_response(
                    db, assignment["assignment_id"], "viewer-a",
                    normalize_intent_response(intent_response()), 2,
                )
                self.assertIn("separate database", study_conflict(db, "annotation"))
                self.assertIsNone(study_conflict(db, "intent"))
            with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                cli_main(["serve", "--db", str(annotation_db), "--study", "intent"])


class IntentApiTests(unittest.TestCase):
    def serve(self, db_path, study="intent", play_limit=2):
        handler = type("TestHandler", (LabHandler,), {
            "db_path": db_path, "study": study,
            "play_limit": play_limit if study == "intent" else None,
            "log_message": lambda *args: None,
        })
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def stop():
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.addCleanup(stop)
        return f"http://127.0.0.1:{server.server_address[1]}"

    def post(self, url, payload):
        request = urllib.request.Request(
            url, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)

    def play(self, base, assignment_id, rater, number):
        return self.post(f"{base}/api/intent-plays/{assignment_id}?rater={rater}", {"play_number": number})

    def next(self, base, rater):
        with urllib.request.urlopen(f"{base}/api/next?rater={rater}") as response:
            raw = response.read().decode()
        return raw, json.loads(raw)

    def test_viewer_api_is_blinded_and_reports_only_the_study_mode(self):
        directory = self.enterContext(scratch())
        root = Path(directory)
        db_path = ingest_synthetic(root)
        base = self.serve(db_path)
        raw, body = self.next(base, "viewer-a")
        for hidden in ("SYN-INTENT", "clip0", str(root), "artifact_id", "sha256",
                       "defect", "repeat_group", "split", "intent_recovery"):
            self.assertNotIn(hidden, raw)
        with database(db_path) as db:
            for (digest,) in db.execute("SELECT sha256 FROM artifacts"):
                self.assertNotIn(digest, raw)
        self.assertEqual(body["study"], "intent")
        self.assertEqual(body["play_limit"], 2)
        self.assertEqual(body["plays_used"], 0)
        self.assertIs(body["collection_closed"], False)
        self.assertEqual(body["progress"], {"completed": 0, "total": 4})
        self.assertEqual(set(body["assignment"]), {
            "assignment_id", "sequence", "started_at", "mime_type", "modality",
            "review_label", "media_url",
        })
        with urllib.request.urlopen(f"{base}/api/health") as response:
            self.assertEqual(json.load(response)["study"], "intent")

    def test_intent_post_has_receipt_replay_conflict_and_rejection_semantics(self):
        directory = self.enterContext(scratch())
        db_path = ingest_synthetic(Path(directory))
        base = self.serve(db_path)
        assignment_id = self.next(base, "viewer-a")[1]["assignment"]["assignment_id"]
        url = f"{base}/api/intent-responses/{assignment_id}?rater=viewer-a"
        payload = intent_response()
        self.assertEqual(self.play(base, assignment_id, "viewer-a", 1)[0], 201)

        status, created = self.post(url, payload)
        self.assertEqual(status, 201)
        self.assertEqual(set(created), {"response_id", "completed_at"})
        # Whitespace-only differences normalize to the same saved response.
        padded = copy.deepcopy(payload)
        padded["components"]["support"]["recall"] += "  "
        status, replay = self.post(url, padded)
        self.assertEqual(status, 200)
        self.assertEqual(replay, {**created, "replayed": True})

        different = copy.deepcopy(payload)
        different["components"]["support"]["recall"] = "Something else"
        status, conflict = self.post(url, different)
        self.assertEqual(status, 409)
        # A conflict is not a closed collection; only a freeze sets the flag.
        self.assertNotIn("collection_closed", conflict)
        self.assertEqual(self.post(url, intent_response(play_count=3))[0], 400)
        self.assertEqual(self.post(url, intent_response(verdict="PASS"))[0], 400)
        # Another viewer cannot answer, or learn about, this assignment.
        status, error = self.post(f"{base}/api/intent-responses/{assignment_id}?rater=viewer-b", payload)
        self.assertEqual(status, 400)
        self.assertNotIn("response_id", error)
        # The PASS/HOLD endpoint is closed while the intent study runs.
        self.assertEqual(self.post(f"{base}/api/annotations/{assignment_id}?rater=viewer-a", {
            "verdict": "PASS", "confidence": 3, "severity": 0, "reason_codes": [],
        })[0], 404)

        with database(db_path) as db:
            rows = db.execute(
                "SELECT response_id, rater_id, components, play_count, play_limit, "
                "response_contract_version FROM intent_responses",
            ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["response_id"], created["response_id"])
        self.assertEqual(json.loads(rows[0]["components"]), payload["components"])
        self.assertEqual(tuple(rows[0])[1:], (
            "viewer-a", rows[0]["components"], 1, 2, "1.0.0",
        ))

    def test_phone_number_is_never_accepted_as_a_rater_id(self):
        directory = self.enterContext(scratch())
        db_path = ingest_synthetic(Path(directory))
        for study in ("intent", "annotation"):
            base = self.serve(db_path, study=study)
            for rater in ("305-555-0100", "3055550100", "rater_3055550100", "1-305-555-0100"):
                with self.subTest(study=study, rater=rater):
                    with self.assertRaises(urllib.error.HTTPError) as rejected:
                        urllib.request.urlopen(f"{base}/api/next?rater={rater}")
                    self.assertEqual(rejected.exception.code, 400)
                    self.assertIn("phone number", json.load(rejected.exception)["error"])
            for rater in ("rater-a", "viewer-20261014", "dryrun-viewer-1"):
                with self.subTest(study=study, rater=rater):
                    self.assertIn("assignment", self.next(base, rater)[1])
        with database(db_path) as db:
            stored = {row[0] for row in db.execute("SELECT DISTINCT rater_id FROM assignments")}
        # Rejected IDs never reached storage; only the pseudonyms did.
        self.assertEqual(stored, {"rater-a", "viewer-20261014", "dryrun-viewer-1"})

    def test_annotation_server_does_not_accept_intent_responses(self):
        directory = self.enterContext(scratch())
        db_path = ingest_synthetic(Path(directory))
        base = self.serve(db_path, study="annotation")
        raw, body = self.next(base, "annotator-a")
        self.assertEqual(body["study"], "annotation")
        self.assertIsNone(body["play_limit"])
        self.assertIsNone(body["plays_used"])
        assignment_id = body["assignment"]["assignment_id"]
        status, _ = self.post(
            f"{base}/api/intent-responses/{assignment_id}?rater=annotator-a", intent_response(),
        )
        self.assertEqual(status, 404)
        self.assertEqual(self.play(base, assignment_id, "annotator-a", 1)[0], 404)

    def test_reload_restores_exposure_and_the_response_reports_every_play(self):
        # Reviewer repro: exhaust both plays, reload / re-enter as the same
        # rater, try a third play, then save. The count must survive re-entry.
        directory = self.enterContext(scratch())
        db_path = ingest_synthetic(Path(directory))
        base = self.serve(db_path)
        assignment_id = self.next(base, "viewer-a")[1]["assignment"]["assignment_id"]
        status, first = self.play(base, assignment_id, "viewer-a", 1)
        self.assertEqual((status, first["plays_used"]), (201, 1))
        self.assertEqual(self.play(base, assignment_id, "viewer-a", 2)[0], 201)
        self.assertEqual(self.play(base, assignment_id, "viewer-a", 2)[0], 200)

        body = self.next(base, "viewer-a")[1]
        self.assertEqual(body["assignment"]["assignment_id"], assignment_id)
        self.assertEqual(body["plays_used"], 2)
        status, refused = self.play(base, assignment_id, "viewer-a", 3)
        self.assertEqual(status, 409)
        self.assertEqual(refused["plays_used"], 2)
        self.assertIn("limit", refused["error"])
        self.assertNotIn("collection_closed", refused)
        for bad in ({"play_number": 0}, {"play_number": "3"}, {"play_number": 1, "x": 1}, {}):
            with self.subTest(bad=bad):
                self.assertEqual(self.post(
                    f"{base}/api/intent-plays/{assignment_id}?rater=viewer-a", bad)[0], 400)
        # Another rater can neither play nor learn this assignment's count.
        status, other = self.play(base, assignment_id, "viewer-b", 3)
        self.assertEqual(status, 400)
        self.assertNotIn("plays_used", other)

        url = f"{base}/api/intent-responses/{assignment_id}?rater=viewer-a"
        status, error = self.post(url, intent_response(play_count=1))
        self.assertEqual(status, 400)
        self.assertIn("2 plays recorded", error["error"])
        self.assertEqual(self.post(url, intent_response(play_count=2))[0], 201)
        with database(db_path) as db:
            saved = db.execute("SELECT play_count FROM intent_responses").fetchone()[0]
            plays = db.execute("SELECT COUNT(*) FROM intent_plays").fetchone()[0]
        self.assertEqual((saved, plays), (2, 2))

    def test_freeze_exports_deterministic_bytes_and_closes_collection(self):
        directory = self.enterContext(scratch())
        root = Path(directory)
        db_path = ingest_synthetic(root)
        out = root / "exports" / "intent-responses.json"
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            cli_main(["export-intent", "--db", str(db_path), "--out", str(out)])
        self.assertFalse(out.exists())

        base = self.serve(db_path)
        first = self.next(base, "viewer-a")[1]["assignment"]["assignment_id"]
        first_url = f"{base}/api/intent-responses/{first}?rater=viewer-a"
        self.assertEqual(self.play(base, first, "viewer-a", 1)[0], 201)
        self.assertEqual(self.post(first_url, intent_response())[0], 201)

        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            self.assertEqual(cli_main(["export-intent", "--db", str(db_path), "--out", str(out)]), 0)
        body = out.read_bytes()
        digest = hashlib.sha256(body).hexdigest()
        self.assertIn(f"sha256 {digest}", printed.getvalue())
        exported = json.loads(body)
        self.assertEqual(exported["intent_response_contract_version"], "1.0.0")
        self.assertEqual(len(exported["responses"]), 1)
        for hidden in (b"SYN-INTENT", b"clip0", b"relative_path", b"artifact_id"):
            self.assertNotIn(hidden, body)
        with database(db_path) as db:
            self.assertEqual(export_intent_responses(db)[0], body)
            csv_body, count = export_intent_responses(db, "csv")
            freezes = db.execute("SELECT export_sha256, response_count FROM intent_freezes").fetchall()
        self.assertEqual([tuple(row) for row in freezes], [(digest, 1)])
        self.assertEqual(count, 1)
        header = csv_body.decode().splitlines()[0].split(",")
        self.assertIn("support_recall", header)
        self.assertIn("tone_could_not_tell", header)
        self.assertNotIn("components", header)

        # After the freeze, new responses are refused but an exact retry
        # of an already-saved response still gets its original receipt.
        # /api/next no longer offers it, so take the open assignment from storage.
        with database(db_path) as db:
            second = db.execute(
                "SELECT assignment_id FROM assignments WHERE rater_id='viewer-a' "
                "AND completed_at IS NULL ORDER BY sequence LIMIT 1",
            ).fetchone()[0]
        status, refused = self.play(base, second, "viewer-a", 1)
        self.assertEqual(status, 409)
        self.assertEqual((refused["collection_closed"], refused["plays_used"]), (True, 0))
        status, error = self.post(f"{base}/api/intent-responses/{second}?rater=viewer-a", intent_response())
        self.assertEqual(status, 409)
        self.assertIn("frozen", error["error"])
        self.assertIs(error["collection_closed"], True)
        self.assertEqual(self.post(first_url, intent_response())[0], 200)
        # A reload after the freeze offers no clip that could never be saved.
        body = self.next(base, "viewer-a")[1]
        self.assertIsNone(body["assignment"])
        self.assertIs(body["collection_closed"], True)
        self.assertIs(self.next(base, "viewer-new")[1]["collection_closed"], True)


if __name__ == "__main__":
    unittest.main()
