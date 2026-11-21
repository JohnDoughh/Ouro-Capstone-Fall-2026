# Team C problem casting: Intent Fidelity and Human Perception

Status: **Sprint 1 submission, draft.** Items marked *Pending* need a team
decision, sponsor confirmation, or council approval before they are frozen.

This document is the repository-level Sprint 1 record required by
`KICKOFF_CHECKLIST.md` ("Required outputs from each team") and the Sprint 1
boundary decisions in `TEAM_SLICES.md`. The walking-skeleton demonstration in
`team_c/sprint1_demo/` is frozen as the Sprint 1 workflow demo. New Team C work
builds on `data/public_intent` and the lab's own contracts, not on that demo.

The pre-registration draft is in `docs/TEAM_C_PREREGISTRATION.md`.

## 1. The problem in our own words

An advertisement can be technically clean and still fail to communicate. Team C
asks whether independent viewers who see only the final artifact can recover
what its creator meant to communicate: who it is for, the problem, the product,
the main benefit, the supporting proof, and the requested action. We also ask
whether an evaluator can tell when that meaning survived and when it became too
ambiguous to judge, in which case it should abstain.

We measure **observable recovery**, meaning what a viewer can report the ad
said. We do not measure whether the ad persuaded anyone.

## 2. Vertical slice

Team C owns:

- the sanitized intent-record contract and its versioning;
- the two-stage blinded workflow: Stage 1 viewers see only the artifact; Stage 2
  independent coders compare frozen responses with the revealed intent record;
- the intent codebook and recovery coding scale;
- per-component recovery, survival and contradiction measures;
- human agreement, viewer certainty, ambiguity and abstention analysis for
  intent;
- comparison of frozen evaluator intent judgments against the human-derived
  survival label, once such outputs exist;
- intent failure views, drift-ready intent anchors, and the Team C independent
  rerun.

## 3. Exclusions and handoffs

| Question | Owner | Team C's position |
|---|---|---|
| Is visible text or a claim rendered correctly and truthfully? | Team A | Team C does not judge rendering or truthfulness. It judges only whether the meaning was recoverable. |
| Are speech, captions and sync correct? | Team B | Team C does not judge these defects, even when they hurt comprehension. It records *comprehension disruption* only as an observed effect, never as a defect verdict. |
| A black frame or cut that hides a message | Team A (visible) / Team B (temporal) | Team C records only whether the affected component was recovered. |
| Perceived clarity, credibility, trust, persuasion | Excluded | Out of scope unless FIU approves the extension. If approved, these are stored and reported separately and never feed recovery or survival. |
| PASS/HOLD production-quality verdicts | Shared annotation contract (2.1.0) | Team C leaves this contract unchanged. Intent capture gets its own versioned contract. |

## 4. Vocabulary mapping (Pending: sponsor and council)

`TEAM_SLICES.md` names the components *thesis, hook, proof, offer, CTA and
critical beats*. The sealed records in `data/public_intent` use the fields
*audience, problem, product, key_benefit, support, call_to_action and tone*,
each with a sponsor-coded `delivery` value.

**Proposal:** the coding unit is the field the sealed record actually contains.
Slice vocabulary is reported as a derived view, so no data is recoded after
reveal.

| Slice component | Sealed-record field(s) | Notes |
|---|---|---|
| thesis | `product` + `key_benefit` | Thesis is recovered when both are recovered. Partial when only one is. |
| hook | `problem` | In 12-second clips the opening frames the problem. Not a perfect match: a hook can also be a purely visual attention device. |
| proof | `support` | Includes correctly reporting that no support was given, when the record says so. |
| offer | none | The public intent records have no offer or terms field. Reported as *not measurable on this set*. We ask the sponsor to include `offer` in future sanitized manifests. |
| CTA | `call_to_action` | Direct match. |
| critical beats | none (`required_beats[]` proposed) | Not in the current records. Proposed as an optional field in the v1 intent contract. |
| *(additional)* | `audience` | Coded and reported as its own component. |
| *(additional)* | `tone` | Coded, but exploratory only. Tone is close to perception, so it is not part of the primary outcome. |

Questions for the sponsor:

1. Will future sanitized intent manifests use the README field list, the slice
   vocabulary, or both?
2. Can future manifests add `offer` and `required_beats[]`?
3. Is the field list in `data/public_intent/README.md` the full schema of the
   sealed records, or do they contain other keys?

## 5. Must-ship deliverables (mandatory spine)

1. Intent-record contract (v1) with a validator, run automatically after the
   reveal hash check.
2. Stage 1 blinded viewer capture in the lab: a separate append-only table and
   endpoint, intent mode in the UI, and an export that freezes responses with a
   recorded SHA-256.
3. Reveal that refuses to run unless a response freeze exists.
4. Stage 2 coding: a codebook, coder sheets that exclude a coder's own viewer
   responses, append-only code import, and separate adjudication records.
5. Intent metrics: recovery rate with Wilson CI, survival under the
   pre-registered rule, contradiction rate, delivery-code strata, and
   Krippendorff's alpha with a bootstrap CI.
