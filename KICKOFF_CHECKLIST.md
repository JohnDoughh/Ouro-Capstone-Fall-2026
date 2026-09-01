# First Combined Meeting

Proposed time: Thursday, September 3, 2026 at 5:00 PM Eastern  
Format: online combined meeting with all three teams or their leaders  
Target duration: 60 minutes

## Sponsor prerequisites

Before the call, confirm:

- FIU has accepted three teams for the project;
- the previously discussed sponsorship remains a single $5,000 program gift;
- students have the research brief and repository link;
- students may contact the sponsor by email or by text/WhatsApp only;
- no real participant annotation begins before FIU determines the applicable human-subjects path.

Do not place private contact details in this public repository.

## Pre-read

Every participant should review:

1. `README.md`
2. `CURRENT_STATUS.md`
3. `TEAM_SLICES.md`
4. `docs/DATA_CONTRACT.md`
5. `docs/RESEARCH_PROTOCOL.md`
6. `docs/THREAT_MODEL.md`

## Agenda

### 0-10 minutes: Ouro and the scientific problem

- What Ouro does.
- Why full-artifact evaluation is a reliability bottleneck.
- The cost of a false PASS.
- The cost of a false HOLD.
- Why calibrated abstention matters.
- Why this is independent validation rather than product development.

### 10-20 minutes: Scaffold demonstration

- Deterministic fixture generation.
- SHA-256 manifest verification.
- Blinded annotation flow.
- Frozen anonymous evaluator output.
- Synthetic benchmark and reproducibility.
- Current limitations and why no synthetic metric is a research finding.

### 20-35 minutes: Ratify the three vertical slices

- Team A: Visual Truth and Continuity.
- Team B: Audio and Temporal Integrity.
- Team C: Intent Fidelity and Human Perception.
- Resolve overlap, exclusions, and shared interfaces.
- Each team states what it owns and what it deliberately leaves to the others.

### 35-50 minutes: Governance and integration

- Team-selected leaders.
- One integration delegate per team.
- Branch, pull-request, review, and merge rules.
- Human-subjects owner.
- Holdout custodian.
- Data-release and privacy owner.
- Independent rerun owner.
- Weekly combined meeting cadence.

### 50-60 minutes: Immediate deliverables

Confirm who will produce each item and by when.

## Required outputs from each team

For the problem-casting submission, each team should provide:

- the problem in its own words;
- its vertical slice;
- explicit exclusions and handoffs;
- must-ship deliverables;
- definition of done;
- five-sprint plan;
- initial risks and dependencies;
- proposed leader and integration delegate;
- the first three repository issues it will own.

## Student skill confirmation

Public information was used only to form a provisional team-level hypothesis. During the meeting, every student should state:

- preferred technical role;
- strongest languages and frameworks;
- statistics and experimental-design experience;
- media-processing experience;
- frontend, API, database, testing, security, and documentation experience;
- preferred research question;
- availability and constraints.

Final task allocation must be based on student-confirmed information and FIU assessment, not assumed from public profiles.

## Non-negotiable boundaries

- No Ouro production or private repository access.
- No customer, campaign, spend, ROAS, or live-performance data.
- No credentials, production URLs, private prompts, evaluator implementation, thresholds, routing, repair logic, or hidden reasoning.
- No live ad generation, repair, launch, or paid-provider use.
- No human annotation until FIU records the applicable determination.
- Raw disagreement is preserved.
- Adjudication never overwrites an original judgment.
- Synthetic demo metrics are never presented as findings.

## Definition of a successful first meeting

The meeting succeeds when:

- all three slices are non-overlapping and independently assessable;
- leaders and integration delegates have a selection process;
- shared contracts have named owners;
- every team can write its problem statement and five-sprint plan;
- no team believes the scaffold is the completed research system;
- no student is waiting for undocumented access or proprietary Ouro material.
