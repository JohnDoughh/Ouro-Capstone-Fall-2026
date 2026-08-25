# Research protocol

## Primary question

At what confidence or policy threshold can an evaluator return `PASS`/`HOLD` at an acceptable error rate, and how much coverage is lost when it abstains?

## Mandatory spine

1. Standalone Evaluation Lab and versioned benchmark package.
2. SHA-256 manifests, deterministic splits, and seeded defect fixtures.
3. Blinded independent annotation with repeat controls.
4. Multimodal benchmark execution against frozen outputs.
5. Agreement and uncertainty estimates with confidence intervals.
6. Calibration/abstention for pre-registered priority defect families, explicitly reporting false `PASS`, false `HOLD`, and risk-versus-coverage.
7. Independent rerun from a clean checkout and documented handoff.

Rigorous results on fewer priority defect families beat shallow coverage.

## Pre-registration decisions

Before collecting judgments, record:

- priority defect families and modalities;
- target sample size and minimum judgments per item;
- primary outcome and acceptable false-`PASS` constraint;
- confidence bins and abstention thresholds;
- exclusion policy;
- bootstrap seed and interval method;
- stopping rule.

Do not choose these after viewing results.

## Label semantics

- `PASS`: no target defect is present.
- `HOLD`: a target defect is present and the artifact should not proceed.
- `UNSURE`: the rater cannot make a defensible binary judgment.

For evaluator metrics, the positive class is `HOLD`/defect present. `UNSURE` human judgments are preserved but excluded from pairwise kappa unless the pre-registration says otherwise.

## Analysis

- Report per-family and pooled confusion matrices.
- Report false `PASS` and false `HOLD` counts and Wilson intervals.
- Report Brier score and expected calibration error.
- Plot/tabulate selective risk against retained coverage for pre-registered confidence thresholds.
- Report agreement without erasing disagreement.
- Separate exploratory findings from registered primary results.

## Stretch

Full modality/defect coverage, intent-survival measures, expanded evaluator-drift protocol, hidden holdout, and an expanded failure-analysis dashboard.