6. A deterministic `intent-report` and a seeded synthetic end-to-end pilot in
   `make check` and CI.
7. An independent rerun section in `docs/INDEPENDENT_RERUN.md`.

Stretch: a coder web UI, the evaluator-intent comparison (needs a council
contract change and evaluator outputs), HTML failure views, an anchor registry,
and persuasion items if FIU approves.

## 6. Definition of done

- Every must-ship item is merged through a reviewed pull request, with
  `make check` passing.
- The synthetic pilot produces a byte-identical report hash on a clean
  checkout, rerun by someone who did not build it.
- Raw responses, codes and adjudications are append-only. No rater's judgment
  is ever overwritten.
- No viewer-facing API response contains an artifact ID, path, SHA-256 or any
  intent text.
- All synthetic outputs are labeled as demonstrations. With four clips, results
  are a protocol pilot, not an estimate.

## 7. Five-sprint plan

| Sprint | Scope |
|---|---|
| 1 | Problem casting, exclusions, vocabulary mapping, pre-registration draft, governance roles, first three issues, walking-skeleton demo. |
| 2 | C-1 intent-record contract. C-2 Stage 1 blinded viewer capture, intent UI mode, `export-intent` freeze. |
| 3 | C-3 codebook, reveal-after-freeze, coder sheets, code import, adjudication records. Propose the intent evaluator-output contract to the council. |
| 4 | C-4 intent metrics, Krippendorff's alpha (shared utility), viewer certainty vs. recovery, ambiguity and abstention, `intent-report`. |
| 5 | Failure views, intent anchors, `make intent-pilot` in CI, independent rerun, documentation, final report. |

## 8. Risks and dependencies

| Risk or dependency | Owner | Mitigation |
|---|---|---|
| FIU human-subjects determination | FIU / Team C HS owner | Team dry runs and synthetic responses only until it is recorded. |
| Sealed records and more sanitized intent manifests | Ouro sponsor | Build against the README schema. Confirm the schema before freezing the contract. |
| No evaluator intent outputs exist | Ouro + council | Propose the contract in Sprint 3. Use labeled synthetic demo outputs meanwhile. |
| Only 4 clips (project target 90–150) | Team C + custodian | Author more fictional clips with `scripts/generate_public_intent_clips.py`. A non-coder custodian seals the commitments. |
| PII in free-recall text | Team C | Length caps, instructions, a pre-export PII screen. |
| Answer leakage (the README sits next to the clips) | Facilitator | Run sessions from the UI only. Log exposures. Exclude exposed viewers. |
| Coder was also a viewer of the same clip | Team C | Coder sheets exclude the coder's own responses. |
| Reveal before freeze | Team C + custodian | Reveal refuses to run without a recorded freeze hash. |

## 9. Roles (Pending: team decision)

Use names or GitHub handles that team members agree to publish. Do not add
private contact details.

| Role | Person | Notes |
|---|---|---|
| Team leader | *Pending* | Selected by the team (`TEAM_SLICES.md`, "Leader selection"). |
| Integration delegate | *Pending* | Sits on the cross-team council and approves shared-contract changes. |
| Holdout/reveal custodian | *Pending* | Must not be a Team C coder. Holds sealed records until the response freeze hash is recorded. |
| Human-subjects owner | *Pending* | Tracks the FIU determination. |
| Independent rerun owner | *Pending* | Must not have built the pipeline being rerun. |

## 10. First three issues

These replace the three issues listed in
`team_c/sprint1_demo/PROBLEM_CASTING_PROPOSAL.md` §12. They follow the
plan's C-1, C-2 and C-3 and move Team C onto `data/public_intent`.

**C-1: Sanitized intent-record contract (v1).**
Add `INTENT_CONTRACT_VERSION` and `validate_intent_record` to
`ouro_eval_lab/contracts.py`. Require the README fields, each with a `delivery`
value from the controlled enum. Allow an optional `required_beats[]`. Reject
unknown keys, oversized text, and private-looking fields. Run the validator in
`scripts/verify_intent_reveal.py` after the hash check. Document it in
`docs/DATA_CONTRACT.md`, with tests. Blocked on sponsor confirmation of the
schema (§4, question 3) before the version is frozen.

**C-2: Stage 1 blinded viewer response capture.**
Add an append-only `intent_responses` table, `POST /api/intent-responses/` with
the same receipt and idempotency semantics as `/api/annotations/`,
`serve --study intent`, an intent form in the UI, and an `export-intent` freeze
that records its SHA-256. Leave the shared annotation contract (2.1.0)
unchanged. Tests cover idempotency, rater isolation, append-only storage and
blinding.

**C-3: Intent codebook and Stage 2 coding workflow.**
Write `docs/INTENT_CODEBOOK.md`: the recovery scale, worked examples on
fictional anchors, and rules for `not_intended` and `omitted_in_edit`. Add a
reveal command that refuses to run without a freeze hash, coder sheets, an
append-only code import, and separate adjudication records. Coordinate the
adjudication shape with the other teams' delegates.
