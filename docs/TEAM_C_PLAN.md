# Team C implementation plan: status tracker

Team C: Intent Fidelity and Human Perception. Last updated **2026-11-04**.

Legend: `[x]` done · `[~]` partly done or waiting on someone · `[ ]` not started.
Notes in *italics* say where the work lives or where it differs from the plan.

## Where we left off

| Branch | State |
|---|---|
| `team-c/sprint1-walking-skeleton` | Pushed. Sprint 1 docs. No PR (team approved). |
| `team-c/sprint2-intent-capture` | Pushed. **PR #23** into `JohnDoughh/Ouro-Capstone-Fall-2026` `main`. Owner requested changes on 2026-10-19 (3 items); all three fixed and pushed (`eecb8b3`, `ada5158`, `1c90147`). Awaiting re-review. |
| `team-c/sprint3-reveal-coding` | Pushed. Branched from Sprint 2: reveal command, codebook draft and this tracker; Sprint 2 fixes merged in; coder sheets and code import added in Sprint 4 (2026-11-04). No PR yet (open one after PR #23 merges, or when Sprint 3 is complete). |

**PR #23 review (2026-10-19), all addressed**

1. Play count reset on reload/re-entry → server-held `intent_plays` log, restored by `/api/next`; a response's `play_count` must equal it.
2. Record schema did not match the sealed records → contract `2.0.0` validates the committed nested envelope (`intended`/`delivery` maps plus `artifact_id`, `delivery_codes`, `fictional`, `frozen_at`, `note`, `record_type`, `relative_path`, `salt`, `schema`). No `offer` or `required_beats`. `intent_coding_units()` derives the coding view after verification.
3. Frozen collection showed "Save status is unknown" → 409 carries `collection_closed`; the UI shows a final closed screen.

Still to do from the review: link this work to the relevant portal cards (team task). Value types of `delivery_codes`, `frozen_at`, `schema`, `record_type` and `note` were inferred from key names; ask the owner/custodian to run `scripts/verify_intent_reveal.py` on the sealed records (errors name keys, never values) to confirm before reveal.

**Portal cards (checked 2026-11-04 against `docs/Cards.png`)**

| Card | State | Where |
|---|---|---|
| Create scoring rules for the seven intent fields (Accepted) | `[~]` draft done | `docs/INTENT_CODEBOOK.md` v0.1; needs calibration and freeze |
| #586 Collect a viewer's response without showing the intended answers | `[x]` | C-2, PR #23 |
| #587 Save the original viewer response and record its hash | `[x]` | append-only `intent_responses`; freeze SHA-256 of the export; per-response `response_sha256` bound into every code (computed from the stored row, not a stored column) |
| #588 Have a different person grade what the viewer understood | `[~]` | coder sheets + import done (a coder never codes a clip they viewed); adjudication still to do |
| #589 Check that the video, response, and evaluator IDs match | `[~]` | clip, response and record are bound by SHA-256 in each code; the evaluator part waits on an intent evaluator-output contract (none exists) |
| #590 Create a repeatable comparison scoreboard and label simulated results | `[ ]` | Sprint 4 `intent-report` (`synthetic_demo` label) and Sprint 5 `make intent-pilot` |

Still to do: link the cards to PR #23 and this branch on the portal (team task).

**Next steps, in order**

1. ~~Build coder sheets and code import.~~ Done in Sprint 4, 2026-11-04 (`ouro_eval_lab/coding.py`, `tests/test_intent_coding.py`).
2. *(Proposal written 2026-11-04: `docs/ADJUDICATION_PROPOSAL.md`; send it to the delegates.)* Propose the adjudication record shape to the Team A and B delegates, then build it.
3. Team: calibrate the codebook on the practice anchors; freeze it with the pre-registration.
4. Team: send the sponsor questions (vocabulary mapping, custodian; record format and `offer`/`required_beats` are now answered by the PR #23 review); name the open roles.

**Known issues**

- 8 existing tests fail on Windows only (`WinError 32`): `with connect()` commits but never closes, so connections wait for the garbage collector. Needs a separate shared-infrastructure PR. Linux CI is unaffected; Team C tests work around it.
- PR #23's hosted CI cannot run: the owner approved it, but an owner-account billing lock stops GitHub Actions. The owner ran the checks locally (Python 3.13).
- `make` and `gh` on this machine: no `make`, so run the `make check` steps one by one. `gh` is at `C:\Program Files\GitHub CLI\gh.exe` (not on PATH until a restart).

---

## Context

The repo is a v0.1 public-safe scaffold (Python 3.11 stdlib, SQLite, vanilla-JS annotation UI). Team A (visual) and Team B (audio/temporal) already had a working PASS/HOLD annotation path. Team C's slice was the only one with no code.

**Research question** (`TEAM_SLICES.md`): Can independent viewers recover the thesis, hook, proof, offer, CTA, and critical beats from the final artifact, and can the evaluator tell when that meaning survived or became too ambiguous to judge?

**Required outputs:** an intent-manifest contract; a two-stage blinded workflow; independent coder comparison; per-component recovery/survival measures; recovery kept separate from persuasion; agreement, uncertainty, calibration and abstention analysis; failure views; drift anchors; and an independent rerun.

**Hard gates:** no real (non-team) viewers until FIU records a human-subjects determination. Synthetic only. Pseudonymous IDs. Raw responses and codes are append-only. Adjudication is stored separately.

## Design principles (apply to every work item)

- [x] Leave the shared PASS/HOLD annotation contract (2.1.0) unchanged. Intent capture is a new, separately versioned contract.
- [x] Reuse existing machinery: assignments, assignment-scoped media and the byte-range server, idempotent receipts (factored into one shared helper), SHA-256 verification, export allow-list pattern, reveal check. *Wilson CI and bootstrap reuse is for Sprint 4.*
- [x] Viewers never see the intent record, manifest, README or other viewers' responses. *Coders-never-viewers is enforced by `intent-coding-sheet`.*

---

## Sprint 1: Problem casting and contracts on paper

*Docs: `docs/TEAM_C_PROBLEM_CASTING.md`, `docs/TEAM_C_PREREGISTRATION.md`. Demo: `team_c/sprint1_demo/` (frozen).*

- [x] Problem statement
- [ ] Leader and integration delegate named *(§9 roles table says Pending)*
- [~] First 3 issues (C-1 intent contract, C-2 viewer response capture, C-3 coding codebook) *(written in §10; not opened on GitHub. C-1 and C-2 are now built, so they could be opened and closed by PR #23)*
- [x] Exclusions and handoffs written down
  - [x] Team A owns rendering and truthfulness; Team C owns whether meaning is recoverable
  - [x] Team B owns speech, caption and sync defects; Team C records comprehension disruption only as an observed effect
  - [x] Persuasion, credibility and trust excluded unless FIU approves
- [~] Vocabulary reconciled (thesis/hook/proof/offer/CTA/beats vs audience/problem/product/key_benefit/support/call_to_action/tone) *(mapping proposed in §4; waiting on sponsor and council. Finding: the records have no `offer` field)*
- [~] Pre-registration draft *(written: coding scale, ⌈2n/3⌉ survival rule, ≥3 viewers, ≥2 coders, primary outcome = Krippendorff's alpha, ambiguity definition, exclusions, seed 20261014, stopping rule. **Not frozen.**)*
- [ ] Holdout/reveal custodian named (must not be a coder)
- [x] *Extra:* `.gitattributes` keeps the demo's hash-bound files byte-exact on Windows

## Sprint 2: Intent-manifest contract + viewer stage (Stage 1)

*All on PR #23.*

### C-1: Sanitized intent-record contract

- [x] `INTENT_CONTRACT_VERSION = "2.0.0"` and `validate_intent_record` in `ouro_eval_lab/contracts.py`
  - [x] the committed nested envelope: seven strings under `intended`, seven codes under `delivery`, plus the nine top-level keys *(1.0.0's top-level `{text, delivery}` shape was wrong; fixed after the PR #23 review)*
  - [x] ~~optional `required_beats[]`~~ *(dropped: not in the records)*
  - [x] rejects unknown keys, oversized text, URLs and contact details; errors never echo values
- [x] `scripts/verify_intent_reveal.py` validates each record after the hash check *(plus `--skip-schema`)*
- [x] Tests *(in `tests/test_intent_capture.py` and `tests/test_public_intent.py`, not `test_contracts.py`)*
- [~] **Confirm the record schema with the sponsor before freezing** *(structure confirmed by the owner in the PR #23 review; value types of the metadata keys still inferred)*
- [x] `docs/DATA_CONTRACT.md` updated

### C-2: Blinded viewer response capture

- [x] `intent_responses` table *(components stored as one canonical JSON column rather than per-field columns; a new table, so no ALTER migration was needed)*
  - [x] free recall, certainty 1–5 and "could not tell" per component, plus `other_beats` *(all seven fields, including `tone`)*
  - [x] play count, play limit, `started_at`, `completed_at`
  - [x] append-only, enforced by triggers
- [x] `validate_intent_response_payload` with strict allow-list and caps
- [x] `POST /api/intent-responses/<assignment_id>?rater=` with the same 201/200/409/400/503 semantics; shared logic factored out, not copied
- [x] Assignment object in `/api/next` unchanged
- [x] `serve --study intent` *(mode exposed as top-level `study`/`play_limit` in `/api/next` and `/api/health`, not a separate `/api/config`)*
- [x] UI intent form reusing media readiness, deadline and recovery logic
- [x] Play limit to standardize exposure *(counted Play button, no scrubbing, default 2; server-held in `intent_plays` since the PR #23 review, so reload cannot reset it)*
- [x] `export-intent` (JSON/CSV) with SHA-256 recorded *(in append-only `intent_freezes`; also closes collection)*
- [x] Tests: API (201/200/409/400, rater isolation, no artifact ID/path/SHA leaks), UI state and blinding, store append-only, play-count reload, frozen-collection closed state
- [x] *Extras:* no repeat exposures in intent mode; one database per study; rater IDs that look like phone numbers rejected (shared change)
- [x] Manual browser test by a team member

## Sprint 3: Reveal + independent coding (Stage 2) + adjudication

*Branch `team-c/sprint3-reveal-coding` (pushed).*

- [~] `docs/INTENT_CODEBOOK.md` *(draft v0.1: scale, decision rules, delivery-code rules including `not_intended` → `not_applicable`, component guidance, invented practice anchors not from the study set, calibration procedure. Needs team calibration and freezing.)*
- [x] `reveal` CLI: refuses unless an `export-intent` freeze exists, runs the reveal checks, validates, loads records with `record_sha256` *(tables `intent_reveals`, which plays the role of `reveal_log`, and `intent_records`; both append-only; repeat reveal is a no-op; different records refused)*
- [x] `intent-coding-sheet --coder <id>`: randomized (response × component × record field) items; excludes the coder's own viewer responses; hides other coders' codes and viewer IDs *(done in Sprint 4. CSV; excludes every clip the coder was assigned as a viewer; also hides viewer certainty, response and artifact IDs; seed 20261014 recorded in append-only `intent_coding_sheets`; one sheet per coder)*
- [x] `intent-import-codes`: validate and append to `intent_codings`; never update; reject duplicates *(done in Sprint 4. All-or-nothing per file; blank rows skipped so coders can import in parts; identical re-import is a no-op; a changed code is refused; enforces the `not_applicable` and note rules; each code bound to `response_sha256`, `record_sha256`, `artifact_sha256` and the codebook version)*
- [~] `intent_adjudications` table + `adjudicate-intent` CLI *(coordinate the shape with Team A and B delegates first; proposal in `docs/ADJUDICATION_PROPOSAL.md`, not yet agreed)*
- [ ] Coder web UI *(stretch)*

## Sprint 4: Metrics, agreement, calibration and abstention

- [ ] `ouro_eval_lab/intent_metrics.py`: per component and clip, recovery rate with Wilson CI, survival under the pre-registered rule, contradicted rate
- [ ] Stratify by delivery code
- [ ] Comprehension disruption share
- [ ] Krippendorff's alpha (nominal and ordinal) with bootstrap CI, as a shared reusable function; tell Teams A and B
- [ ] Viewer certainty vs coded recovery (human calibration, separate from evaluator calibration)
- [ ] Ambiguity and abstention reference class
- [ ] Propose the intent evaluator-output contract through the council; then false PASS/false HOLD, Brier, ECE and risk-vs-coverage (synthetic demo outputs only until the sponsor provides frozen outputs)
- [ ] Recovery vs persuasion: separate table and report section, only if FIU approves
- [ ] `intent-report` CLI: deterministic JSON with `synthetic_demo`, disclaimer, seeds, and hashes of manifest, freeze, revealed records and codes
- [ ] Tests: hand-computed alpha fixtures, edge cases, survival boundaries, report determinism

## Sprint 5: Failure views, anchors, rerun, final report

- [ ] `intent-report --html`: offline clip × component heatmap, delivery codes, disagreement highlights, PII-screened snippets
- [ ] `data/public_intent/anchors.json` drift anchors bound by SHA-256
- [ ] `make intent-pilot`: seeded synthetic end-to-end run with byte-stable report hash, in `make check` and CI
- [ ] Intent section in `docs/INDEPENDENT_RERUN.md`; a non-builder reruns it
- [~] Docs: `CURRENT_STATUS.md` *(updated through Sprint 3 reveal)*, `README.md` commands *(updated)*, `docs/THREAT_MODEL.md` *(not yet)*, final report *(not yet)*

---

## Dependencies and risks

| Dependency or risk | Owner | Mitigation | Status |
|---|---|---|---|
| FIU human-subjects determination | FIU / Team C HS owner | Team dry runs and synthetic responses only until recorded | Open; HS owner not named |
| Sealed intent records and more sanitized manifests | Ouro sponsor | Build against the README schema; confirm before freezing | Sponsor email drafted, not sent |
| Evaluator intent outputs (none exist) | Ouro + council | Propose the contract early; synthetic demo outputs meanwhile | Not started |
| Only 4 clips (target 90–150) | Team C + custodian | More fictional clips via `scripts/generate_public_intent_clips.py`; non-coder custodian seals commitments | Not started |
| PII in free-recall text | Team C | Length caps, instructions, contact-detail rejection | **Done** at submit time (emails and phone numbers rejected in answers and rater IDs) |
| Answer leakage (README next to clips) | Facilitator | Run sessions from the UI only; log exposures | UI blinding done; codebook examples avoid study clips; exposure log not built |

## Verification (per PR and at the end)

- [~] `make check` *(run step by step on Windows; passes apart from the 8 known Windows-only errors)*
- [x] `node --test tests/web_lab_state.test.cjs` *(45 pass)*
- [~] Manual end-to-end check:
  - [x] serve in intent mode on a separate database; answer all 4 clips; replay and timeout retry
  - [x] `export-intent` and record the hash
  - [x] reveal fails before the freeze and with tampered records *(with stand-in records; real records still sealed)*
  - [~] coding sheets and import for two coders *(automated tests cover two coders; a manual run on the dry-run database is still to do)*
  - [ ] `intent-report`, byte-identical on rerun
  - [x] no artifact ID, SHA or intent text reaches the viewer API
- [~] Each PR: feature branch, Team C checkbox, docs and contracts together *(done for PR #23; shared-contract PRs need all three delegates)*
