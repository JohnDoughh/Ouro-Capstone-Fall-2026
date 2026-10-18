import csv
import hashlib
import io
import json
import re
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from ouro_eval_lab.api import LabHandler
from ouro_eval_lab.contracts import (
    ANNOTATION_CONTRACT_VERSION, EVIDENCE_FIELDS, TEAM_A_RUBRIC_FAMILIES, ContractError,
    validate_annotation_payload,
)
from ouro_eval_lab.runner import EXPORT_FIELDS, export_annotations
from ouro_eval_lab.store import connect, ingest, initialize

ONTOLOGY = Path(__file__).resolve().parents[1] / "docs" / "team_a" / "ontology.yaml"
REFERENCE_SHA256 = hashlib.sha256(b"Synthetic approved claim reference: COLD 24 H").hexdigest()
FAMILY_4_HOLD = {
    "verdict": "HOLD", "confidence": 4, "severity": 2,
    "defect_timestamps": "00:06-00:09",
    "rubric_version": "v0.1", "defect_family_id": 4,
    "region": "orange claim badge, lower right of the carton",
    "reference_id": REFERENCE_SHA256,
    "evidence_description": "Badge reads COLD 12 H; the approved reference says COLD 24 H.",
    "reason_codes": ["visual_integrity"], "note": "Synthetic evidence round trip",
}


def _synthetic_artifacts(root: Path, count: int) -> dict:
    artifacts = []
    for index in range(count):
        body = f"Synthetic evidence fixture {index}".encode()
        (root / f"fixture-{index}.txt").write_bytes(body)
        artifacts.append({
            "sha256": hashlib.sha256(body).hexdigest(), "artifact_id": f"synthetic-{index}",
            "relative_path": f"fixture-{index}.txt", "byte_length": len(body),
            "mime_type": "text/plain", "modality": "text", "split": "development",
            "defect_family": "synthetic", "defect_present": 0, "synthetic": 1,
        })
    return {"artifacts": artifacts}


class EvidenceContractTests(unittest.TestCase):
    def test_family_4_hold_with_reference_is_valid(self):
        validate_annotation_payload(FAMILY_4_HOLD)

    def test_hold_without_evidence_stays_valid(self):
        validate_annotation_payload({key: value for key, value in FAMILY_4_HOLD.items()
                                     if key not in EVIDENCE_FIELDS})

    def test_pass_and_unsure_reject_evidence_but_accept_empty_fields(self):
        for verdict in ("PASS", "UNSURE"):
            base = {"verdict": verdict, "confidence": 3, "severity": 0, "reason_codes": []}
            validate_annotation_payload({**base, **{field: None for field in EVIDENCE_FIELDS}})
            validate_annotation_payload({**base, "region": "", "evidence_description": ""})
            with self.subTest(verdict=verdict), self.assertRaisesRegex(ContractError, "cannot include evidence"):
                validate_annotation_payload({**base, "region": "center"})

    def test_evidence_is_anchored_to_a_known_rubric_family(self):
        invalid = [
            ({"rubric_version": None}, "both rubric_version and defect_family_id"),
            ({"defect_family_id": None}, "both rubric_version and defect_family_id"),
            ({"rubric_version": "v9.9"}, "known Team A rubric version"),
            ({"defect_family_id": 7}, "defect_family_id must be one of"),
            ({"defect_family_id": "4"}, "defect_family_id must be one of"),
            ({"defect_family_id": True}, "defect_family_id must be one of"),
            ({"region": "x" * 241}, "region must be a string"),
            ({"evidence_description": "x" * 501}, "evidence_description must be a string"),
            ({"reference_id": None}, "requires reference_id"),
            ({"reference_id": REFERENCE_SHA256.upper()}, "requires reference_id"),
            ({"defect_family_id": 5}, "does not use a reference"),
        ]
        for change, message in invalid:
            with self.subTest(change=change), self.assertRaisesRegex(ContractError, message):
                validate_annotation_payload({**FAMILY_4_HOLD, **change})
        validate_annotation_payload({**FAMILY_4_HOLD, "defect_family_id": 5, "reference_id": None})

    @unittest.skipUnless(ONTOLOGY.exists(), "Team A ontology.yaml is not on this branch yet")
    def test_rubric_families_match_the_team_a_ontology_file(self):
        text = ONTOLOGY.read_text()
        version = re.search(r'^rubric_version:\s*"([^"]+)"', text, re.MULTILINE).group(1)
        families = {
            int(family_id): flag == "true"
            for family_id, flag in re.findall(r"- id:\s*(\d+).*?requires_reference:\s*(true|false)", text, re.DOTALL)
        }
        self.assertEqual(TEAM_A_RUBRIC_FAMILIES[version], families)


