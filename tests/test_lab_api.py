import hashlib
import json
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from ouro_eval_lab.api import LabHandler
from ouro_eval_lab.store import connect, ingest, next_assignment, save_annotation


class LabApiTests(unittest.TestCase):
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
