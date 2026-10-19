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

Human annotation contract version: `2.1.0`. Annotations include pseudonymous `rater_id`, assignment ID, artifact SHA, `PASS`/`HOLD`/`UNSURE`, integer confidence from 1 to 5, integer severity from 0 to 3, optional defect timestamps, controlled reason codes, optional short note, and start/completion timestamps. The accepted reason codes for new submissions are `visual_integrity`, `audio_integrity`, `temporal_integrity`, and `intent_integrity`; the list may be empty but may not contain duplicates or unknown codes. This enforces the existing controlled vocabulary without rewriting historical stored annotations or exports. Confidence is ordinal and distinct from evaluator-output probability in contract `1.0.0`. Severity 0 means no observable defect; 1 is minor; 2 is moderate; 3 is severe. Severity records observed impact independently from the verdict; the common PASS/HOLD alignments are guidance, not validation rules. Defect timestamps are reviewer-entered text up to 240 characters; separate multiple points/ranges with semicolons, for example `00:04-00:05; 00:08`. The API resolves the rater from the assignment and never accepts an artifact ID supplied by the browser. Rater IDs are 1–80 letters, numbers, `-` or `_`; both the interface and the API also reject an ID that looks like a phone number, because a rater ID must stay pseudonymous.

An annotation POST is serialized by assignment. The first accepted judgment returns `201` and its annotation ID/completion time. A retry of the same assignment, rater, and normalized judgment returns the original receipt with `200` and `replayed: true`; it neither creates nor changes an annotation. A different judgment for a completed assignment returns `409`. `400` is reserved for a definite pre-write validation rejection; storage/transaction ambiguity returns `503` or a transport failure. After an acknowledgement timeout, the browser freezes the original request in tab-scoped session storage and permits only an exact retry until it receives a receipt. A timeout is not evidence of rollback. Recovery across a closed tab or another device is not guaranteed. This is a delivery/retry clarification, not a change to stored annotation format or historical records.

Existing annotations created before version `2.0.0` retain their original 0-to-1 confidence value and export with `confidence_scale: "legacy-0-1"`, unknown severity (`null`), and unknown defect timestamps (`null`). They are not silently converted.

Repeat items share a hidden `repeat_group`. The interface does not label them as repeats.

The reviewer-facing `/api/next` response uses a neutral `review_label` such as
`Item 001`, numbered by the rater's randomized assignment sequence. It is stable
when reloading that assignment; a repeat receives its own item number. The
response includes only `assignment_id`, `sequence`, `started_at`, `mime_type`,
`modality`, `review_label`, and an assignment-scoped `media_url`. It does not
expose the source `artifact_id`, filename/path, artifact SHA, truth, defect
family, split, repeat marker, or evaluator output. Original artifact IDs and
SHA bindings remain in the local database; annotation exports retain the
original annotation ID and artifact SHA. This presentation change does not
change annotation contract `2.1.0` or rewrite saved judgments.

## Intent fidelity (Team C)

Two separately versioned contracts serve the intent study. Neither changes
annotation contract `2.1.0`, the evaluator-output contract `1.0.0`, or any
stored PASS/HOLD judgment.

### Intent record `2.0.0`

A revealed, sponsor-sanitized intent record describes what one clip was meant
to communicate. Version `2.0.0` validates the envelope the sealed records were
committed in: the seven component strings nest under `intended` and their
delivery codes under `delivery`. The repository owner checked this structure
against the four preserved records and their commitments in the PR #23 review
(key names and nesting only; no content was disclosed).
It replaces the provisional `1.0.0` shape of seven top-level `{text, delivery}`
objects, which never matched the committed files. The originals and their
commitments are never rewritten.

This example is fictional and says nothing about the sealed records:

```json
{
  "schema": "fictional-intent-record",
  "record_type": "fictional_intent_record",
  "artifact_id": "syn-intent-01",
  "relative_path": "clip01.mp4",
  "salt": "random salt",
  "fictional": true,
  "frozen_at": "2026-01-01T00:00:00Z",
  "note": "free text",
  "delivery_codes": ["explicit_text", "implied", "not_intended", "omitted_in_edit",
                     "partially_delivered", "visual_only"],
  "intended": {
    "audience": "...", "problem": "...", "product": "...", "key_benefit": "...",
    "support": "...", "call_to_action": "...", "tone": ""
  },
  "delivery": {
    "audience": "explicit_text", "problem": "implied", "product": "explicit_text",
    "key_benefit": "partially_delivered", "support": "visual_only",
    "call_to_action": "omitted_in_edit", "tone": "not_intended"
  }
}
```

- All eleven top-level keys are required. Unknown keys are rejected, not
  dropped: an unexpected key may be a private field (prompt, campaign,
  customer). There is no `offer` or `required_beats`.
- `intended` and `delivery` each hold exactly the seven fields `audience`,
  `problem`, `product`, `key_benefit`, `support`, `call_to_action`, `tone`.
  These are the pilot's coding units. Mappings to thesis/hook/proof/offer/CTA
  are derived interpretations, not part of the record.
