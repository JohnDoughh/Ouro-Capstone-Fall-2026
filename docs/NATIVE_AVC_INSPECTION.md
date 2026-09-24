# Native AVC inspection

This path exists so the FIU teams can inspect a genuine, sanitized Ouro AVC
result without changing the frozen synthetic benchmark contract.

## Why it is separate

The original v1 demo expects `PASS`/`HOLD` plus a numeric probability.
Native AVC v1 instead emits an operational `approve`/`hold`/`reject`
delivery decision and does not report a calibrated final probability. Those
meanings are not interchangeable.

The lab therefore keeps two distinct paths:

- `benchmark`: frozen synthetic v1 demonstration only.
- `inspect-avc`: post-review inspection of one separately authorized native
  AVC evaluation bound to an artifact SHA-256 in the manifest.

`inspect-avc` never maps native HOLD to a defect label and never invents a
probability.

## Blinding rule

Do not show the native AVC evaluation to human reviewers before their independent
judgments are frozen. Reviewers receive only the authorized media/rubric side of
the package. The evaluator JSON is sponsor/evaluation-side material for later
comparison.

## Command

```bash
python -m ouro_eval_lab.cli inspect-avc \
  --manifest path/to/manifest.json \
  --evaluation path/to/evaluation.json \
  --out data/exports/native-avc-inspection.json
```

The command:

1. verifies every artifact byte against the supplied manifest;
2. strictly validates the native AVC public fields and rejects extras;
3. requires the evaluation SHA and byte length to match one manifest artifact;
4. preserves the native delivery decision, coverage and modality states;
5. emits `probability: null`;
6. marks calibration and defect-confusion analysis ineligible until independent
   reference labels exist.

## Genuine versus simulated provenance

A sanitized evaluation with `canonical-approved-synthetic` provenance is marked
`genuine_avc: true`. `simulated-test-only` remains useful for software tests,
but is marked `genuine_avc: false` and must never be represented as an Ouro
performance result.

Schema validation alone does not prove sponsor authorization. Only use files
delivered through the approved sponsor handoff.

## What this does not establish

A native `approve`, `hold` or `reject` decision is not the human reference
label. The inspection output therefore does not produce false-PASS, false-HOLD,
Brier, ECE, calibration, precision/recall or defect confusion metrics.

Those analyses belong after the teams have frozen independent human judgments,
applied their pre-registered adjudication/reference rule, and joined that
reference to the same artifact SHA-256.
