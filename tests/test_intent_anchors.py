"""Team C Sprint 5: drift anchors (contract, binding, blind sheet, coder check).

Every anchor here is invented test data, not study data.
"""
import contextlib
import copy
import csv
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from ouro_eval_lab.cli import main as cli_main
from ouro_eval_lab.contracts import INTENT_CODEBOOK_VERSION, ContractError
from ouro_eval_lab.intent_anchors import (
    ANCHOR_SHEET_FIELDS, AnchorRefused, check_coder, codebook_sha256, load_anchor_set,
    render_anchor_sheet, validate_anchor_set,
)

CODEBOOK_TEXT = "# Test codebook\n\nRule 1.\nRule 2.\n"


def _anchor(anchor_id, component, delivery, intended, viewer, code, rationale="Test rationale.",
            could_not_tell=False):
    return {
        "anchor_id": anchor_id, "component": component, "delivery": delivery,
        "intended_text": intended, "viewer_text": viewer,
        "viewer_could_not_tell": could_not_tell, "expected_code": code, "rationale": rationale,
    }


def anchor_set(codebook_digest):
    return {
        "schema": "team-c-intent-anchors",
        "contract_version": "1.0.0",
        "anchor_set_version": "test-1",
        "codebook_version": INTENT_CODEBOOK_VERSION,
        "codebook_sha256": codebook_digest,
        "fictional": True,
        "anchors": [
            _anchor("T1", "key_benefit", "explicit_text", "feels weightless", "so light you forget them", "recovered"),
            _anchor("T2", "key_benefit", "explicit_text", "feels weightless", "a comfortable shoe", "partially_recovered"),
            _anchor("T3", "support", "not_intended", "", "the lightest shoe ever", "not_applicable"),
            _anchor("T4", "call_to_action", "omitted_in_edit", "download free", "", "not_recovered",
                    could_not_tell=True),
        ],
    }


class AnchorContractTests(unittest.TestCase):
    def setUp(self):
        self.document = anchor_set("a" * 64)

    def assertRejected(self, pattern, mutate):
        document = copy.deepcopy(self.document)
        mutate(document)
        with self.assertRaisesRegex(ContractError, pattern):
            validate_anchor_set(document)

    def test_valid_set_passes(self):
        validate_anchor_set(self.document)

    def test_rejects_unknown_and_missing_fields(self):
        self.assertRejected("unknown fields: prompt", lambda d: d.update(prompt="x"))
        self.assertRejected("missing fields: fictional", lambda d: d.pop("fictional"))
        self.assertRejected("must contain exactly", lambda d: d["anchors"][0].update(clip="x"))

    def test_rejects_non_fictional_sets_and_bad_hashes(self):
        self.assertRejected("must be fictional", lambda d: d.update(fictional=False))
        self.assertRejected("64 lowercase hex", lambda d: d.update(codebook_sha256="A" * 64))

    def test_rejects_duplicate_ids_and_uncontrolled_values(self):
        self.assertRejected("T1 is duplicated", lambda d: d["anchors"][1].update(anchor_id="T1"))
        self.assertRejected("component", lambda d: d["anchors"][0].update(component="offer"))
        self.assertRejected("delivery", lambda d: d["anchors"][0].update(delivery="spoken"))

    def test_expected_code_follows_the_coding_rules(self):
        self.assertRejected("not_intended component must be coded not_applicable",
                            lambda d: d["anchors"][2].update(expected_code="not_recovered"))
        self.assertRejected("only for components whose delivery is not_intended",
                            lambda d: d["anchors"][0].update(expected_code="not_applicable"))
        self.assertRejected("codebook rule 5", lambda d: d["anchors"][3].update(expected_code="recovered"))

    def test_rejects_urls_and_contact_details_without_echoing_them(self):
        document = copy.deepcopy(self.document)
        document["anchors"][0]["viewer_text"] = "see www.example.test or 305-555-0100"
        with self.assertRaises(ContractError) as caught:
            validate_anchor_set(document)
        self.assertNotIn("example.test", str(caught.exception))
        self.assertIn("T1", str(caught.exception))


class AnchorBindingTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.codebook = self.root / "codebook.md"
        self.codebook.write_bytes(CODEBOOK_TEXT.encode())
        self.anchors = self.root / "anchors.json"
        self.anchors.write_bytes(json.dumps(anchor_set(codebook_sha256(self.codebook)), indent=2).encode())

    def test_codebook_hash_ignores_line_endings(self):
        crlf = self.root / "crlf.md"
        crlf.write_bytes(CODEBOOK_TEXT.replace("\n", "\r\n").encode())
        self.assertEqual(codebook_sha256(crlf), codebook_sha256(self.codebook))
        self.assertEqual(codebook_sha256(self.codebook), hashlib.sha256(CODEBOOK_TEXT.encode()).hexdigest())

    def test_loads_a_bound_set_and_checks_the_pinned_hash(self):
        digest = hashlib.sha256(self.anchors.read_bytes()).hexdigest()
        pinned = self.root / "anchors.sha256"
        pinned.write_text(f"{digest}  anchors.json\n")
        loaded = load_anchor_set(self.anchors, self.codebook, pinned)
        self.assertEqual(loaded["sha256"], digest)
        pinned.write_text("0" * 64 + "\n")
        with self.assertRaisesRegex(AnchorRefused, "does not match the pinned value"):
            load_anchor_set(self.anchors, self.codebook, pinned)

    def test_refuses_a_changed_codebook(self):
        self.codebook.write_bytes((CODEBOOK_TEXT + "Rule 3.\n").encode())
        with self.assertRaisesRegex(AnchorRefused, "codebook text has changed"):
            load_anchor_set(self.anchors, self.codebook)

    def test_refuses_anchors_for_another_codebook_version(self):
        document = json.loads(self.anchors.read_bytes())
        document["codebook_version"] = "0.0-old"
        self.anchors.write_bytes(json.dumps(document).encode())
        with self.assertRaisesRegex(AnchorRefused, "codebook 0.0-old"):
            load_anchor_set(self.anchors, self.codebook)

    def test_refuses_missing_or_malformed_files(self):
        with self.assertRaisesRegex(AnchorRefused, "not found"):
            load_anchor_set(self.root / "missing.json", self.codebook)
        self.anchors.write_bytes(b"{not json")
        with self.assertRaisesRegex(AnchorRefused, "not valid UTF-8 JSON"):
            load_anchor_set(self.anchors, self.codebook)


class AnchorCoderCheckTests(unittest.TestCase):
    def setUp(self):
        self.document = anchor_set("a" * 64)

    def filled(self, codes):
        rows = list(csv.DictReader(io.StringIO(render_anchor_sheet(self.document).decode())))
        for row in rows:
            code, confidence, note = codes[row["anchor_id"]]
            row.update(code=code, confidence=confidence, note=note)
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=ANCHOR_SHEET_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        return buffer.getvalue().encode()

    def test_sheet_is_blind(self):
        sheet = render_anchor_sheet(self.document).decode()
        self.assertEqual(sheet.splitlines()[0], ",".join(ANCHOR_SHEET_FIELDS))
        self.assertNotIn("expected_code", sheet)
        self.assertNotIn("Test rationale", sheet)
        self.assertNotIn("partially_recovered", sheet)

    def test_sheet_neutralizes_spreadsheet_formulas(self):
        self.document["anchors"][0]["viewer_text"] = "=1+1"
        self.assertIn("'=1+1", render_anchor_sheet(self.document).decode())

    def test_reports_matches_and_mismatches_by_id_only(self):
        body = self.filled({
            "T1": ("recovered", "3", ""), "T2": ("recovered", "2", ""),
            "T3": ("not_applicable", "3", ""), "T4": ("not_recovered", "3", ""),
        })
        result = check_coder(self.document, body)
        self.assertEqual((result["anchors"], result["matching"]), (4, 3))
        self.assertEqual(result["mismatches"], [{"anchor_id": "T2", "expected": "partially_recovered",
                                                 "given": "recovered"}])
        self.assertEqual(result["codes_sha256"], hashlib.sha256(body).hexdigest())
        self.assertNotIn("comfortable", json.dumps(result))

    def test_refuses_incomplete_duplicate_or_invalid_codes(self):
        complete = {
            "T1": ("recovered", "3", ""), "T2": ("partially_recovered", "2", "vaguer"),
            "T3": ("not_applicable", "3", ""), "T4": ("not_recovered", "3", ""),
        }
        lines = self.filled(complete).decode().splitlines()
        with self.assertRaisesRegex(AnchorRefused, "1 anchors not coded: T4"):
            check_coder(self.document, ("\n".join(lines[:-1]) + "\n").encode())
        with self.assertRaisesRegex(AnchorRefused, "coded twice"):
            check_coder(self.document, ("\n".join(lines + [lines[1]]) + "\n").encode())
        with self.assertRaisesRegex(AnchorRefused, "anchor T3.*not_applicable"):
            check_coder(self.document, self.filled({**complete, "T3": ("not_recovered", "3", "")}))
        with self.assertRaisesRegex(AnchorRefused, "a note is required"):
            check_coder(self.document, self.filled({**complete, "T2": ("partially_recovered", "2", "")}))
        with self.assertRaisesRegex(AnchorRefused, "need anchor_id, code"):
            check_coder(self.document, b"id,code\nT1,recovered\n")