- `delivery_codes` is a nonempty list of unique codes from `explicit_text`,
  `implied`, `visual_only`, `partially_delivered`, `omitted_in_edit`,
  `not_intended`. Every `delivery` value must be one of the record's codes.
- Each `intended` string is at most 300 characters. It may be empty only when
  its delivery is `not_intended`; `omitted_in_edit` was intended, so its text
  is required.
- `fictional` must be `true`. `frozen_at` is an ISO-8601 timestamp with a
  timezone. `schema` and `record_type` are nonempty strings of at most 80
  characters; `note` is at most 500. URLs, emails and phone numbers are
  rejected in every text value.
- Validation errors name keys, never values, so the custodian can run the
  check on sealed records and share the output without disclosing intent.
- `scripts/verify_intent_reveal.py` validates each record only after its bytes
  match the pre-published commitment. `--skip-schema` checks commitments alone.
- `intent_coding_units(record)` derives the per-component coding view
  (`{field: {text, delivery}}`) from a verified record. The view is never
  stored over the original.

### Intent response `1.0.0` (Stage 1 viewer capture)

`serve --study intent` runs the intent study instead of PASS/HOLD annotation.
One database serves one study: the server refuses a database that already holds
the other study's submissions, or repeat assignments. Intent assignments have no
hidden repeats, because a repeat is a second exposure. `/api/next` adds the
top-level fields `study`, `play_limit`, `plays_used` (the current
assignment's recorded plays; `null` during annotation) and
`collection_closed`. The assignment object
keeps the same neutral fields as annotation, with no artifact ID, filename or
SHA-256.

The viewer sees only the clip. It plays only through a counted Play button, from
the start, up to the play limit (default 2, the pre-registered value).

#### Play starts

The server, not the browser, holds the exposure count. Before each play the
browser sends `POST /api/intent-plays/<assignment_id>?rater=` with exactly
`{"play_number": n}`, where `n` is the next play (recorded plays + 1). The clip
plays only after the server acknowledges it.

- `201` records the play and returns `play_id`, `play_number` and `plays_used`.
- `200` with `replayed: true` answers a `play_number` that is already recorded,
  so a request whose reply was lost never counts twice.
- `409` refuses a play beyond the limit, on a completed assignment, out of
  order, or after the freeze. The body carries `error` and the durable
  `plays_used`; a freeze also sets `collection_closed: true`.
- `400` rejects a malformed request or another rater's assignment before any
  write, and `503` means the outcome is unknown (retry the same `play_number`).

Play starts are stored in the append-only `intent_plays` table, one row per
start, unique per assignment and play number. Because `/api/next` restores
`plays_used`, reloading or signing in again never grants fresh plays. A play
that was recorded but failed to start in the browser stays counted; the next
press retries it without a new count. The count is of plays started through the
lab UI; the media URL itself is not gated per play.

#### Response

The viewer then submits to `POST /api/intent-responses/<assignment_id>?rater=`:

```json
{
  "components": {
    "audience": {"recall": "free text", "certainty": 4, "could_not_tell": false},
    "tone": {"recall": "", "certainty": null, "could_not_tell": true}
  },
  "other_beats": "optional free text",
  "play_count": 2
}
```

- `components` holds exactly the seven record fields, each with exactly
  `recall` (at most 300 characters), `certainty` (integer 1–5) and
  `could_not_tell` (boolean). A component marked could-not-tell has empty
  recall and null certainty; otherwise both are required.
- `other_beats` is optional, at most 500 characters.
- `play_count` is an integer from 0 to 20 and may not exceed the server's play
  limit. It must equal the plays recorded in `intent_plays` for the assignment;
  any other value is a `400` rejection, so the stored and exported count is the
  durable one.
- Emails and phone numbers are rejected in all viewer text.
- Text is trimmed before storage. An exact retry is compared after trimming.

Receipts follow the annotation semantics above: `201` with `response_id` and
`completed_at` for the first save, `200` with `replayed: true` for an exact
retry, `409` for a different response to a completed assignment, `400` for a
definite pre-write rejection, and `503` when the outcome is unknown. A `409`
from a frozen collection also sets `collection_closed: true`: it is a definite
rejection with no write, so the browser clears its recovery record and shows a
final "collection closed" screen instead of offering a retry. The PASS/HOLD
endpoint returns `404` while the intent study runs, and the intent endpoint
returns `404` during annotation.

Responses are stored in `intent_responses`. Database triggers reject every
`UPDATE` and `DELETE` on that table.

### Response freeze

`export-intent` writes every response, allow-listed and in a deterministic
order, as JSON (or CSV with one column per component part). It prints the
SHA-256 of the exact bytes written and records it, with the response count, in
the append-only `intent_freezes` table. Export and freeze run in one write
transaction. The first freeze closes collection: later new responses and play
starts return `409` with `collection_closed: true`, while an exact retry of an
already-saved response still receives its original receipt. After the freeze,
`/api/next` returns `collection_closed: true` and no assignment. Exports contain the artifact SHA-256 but no artifact ID or
filename. The freeze must exist before any intent record is revealed.

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
