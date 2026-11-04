# Team C Problem-Casting Proposal (Sprint 1)

Research area: Intent Fidelity and Human Perception
Central question: Can independent viewers recover the intended thesis, hook,
proof, offer, CTA, and required commercial beats from the final advertisement,
and can Ouro recognize when that meaning survived or became too ambiguous to
judge?

---

## 1. Bounded initial set of intent-fidelity dimensions

For Sprint 1, Team C is scoping to five beats, chosen because they are the
minimum set needed to say an ad's core message survived at all:

- **Thesis survival:** did the viewer recover the main claim?
- **Hook recovery:** did the opening moment register as intended?
- **Proof and evidence recovery:** did the viewer recover supporting evidence,
  including correctly recovering that none was present?
- **Offer accuracy:** did the viewer recover the actual offer/terms?
- **CTA recovery:** did the viewer recover the intended action?

Deferred past Sprint 1 (not excluded, just not yet in scope):
**required critical-beat survival** (multi-beat combinations), **comprehension
disruption** (mid-ad breakdowns), and **evaluator ambiguity** (AVC's own
uncertainty signal). These depend on having more than one fixture and more
than one viewer, which Sprint 2 will add.

## 2. Initial sanitized intent-manifest structure

See `contracts/intent_manifest.json`. Each beat has a plain-language
description, a `required` flag, and an optional `expected_recovery` field for
beats where the correct answer is "nothing was there" (e.g. our proof gap).
Versioned (`manifest_version`) and tied to an `artifact_id` and
`artifact_sha256` so it can bind to a real Ouro artifact later without a
format change.

## 3. Two-stage blinded workflow

**Stage 1 (implemented this sprint):** viewer sees only the artifact, with no
access to the manifest, and records what they recovered per beat, their
confidence (1-5), and whether they flag ambiguity.

**Stage 2 (Sprint 2):** an independent coder who did not watch the ad
scores the viewer's free-text response against the manifest to produce a
match/no-match, so recovery scoring isn't self-graded by the same person who
watched the ad.

## 4. How viewers describe/select recovered messages

Sprint 1 uses free-text recall per beat (see `annotations/viewer_response_001.json`)
rather than multiple-choice, because free recall is a harder and more honest
test of whether the message actually landed. Multiple-choice recognition is a
candidate lower-cost alternative for Sprint 2 if free-text coding proves too
slow to scale.

## 5. Independent coder comparison against the frozen manifest

Not yet implemented with a real second coder (single-viewer skeleton this
sprint). The comparison script (`compare.py`) currently applies one
transparent, documented rule per beat as a placeholder for that coder
judgment. This rule is explicitly flagged in the code as provisional and not
a rubric.

## 6. Representing confidence, uncertainty, and ambiguity

Each viewer beat response carries a `confidence` score (1-5) and a boolean
`ambiguity_flag`. Each AVC beat judgment carries a `confidence` float
(0.0-1.0). The scoreboard keeps both alongside the pass/fail comparison so
disagreement severity is visible, not just whether the beat matched.

## 7. Keeping observable recovery separate from persuasion

The manifest and viewer schema only ask "what did you recover," never "did
you like it" or "did it convince you." No field in `viewer_response_001.json`
records persuasion, credibility, or trust. Per the project boundary, that
extension stays out unless FIU approves it.

## 8. What belongs exclusively to Team C

- The intent-manifest contract and its versioning
- The blinded recovery workflow and viewer instrument
- Recovery/survival scoring per beat
- Comparison against frozen AVC output for intent-related beats
- Calibration and abstention analysis for intent judgments specifically

## 9. What hands off to Team A or Team B

- Whether captions/text render correctly as visual objects → **Team A**
- Whether audio/captions are accurate and synchronized in time → **Team B**
- Whether a black frame is a visible defect (A) vs. a temporal interruption (B)
- Team C only asks: given what's on screen, did the *meaning* survive?
  execution defects that A/B catch are a separate question from ours, even
  when they touch the same frame.

## 10. Smallest end-to-end intent slice, demonstrated this sprint

Implemented in this repository:

```
fixtures/fixture_ad_001.md          (synthetic ad script)
contracts/intent_manifest.json      (frozen answer key)
annotations/viewer_response_001.json (fictional test response, V-001)
evaluator_outputs/avc_output_001.json (simulated evaluator output)
compare.py                          (runs the comparison)
scoreboard.csv                      (output, one row per beat)
```

Run it with `python3 compare.py`. It is fully reproducible: same inputs,
same output, every time.

**Result this run (workflow demonstration, not evidence):** 4 of 5 beats agree
between the simulated evaluator output and the fictional viewer. The "offer" beat disagreed: the simulated evaluator passed it
at 64% confidence while the fictional viewer was ambiguous about the exact deadline.
That single disagreement is the shape of finding Team C exists to produce,
even though both the AVC output and the single viewer here are placeholders,
not real findings.

## 11. Cross-team integration delegate

To be confirmed in the Team C channel and with the Team A/B leads.

## 12. First three proposed GitHub issues

1. **Define the v1 intent-manifest JSON schema** and add a validator, so all
   future manifests are checked automatically rather than eyeballed.
2. **Build the Stage 2 independent-coder scoring step**, replacing the
   placeholder rule in `compare.py` with a real second-coder comparison
   against the manifest.
3. **Expand from 1 fixture/1 viewer to a small fixture set** (3-5 synthetic
   ads, 2+ viewers each) to get a first real inter-rater agreement number
   instead of a single anecdotal run.

---

## Honest status for Sprint 1

What works: the manifest format, the blinded single-viewer workflow, the
comparison logic, and a reproducible one-command run producing a scoreboard.

What's still placeholder: the viewer response (fictional test data), the
evaluator output (simulated, clearly labeled), and
the comparison rule inside `compare.py` (a stand-in for real Stage 2 coding).

What's not done: testing this cast problem against Johnathan directly, and
selecting our integration delegate. Both carried over from Sprint 1.
