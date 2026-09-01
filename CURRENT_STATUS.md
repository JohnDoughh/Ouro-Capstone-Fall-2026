# Current Status

Status date: 2026-09-01  
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
- Confidence, generic reason codes, optional notes, and start/completion times.
- Append-only raw annotation behavior.
- False PASS and false HOLD calculations with Wilson intervals.
- Brier score, expected calibration error, risk-versus-coverage, and basic Cohen's kappa.
- JSON and CSV annotation exports.
- Data contract, threat model, research protocol, and independent-rerun guide.
- Docker, Compose, Make, tests, and CI scaffolding.

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

The JSON placeholders are not full video. Actual MP4 or other approved video containers, audio tracks, temporal playback, and timestamped defect evidence are still required.

### Annotation depth

The current interface captures only:

- PASS, HOLD, or UNSURE;
- confidence;
- four generic reason groups;
- an optional note.

It does not yet capture the required final ontology, including defect timestamps, perceptual severity, commercial-meaning recovery, suspected failure origin, rubric version, or structured evidence.

### Adjudication

A database table is present, but there is no adjudication API, interface, reviewer role, or append-only adjudication workflow.

### Calibration and abstention

The scaffold calculates basic calibration metrics, but it does not yet provide:

- precision, recall, or F1;
- reliability plots;
- pre-registered asymmetric error costs;
- human-grounded evaluator calibration;
- an evaluator NOT_REVIEWED or insufficient-evidence state;
- policy selection that is isolated from the holdout.

### Intent Fidelity

Intent Fidelity is documented but not implemented. Missing elements include:

- a sanitized intent-manifest contract;
- blinded viewer-recovery questions;
- independent coder comparison;
- thesis, hook, proof, offer, CTA, and critical-beat survival metrics;
- separation between observable recovery and perceived persuasion.

### Failure analysis and drift

The browser currently provides an annotation interface, not the promised failure-analysis dashboard. The evaluator-drift protocol is documented but has no implemented anchor-set registry, hidden holdout, paired version comparison, or versioned evaluator report card.

### Access and privacy

Do not collect real participant data until these are resolved:

- FIU human-subjects determination;
- named access and authorization;
- role separation;
- aggregate-result access control;
- access logging;
- incident contact;
- retention and deletion schedule;
- protection against PII in free-text notes and self-selected rater IDs;
- review of the public export boundary.

The current boundary scanner skips the generated data directory. That behavior is acceptable only for synthetic demo output and must not be treated as validation of real annotation exports.

### Deployment

The local Make workflow is the demonstrated path. Docker and Compose require a clean-start verification. The named Compose volume can hide image-time seeded data, so the startup path must initialize or seed an empty volume explicitly.

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
- frozen evaluator outputs using anonymous version aliases;
- an Ouro-controlled private-to-public export adapter;
- the first priority defect families;
- sanitized intent manifests for the Intent Fidelity subset;
- rights, likeness, voice, and export approval for every Ouro-supplied artifact;
- weekly product and technical context;
- timely blocker resolution.

No Ouro production access, customer data, private prompts, evaluator implementation, routing, repair logic, credentials, commercial thresholds, spend, ROAS, or live campaign data may enter this repository.