class EvidenceStorageExportTests(unittest.TestCase):
    def test_family_4_evidence_survives_api_storage_and_both_exports(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db_path = root / "lab.db"
            ingest(db_path, _synthetic_artifacts(root, 3), root)
            handler = type("TestHandler", (LabHandler,), {"db_path": db_path, "log_message": lambda *args: None})
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_address[1]}"

                def submit(payload: dict) -> tuple[int, dict, str]:
                    with urllib.request.urlopen(f"{base}/api/next?rater=rater-a") as response:
                        assignment_id = json.load(response)["assignment"]["assignment_id"]
                    status, receipt = post(assignment_id, payload)
                    return status, receipt, assignment_id

                def post(assignment_id: str, payload: dict) -> tuple[int, dict]:
                    request = urllib.request.Request(
                        f"{base}/api/annotations/{assignment_id}?rater=rater-a",
                        data=json.dumps(payload).encode(),
                        headers={"Content-Type": "application/json"}, method="POST",
                    )
                    with urllib.request.urlopen(request) as response:
                        return response.status, json.load(response)

                status, hold, hold_assignment = submit(FAMILY_4_HOLD)
                self.assertEqual(status, 201)
                self.assertEqual(post(hold_assignment, FAMILY_4_HOLD)[1]["replayed"], True)
                with self.assertRaises(urllib.error.HTTPError) as conflict:
                    post(hold_assignment, {**FAMILY_4_HOLD, "region": "upper left"})
                self.assertEqual(conflict.exception.code, 409)
                with self.assertRaises(urllib.error.HTTPError) as rejected:
                    submit({"verdict": "PASS", "confidence": 5, "severity": 0,
                            "reason_codes": [], "region": "center"})
                self.assertEqual(rejected.exception.code, 400)
                plain = {"confidence": 5, "severity": 0, "reason_codes": [], "note": ""}
                self.assertEqual(submit({**plain, "verdict": "PASS"})[0], 201)
                self.assertEqual(submit({**plain, "verdict": "UNSURE", "confidence": 1})[0], 201)

                with connect(db_path) as db:
                    artifact_sha256 = db.execute(
                        "SELECT artifact_sha256 FROM assignments WHERE assignment_id=?", (hold_assignment,),
                    ).fetchone()[0]
                    exported_json = json.loads(export_annotations(db, "json"))
                    exported_csv = list(csv.DictReader(io.StringIO(export_annotations(db, "csv"))))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

            self.assertEqual(exported_json["annotation_contract_version"], ANNOTATION_CONTRACT_VERSION)
            self.assertEqual(len(exported_json["annotations"]), 3)
            by_verdict = {row["verdict"]: row for row in exported_json["annotations"]}
            saved = by_verdict["HOLD"]
            expected = {
                "annotation_id": hold["annotation_id"], "rater_id": "rater-a",
                "artifact_sha256": artifact_sha256, "confidence_scale": "1-5",
                **FAMILY_4_HOLD,
            }
            for field, value in expected.items():
                with self.subTest(export="json", field=field):
                    self.assertEqual(saved[field], value)
                    self.assertIs(type(saved[field]), float if field == "confidence" else type(value))
            for verdict in ("PASS", "UNSURE"):
                for field in EVIDENCE_FIELDS:
                    with self.subTest(export="json", verdict=verdict, field=field):
                        self.assertIsNone(by_verdict[verdict][field])

            self.assertEqual(list(exported_csv[0]), EXPORT_FIELDS)
            csv_by_verdict = {row["verdict"]: row for row in exported_csv}
            csv_expected = {**expected, "confidence": "4.0",
                            "reason_codes": "|".join(FAMILY_4_HOLD["reason_codes"])}
            for field, value in csv_expected.items():
                with self.subTest(export="csv", field=field):
                    self.assertEqual(csv_by_verdict["HOLD"][field], str(value))
            for verdict in ("PASS", "UNSURE"):
                for field in EVIDENCE_FIELDS:
                    with self.subTest(export="csv", verdict=verdict, field=field):
                        self.assertEqual(csv_by_verdict[verdict][field], "")


