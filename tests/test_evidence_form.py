import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

from ouro_eval_lab.contracts import EVIDENCE_FIELDS, TEAM_A_RUBRIC_FAMILIES

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "ouro_eval_lab" / "web" / "index.html"
ONTOLOGY = ROOT / "docs" / "team_a" / "ontology.yaml"


class _EvidenceSection(HTMLParser):
    """Collects control names and select options inside #evidence-fields."""

    def __init__(self):
        super().__init__()
        self.depth = 0
        self.names: list[str] = []
        self.options: dict[str, list[tuple[str, str]]] = {}
        self._select = None
        self._option = None
        self.text: list[str] = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id") == "evidence-fields":
            self.depth = 1
            return
        if not self.depth:
            return
        if tag == "fieldset":
            self.depth += 1
        if tag in {"input", "select", "textarea"} and attrs.get("name"):
            self.names.append(attrs["name"])
        if tag == "select":
            self._select = attrs["name"]
            self.options[self._select] = []
        if tag == "option":
            self._option = [attrs.get("value", ""), ""]

    def handle_endtag(self, tag):
        if not self.depth:
            return
        if tag == "fieldset":
            self.depth -= 1
        if tag == "option" and self._option is not None:
            self.options[self._select].append((self._option[0], self._option[1].strip()))
            self._option = None
        if tag == "select":
            self._select = None

    def handle_data(self, data):
        if not self.depth:
            return
        self.text.append(data)
        if self._option is not None:
            self._option[1] += data


class EvidenceFormTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.form = _EvidenceSection()
        cls.form.feed(INDEX.read_text())

    def test_form_sends_exactly_the_contract_evidence_fields(self):
        self.assertEqual(sorted(self.form.names), sorted(EVIDENCE_FIELDS))

    def test_rubric_and_family_choices_match_the_contract(self):
        rubric_options = [value for value, _ in self.form.options["rubric_version"]]
        self.assertEqual(rubric_options, list(TEAM_A_RUBRIC_FAMILIES))
        family_options = [value for value, _ in self.form.options["defect_family_id"] if value]
        self.assertEqual([int(value) for value in family_options], sorted(TEAM_A_RUBRIC_FAMILIES["v0.1"]))

    @unittest.skipUnless(ONTOLOGY.exists(), "Team A ontology.yaml is not on this branch")
    def test_family_labels_use_the_ontology_names(self):
        names = {
            int(family_id): name
            for family_id, name in re.findall(r'- id:\s*(\d+)\s*\n\s*name:\s*"([^"]+)"', ONTOLOGY.read_text())
        }
        labels = {int(value): label for value, label in self.form.options["defect_family_id"] if value}
        self.assertEqual(labels, {family_id: f"{family_id} · {name}" for family_id, name in names.items()})

    def test_evidence_section_starts_hidden_and_reveals_no_answer(self):
        html = INDEX.read_text()
        self.assertRegex(html, r'id="evidence-fields"[^>]*class="[^"]*\bhidden\b')
        text = " ".join(self.form.text).lower()
        # Static copy only: no truth labels, defect keys, or evaluator output.
        for hidden in ("defect_present", "seeded", "clean", "defective", "evaluator", "cold 12", "cold 24"):
            self.assertNotIn(hidden, text)
        self.assertNotRegex(html, r'<option value="[1-6]"[^>]*selected')
        self.assertNotRegex(html, r'name="reference_id"[^>]*value="[0-9a-f]')


if __name__ == "__main__":
    unittest.main()
