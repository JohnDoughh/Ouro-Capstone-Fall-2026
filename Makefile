.PHONY: bootstrap run benchmark card465-evidence dropout-agreement-report intent-pilot intent-anchors test check clean

PYTHON ?= python3
SEED ?= 20260825

bootstrap:
	$(PYTHON) -m ouro_eval_lab.cli bootstrap --root data/fixtures --db data/lab.db --seed $(SEED)

run:
	$(PYTHON) -m ouro_eval_lab.cli serve --db data/lab.db --port 8080

benchmark:
	$(PYTHON) -m ouro_eval_lab.cli benchmark --manifest data/fixtures/manifest.json --outputs data/fixtures/evaluator_outputs.json --out data/exports/report.json

card465-evidence:
	$(PYTHON) scripts/build_card465_dropout_evidence.py

dropout-agreement-report:
	$(PYTHON) scripts/build_dropout_agreement_report.py

intent-pilot:
	$(PYTHON) -m ouro_eval_lab.cli intent-pilot --out data/exports/intent-pilot.json --html data/exports/intent-pilot.html --expect team_c/intent_pilot/EXPECTED_SHA256

intent-anchors:
	$(PYTHON) -m ouro_eval_lab.cli intent-anchors verify --anchors team_c/anchors/practice_anchors.json --pinned team_c/anchors/practice_anchors.sha256

test:
	$(PYTHON) -m unittest discover -s tests -v

check: test
	$(PYTHON) -m compileall -q ouro_eval_lab
	$(PYTHON) scripts/check_public_boundary.py .
	$(PYTHON) -m ouro_eval_lab.cli verify --manifest data/public_playable/manifest.json
	$(PYTHON) -m ouro_eval_lab.cli verify --manifest data/public_audio/manifest.json
	$(PYTHON) -m ouro_eval_lab.cli verify --manifest data/public_intent/manifest.json
	$(MAKE) intent-pilot
	$(MAKE) intent-anchors

clean:
	rm -f data/lab.db
	rm -rf data/fixtures data/exports
