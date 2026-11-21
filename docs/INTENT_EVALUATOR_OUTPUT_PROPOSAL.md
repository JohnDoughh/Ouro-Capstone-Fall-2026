# Proposal: what an evaluator reports about intent

**From Team C. Draft v2, 2026-11-11. Not agreed.**

v1 (2026-11-04) went to the council. v2 takes in Team B's feedback
(2026-11-11). Team A has not replied yet. This is still a proposal: no contract
or code is built until the council agrees.

## The problem

Team C measures whether viewers recover what each clip was meant to say: per
clip and intent field, did the meaning **survive**? To compare an evaluator
with people, we need the evaluator's answer to the same question, in a fixed
format, frozen before anyone sees the human results.

The existing evaluator format (`1.0.0`) answers a different question: one
PASS/HOLD per clip for production defects. It has no intent field and no way
to abstain. It stays unchanged. This is a separate, separately versioned
format.

## One record per clip and intent field

The unit is one clip (by SHA-256) and one intent field. Judging individual
viewer responses is a different task and is not part of this comparison.

| Field | Rule |
|---|---|
| `clip_sha256` | SHA-256 of the clip. |
| `field` | One of the seven intent fields. |
| `evaluator` | Anonymous alias only (`eval-...`), never a model or product name. |
| `answer` | `survived`, `not_survived` or `abstain` (too ambiguous to judge). |
| `survival_probability` | A number from 0 to 1, or `null`. Allowed with any answer, including `abstain`. |
| `probability_unavailable_reason` | Required when the probability is `null`, forbidden otherwise. One of `not_estimated` (the evaluator does not produce one) or `not_meaningful` (it cannot give a meaningful one for this record). |
| `evidence_codes` | 1 to 3 codes from the fixed list below, no repeats. |
| `ran_at`, `format_version` | When it ran, and the version of this format. |

A probability is never filled in or guessed when the evaluator did not supply
one.

A file must not contain the intended text, prompts, model names, thresholds,
reasoning, free text or anything from Ouro systems. The validator rejects
unknown keys, and its errors name keys, never values.

## Evidence codes

| Code | Meaning |
|---|---|
| `stated_in_text` | The meaning is stated in on-screen text. |
| `stated_in_speech` | The meaning is stated in speech. |
| `shown_visually` | The meaning is shown without being stated. |
| `implied` | The meaning can be inferred but is not stated or shown directly. |
| `absent` | Nothing in the clip carries the meaning. |
| `conflicting_signals` | The clip carries signals that point different ways. |

Validation: `absent` cannot appear with any other code. `answer: survived`
needs at least one of the first four codes. `conflicting_signals` is expected
with `abstain` but not required.

## How it is scored

Against the human reference from `intent-report`. Synthetic outputs only until
the sponsor provides frozen ones.

**Fields.** The evaluator answers all seven. The six primary fields are scored
and reported together. `tone` is reported separately, labelled exploratory,
and never enters the primary result.

**Which cells count.** Only cells with a settled human reference (survived or
not survived) are scored. The others are counted and reported separately,
never scored as right or wrong:

| Human reference | Handling |
|---|---|
| `not_applicable` (the record's delivery is `not_intended`) | Decided before scoring: excluded and counted. The creator did not try to say it, so there is nothing to survive. |
| ambiguous (viewers or coders split, pre-registered) | Not scored as right or wrong. Used only as the reference class for abstention. |
| `pending_adjudication` | Excluded and counted until adjudicated. |
| `insufficient_responses` | Excluded and counted. |

**Measures on scored cells:**

- **false survived:** the evaluator says survived, people did not recover it;
- **false not-survived:** the reverse;
- **abstention:** how often it abstains, and whether its abstentions fall on
  the ambiguous cells, shown as risk versus coverage;
- **calibration** (Brier score, ECE): only on records that have a probability
  **and** a settled reference. If there are none, calibration is reported as
  unavailable, with the counts of null probabilities by reason. It is never
  computed from the `answer` alone.

## Freezing

An independent custodian freezes the evaluator output file and records its
SHA-256 before any human results or codes are revealed. The custodian is not a
coder, not a viewer and not the person who runs the evaluator. **Jonathan to
confirm who.**

## Still open

1. Team A's position on all of the above.
2. Who the custodian is (Jonathan).
3. Whether the two `probability_unavailable_reason` values and the evidence
   code rules are enough.

Until this is agreed, Team C's report marks the evaluator comparison as not
available, and any demo uses clearly labelled synthetic outputs only.