class EvidenceMigrationTests(unittest.TestCase):
    def test_fresh_database_has_every_evidence_column(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "fresh.db"
            initialize(db_path)
            with connect(db_path) as db:
                columns = {row["name"] for row in db.execute("PRAGMA table_info(annotations)")}
            self.assertTrue(set(EVIDENCE_FIELDS) <= columns)
            self.assertTrue(set(EXPORT_FIELDS) <= columns)

    def test_existing_2_1_database_keeps_every_row_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "existing.db"
            db = sqlite3.connect(db_path)
            db.execute("""CREATE TABLE annotations (
                annotation_id TEXT PRIMARY KEY, assignment_id TEXT UNIQUE NOT NULL, rater_id TEXT NOT NULL,
                artifact_sha256 TEXT NOT NULL, verdict TEXT NOT NULL, confidence REAL NOT NULL,
                confidence_scale TEXT NOT NULL DEFAULT '1-5', severity INTEGER, defect_timestamps TEXT,
                reason_codes TEXT NOT NULL, note TEXT NOT NULL, started_at TEXT NOT NULL,
                completed_at TEXT NOT NULL)""")
            rows = [
                ("a1", "s1", "rater-a", "a" * 64, "HOLD", 4.0, "1-5", 3, "00:01", '["visual_integrity"]',
                 "kept", "2026-10-01T00:00:00+00:00", "2026-10-01T00:01:00+00:00"),
                ("a2", "s2", "rater-b", "b" * 64, "PASS", 0.25, "legacy-0-1", None, None, "[]",
                 "", "2026-09-01T00:00:00+00:00", "2026-09-01T00:01:00+00:00"),
            ]
            db.executemany("INSERT INTO annotations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
            db.commit()
            db.close()

            initialize(db_path)
            initialize(db_path)  # Re-running the migration is a no-op.
            with connect(db_path) as db:
                after = [tuple(row) for row in db.execute(
                    "SELECT annotation_id, assignment_id, rater_id, artifact_sha256, verdict, confidence, "
                    "confidence_scale, severity, defect_timestamps, reason_codes, note, started_at, completed_at "
                    "FROM annotations ORDER BY annotation_id")]
                evidence = db.execute(
                    "SELECT " + ", ".join(EVIDENCE_FIELDS) + " FROM annotations").fetchall()
                exported = json.loads(export_annotations(db))["annotations"]
            self.assertEqual(after, rows)
            self.assertEqual([tuple(row) for row in evidence], [(None,) * len(EVIDENCE_FIELDS)] * 2)
            self.assertEqual([row["confidence_scale"] for row in exported], ["legacy-0-1", "1-5"])
            for row in exported:
                for field in EVIDENCE_FIELDS:
                    self.assertIsNone(row[field])


if __name__ == "__main__":
    unittest.main()
