# Ouro Multimodal Evaluation Lab

A standalone, public-safe research scaffold for FIU's Fall 2026 capstone. The lab studies one question:

> When is a multimodal evaluator reliable enough to return `PASS` or `HOLD`, and when should it abstain?

This repository contains only synthetic fixtures and frozen, anonymous evaluator outputs. It has no connection to Ouro production systems, customer data, private prompts, model routing, repair logic, credentials, or commercial thresholds.

## What ships in the scaffold

- deterministic multimodal fixtures and SHA-256 manifests;
- a frozen evaluator-output contract using anonymous evaluator aliases;
- blinded, randomized annotations with confidence, timing, and repeat-item controls;
- raw disagreement preservation and separate adjudication records;
- a benchmark runner for false `PASS`, false `HOLD`, calibration, Brier score, ECE, and risk-versus-coverage;
- inter-rater agreement with confidence intervals;
- a browser dashboard and JSON/CSV export;
- export-boundary validation, Docker support, tests, and handoff documentation.

The included outputs demonstrate the pipeline. They are synthetic examples, not research findings or claims about Ouro.

## Quick start

Requires Python 3.11+ and no third-party packages.

```bash
make bootstrap
make run
```

Open <http://localhost:8080>. Use separate pseudonymous rater IDs (for example `rater-a` and `rater-b`) to create independent judgments.

Run the reproducible benchmark:

```bash
make benchmark
```

Run all checks:

```bash
make check
```

## Workflow

1. `seed` generates the same synthetic artifacts from the same seed.
2. `ingest` verifies every artifact against its SHA-256 manifest.
3. The API creates randomized assignments, including blinded repeats.
4. Raters annotate without seeing ground truth or evaluator outputs.
5. `benchmark` joins frozen outputs to ground truth by artifact hash and writes an auditable report.
6. `export` emits only allow-listed, nonconfidential fields.
7. A second person follows `docs/INDEPENDENT_RERUN.md` from a clean checkout.

## Commands

```bash
python -m ouro_eval_lab.cli seed --root data/fixtures --seed 20260825
python -m ouro_eval_lab.cli init-db --db data/lab.db
python -m ouro_eval_lab.cli ingest --db data/lab.db --manifest data/fixtures/manifest.json
python -m ouro_eval_lab.cli serve --db data/lab.db --port 8080
python -m ouro_eval_lab.cli benchmark --manifest data/fixtures/manifest.json --outputs data/fixtures/evaluator_outputs.json --out data/exports/report.json
python -m ouro_eval_lab.cli export --db data/lab.db --out data/exports/annotations.json
```

## Non-negotiable boundaries

- Do not add production or customer material.
- Do not add credentials, private prompts, model identities, hidden reasoning, routing, repair logic, or commercial thresholds.
- Do not treat synthetic demo metrics as conclusions.
- Preserve independent judgments and disagreement; adjudication is an additional record, never an overwrite.
- Pin analyses to artifact hashes, manifest version, evaluator alias, code commit, and random seed.

See [DATA_CONTRACT.md](docs/DATA_CONTRACT.md), [THREAT_MODEL.md](docs/THREAT_MODEL.md), and [RESEARCH_PROTOCOL.md](docs/RESEARCH_PROTOCOL.md) before adding data.
