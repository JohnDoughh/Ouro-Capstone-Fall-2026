# Current Status

Status date: 2026-09-24  
Repository phase: public-safe v0.1 research scaffold  
Research status: no real participant data has been approved or collected

## Bottom line

This repository is a working kickoff scaffold, not a completed research lab and not a source of research findings. It is sufficient for the FIU teams to begin design, implementation, and validation work. It is not yet approved for real participant annotation or suitable for drawing conclusions about Ouro.

The implementation commit has passing CI for unit tests, compilation, public-boundary scanning, synthetic bootstrap, benchmark execution, manifest verification, and byte-for-byte reproducibility of the synthetic report.

## Built and working

- Python 3.11 application with no required third-party runtime packages.
- Browser-based annotation interface.
- SQLite storage for artifacts, assignments, annotations, and an adjudication schema.
- Deterministic synthetic fixture generation.
- SHA-256 manifests, byte-length validation, and tamper rejection.
- Anonymous evaluator-output contract.
- Randomized assignments and repeat-item generation.
- PASS, HOLD, and UNSURE human judgments.
- Five-point human confidence, 0-to-3 severity, generic reason codes, optional notes, and start/completion times.
- Append-only raw annotation behavior.
- False PASS and false HOLD calculations with Wilson intervals.
- Brier score, expected calibration error, risk-versus-coverage, and basic Cohen's kappa.
- JSON and CSV annotation exports.
- Playable fictional MP4 practice fixtures with byte-bound manifests.
- A separately versioned native AVC inspection validator/CLI that preserves native decisions and explicitly excludes unavailable probability from calibration.
- Data contract, threat model, research protocol, and independent-rerun guide.
- Docker, Compose, Make, tests, CI scaffolding, and an idempotent empty-volume startup path.

## Important limitations

### Benchmark validity

The current benchmark joins anonymous evaluator outputs directly to seeded synthetic truth. It does not yet compare Ouro with an independently derived human reference label. Human annotation exports and evaluator benchmark execution are separate paths.

### Agreement analysis

The current agreement endpoint uses the first two non-UNSURE annotation rows for each artifact. Because repeat assignments can create multiple rows from the same rater, this must be replaced before reporting inter-rater agreement. The final design must separate:

- within-rater repeat consistency;
- between-rater agreement;
- adjudicated reference labels;
- uncertainty and disagreement distributions.

The final multi-rater method should support at least three independent raters and use Krippendorff's alpha or another pre-registered method suitable for the selected label scale.

### Media realism

The synthetic corpus contains 16 demonstration artifacts:

- SVG image fixtures;
- WAV tone fixtures;
- text fixtures;
- JSON frame-sequence placeholders labeled as video.

The original JSON placeholders are not full video. A public-safe fictional MP4 pair now exercises browser playback and visual review, but broader approved full-video/full-audio coverage and timestamped evidence remain required.

### Annotation depth

The current interface captures:

- PASS, HOLD, or UNSURE;
- confidence on a five-point scale;
- severity from 0 (none) to 3 (severe);
- optional defect timestamp(s);
- optional structured evidence on `HOLD` (Team A rubric version, defect family ID, region, reference SHA-256, evidence description), collected by the rating form only when HOLD is selected, then stored and exported as entered;
- four generic reason groups;
- an optional note.

It does not yet capture the rest of the required final ontology, including commercial-meaning recovery or suspected failure origin. Existing annotations from before timestamp capture are retained with unknown timestamps and identified as legacy confidence in exports.

### Adjudication

A database table is present, but there is no adjudication API, interface, reviewer role, or append-only adjudication workflow.

### Calibration and abstention

The scaffold calculates basic calibration metrics, but it does not yet provide:

- precision, recall, or F1;
- reliability plots;
- pre-registered asymmetric error costs;
- human-grounded evaluator calibration;
- human-grounded evaluator calibration;
- policy selection that is isolated from the holdout.

Native AVC inspection is now separated from v1 calibration: its final probability
is explicitly unavailable/null, so native AVC records are excluded rather than
coerced into Brier/ECE calculations.

### Intent Fidelity

Intent Fidelity Stage 1 is implemented (Team C, Sprint 2):

- intent-record contract `2.0.0`, matching the committed nested envelope of
  the sealed records (structure checked in the PR #23 review), validated by
  `scripts/verify_intent_reveal.py` after the commitment check;
- blinded viewer capture: `serve --study intent`, a recall form with certainty
  and “could not tell”, a server-held play limit that survives reload
  (append-only `intent_plays`), no repeat exposures, append-only
  `intent_responses`, and idempotent receipts;
- `export-intent`, which freezes responses by SHA-256 and closes collection;
  the browser shows a final “collection closed” state after the freeze;
- `reveal`, which refuses until a freeze exists and loads verified records
  into append-only tables bound to that freeze (Sprint 3);
- blinded coder sheets (`intent-coding-sheet`) and append-only code import
  (`intent-import-codes`); each code is bound to the SHA-256 of the exact
  response, revealed record and clip (Sprint 4);
- a draft coding codebook, `docs/INTENT_CODEBOOK.md` (not yet calibrated or
  frozen);
- `intent-report`, a deterministic JSON report labelled synthetic: recovery,
  contradiction and survival per clip and component, delivery strata,
  comprehension disruption, viewer calibration, the ambiguity list, and
  Krippendorff's alpha with a bootstrap interval (shared function in
  `metrics.py`) (Sprint 4);
