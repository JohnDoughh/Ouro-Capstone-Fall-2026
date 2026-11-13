# Team C implementation plan: status tracker

Team C: Intent Fidelity and Human Perception. Last updated **2026-11-13**.

Legend: `[x]` done · `[~]` partly done or waiting on someone · `[ ]` not started.
Notes in *italics* say where the work lives or where it differs from the plan.

## Where we left off

| Branch | State |
|---|---|
| `team-c/sprint1-walking-skeleton` | Pushed. Sprint 1 docs. No PR (team approved). |
| `team-c/sprint2-intent-capture` | Pushed. **PR #23** into `JohnDoughh/Ouro-Capstone-Fall-2026` `main`. Owner requested changes on 2026-10-15 (3 items; answered 2026-10-19); all three fixed and pushed (`eecb8b3`, `ada5158`, `1c90147`). 2026-11-04: `main` had moved ~40 commits and conflicted in 11 files; merged `main` in and resolved (`70df507`). Awaiting re-review: GitHub keeps it `BLOCKED` until the owner approves or dismisses the 2026-10-15 review. |
| `team-c/sprint3-reveal-coding` | Pushed. Branched from Sprint 2: reveal, codebook draft, this tracker, coder sheets, code import, Sprint 4 metrics and `intent-report`, both proposals. `main` merged in via Sprint 2 (`dbacf07`). **PR #39** into `main` (opened 2026-11-04; builds on #23, so merge #23 first). Head `a421266` or later. |
| `team-c/sprint5-failure-views` | Pushed 2026-11-11, extended 2026-11-13. Branched from Sprint 3: `intent-pilot`, `intent-report --html`, rerun and threat-model sections; then `intent-status`, the empty-database guard on `serve`, drift-anchor contract and `intent-anchors`, practice anchors, operator guide, limitations statement, final report draft. Upstream `main` (PR #40) merged in. **PR #42** into `main` (opened 2026-11-13, stacked on #39: merge #23, then #39, then #42). All three `MERGEABLE` at opening. |

**Session of 2026-11-04 in one paragraph.** Built coder sheets and code import, then the Sprint 4 metrics, shared Krippendorff's alpha and `intent-report`. `main` had moved ~40 commits and PR #23 conflicted in 11 files; merged `main` into Sprint 2 and then Sprint 3, and both PRs are mergeable again. Commented on PR #23 and opened PR #39. Wrote and sent the adjudication proposal to the Team A and B delegates; drafted the evaluator-output proposal for the council and a shared-alpha note for Teams A and B (both still to send). Sprint 5 is **on hold** until the team says to start.

**Session of 2026-11-11 in one paragraph.** Checked both PRs (no new reviews, both mergeable, `main` unchanged). Team B's delegate replied to the evaluator-output proposal (feedback, not approval); folded it into v2 (`c6295e0`) and documented one-judgment-per-rater, `UNSURE` and bootstrap grouping in the shared alpha functions. Found what blocks merging: Team C has read-only access upstream, and PR #23 stays blocked until JohnDoughh re-reviews; a message to him is drafted below for you to send. Team said go on Sprint 5: built the seeded synthetic pilot (`intent-pilot`, in `make check`), the offline HTML view (`intent-report --html`), and the intent sections of the rerun guide and threat model, on `team-c/sprint5-failure-views` (`677fc69`). 169 Python and 52 browser tests pass.

**Session of 2026-11-13 in one paragraph.** Course Sprint 5 asks: can someone else run it, and are we honest about what does not work? Upstream `main` had moved one PR (#40, Team A/B dropout evidence, no Team C files); merged it into Sprint 5 cleanly (Sprint 2 and 3 also merge cleanly). PR #23 still `CHANGES_REQUESTED`/`MERGEABLE`; PR #39 mergeable state `UNKNOWN` on GitHub. Hardened for operators: `intent-status` (read-only stage, counts, freeze hash, warnings, next command) and `serve --study intent` now refuses a database with no clips (it used to show viewers "0 of 0"). Built the drift-anchor contract 1.0.0 and `intent-anchors verify|sheet|check`, bound to the codebook's LF-normalized SHA-256; committed the codebook's 11 practice anchors as a draft set for calibration and added it to `make check`. Recorded a full operator walkthrough on a fresh database (`docs/TEAM_C_OPERATOR_GUIDE.md` §8), which found and fixed a viewer-count bug in the new status command. Wrote `docs/TEAM_C_LIMITATIONS.md` and the draft `docs/TEAM_C_FINAL_REPORT.md`. 200 Python and 52 browser tests pass. Sprint 5 review and retrospective drafted in the team's format for the portal.

**Check of 2026-11-11.** No new reviews or comments on PR #23 or #39 since 2026-11-04; both `MERGEABLE`; `main` unchanged (`3bc94bb`). New open PR #40 (Team A/B dropout evidence) touches no Team C files. No reply seen on GitHub from the delegates or the council.

**Waiting on others**

| What | Who | Then |
|---|---|---|
| Re-review and merge PR #23, then PR #39 | Repo owner (JohnDoughh; only he can merge, Team C is read-only) | Message him directly (draft below); answer any review comments; keep both mergeable |
| Adjudication shape (`docs/ADJUDICATION_PROPOSAL.md`, sent 2026-11-04) | Team A and B delegates | Build `intent_adjudications` + `adjudicate-intent` and the shared reference-label helper; then `intent-report` can decide survival where coders disagreed |
| Evaluator-output format (`docs/INTENT_EVALUATOR_OUTPUT_PROPOSAL.md`, v2 2026-11-11) | Team A delegate (Team B replied 2026-11-11, folded into v2); Jonathan to name the independent custodian | Build the contract, validator and the false survived / false not-survived, Brier, ECE and risk-coverage section of `intent-report` (synthetic outputs only) |
| Record value types | Owner/custodian runs `scripts/verify_intent_reveal.py` on the sealed records | Adjust the 2.0.0 validator if any inferred type is wrong |
| Persuasion | FIU | Only then add a separate persuasion section |

**PR #23 review (2026-10-19), all addressed**

1. Play count reset on reload/re-entry → server-held `intent_plays` log, restored by `/api/next`; a response's `play_count` must equal it.
2. Record schema did not match the sealed records → contract `2.0.0` validates the committed nested envelope (`intended`/`delivery` maps plus `artifact_id`, `delivery_codes`, `fictional`, `frozen_at`, `note`, `record_type`, `relative_path`, `salt`, `schema`). No `offer` or `required_beats`. `intent_coding_units()` derives the coding view after verification.
3. Frozen collection showed "Save status is unknown" → 409 carries `collection_closed`; the UI shows a final closed screen.

Value types of `delivery_codes`, `frozen_at`, `schema`, `record_type` and `note` were inferred from key names; the owner/custodian is asked to run `scripts/verify_intent_reveal.py` on the sealed records (errors name keys, never values) before reveal. 2026-11-04: `main` merged in and conflicts resolved (`70df507`); a comment on PR #23 explains the resolution.

**Portal cards (checked 2026-11-04 against `docs/Cards.png`)**

Rule agreed: a card moves to complete only when its PR merges.

| Card | Move to | Link to | State |
|---|---|---|---|
| Create scoring rules for the seven intent fields (Accepted) | stays Accepted | — | `[~]` codebook v0.1 drafted; needs calibration and freeze |
| #586 Collect a viewer's response without showing the intended answers | in review | PR #23 | `[x]` code done |
| #587 Save the original viewer response and record its hash | in review | PR #23, PR #39 | `[x]` append-only responses, freeze SHA-256, per-response `response_sha256` bound into every code (computed from the stored row) |
| #588 Have a different person grade what the viewer understood | in progress | PR #39 | `[~]` coder sheets + import done; adjudication waits on the delegates |
| #589 Check that the video, response, and evaluator IDs match | in progress | PR #39 | `[~]` clip/response/record bound by SHA-256; evaluator part waits on the council |
| #590 Create a repeatable comparison scoreboard and label simulated results | in progress | PR #39 (+ Sprint 5 PR) | `[~]` `intent-report` is repeatable and labelled synthetic; seeded pilot and HTML view built on the Sprint 5 branch; evaluator comparison still to do |

**Next steps, in order**

1. **You (team):** message Jonathan to re-review and merge PR #23 then #39 and to name the evaluator-output custodian. Send v2 of the evaluator-output proposal to the council (reply to Team B, chase Team A, ask Jonathan for a custodian) and the shared-alpha note (below) to the Team A and B delegates.
2. **You (team):** move and link the portal cards as in the table above.
3. **Claude, each session:** check PR #23 and #39 for review comments and that both are still `MERGEABLE` (`main` moves fast); if not, merge `main` into Sprint 2, then Sprint 2 into Sprint 3, and push.
4. **Claude, when the delegates reply:** build adjudication (Sprint 3 item below).
5. **Claude, when Team A replies and the council agrees v2:** build the intent evaluator-output contract and comparison (Sprint 4 item below).
6. **Team:** calibrate the codebook on the practice anchors and freeze it with the pre-registration; run the coder sheets by hand with two people on the dry-run database.
7. **Team:** send the sponsor questions (vocabulary mapping, custodian); name the open roles (leader, integration delegate, human-subjects owner, reveal custodian).
8. **Sprint 5** (started 2026-11-11). Done: pilot, HTML view, rerun and threat-model docs, `intent-status`, anchor tooling and practice anchors, operator guide, limitations statement, final report draft. Left: **team** gets a non-builder to run the intent rerun section and the operator guide; runs the calibration round with `intent-anchors sheet`/`check`; freezes the codebook, then the study anchors; fills the final report once data exist. Post the Sprint 5 review and retrospective on the capstone site by Sunday 2026-11-15. Sprint 5 PR opened as **#42** (2026-11-13), stacked on #39.

**Draft to send: message to Jonathan (repo owner)**

> Hi Jonathan — PR #23 (Team C intent capture) has had all three of your requested changes addressed since Oct 19 and is mergeable with current `main`; it's only blocked by the Oct 15 "changes requested" review. Could you re-review (or dismiss it if you're satisfied) and merge? PR #39 builds directly on it (reveal, coding, intent metrics) and is also mergeable. Locally on Windows, all Python tests, 52 browser tests, the boundary scan and the manifest checks pass. Separately, could you name an independent custodian for freezing evaluator outputs (from the evaluator-output proposal)?

**Draft to send: shared-alpha note for Teams A and B**

> Team C added `krippendorff_alpha` and `bootstrap_alpha_interval` to the shared `ouro_eval_lab/metrics.py` (PR #39). They work with any labels, so you can use them for PASS/HOLD. Any number of raters; missing ratings are fine (`None`). Nominal by default; pass `order=[...]` for ordinal scales such as severity 0–3. The bootstrap resamples groups of items, optionally within strata such as clips; pass a seed. It matches Krippendorff's published example (0.743 nominal, 0.815 ordinal) and returns `None` when alpha is undefined. One judgment per rater per unit: keep same-rater repeats out and compute them separately. `UNSURE` counts as a category unless you pass it as `None`; say which you chose. Put units that share a viewer or clip in one bootstrap cluster. Example: `krippendorff_alpha([("PASS","PASS"), ("HOLD","PASS"), ("HOLD","HOLD"), ("PASS","PASS",None)])` gives 0.533.

**Known issues**

- ~~8 existing tests fail on Windows only (`WinError 32`).~~ Fixed upstream by PR #32 (connections close on every platform); gone since `main` was merged in on 2026-11-04.
- Pilot hash: any change that alters intent report output (adjudication, evaluator comparison, metric fixes) changes the pilot report. Regenerate `team_c/intent_pilot/EXPECTED_SHA256` in the same commit and say why, or `make check` fails.
- `main` moves fast (other teams merge often). Check `mergeable` on both PRs at the start of each session. No `upstream` remote is configured: `git fetch https://github.com/JohnDoughh/Ouro-Capstone-Fall-2026.git main:refs/remotes/upstream-main`.
- PR #23's hosted CI cannot run: the owner approved it, but an owner-account billing lock stops GitHub Actions. The owner ran the checks locally (Python 3.13).
- `make` and `gh` on this machine: no `make`, so run the `make check` steps one by one. `gh` is at `C:\Program Files\GitHub CLI\gh.exe` (not on PATH until a restart).

---

## Context

The repo is a v0.1 public-safe scaffold (Python 3.11 stdlib, SQLite, vanilla-JS annotation UI). Team A (visual) and Team B (audio/temporal) already had a working PASS/HOLD annotation path. Team C's slice was the only one with no code.

**Research question** (`TEAM_SLICES.md`): Can independent viewers recover the thesis, hook, proof, offer, CTA, and critical beats from the final artifact, and can the evaluator tell when that meaning survived or became too ambiguous to judge?

**Required outputs:** an intent-manifest contract; a two-stage blinded workflow; independent coder comparison; per-component recovery/survival measures; recovery kept separate from persuasion; agreement, uncertainty, calibration and abstention analysis; failure views; drift anchors; and an independent rerun.

**Hard gates:** no real (non-team) viewers until FIU records a human-subjects determination. Synthetic only. Pseudonymous IDs. Raw responses and codes are append-only. Adjudication is stored separately.

## Design principles (apply to every work item)

- [x] Leave the shared PASS/HOLD annotation contract unchanged (2.1.0 when we started; other teams have since moved it to 2.2.0). Intent capture is a new, separately versioned contract.
- [x] Reuse existing machinery: assignments, assignment-scoped media and the byte-range server, idempotent receipts (factored into one shared helper), SHA-256 verification, export allow-list pattern, reveal check, Wilson intervals (Sprint 4).
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

*Branch `team-c/sprint3-reveal-coding`, **PR #39**.*

- [~] `docs/INTENT_CODEBOOK.md` *(draft v0.1: scale, decision rules, delivery-code rules including `not_intended` → `not_applicable`, component guidance, invented practice anchors not from the study set, calibration procedure. Needs team calibration and freezing.)*
- [x] `reveal` CLI: refuses unless an `export-intent` freeze exists, runs the reveal checks, validates, loads records with `record_sha256` *(tables `intent_reveals`, which plays the role of `reveal_log`, and `intent_records`; both append-only; repeat reveal is a no-op; different records refused)*
- [x] `intent-coding-sheet --coder <id>`: randomized (response × component × record field) items; excludes the coder's own viewer responses; hides other coders' codes and viewer IDs *(done in Sprint 4. CSV; excludes every clip the coder was assigned as a viewer; also hides viewer certainty, response and artifact IDs; seed 20261014 recorded in append-only `intent_coding_sheets`; one sheet per coder)*
- [x] `intent-import-codes`: validate and append to `intent_codings`; never update; reject duplicates *(done in Sprint 4. All-or-nothing per file; blank rows skipped so coders can import in parts; identical re-import is a no-op; a changed code is refused; enforces the `not_applicable` and note rules; each code bound to `response_sha256`, `record_sha256`, `artifact_sha256` and the codebook version)*
- [~] `intent_adjudications` table + `adjudicate-intent` CLI *(proposal `docs/ADJUDICATION_PROPOSAL.md` sent to the Team A and B delegates 2026-11-04; awaiting reply. When agreed: append-only table, decision lists the coding IDs it settles, adjudicator not one of the coders, corrections as new rows; shared reference-label helper; then wire it into `intent_metrics.reference_code`)*
- [ ] Coder web UI *(stretch)*

## Sprint 4: Metrics, agreement, calibration and abstention

*Built 2026-11-04 on `team-c/sprint3-reveal-coding` (PR #39). Survival and the reference code use agreed codes only until adjudication exists; disagreements show as `pending_adjudication`.*

- [x] `ouro_eval_lab/intent_metrics.py`: per component and clip, recovery rate with Wilson CI, survival under the pre-registered rule, contradicted rate *(plus partial-credit sensitivity, labelled exploratory; cells with < 3 responses are `insufficient_responses`)*
- [x] Stratify by delivery code *(primary components)*
- [x] Comprehension disruption share *(delivered primary components coded `not_recovered` or `contradicted`)*
- [~] Krippendorff's alpha (nominal and ordinal) with bootstrap CI, as a shared reusable function; tell Teams A and B *(`krippendorff_alpha` and `bootstrap_alpha_interval` in shared `metrics.py`, checked against Krippendorff's published example; note to Teams A and B drafted 2026-11-04, to send)*
- [x] Viewer certainty vs coded recovery (human calibration, separate from evaluator calibration) *(mean certainty by reference code; confidently wrong = contradicted with certainty 4–5)*
- [x] Ambiguity and abstention reference class *(viewers split or coders split, §8; listed by cell)*
- [~] Propose the intent evaluator-output contract through the council *(v1 2026-11-04; Team B replied 2026-11-11: per clip and field, separate format, all seven fields with tone separate, nullable probability with a reason, independent custodian. Folded into v2 the same day. Waiting on Team A; not approved)*; then false PASS/false HOLD, Brier, ECE and risk-vs-coverage (synthetic demo outputs only until the sponsor provides frozen outputs)
- [ ] Recovery vs persuasion: separate table and report section, only if FIU approves
- [x] `intent-report` CLI: deterministic JSON with `synthetic_demo`, disclaimer, seeds, and hashes of manifest, freeze, revealed records and codes *(clips are bound by their artifact SHA-256, which the reveal checked against the manifest, rather than by a manifest file hash; also records the code commit, contract and codebook versions, and import hashes; no timestamps, IDs or free text)*
- [x] Tests: hand-computed alpha fixtures, edge cases, survival boundaries, report determinism *(`tests/test_intent_metrics.py`, 18 tests)*

## Sprint 5: Failure views, anchors, rerun, final report

*Started 2026-11-11 on `team-c/sprint5-failure-views`. Everything is synthetic until real data and the open approvals exist.*

- [x] `intent-report --html`: offline clip × component heatmap, delivery codes, disagreement highlights *(`ouro_eval_lab/intent_html.py`; no scripts, renders only the report and binds it by SHA-256; failure tables for not-survived, pending-adjudication and ambiguous cells; light and dark. **Snippets left out:** the report has no free text by design; adding viewer text would need a separate, screened export and a team decision)*
- [~] Drift anchors bound by SHA-256 *(2026-11-13: anchor contract 1.0.0 and `intent-anchors verify|sheet|check` built and tested; bound to the codebook version and its LF-normalized SHA-256 and pinned by their own; the codebook's 11 practice anchors committed as `team_c/anchors/practice_anchors.json` for calibration, in `make check`. **Left:** the study set `data/public_intent/anchors.json`, after the codebook is calibrated and frozen. Team to confirm the delivery codes assumed `explicit_text` for practice anchors whose codebook entry gives none)*
- [x] *Extra (2026-11-13):* `intent-status`, read-only stage/next-command check with no IDs or text; `serve --study intent` refuses an empty database
- [x] *Extra (2026-11-13):* `docs/TEAM_C_OPERATOR_GUIDE.md` (roles, steps, irreversible actions, troubleshooting, run log, recorded walkthrough) and `docs/TEAM_C_LIMITATIONS.md`
- [x] `make intent-pilot`: seeded synthetic end-to-end run with byte-stable report hash, in `make check` and CI *(`ouro_eval_lab/intent_pilot.py`, CLI `intent-pilot`; 6 fictional clips, 5 simulated viewers, 2 simulated coders, all delivery codes; pins random IDs and the clock for the run only; hash in `team_c/intent_pilot/EXPECTED_SHA256`, same on separate runs; `tests/test_intent_pilot.py`)*
- [~] Intent section in `docs/INDEPENDENT_RERUN.md`; a non-builder reruns it *(section written 2026-11-11; the rerun by a non-builder is still to do)*
- [~] Docs: `CURRENT_STATUS.md`, `README.md` commands, `docs/THREAT_MODEL.md`, `docs/DATA_CONTRACT.md` *(all updated through 2026-11-13)*, final report *(draft `docs/TEAM_C_FINAL_REPORT.md`; results sections open until real data exist)*

---

## Dependencies and risks

| Dependency or risk | Owner | Mitigation | Status |
|---|---|---|---|
| FIU human-subjects determination | FIU / Team C HS owner | Team dry runs and synthetic responses only until recorded | Open; HS owner not named |
| Sealed intent records and more sanitized manifests | Ouro sponsor | Build against the README schema; confirm before freezing | Sponsor email drafted, not sent |
| Evaluator intent outputs (none exist) | Ouro + council | Propose the contract early; synthetic demo outputs meanwhile | v2 2026-11-11 after Team B's feedback; Team A pending |
| Adjudication shape shared by all teams | Team A and B delegates | Proposal; Team C leaves the shared table alone meanwhile; survival reported only where coders agree | Sent 2026-11-04; awaiting reply |
| Only 4 clips (target 90–150) | Team C + custodian | More fictional clips via `scripts/generate_public_intent_clips.py`; non-coder custodian seals commitments | Not started |
| PII in free-recall text | Team C | Length caps, instructions, contact-detail rejection | **Done** at submit time (emails and phone numbers rejected in answers and rater IDs) |
| Answer leakage (README next to clips) | Facilitator | Run sessions from the UI only; log exposures | UI blinding done; codebook examples avoid study clips; exposure log not built |

## Verification (per PR and at the end)

- [x] `make check` *(run step by step on Windows; 155 Python tests on Sprint 3, 169 on Sprint 5 (2026-11-11), 200 on 2026-11-13, all pass; `make check` now includes `make intent-pilot` and `make intent-anchors`)*
- [x] `node --test tests/web_lab_state.test.cjs` *(52 pass; rechecked on Sprint 5, 2026-11-13)*
- [~] Manual end-to-end check:
  - [x] serve in intent mode on a separate database; answer all 4 clips; replay and timeout retry
  - [x] `export-intent` and record the hash
  - [x] reveal fails before the freeze and with tampered records *(with stand-in records; real records still sealed)*
  - [~] coding sheets and import for two coders *(automated tests cover two coders; the 2026-11-13 walkthrough ran collection, freeze and status on a fresh database and sheets/report on the pilot database; coding by two people by hand is still to do)*
  - [~] `intent-report`, byte-identical on rerun *(automated test checks it; the synthetic pilot repeats byte for byte across separate runs and matches its recorded hash; a manual run on the dry-run database is still to do)*
  - [x] HTML view checked by eye in light and dark mode (headless Chrome screenshots, 2026-11-11)
  - [x] no artifact ID, SHA or intent text reaches the viewer API
- [~] Each PR: feature branch, Team C checkbox, docs and contracts together *(done for PR #23 and PR #39; shared-contract PRs need all three delegates)*
