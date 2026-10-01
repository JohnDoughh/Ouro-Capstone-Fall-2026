import hashlib
import json
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer
from pathlib import Path

from ouro_eval_lab.api import LabHandler
from ouro_eval_lab.runner import export_annotations
from ouro_eval_lab.store import connect, ingest, next_assignment, save_annotation


class LabApiTests(unittest.TestCase):
    def test_reviewer_metadata_is_blinded_without_changing_saved_media_bindings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_id = "SYN-ORBIT-CLEAN"
            fixture = root / "clean.txt"
            original = b"Synthetic observation exercise."
            fixture.write_bytes(original)
            digest = hashlib.sha256(original).hexdigest()
            db_path = root / "lab.db"
            ingest(db_path, {"artifacts": [{
                "sha256": digest, "artifact_id": source_id,
                "relative_path": fixture.name, "byte_length": len(original),
                "mime_type": "text/plain", "modality": "text", "split": "practice",
                "defect_family": "synthetic", "defect_present": 0, "synthetic": 1,
            }]}, root)
            # Existing assignments, as well as fresh ones, must receive the fix.
            with connect(db_path) as db:
                next_assignment(db, "rater-a")
                source_before = dict(db.execute("SELECT * FROM artifacts").fetchone())
            handler = type("TestHandler", (LabHandler,), {
                "db_path": db_path, "log_message": lambda *args: None,
            })
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_address[1]}"

                def get_assignment():
                    with urllib.request.urlopen(f"{base}/api/next?rater=rater-a") as response:
                        raw = response.read().decode()
                    for hidden in (source_id, fixture.name, digest, str(root),
                                   "defect_present", "defect_family", "repeat_group", "split",
                                   "artifact_id", "evaluator"):
                        self.assertNotIn(hidden, raw)
                    assignment = json.loads(raw)["assignment"]
                    self.assertEqual(set(assignment), {
                        "assignment_id", "sequence", "started_at", "mime_type", "modality",
                        "review_label", "media_url",
                    })
                    return assignment

                assignment = get_assignment()
                self.assertEqual(assignment["review_label"], "Item 001")
                self.assertEqual(get_assignment(), assignment)
                with urllib.request.urlopen(base + assignment["media_url"]) as response:
                    self.assertEqual(response.read(), original)
                    self.assertNotIn(fixture.name, str(response.headers))
                payload = {
                    "verdict": "UNSURE", "confidence": 2, "severity": 1,
                    "reason_codes": [], "note": "Synthetic observation",
                }
                request = urllib.request.Request(
                    f"{base}/api/annotations/{assignment['assignment_id']}?rater=rater-a",
                    data=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json"}, method="POST",
                )
                with urllib.request.urlopen(request) as response:
                    self.assertEqual(response.status, 201)
                    receipt = json.load(response)
                repeated = get_assignment()
                self.assertEqual(repeated["review_label"], "Item 002")
                self.assertNotEqual(repeated["assignment_id"], assignment["assignment_id"])
                with connect(db_path) as db:
                    source_after = dict(db.execute("SELECT * FROM artifacts").fetchone())
                    exported = json.loads(export_annotations(db))["annotations"]
                    self.assertEqual(db.execute(
                        "SELECT assignment_id FROM annotations WHERE annotation_id=?",
                        (receipt["annotation_id"],),
                    ).fetchone()[0], assignment["assignment_id"])
                    self.assertEqual(db.execute(
                        "SELECT artifact_sha256 FROM assignments WHERE assignment_id=?",
                        (repeated["assignment_id"],),
                    ).fetchone()[0], digest)
                self.assertEqual(source_before, source_after)
                self.assertEqual(len(exported), 1)
                self.assertEqual(exported[0]["artifact_sha256"], digest)
                self.assertEqual(exported[0]["annotation_id"], receipt["annotation_id"])
                self.assertEqual(exported[0]["verdict"], "UNSURE")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_annotation_retry_returns_original_receipt_without_rewriting_judgment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db_path = root / "lab.db"
            ingest(db_path, {"artifacts": [{
                "sha256": "a" * 64,
                "artifact_id": "synthetic-a",
                "relative_path": "synthetic.txt",
                "byte_length": 9,
                "mime_type": "text/plain",
                "modality": "text",
                "split": "practice",
                "defect_family": "synthetic",
                "defect_present": 1,
                "synthetic": 1,
            }]}, root)
            handler = type("TestHandler", (LabHandler,), {
                "db_path": db_path,
                "log_message": lambda *args: None,
            })
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_address[1]}"

                def post(rater: str, assignment_id: str, payload: dict):
                    request = urllib.request.Request(
                        f"{base}/api/annotations/{assignment_id}?rater={rater}",
                        data=json.dumps(payload).encode(),
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with urllib.request.urlopen(request) as response:
                        return response.status, json.load(response)

                payload = {
                    "verdict": "HOLD", "confidence": 4, "severity": 2,
                    "defect_timestamps": " 00:01-00:02 ",
                    "reason_codes": ["visual_integrity"],
                    "note": "Synthetic test annotation",
                }
                with urllib.request.urlopen(f"{base}/api/next?rater=synthetic-rater") as response:
                    assignment_id = json.load(response)["assignment"]["assignment_id"]
                created_status, created = post("synthetic-rater", assignment_id, payload)
                self.assertEqual(created_status, 201)
                replay_status, replay = post("synthetic-rater", assignment_id, payload)
                self.assertEqual(replay_status, 200)
                self.assertEqual(replay["annotation_id"], created["annotation_id"])
                self.assertEqual(replay["completed_at"], created["completed_at"])
                self.assertIs(replay["replayed"], True)
                # A different judgment is never treated as an idempotent retry.
                changed = {**payload, "verdict": "PASS"}
                with self.assertRaises(urllib.error.HTTPError) as conflict:
                    post("synthetic-rater", assignment_id, changed)
                self.assertEqual(conflict.exception.code, 409)
                with connect(db_path) as db:
                    rows = db.execute(
                        "SELECT annotation_id, verdict, defect_timestamps FROM annotations WHERE assignment_id=?",
                        (assignment_id,),
                    ).fetchall()
                self.assertEqual(len(rows), 1)
                self.assertEqual(tuple(rows[0]), (created["annotation_id"], "HOLD", "00:01-00:02"))

                invalid = {**payload, "reason_codes": ["not-a-public-reason"]}
                with self.assertRaises(urllib.error.HTTPError) as rejected:
                    post("synthetic-rater", assignment_id, invalid)
                self.assertEqual(rejected.exception.code, 400)

                # Two first submissions may race; BEGIN IMMEDIATE makes the
                # later request observe the first commit and replay its receipt.
                with urllib.request.urlopen(f"{base}/api/next?rater=synthetic-rater-2") as response:
                    second_id = json.load(response)["assignment"]["assignment_id"]
                barrier = threading.Barrier(2)

                def concurrent_post():
                    barrier.wait(timeout=5)
                    return post("synthetic-rater-2", second_id, payload)

                with ThreadPoolExecutor(max_workers=2) as executor:
                    futures = [executor.submit(concurrent_post) for _ in range(2)]
                    results = [future.result(timeout=10) for future in futures]
                self.assertEqual(sorted(status for status, _ in results), [200, 201])
                self.assertEqual(len({receipt["annotation_id"] for _, receipt in results}), 1)
                with connect(db_path) as db:
                    self.assertEqual(db.execute(
                        "SELECT COUNT(*) FROM annotations WHERE assignment_id=?", (second_id,)
                    ).fetchone()[0], 1)

                # A real SQLite writer lock is not misreported as a
                # validation/no-write response. The same payload remains safe
                # to submit when the lock goes away.
                with urllib.request.urlopen(f"{base}/api/next?rater=synthetic-rater-3") as response:
                    third_id = json.load(response)["assignment"]["assignment_id"]
                with connect(db_path) as locked:
                    locked.execute("BEGIN IMMEDIATE")
                    with self.assertRaises(urllib.error.HTTPError) as unavailable:
                        post("synthetic-rater-3", third_id, payload)
                    self.assertEqual(unavailable.exception.code, 503)
                    self.assertIn("status unknown", json.load(unavailable.exception)["error"])
                self.assertEqual(post("synthetic-rater-3", third_id, payload)[0], 201)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_aggregates_are_offline_only_during_collection(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "lab.db"
            report_path = Path(directory) / "agreement.json"
            ingest(db_path, {"artifacts": [{
                "sha256": "a" * 64,
                "artifact_id": "synthetic-a",
                "relative_path": "synthetic.txt",
                "byte_length": 9,
                "mime_type": "text/plain",
                "modality": "text",
                "split": "practice",
                "defect_family": "synthetic",
                "defect_present": 1,
                "synthetic": 1,
            }]}, Path(directory))
            with connect(db_path) as db:
                for rater_id in ("synthetic-rater-1", "synthetic-rater-2"):
                    assignment = next_assignment(db, rater_id)
                    save_annotation(db, assignment["assignment_id"], rater_id, {
                        "verdict": "HOLD",
                        "confidence": 4,
                        "severity": 2,
                        "reason_codes": ["wrong-fact"],
                        "note": "Synthetic test annotation",
                    })
            handler = type("TestHandler", (LabHandler,), {
                "db_path": db_path,
                "log_message": lambda *args: None,
            })
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                url = f"http://127.0.0.1:{server.server_address[1]}/api/agreement"
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    urllib.request.urlopen(url)
                self.assertEqual(caught.exception.code, 404)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

            command = subprocess.run(
                [sys.executable, "-m", "ouro_eval_lab.cli", "agreement",
                 "--db", str(db_path), "--out", str(report_path)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(command.returncode, 0, command.stderr)
            self.assertEqual(json.loads(report_path.read_text())["pair_count"], 1)

    def test_offline_agreement_does_not_create_an_empty_database(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "missing.db"
            command = subprocess.run(
                [sys.executable, "-m", "ouro_eval_lab.cli", "agreement",
                 "--db", str(db_path), "--out", str(Path(directory) / "report.json")],
                capture_output=True, text=True, check=False,
            )
            self.assertNotEqual(command.returncode, 0)
            self.assertFalse(db_path.exists())

    def test_media_endpoint_rejects_same_length_tampering_and_missing_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "synthetic.txt"
            original = b"correct!!"
            fixture.write_bytes(original)
            db_path = root / "lab.db"
            ingest(db_path, {"artifacts": [{
                "sha256": hashlib.sha256(original).hexdigest(),
                "artifact_id": "synthetic-media",
                "relative_path": fixture.name,
                "byte_length": len(original),
                "mime_type": "text/plain",
                "modality": "text",
                "split": "practice",
                "defect_family": "synthetic",
                "defect_present": 1,
                "synthetic": 1,
            }]}, root)
            handler = type("TestHandler", (LabHandler,), {
                "db_path": db_path,
                "log_message": lambda *args: None,
            })
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_address[1]}"
                with urllib.request.urlopen(f"{base}/api/next?rater=synthetic-rater") as response:
                    media_url = json.load(response)["assignment"]["media_url"]
                fixture.write_bytes(b"changed!!")  # Same length, different SHA-256.
                with self.assertRaises(urllib.error.HTTPError) as tampered:
                    urllib.request.urlopen(base + media_url)
                self.assertEqual(tampered.exception.code, 409)
                fixture.unlink()
                with self.assertRaises(urllib.error.HTTPError) as missing:
                    urllib.request.urlopen(base + media_url)
                self.assertEqual(missing.exception.code, 404)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