- `intent-report --html`, an offline HTML view of that report: a clip ×
  component heatmap with survival, delivery codes, ambiguity and coder
  disagreement, plus failure tables; no scripts, no free text, bound to the
  report's SHA-256 (Sprint 5);
- `intent-pilot` (and `make intent-pilot`, run by `make check`): a seeded
  synthetic run of the whole intent study, from fictional records to the
  report, with simulated viewers and coders. Its report hash is recorded in
  `team_c/intent_pilot/EXPECTED_SHA256` and must match byte for byte
  (Sprint 5);
- `intent-status`: a read-only check that prints a study database's stage
  (empty, collecting, frozen, revealed, coding, coded), counts, the freeze
  hash, warnings against the pre-registered minimums, and the next command;
  `serve --study intent` now refuses a database with no ingested clips
  (Sprint 5);
- drift-anchor contract `1.0.0` and `intent-anchors verify|sheet|check`,
  with the codebook's practice anchors committed as a draft set for the
  calibration round (`team_c/anchors/`, checked by `make check`) (Sprint 5);
- an operator guide with a recorded walkthrough
  (`docs/TEAM_C_OPERATOR_GUIDE.md`) and a limitations statement
  (`docs/TEAM_C_LIMITATIONS.md`) (Sprint 5).

Still missing:

- adjudication records (shape proposed to Teams A and B in
  `docs/ADJUDICATION_PROPOSAL.md`); until then, survival is reported only
  where coders agree;
- offer and critical-beat measures (not in the sealed records); thesis, hook,
  proof and CTA are reported only as derived labels on their fields;
- evaluator comparison, which needs an intent evaluator-output contract;
- separation between observable recovery and perceived persuasion in reporting.
  Stage 1 collects no persuasion items;
- study drift anchors (`data/public_intent/anchors.json`): the format and
  checks exist, but the set waits for the codebook to be calibrated and
  frozen;
- a rerun of the intent section of `docs/INDEPENDENT_RERUN.md` by someone who
  did not build it;
- free-text snippets in the HTML view (left out: the view shows only the
  report, which carries no viewer text).

### Failure analysis and drift

The browser currently provides an annotation interface, not the promised failure-analysis dashboard. The evaluator-drift protocol is documented but has no implemented anchor-set registry, hidden holdout, paired version comparison, or versioned evaluator report card.

### Access and privacy

Do not collect real participant data until these are resolved:

- FIU human-subjects determination;
- named access and authorization;
- role separation;
- authenticated post-freeze aggregate-result access control (the web aggregate endpoint is disabled during collection, but this does not replace the remaining access gates);
- access logging;
- incident contact;
- retention and deletion schedule;
- protection against PII in free-text notes and self-selected rater IDs;
- review of the public export boundary.

The current boundary scanner skips the generated data directory. That behavior is acceptable only for synthetic demo output and must not be treated as validation of real annotation exports.

### Deployment

The local Make workflow is the demonstrated path. Docker and Compose now initialize
or verify the deterministic synthetic demo at container start, including when the
named data volume is empty. The Compose service also exposes a health check. A second
person must still record the independent clean-checkout rerun required by the protocol.

### Holdout integrity

Split labels exist in the manifest, but holdout truth is visible to repository contributors and the benchmark reads all splits. A real study needs a pre-registered split policy, protected holdout custody, and analysis code that cannot silently tune against the holdout.

### Sanitized artifacts

The public contract currently requires `synthetic: true`. The research brief also allows separately approved sanitized artifacts, but a reviewed sanitized-ingest contract and Ouro-controlled release process have not been implemented.

## Gates before real annotation

All of the following must be satisfied:

1. FIU records the applicable human-subjects determination.
2. The protocol, ontology, primary outcomes, sample target, stopping rule, exclusions, and analysis seed are pre-registered.
3. Authentication, authorization, result blinding, logging, retention, deletion, and incident ownership are documented and tested.
4. The annotation contract includes rubric version, structured evidence, defect timing where relevant, severity, and permitted reason codes.
5. Repeat consistency and inter-rater agreement are calculated separately and tested.
6. The benchmark derives a human reference label under a pre-registered rule and compares frozen evaluator outputs against it.
7. Actual approved full-video and full-audio fixtures work end to end.
8. Sanitized artifacts, if used, pass a separately approved release process.
9. The holdout is protected from development and calibration.
10. A clean environment reproduces the release candidate and its report hash.

## Ouro sponsor inputs still required

Ouro must provide, after the appropriate approvals:

- approved synthetic and separately reviewed sanitized artifact packages;
- authorized sanitized native AVC evaluation packages using anonymous version aliases;
- the Ouro-controlled private-to-public export adapter and approved release record;
- the first priority defect families;
- sanitized intent manifests for the Intent Fidelity subset;
- rights, likeness, voice, and export approval for every Ouro-supplied artifact;
- weekly product and technical context;
- timely blocker resolution.

No Ouro production access, customer data, private prompts, evaluator implementation, routing, repair logic, credentials, commercial thresholds, spend, ROAS, or live campaign data may enter this repository.
