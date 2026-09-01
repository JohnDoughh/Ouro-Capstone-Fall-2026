# Three-Team Research Slices

Status: provisional kickoff proposal  
Decision authority: each FIU team and FIU faculty must ratify the final slice during problem casting

## Design rule

Each team owns a complementary vertical slice end to end. No team is merely a frontend, backend, statistics, or documentation team.

Every slice must include:

1. a versioned extension of the shared data and rubric contracts;
2. approved synthetic or sanitized fixtures;
3. a blinded annotation workflow;
4. independent raw judgments and separate adjudication;
5. frozen anonymous evaluator outputs;
6. agreement and uncertainty analysis;
7. false PASS, false HOLD, calibration, and abstention analysis;
8. tests, limitations, and a clean independent rerun;
9. a final report that distinguishes evidence from speculation.

The three teams share interfaces, not conclusions. Each team should be independently assessable.

## Team A: Visual Truth and Continuity

### Research question

When can Ouro reliably judge whether the visible advertisement is internally coherent and commercially truthful, and when should it abstain?

### Priority families

- presenter identity continuity;
- face, hand, body, and object integrity;
- product and packaging accuracy;
- visible text and claim accuracy;
- scene-to-scene visual continuity;
- composition and occlusion;
- black frames and visible rendering defects;
- originality and obvious synthetic artifacts where operationally defined.

### Required outputs

- a bounded visual-defect ontology and rating handbook;
- real playable visual fixtures with clean and seeded-defect controls;
- timestamp or frame-range evidence for temporal visual defects;
- visual annotation interface extensions;
- per-family human agreement and uncertainty;
- human-grounded evaluator comparison;
- calibrated visual PASS, HOLD, and abstention analysis;
- visual failure views and an independent rerun.

### Why this fits Team A

The existing team profile shows the strongest combined depth in AI activity, Python/data work, software engineering, debugging, full-stack implementation, and technical teaching. This slice has the widest visual taxonomy and benefits from disciplined fixture design, reliable data pipelines, and clear rater instructions.

## Team B: Audio and Temporal Integrity

### Research question

When can Ouro reliably judge whether an advertisement's audio, speech, captions, and timeline remain coherent from beginning to end, and when should it abstain?

### Priority families

- missing, distorted, clipped, or discontinuous audio;
- speech cutoff and repetition;
- pronunciation and delivery defects;
- voice consistency;
- audio-video synchronization;
- caption accuracy and synchronization;
- abrupt cuts and missing beats;
- timeline coherence;
- black frames when caused by temporal execution;
- cross-scene audio continuity.

### Required outputs

- an audio-temporal ontology and rating handbook;
- actual playable audio and video fixtures;
- structured time-range evidence;
- media-capable blinded annotation extensions;
- repeat-consistency and inter-rater analysis;
- human-grounded evaluator comparison;
- calibrated audio-temporal PASS, HOLD, and abstention analysis;
- audio-temporal failure views and an independent rerun.

### Why this fits Team B

The existing team profile combines an AI Anchor and volunteer leader with cloud, backend, security, infrastructure, AI-program, and digital-media exposure. This slice requires reliable media handling, careful access controls, timestamped data, and operational discipline around large binary artifacts.

## Team C: Intent Fidelity and Human Perception

### Research question

Can independent viewers recover the thesis, hook, proof, offer, CTA, and required commercial beats from the final artifact, and can Ouro recognize when that meaning survived or became too ambiguous to judge?

### Priority families

- thesis survival;
- hook recovery;
- proof and evidence recovery;
- offer accuracy;
- CTA recovery;
- required critical-beat survival;
- comprehension disruption;
- evaluator ambiguity;
- bounded perceived clarity, credibility, and trust only if FIU approves the extension.

### Required outputs

- a sanitized intent-manifest contract;
- a two-stage blinded workflow in which viewers first see only the artifact;
- independent coder comparison against the frozen intent manifest;
- recovery and survival measures for each intent component;
- separation of observable intent recovery from perceived persuasion;
- human agreement, uncertainty, calibration, and abstention analysis;
- intent-focused failure views, drift-ready anchor examples, and an independent rerun.

### Why this fits Team C

The existing team profile combines an AI Practitioner and volunteer leader with deployed full-stack product development, API/authentication experience, application development, and security training. This slice has the most human-facing workflow and benefits from product thinking, careful blinding, and strong interface design.

## Cross-team integration council

Each team selects one integration delegate. The three delegates maintain these shared contracts:

- artifact and manifest contract;
- annotation envelope;
- evaluator-output envelope;
- rubric/version identifiers;
- export allow-list;
- analysis metadata;
- CI and reproducibility requirements.

Shared contract changes require:

1. a written compatibility note;
2. validator updates;
3. regression tests;
4. approval from all three integration delegates;
5. documentation updates in the same pull request.

## Sprint 1 boundary decisions

By the end of Sprint 1, the teams must freeze:

- the exact slice owned by each team;
- exclusions and handoffs;
- priority defect families;
- required artifact types;
- the initial rubric and evidence model;
- the human-subjects gate;
- shared contract ownership;
- the holdout custodian;
- the independent rerun owner;
- the minimum mandatory deliverable for each slice.

## Leader selection

This document does not appoint team leaders. FIU has asked each team to select its own leader. The skill-based allocation is provisional and must be confirmed by the students after they describe their interests, availability, and relevant experience.
