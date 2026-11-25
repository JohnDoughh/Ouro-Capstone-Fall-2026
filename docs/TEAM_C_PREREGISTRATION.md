# Team C pre-registration (draft)

Status: **DRAFT, not frozen.** `docs/RESEARCH_PROTOCOL.md` requires these
decisions before any judgments are collected. This draft must be reviewed by
the team, frozen by commit hash, and recorded in the reveal log before Stage 1
collection begins. After freezing, any change is a dated amendment that states
whether it was made before or after any response was seen.

No real (non-team) viewers take part until FIU records the human-subjects
determination. Team dry runs and synthetic responses are labeled as such and
are never pooled with participant data.

## 1. Study set

- Artifacts: `data/public_intent` clip01–clip04 (fictional, 12 s each), verified
  against `data/public_intent/manifest.json` before every session.
- Intent records: the four sealed sponsor records, revealed only after the
  response freeze and checked with `scripts/verify_intent_reveal.py`.
- With four clips this is a **protocol pilot**. No result generalizes to Ouro
  artifacts or real advertising.

## 2. Components

Coded components, using the sealed-record fields (see the vocabulary mapping in
`docs/TEAM_C_PROBLEM_CASTING.md` §4):

- primary: `audience`, `problem`, `product`, `key_benefit`, `support`,
  `call_to_action`;
- exploratory: `tone`;
- derived views: thesis = `product` + `key_benefit`; hook = `problem`;
  proof = `support`; CTA = `call_to_action`. Offer is not measurable on this
  set.

## 3. Stage 1: viewer task

- The viewer sees only the clip in the lab UI: no README, manifest, records or
  other responses.
- Per component, the viewer writes free recall (capped length), rates certainty
  from 1 (guessing) to 5 (certain), or ticks "could not tell".
- Exposure: up to **2 plays** per clip, recorded. A third play is blocked.
- Clip order is randomized per viewer with the lab's assignment randomization.
- Instructions ask viewers not to include names, contact details or other
  personal information.

## 4. Stage 2: coding scale

Each (response, component) pair is coded by each coder as one of:

| Code | Meaning |
|---|---|
| `recovered` | The response states the intended content, in any wording. |
| `partially_recovered` | The response contains part of the intended content, or a correct but vaguer version of it. |
| `not_recovered` | The response is blank, "could not tell", or off-topic. |
| `contradicted` | The response states content that conflicts with the record. The meaning was distorted, not just lost. |
| `not_applicable` | The record's `delivery` is `not_intended`. Coders must not code these as `not_recovered`. |

Coders also give a confidence from 1 to 3 for each code. The full definitions
and worked examples go in `docs/INTENT_CODEBOOK.md` (Sprint 3) and must agree
with this table.

Delivery codes:

- `not_intended`: excluded from recovery and survival denominators.
- `omitted_in_edit`: intended but not delivered. Coded as usual and reported as
  its own stratum. A low recovery rate here is the expected result, not a
  viewer failure.
- `explicit_text`, `implied`, `visual_only`, `partially_delivered`: coded as
  usual and reported by stratum.

## 5. Reference label per response

- Two coders agree: that code is the reference.
- Two coders disagree: an adjudication record, stored separately, names the
  reference code and the coding IDs it resolves. The original codes are never
  changed.
- Agreement statistics always use the raw codes, before adjudication.

## 6. Survival rule

For each (clip, component) with at least 3 eligible responses:

- **survived**: at least ⌈2n/3⌉ of the n reference codes are `recovered`;
- **not survived**: otherwise.

`partially_recovered` does not count toward survival. A sensitivity analysis
that counts it as recovered is reported separately and labeled exploratory.

## 7. Outcomes

**Primary (protocol pilot):** inter-coder reliability of the recovery codes,
Krippendorff's alpha (nominal) over all primary components, with a 95%
bootstrap CI.
Interpretation thresholds: α ≥ 0.80 reliable; 0.667 ≤ α < 0.80 tentative only;
α < 0.667 means the codebook must be revised before any recovery result is
reported.

**Secondary:**

1. Recovery rate per (clip, component) with a 95% Wilson interval.
2. Survival per (clip, component) under §6.
3. Contradiction rate per component.
4. Recovery by delivery stratum (does `explicit_text` survive more than
   `implied` or `visual_only`?).
5. Comprehension disruption: the share of delivered components (delivery not in
   `not_intended`, `omitted_in_edit`) that were `not_recovered` or
   `contradicted`.
6. Viewer calibration: mean viewer certainty by reference code, and the
   certainty of `contradicted` responses (confidently wrong).

**Exploratory:** `tone`, the partial-credit sensitivity analysis, and ordinal
alpha treating the scale as `not_recovered` < `partially_recovered` <
`recovered` (with `contradicted` excluded).

Evaluator comparison (false survived / false not-survived, Brier, ECE,
risk-vs-coverage) is **not pre-registered here**. It depends on an intent
evaluator-output contract that the council has not approved, and on frozen
evaluator outputs that do not exist. It will be added by amendment before any
evaluator output is seen.

## 8. Ambiguity and abstention reference class

A (clip, component) is **ambiguous** when either:

- viewers split: the share of `recovered` reference codes is greater than 1/3
  but below the survival threshold; or
- coders split: coders disagree on at least half of that cell's responses.

Ambiguous cells are the reference class for "an evaluator should abstain". They
are reported as a count and a list, not hidden inside the survival rate.

## 9. Sample size

- Minimum 3 eligible viewers per clip; target 5.
- Minimum 2 coders per response; target 3, so that alpha uses more than two
  raters.
- A coder never codes a clip they watched as a viewer.
- Coders do not see viewer IDs or other coders' codes.

## 10. Exclusion policy

Decided before any response is seen:

- Viewer exposed to the README, manifest, records or another viewer's
  responses before responding (from the facilitator's exposure log): all of
  that viewer's responses are excluded.
- Incomplete responses (fewer than half of the primary components answered,
  counting "could not tell" as answered): excluded.
- Responses saved after the play limit was bypassed: excluded.
- Responses containing personal information: the text is redacted before
  export; the codes are kept.
- All exclusions are listed with a reason code in the report. Nothing is
  silently dropped.

## 11. Stopping rule

Fixed design: collect until every clip has the target number of eligible
viewers, or until the collection window closes (date to be set when frozen).
No viewers are added after any response has been coded. No interim look at
recovery rates.

## 12. Seeds and analysis parameters

- Bootstrap: 2,000 resamples, percentile intervals, seed **20261014**, with
  resampling over responses within clip.
- Coder-sheet order and clip assignment order use seeds recorded in the report.
- Wilson intervals use z = 1.96.
- Every report records the code commit, the intent contract version, the
  response freeze SHA-256, the revealed-record hashes and the codes-file
  SHA-256.

## 13. Open items before freezing

- Sponsor confirmation of the sealed-record schema and the vocabulary mapping.
- Named holdout/reveal custodian.
- Collection window dates.
- FIU human-subjects determination (gates real viewers only; dry runs may
  proceed).