class CommittedPracticeAnchorsTests(unittest.TestCase):
    """The codebook's practice anchors, committed as a draft set for calibration."""

    ROOT = Path(__file__).resolve().parents[1]

    def test_practice_anchors_match_the_codebook_and_their_pinned_hash(self):
        anchors = self.ROOT / "team_c" / "anchors"
        loaded = load_anchor_set(
            anchors / "practice_anchors.json", self.ROOT / "docs" / "INTENT_CODEBOOK.md",
            anchors / "practice_anchors.sha256",
        )
        # If the codebook changed on purpose, re-bind: put its new hash in the
        # set, then record the set's new SHA-256 in practice_anchors.sha256.
        document = loaded["document"]
        self.assertTrue(document["anchor_set_version"].startswith("practice-"))
        self.assertEqual(len(document["anchors"]), 11)
        codes = {anchor["expected_code"] for anchor in document["anchors"]}
        self.assertEqual(codes, {"recovered", "partially_recovered", "not_recovered", "contradicted",
                                 "not_applicable"})


class AnchorCliTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.codebook = self.root / "codebook.md"
        self.codebook.write_bytes(CODEBOOK_TEXT.encode())
        self.document = anchor_set(codebook_sha256(self.codebook))
        self.anchors = self.root / "anchors.json"
        self.anchors.write_bytes(json.dumps(self.document).encode())

    def run_cli(self, *args):
        with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()) as err:
            try:
                code = cli_main(["intent-anchors", *args, "--anchors", str(self.anchors),
                                 "--codebook", str(self.codebook)])
            except SystemExit as exit_:
                code = exit_.code
        return code, out.getvalue() + err.getvalue()

    def test_verify_sheet_and_check(self):
        code, printed = self.run_cli("verify")
        self.assertEqual(code, 0, printed)
        self.assertIn("4 anchors", printed)
        sheet = self.root / "sheet.csv"
        code, printed = self.run_cli("sheet", "--out", str(sheet))
        self.assertEqual(code, 0, printed)
        rows = list(csv.DictReader(io.StringIO(sheet.read_text(encoding="utf-8"))))
        expected = {a["anchor_id"]: a["expected_code"] for a in self.document["anchors"]}
        for row in rows:
            row.update(code=expected[row["anchor_id"]], confidence="3",
                       note="vaguer" if row["anchor_id"] == "T2" else "")
        with sheet.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=ANCHOR_SHEET_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        code, printed = self.run_cli("check", "--codes", str(sheet))
        self.assertEqual(code, 0, printed)
        self.assertIn("4 of 4 anchors match", printed)

    def test_refusals_exit_with_a_usage_error(self):
        self.codebook.write_bytes(b"changed\n")
        code, printed = self.run_cli("verify")
        self.assertEqual(code, 2)
        self.assertIn("codebook text has changed", printed)
        code, printed = self.run_cli("sheet")
        self.assertEqual(code, 2)
        self.assertIn("needs --out", printed)


if __name__ == "__main__":
    unittest.main()
