"""Team C Stage 2: blinded coder sheets and append-only code import.

All records and responses here are test-only fictions, not study data.
"""
import contextlib
import csv
import gc
import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from ouro_eval_lab.cli import main as cli_main
from ouro_eval_lab.coding import (
    SHEET_FIELDS, CodingRefused, import_codes, issue_sheet, response_sha256,
)
from ouro_eval_lab.contracts import INTENT_FIELDS, ContractError, validate_intent_code
from ouro_eval_lab.runner import export_intent_responses
from ouro_eval_lab.store import next_assignment, record_intent_freeze, save_intent_response
from tests.test_intent_reveal import Study, database

VIEWERS = ("viewer_a", "viewer_b")


def answer(recall="Fictional answer"):
    return {
        "components": {
            field: {"recall": recall, "certainty": 4, "could_not_tell": False} for field in INTENT_FIELDS
        },
        "other_beats": "",
        "play_count": 0,
    }


class CodingStudy(Study):
    """Two clips, two viewers who answered both, a real freeze, then the reveal."""

    def collect(self, recall="Fictional answer", viewers=VIEWERS):
        with database(self.db) as db:
            for viewer in viewers:
                while (assignment := next_assignment(db, viewer, repeats=False)) is not None:
                    save_intent_response(db, assignment["assignment_id"], viewer, answer(recall), 2)

    def freeze_and_reveal(self):
        with database(self.db) as db:
            body, count = export_intent_responses(db, "json")
            record_intent_freeze(db, hashlib.sha256(body).hexdigest(), "json", count)
        return self.reveal()

    def sheet(self, coder="coder_1", seed=20261014):
        with database(self.db) as db:
            db.execute("BEGIN IMMEDIATE")
            return issue_sheet(db, coder, seed)

    def import_codes(self, body, coder="coder_1"):
        with database(self.db) as db:
            db.execute("BEGIN IMMEDIATE")
            return import_codes(db, coder, body)

    def rows(self, table):
        with database(self.db) as db:
            return [dict(row) for row in db.execute(f"SELECT * FROM {table}")]


def read_sheet(body):
    return list(csv.DictReader(io.StringIO(body.decode(), newline="")))


def fill(rows, code="recovered", confidence="3", note=""):
    """Code every row; not_intended rows get not_applicable as the codebook requires."""
    for row in rows:
        row["code"] = "not_applicable" if row["delivery"] == "not_intended" else code
        row["confidence"], row["note"] = confidence, note
    return rows


