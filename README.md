# Ouro Multimodal Evaluation Lab

A standalone, public-safe research scaffold for FIU's Fall 2026 capstone. The lab studies one question:

> When is a multimodal evaluator reliable enough to return `PASS` or `HOLD`, and when should it abstain?

This repository contains only synthetic fixtures and frozen, anonymous evaluator outputs. It has no connection to Ouro production systems, customer data, private prompts, model routing, repair logic, credentials, or commercial thresholds.

## Start here

This is a working v0.1 scaffold, not a completed research lab and not a source of research findings.

- [Current implementation status and research gates](CURRENT_STATUS.md)
- [Proposed three-team vertical slices](TEAM_SLICES.md)
- [First combined meeting checklist](KICKOFF_CHECKLIST.md)
- [Frozen public data contract](docs/DATA_CONTRACT.md)
- [Research protocol](docs/RESEARCH_PROTOCOL.md)
- [Threat model](docs/THREAT_MODEL.md)
- [Independent rerun procedure](docs/INDEPENDENT_RERUN.md)

Do not begin real participant annotation until FIU has recorded the applicable human-subjects determination and the gates in `CURRENT_STATUS.md` have been satisfied.

## What ships in the scaffold

- deterministic synthetic fixtures and SHA-256 manifests;
- a frozen evaluator-output contract using anonymous evaluator aliases;
- a browser annotation interface with blinded randomized assignments, confidence, timing, and repeat-item controls;
- raw annotation preservation and a separate adjudication database schema;
- a synthetic benchmark runner for false `PASS`, false `HOLD`, Brier score, ECE, and risk-versus-coverage;
- basic two-rater agreement with confidence intervals;
- JSON/CSV annotation export;
- export-boundary scanning, Docker support, tests, and handoff documentation.

The current fixtures and outputs demonstrate the pipeline. They are synthetic examples, not research findings or claims about Ouro. The current video fixtures are JSON placeholders rather than playable full-video artifacts. The current benchmark compares anonymous evaluator outputs with seeded synthetic truth; human-grounded comparison is a required student deliverable.

## Quick start

Requires Python 3.11+ and no third-party packages.

```bash
make bootstrap
make run
```

Open <http://localhost:8080>. Use separate pseudonymous rater IDs such as `rater-a` and `rater-b` only for the synthetic demonstration.

Run the reproducible synthetic benchmark:

```bash
make benchmark
```

Run all checks:

```bash
make check
```

## Demonstration workflow

1. `seed` generates the same synthetic artifacts from the same seed.
2. `ingest` verifies every artifact against its SHA-256 manifest.
3. The API creates randomized assignments, including blinded repeats.
4. Raters annotate without seeing seeded truth or evaluator outputs.
5. `benchmark` joins frozen outputs to seeded synthetic truth by artifact hash and writes an auditable demonstration report.
6. `export` emits allow-listed annotation fields.
7. A second person follows `docs/INDEPENDENT_RERUN.md` from a clean checkout.

See `CURRENT_STATUS.md` for the differences between this demonstration and a valid human-grounded study.

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
- Do not place private student or sponsor contact information in this public repository.
