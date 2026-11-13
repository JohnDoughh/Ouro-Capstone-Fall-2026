# Team C final report: Intent Fidelity and Human Perception

Status: **DRAFT, 2026-11-13.** Sections marked *Open* need results that do not
exist yet. Nothing in this report is a research finding; every number in it is
from synthetic data and is labelled so.

## 1. Question

Can independent viewers recover what an advertisement was meant to say
(audience, problem, product, key benefit, support, call to action, and tone)
from the final video, and can an evaluator tell when that meaning survived or
became too ambiguous to judge? (`TEAM_SLICES.md`, Team C.)

## 2. What we built (evidence: code and tests in this repository)

| Required output | What exists | Where |
|---|---|---|
| Sanitized intent-manifest contract | Intent record contract 2.0.0, matched to the sponsor's sealed envelope, strict allow-list, no values in errors | `ouro_eval_lab/contracts.py`, `docs/DATA_CONTRACT.md` |
| Two-stage blinded workflow | Stage 1 viewer capture with a server-held play limit; freeze by SHA-256; reveal that refuses before the freeze and checks every record against its commitment; Stage 2 coder sheets that hide viewer identity and never give a coder a clip they viewed | `serve --study intent`, `export-intent`, `reveal`, `intent-coding-sheet`, `intent-import-codes` |
| Independent coder comparison | Append-only codes, each bound to the response, record and clip by SHA-256 | `ouro_eval_lab/coding.py` |
| Recovery and survival per component | Recovery and contradiction rates with Wilson intervals; survival under the pre-registered ⌈2n/3⌉ rule; delivery strata | `intent-report` |
| Recovery kept separate from persuasion | No persuasion items collected; report section marked not available | `intent-report` |
| Agreement, uncertainty, calibration, abstention | Krippendorff's alpha (shared function, checked against the published example) with bootstrap interval; viewer certainty against coded recovery; ambiguity reference class | `ouro_eval_lab/metrics.py`, `intent_metrics.py` |
| Failure views | Offline HTML heatmap and failure tables, bound to the report by SHA-256 | `intent-report --html` |
| Drift-ready anchors | Anchor contract 1.0.0, bound to the codebook text; blind re-coding sheet and coder check; practice set for calibration | `intent-anchors`, `team_c/anchors/` |
| Independent rerun | Seeded synthetic pilot with a recorded report hash, in `make check`; rerun guide; operator guide with a recorded walkthrough | `intent-pilot`, `docs/INDEPENDENT_RERUN.md`, `docs/TEAM_C_OPERATOR_GUIDE.md` |

Verification on 2026-11-13 (Windows 11, Python 3.14.7): 200 Python tests and
52 browser-state tests pass; the public-boundary scan, all three manifest
checks, the pilot hash and the anchor binding pass.

## 3. What we ran (synthetic only)

The pilot runs the whole protocol on 6 fictional clips with 5 simulated
viewers and 2 simulated coders whose behaviour follows probabilities we chose.
**Synthetic demo. Not a research finding.**

| Pilot output | Value | What it shows |
|---|---|---|
| Report SHA-256 | `12807ee8…4b27`, identical on every run | The analysis is deterministic |
| Primary cells | 8 survived, 14 not survived, 13 pending adjudication, 1 not applicable (of 36) | Every survival state is reachable and reported |
| Primary nominal alpha | 0.84 (95% CI 0.78–0.88) | The agreement code runs end to end; the value reflects our invented 5% coder slip rate, nothing more |
| Delivery strata | All six delivery codes appear | Stratified reporting works |

A dry run on the four public fictional clips (three team-member IDs, placeholder
answers) confirmed through the live server that no answer-bearing field reaches
a viewer, that retries do not duplicate answers, and that the freeze closes
collection (`docs/TEAM_C_OPERATOR_GUIDE.md` §8).

## 4. What we can and cannot claim

**Can claim (tested):** the workflow keeps viewers blind to the intended
answers, keeps raw judgments and disagreement, binds every code to the exact
inputs by SHA-256, and gives the same report from the same inputs.

**Cannot claim:** anything about how well real viewers recover intent, how
reliable human coding of intent is, or how any evaluator performs. Those need
real participants, the revealed sealed records, adjudication and evaluator
outputs, none of which exist yet. The full list is in
[`TEAM_C_LIMITATIONS.md`](TEAM_C_LIMITATIONS.md).

## 5. Results with real data

*Open.* Requires: FIU human-subjects determination; frozen codebook and
pre-registration; revealed sealed records; at least 3 viewers per clip and 2
coders; adjudication records.

## 6. Evaluator comparison

*Open.* Requires the council to agree the intent evaluator-output format
(`docs/INTENT_EVALUATOR_OUTPUT_PROPOSAL.md`, v2) and frozen evaluator outputs
from an independent custodian. Planned: false survived / false not-survived,
Brier score, expected calibration error and risk-versus-coverage, with
abstention reported separately.

## 7. Reproduce

```
python -m ouro_eval_lab.cli intent-pilot --out data/exports/intent-pilot.json --html data/exports/intent-pilot.html --expect team_c/intent_pilot/EXPECTED_SHA256
```

It must print `matches team_c/intent_pilot/EXPECTED_SHA256`. Full steps:
`docs/INDEPENDENT_RERUN.md`.
