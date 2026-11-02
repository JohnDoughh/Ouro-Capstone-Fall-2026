# Card #465 fictional dropout reproducibility fixture

This public package tests Team B's package-building code using a deliberately invented annotation and an explicitly simulated evaluator output for synthetic `dropout.wav`. It contains no actual course observation and establishes no human agreement, AVC accuracy or research result.

The original submitted observation and original exports are preserved unchanged in the Product Owner's private review archive. This correction does not edit that original response or establish permission for public use. Earlier public PR commits remain historical records; this change does not retract that prior exposure.

## Pinned media

- Artifact: `syn-tone-b`, `data/public_audio/dropout.wav`
- SHA-256: `9f4f1593b2b5c7f24495f9e1f12d55920cde80d8608916bbb5d70d72e8d10478`
- Byte length: 336044
- Generated dropout: `[4.000, 5.000)` seconds

`fictional_annotation.json` is a new software-test input with an explicitly fictional rater, fixed illustrative times, severity 2 and confidence 4. Its `provenance` is `fictional-test-only`; these are not copied or amended human ratings. `simulated_evaluator_output.json` remains labeled `simulated-test-only`.

The export's existing `human_annotation` and `human_*` field names are retained for compatibility with the original demonstration format. Their values here are fictional examples, not a human participant's data. Every record retains the same artifact SHA-256. Actual original judgments must remain separate and unchanged.

## Reproduce

```sh
python3 scripts/build_card465_dropout_evidence.py
python3 scripts/build_dropout_agreement_report.py
python3 -m unittest tests.test_card465_dropout_evidence -v
python3 -m unittest tests.test_dropout_agreement_report -v
make check
```

`build_dropout_agreement_report.py` writes a deterministic summary of
agreement, disagreement, uncertainty and coverage. False-pass and false-hold
counts are emitted only when an input is explicitly marked as an independent,
comparable reference; the committed fictional example therefore marks those
metrics unavailable instead of treating its demonstration annotation as
ground truth.

The builder checks media bytes, artifact identity, human-shaped ordinal scales and timestamps, explicit fictional annotation provenance and simulated output provenance. It rejects unmarked/course-observation inputs. Outputs use explicit UTF-8 LF bytes on every OS; Git preserves the committed fixture/export bytes. Repeated runs match the committed JSON files and SHA256SUMS byte for byte.

This public fixture is not evidence of a new student rating or a replacement for the separately preserved original submission. It does not accept portal card #465 or claim broader collection/publication approval.