def write(rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=SHEET_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


class IntentCodingSheetTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.addCleanup(gc.collect)
        self.study = CodingStudy(Path(directory))

    def test_sheet_is_refused_before_the_reveal(self):
        self.study.collect()
        with self.assertRaisesRegex(CodingRefused, "run export-intent and reveal first"):
            self.study.sheet()
        self.assertEqual(self.study.count("intent_coding_sheets"), 0)

    def test_sheet_lists_every_response_component_without_identifying_data(self):
        self.study.collect()
        self.study.freeze_and_reveal()
        result = self.study.sheet()
        rows = read_sheet(result["body"])
        self.assertEqual(list(rows[0]), SHEET_FIELDS)
        self.assertEqual(result["item_count"], 2 * 2 * len(INTENT_FIELDS))
        self.assertEqual(len({row["item_id"] for row in rows}), len(rows))
        self.assertEqual({row["code"] + row["confidence"] + row["note"] for row in rows}, {""})
        text = result["body"].decode()
        responses = self.study.rows("intent_responses")
        for secret in (*VIEWERS, *(r["response_id"] for r in responses),
                       *(a["artifact_id"] for a in self.study.artifacts),
                       *(a["sha256"] for a in self.study.artifacts), "certainty"):
            self.assertNotIn(secret, text)
        sheet = self.study.rows("intent_coding_sheets")
        self.assertEqual(len(sheet), 1)
        self.assertEqual(sheet[0]["seed"], 20261014)
        self.assertEqual(sheet[0]["codebook_version"], "0.1-draft")

    def test_coder_never_gets_a_clip_they_were_assigned_as_a_viewer(self):
        self.study.collect()
        with database(self.study.db) as db:
            # coder_1 was assigned clipA as a viewer but never answered it.
            db.execute("INSERT INTO assignments VALUES ('own', 'coder_1', ?, 0, NULL, NULL, NULL)",
                       (self.study.artifacts[0]["sha256"],))
        self.study.freeze_and_reveal()
        result = self.study.sheet()
        self.assertEqual(result["item_count"], 2 * len(INTENT_FIELDS))
        intended = {row["intended_text"] for row in read_sheet(result["body"])}
        self.assertTrue(intended)
        with self.assertRaisesRegex(CodingRefused, "viewed every clip"):
            self.study.sheet("viewer_a")

    def test_sheet_order_is_seeded_and_issued_once_per_coder(self):
        self.study.collect()
        self.study.freeze_and_reveal()
        first = self.study.sheet()
        again = self.study.sheet()
        self.assertTrue(again["reissued"])
        self.assertEqual(again["body"], first["body"])
        self.assertEqual(self.study.count("intent_coding_sheets"), 1)
        with self.assertRaisesRegex(CodingRefused, "one sheet per coder"):
            self.study.sheet(seed=7)
        other = self.study.sheet("coder_2")
        # Item IDs are per coder, so one coder's IDs are useless on another's sheet.
        self.assertFalse({r["item_id"] for r in read_sheet(other["body"])}
                         & {r["item_id"] for r in read_sheet(first["body"])})

    def test_formula_like_text_is_neutralized_for_spreadsheets(self):
        self.study.collect(recall="=HYPERLINK(1)")
        self.study.freeze_and_reveal()
        rows = read_sheet(self.study.sheet()["body"])
        self.assertTrue(all(row["viewer_recall"] == "'=HYPERLINK(1)" for row in rows))

    def test_coder_ids_must_be_pseudonymous(self):
        self.study.collect()
        self.study.freeze_and_reveal()
        with self.assertRaisesRegex(ValueError, "not a phone number"):
            self.study.sheet("305-555-0100")


class IntentCodeImportTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.addCleanup(gc.collect)
        self.study = CodingStudy(Path(directory))

    def ready(self, **seal):
        if seal:
            self.study.seal(**seal)
        self.study.collect()
        self.study.freeze_and_reveal()
        return read_sheet(self.study.sheet()["body"])

    def test_codes_are_bound_to_the_exact_response_record_and_clip(self):
        rows = self.ready()
        result = self.study.import_codes(write(fill(rows)))
        self.assertEqual((result["coded"], result["unchanged"], result["uncoded"]), (len(rows), 0, 0))
        with database(self.study.db) as db:
            responses = {r["response_id"]: r for r in db.execute("SELECT * FROM intent_responses")}
            records = {r["artifact_sha256"]: r["record_sha256"]
                       for r in db.execute("SELECT * FROM intent_records")}
        codings = self.study.rows("intent_codings")
        self.assertEqual(len(codings), len(rows))
        for coding in codings:
            response = responses[coding["response_id"]]
            self.assertEqual(coding["response_sha256"], response_sha256(response))
            self.assertEqual(coding["artifact_sha256"], response["artifact_sha256"])
            self.assertEqual(coding["record_sha256"], records[response["artifact_sha256"]])
            self.assertEqual(coding["coder_id"], "coder_1")
        self.assertEqual({(c["response_id"], c["component"]) for c in codings},
                         {(r, f) for r in responses for f in INTENT_FIELDS})
        imports = self.study.rows("intent_code_imports")
        self.assertEqual(len(imports), 1)
        self.assertEqual(imports[0]["import_sha256"], result["import_sha256"])

    def test_partial_import_then_identical_reimport_is_a_no_op(self):
        rows = self.ready()
        fill(rows[:5])
        first = self.study.import_codes(write(rows))
        self.assertEqual((first["coded"], first["uncoded"]), (5, len(rows) - 5))
        again = self.study.import_codes(write(rows))
        self.assertEqual((again["coded"], again["unchanged"], again["import_id"]), (0, 5, None))
        self.assertEqual(self.study.count("intent_code_imports"), 1)
        fill(rows)
        rest = self.study.import_codes(write(rows))
        self.assertEqual((rest["coded"], rest["unchanged"]), (len(rows) - 5, 5))
        self.assertEqual(self.study.count("intent_codings"), len(rows))

    def test_a_changed_code_is_refused_and_nothing_is_written(self):
        rows = self.ready()
        self.study.import_codes(write(fill(rows[:1]) + rows[1:]))
        rows[0]["code"], rows[0]["note"] = "contradicted", "states a different benefit"
        fill(rows[1:])
        with self.assertRaisesRegex(CodingRefused, "codes are append-only"):
            self.study.import_codes(write(rows))
        self.assertEqual(self.study.count("intent_codings"), 1)
        self.assertEqual(self.study.rows("intent_codings")[0]["code"], "recovered")

    def test_items_from_another_coders_sheet_and_duplicates_are_refused(self):
        rows = self.ready()
        other = read_sheet(self.study.sheet("coder_2")["body"])
        with self.assertRaisesRegex(CodingRefused, "not on this coder's sheet"):
            self.study.import_codes(write(fill(other[:1])))
        with self.assertRaisesRegex(CodingRefused, "appears more than once"):
            self.study.import_codes(write(fill([rows[0], dict(rows[0])])))
        with self.assertRaisesRegex(CodingRefused, "no coding sheet was issued"):
            self.study.import_codes(write(fill(rows[:1])), coder="coder_3")
        self.assertEqual(self.study.count("intent_codings"), 0)

    def test_not_intended_components_must_be_not_applicable(self):
        delivery = {field: "explicit_text" for field in INTENT_FIELDS}
        delivery["support"] = "not_intended"
        intended = {field: f"Fictional {field}" for field in INTENT_FIELDS}
        intended["support"] = ""
        rows = self.ready(delivery=delivery, intended=intended)
        support = [row for row in rows if row["component"] == "support"]
        self.assertTrue(support and all(row["delivery"] == "not_intended" for row in support))
        bad = [dict(row, code="not_recovered", confidence="3", note="") for row in support[:1]]
        with self.assertRaisesRegex(CodingRefused, "must be coded not_applicable"):
            self.study.import_codes(write(bad))
        self.assertEqual(self.study.import_codes(write(fill(rows)))["coded"], len(rows))

    def test_one_bad_row_rejects_the_whole_file(self):
        rows = fill(self.ready())
        rows[3]["confidence"] = "5"
        with self.assertRaisesRegex(CodingRefused, "confidence must be 1, 2 or 3"):
            self.study.import_codes(write(rows))
        self.assertEqual(self.study.count("intent_codings"), 0)
        self.assertEqual(self.study.count("intent_code_imports"), 0)

    def test_missing_columns_are_refused(self):
        self.ready()
        with self.assertRaisesRegex(CodingRefused, "missing columns: confidence"):
            self.study.import_codes(b"item_id,code,note\n")

    def test_excel_byte_order_mark_is_accepted(self):
        rows = fill(self.ready())
        self.assertEqual(self.study.import_codes(b"\xef\xbb\xbf" + write(rows))["coded"], len(rows))

    def test_stored_codes_are_append_only(self):
        self.study.import_codes(write(fill(self.ready())))
        with database(self.study.db) as db:
            for statement in ("UPDATE intent_codings SET code = 'contradicted'",
                              "DELETE FROM intent_codings",
                              "DELETE FROM intent_coding_sheets",
                              "UPDATE intent_code_imports SET coded_count = 0"):
                with self.subTest(statement=statement), self.assertRaises(sqlite3.IntegrityError):
                    db.execute(statement)


class IntentCodeContractTests(unittest.TestCase):
    def test_valid_code_is_normalized(self):
        self.assertEqual(validate_intent_code(" recovered ", "2", " ", "implied"),
                         {"code": "recovered", "confidence": 2, "note": ""})

    def test_invalid_codes_name_the_rule_not_the_value(self):
        cases = [
            (("maybe", "2", "", "implied"), "code must be one of"),
            (("recovered", "0", "", "implied"), "confidence must be 1, 2 or 3"),
            (("recovered", "2.0", "", "implied"), "confidence must be 1, 2 or 3"),
            (("not_applicable", "3", "", "implied"), "only for components whose delivery is not_intended"),
            (("partially_recovered", "2", "", "implied"), "a note is required"),
            (("recovered", "1", "", "implied"), "a note is required"),
            (("recovered", "3", "mail me at a@b.example", "implied"), "contact details"),
            (("recovered", "3", "x" * 301, "implied"), "at most 300"),
        ]
        for args, message in cases:
            with self.subTest(args=args[:2]), self.assertRaisesRegex(ContractError, message):
                validate_intent_code(*args)


class IntentCodingCliTests(unittest.TestCase):
    def test_sheet_and_import_through_the_cli(self):
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.addCleanup(gc.collect)
        study = CodingStudy(directory)
        study.collect()
        study.freeze_and_reveal()
        sheet = directory / "sheets" / "coder_1.csv"
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cli_main(["intent-coding-sheet", "--db", str(study.db), "--coder", "coder_1", "--out", str(sheet)])
        self.assertIn("issued a sheet of 28 items", out.getvalue())
        filled = directory / "filled.csv"
        filled.write_bytes(write(fill(read_sheet(sheet.read_bytes()))))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cli_main(["intent-import-codes", "--db", str(study.db), "--coder", "coder_1",
                      "--codes", str(filled)])
        self.assertIn("imported 28 codes (0 already stored, 0 left blank)", out.getvalue())
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            cli_main(["intent-import-codes", "--db", str(study.db), "--coder", "coder_9",
                      "--codes", str(filled)])


if __name__ == "__main__":
    unittest.main()
