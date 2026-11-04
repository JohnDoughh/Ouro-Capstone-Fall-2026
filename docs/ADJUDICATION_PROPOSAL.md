# Proposal: one adjudication record shape for Teams A, B and C

Status: **PROPOSAL from Team C, 2026-11-04. Not agreed.** For the Team A and
Team B integration delegates to accept, amend or reject. Nothing in the shared
schema changes until all three delegates agree.

## Why

All three teams must keep raw judgments and disagreement, and store
adjudication separately (`AGENTS.md`, `TEAM_SLICES.md` item 4). The existing
shared `adjudications` table (`ouro_eval_lab/store.py`) cannot do that yet:

- it links a decision to an artifact, not to the judgments it resolves, so a
  reader cannot tell which disagreement was settled;
- it has no append-only triggers, so a decision can be edited or deleted;
- it has no method, rule version or reason code, so an analysis cannot filter
  or audit decisions.

Team C needs adjudication now (Sprint 3: two coders disagree on a recovery
code). We would rather agree one shape than build three.

## Proposed record

One append-only table per study, all with the same columns. Team C would use
`intent_adjudications`; Teams A and B could use the existing table name once
it is migrated, or a new one.

| Column | Meaning |
|---|---|
| `adjudication_id` | Random token. |
| `unit` | What is being decided, as a stable key. A/B: `artifact_sha256`. C: `response_id` + `:` + component. |
| `resolves` | JSON list of the raw judgment IDs this decision settles (annotation IDs for A/B, coding IDs for C). At least two, all for the same unit, all existing. |
| `reference_value` | The decided label. A/B: `PASS`/`HOLD`. C: a recovery code. Validated against the study's own vocabulary. |
| `adjudicator_id` | Pseudonymous ID. **Must not** be the author of any resolved judgment. |
| `method` | `discussion`, `third_judge` or `pre_registered_rule`. |
| `rule_version` | The codebook or protocol version applied, e.g. `intent-codebook 0.1-draft`. |
| `reason` | Short text, at most 300 characters, no contact details. |
| `supersedes` | Optional earlier `adjudication_id` for the same unit. A correction is a new row that names the old one; nothing is overwritten. |
| `created_at` | UTC timestamp. |

Rules, enforced in code and tests:

1. Triggers reject every `UPDATE` and `DELETE`.
2. Only units with a real disagreement can be adjudicated; agreement already
   gives the reference label.
3. The reference label for a unit is the latest non-superseded adjudication,
   else the agreed raw value. One shared helper computes it for all teams.
4. Agreement statistics (kappa, Krippendorff's alpha) always use the raw
   judgments, never adjudicated values.
5. Exports list adjudications in a separate file or section with its own
   SHA-256, never merged into the raw judgments.

## Questions for the delegates

1. Is a per-study table with identical columns acceptable, or do you want one
   shared table with a `study` column?
2. Should the adjudicator be barred from the judgments they resolve (proposed),
   or only recorded?
3. Is the `method` list complete for visual and audio review?
4. Should `UNSURE` annotations (Teams A/B) count as disagreement that needs
   adjudication, or be excluded?
5. Who owns the migration of the existing `adjudications` table, which holds
   no rows in the public demo?

## What Team C does meanwhile

Team C will not touch the shared table. Once the shape is agreed (or amended),
Team C builds `intent_adjudications` and an `adjudicate-intent` command first,
with the shared reference-label helper, so Teams A and B can reuse both.
