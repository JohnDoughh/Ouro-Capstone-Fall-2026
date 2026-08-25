.PHONY: bootstrap run benchmark test check clean

PYTHON ?= python3
SEED ?= 20260825

bootstrap:
	$(PYTHON) -m ouro_eval_lab.cli seed --root data/fixtures --seed $(SEED)
	$(PYTHON) -m ouro_eval_lab.cli init-db --db data/lab.db
	$(PYTHON) -m ouro_eval_lab.cli ingest --db data/lab.db --manifest data/fixtures/manifest.json

run:
	$(PYTHON) -m ouro_eval_lab.cli serve --db data/lab.db --port 8080

benchmark:
	$(PYTHON) -m ouro_eval_lab.cli benchmark --manifest data/fixtures/manifest.json --outputs data/fixtures/evaluator_outputs.json --out data/exports/report.json

test:
	$(PYTHON) -m unittest discover -s tests -v

check: test
	$(PYTHON) -m compileall -q ouro_eval_lab
	$(PYTHON) scripts/check_public_boundary.py .

clean:
	rm -f data/lab.db
	rm -rf data/fixtures data/exports
