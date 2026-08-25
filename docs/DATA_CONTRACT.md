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

Annotations include pseudonymous `rater_id`, assignment ID, artifact SHA, `PASS`/`HOLD`/`UNSURE`, confidence, controlled reason codes, optional short note, and start/completion timestamps. The API resolves the rater from the assignment and never accepts an artifact ID supplied by the browser.

Repeat items share a hidden `repeat_group`. The interface does not label them as repeats.

## Adjudication

Adjudication is stored as a separate append-only decision linked to annotations. It must never modify or delete a rater's original response.

## Compatibility

- Breaking field or meaning changes require a major version.
- Added optional fields require a minor version.
- Clarifications and test-only changes require a patch version.
- Every contract change needs validator and regression-test updates.
