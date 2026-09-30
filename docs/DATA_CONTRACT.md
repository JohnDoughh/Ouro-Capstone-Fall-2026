# Frozen public data contract

Contract version: `1.0.0`

The public lab accepts a deliberately small interface. Ouro may privately adapt internal records to this contract, but private fields must never cross into this repository or the student environment.

## Artifact manifest

Required fields:

| Field | Meaning |
|---|---|
| `contract_version` | Semantic version of this public contract |
| `benchmark_id` | Public-safe benchmark identifier |
| `seed` | Fixture/split seed |
| `created_at` | UTC timestamp |
| `artifacts` | Ordered list of artifact records |

Each artifact record includes `artifact_id`, `relative_path`, `sha256`, `byte_length`, `mime_type`, `modality`, `split`, `defect_family`, `defect_present`, and `synthetic`. `synthetic` must be `true` in the public repository.

The SHA-256 is the durable join key. Human-readable IDs are labels only.

## Frozen evaluator output

```json
{
  "artifact_sha256": "64 lowercase hex characters",
  "evaluator_alias": "eval-alpha",
  "verdict": "PASS",
  "confidence": 0.87,
  "evidence_codes": ["visual_integrity"],
  "evaluated_at": "2026-08-25T00:00:00Z",
  "contract_version": "1.0.0"
}
```

Allowed verdicts are `PASS` and `HOLD`. Confidence is the probability assigned to the emitted verdict. The contract excludes model/vendor identity, prompts, chain of thought, weights, routing, repair logic, thresholds, URLs, credentials, cost, latency internals, and customer context.

## Human annotation

Human annotation contract version: `2.1.0`. Annotations include pseudonymous `rater_id`, assignment ID, artifact SHA, `PASS`/`HOLD`/`UNSURE`, integer confidence from 1 to 5, integer severity from 0 to 3, optional defect timestamps, controlled reason codes, optional short note, and start/completion timestamps. Confidence is ordinal and distinct from evaluator-output probability in contract `1.0.0`. Severity 0 means no observable defect; 1 is minor; 2 is moderate; 3 is severe. Severity records observed impact independently from the verdict; the common PASS/HOLD alignments are guidance, not validation rules. Defect timestamps are reviewer-entered text up to 240 characters; separate multiple points/ranges with semicolons, for example `00:04-00:05; 00:08`. The API resolves the rater from the assignment and never accepts an artifact ID supplied by the browser.

Existing annotations created before version `2.0.0` retain their original 0-to-1 confidence value and export with `confidence_scale: "legacy-0-1"`, unknown severity (`null`), and unknown defect timestamps (`null`). They are not silently converted.

Repeat items share a hidden `repeat_group`. The interface does not label them as repeats.

## Adjudication

Adjudication is stored as a separate append-only decision linked to annotations. It must never modify or delete a rater's original response.

## Compatibility

- Breaking field or meaning changes require a major version.
- Added optional fields require a minor version.
- Clarifications and test-only changes require a patch version.
- Every contract change needs validator and regression-test updates.


## Separately versioned native AVC inspection

The frozen 1.0.0 evaluator-output contract above remains unchanged. Genuine AVC
reports do **not** satisfy it: AVC's native delivery decision is
`approve`/`hold`/`reject`, and the native report version used for this study
does not provide a calibrated final probability. Converting those fields into
v1 `PASS`/`HOLD` plus a fabricated probability is prohibited.

A separate inspection-only validator accepts sponsor-sanitized
`2.0.0-proposed.2` records with:

- exact media SHA-256 and byte length;
- anonymous evaluator alias `evaluator-01`;
- native `approve`/`hold`/`reject` delivery decision;
- complete/incomplete evidence coverage;
- the five controlled modality states;
- `detected_failure` when any native modality is `failed`, including when
  coverage is also incomplete; otherwise `inconclusive` for incomplete
  coverage and `unassessed` for complete coverage;
- `probability: null` with `PROBABILITY_NOT_REPORTED`;
- allow-listed provenance/evidence codes only.

`2.0.0-proposed.1` remains readable under its original rules; it is not
reinterpreted as `.2`. Producers using the failure-preserving rule must emit
`.2`. A failed modality cannot accompany an `approve` delivery decision.
Unsupported or unfinished checks remain `inconclusive` modalities and require
incomplete coverage; they are not silently promoted to covered. The original
controlled evidence codes, including `COVERAGE_INCOMPLETE` when applicable,
remain in the inspected record. `detected_failure` describes a native check
result, not an independently established human defect label or a calibrated
probability. This is a sponsor-review inspection contract, not a lab importer.

This inspection path does not feed `benchmark`, Brier score, ECE, false-PASS,
false-HOLD, or defect confusion metrics. Those analyses require independently
derived human reference labels. A native AVC delivery decision is operational
behavior, not ground-truth defect presence.

The evaluator answer must remain hidden from raters until their blinded human
judgments are frozen. Use `inspect-avc` only for post-review sponsor/student
analysis of an authorized sanitized evaluation file.
