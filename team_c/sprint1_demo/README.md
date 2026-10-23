# Team C Sprint 1 walking skeleton (workflow demonstration)

Team C: Intent Fidelity and Human Perception.

This package shows the smallest end-to-end path for Team C's question, on one
fictional ad. **Every input is fictional or simulated. The result is a workflow
demonstration, not evidence about AVC or about real viewers.**

```
fixture (fictional ad script)
   -> intent manifest (frozen answer key, bound to the fixture's SHA-256)
   -> viewer response (fictional test record V-001)
   -> evaluator output (simulated, not real AVC output)
   -> compare.py
   -> scoreboard.csv
```

## Files

| File | What it is |
|---|---|
| `fixtures/fixture_ad_001.md` | Fictional ad script standing in for a rendered video. The only file a viewer sees. |
| `contracts/intent_manifest.json` | Frozen intent record: thesis, hook, proof, offer, CTA. Bound to the fixture by SHA-256. Never shown to the viewer. |
| `annotations/viewer_response_001.json` | **Fictional test response.** V-001 is not a real person. No real participant data is collected before FIU's human-subjects determination. |
| `evaluator_outputs/avc_output_001.json` | **Simulated evaluator record** (`simulated-evaluator-v0`). Hand-written to match the evaluator-output shape. Says nothing about AVC. |
| `compare.py` | Per-beat comparison. Stops if the fixture no longer matches the manifest's hash. |
| `scoreboard.csv` | Output: one row per beat. |
| `SHA256SUMS` | Expected hashes for every input and for the scoreboard. |
| `PROBLEM_CASTING_PROPOSAL.md` | Sprint 1 problem-casting proposal. |

## Rerun from a clean checkout

Needs Python 3.11+ and no other packages.

```
git clone https://github.com/AlejandroCordovilla/Ouro-Capstone-Fall-2026.git
cd Ouro-Capstone-Fall-2026
git checkout team-c/sprint1-walking-skeleton
cd team_c/sprint1_demo

shasum -a 256 -c SHA256SUMS     # 1. inputs and expected output are unchanged
python3 compare.py              # 2. regenerate scoreboard.csv
shasum -a 256 -c SHA256SUMS     # 3. regenerated scoreboard matches byte for byte
```

On Linux, use `sha256sum -c SHA256SUMS`. Every line should print `OK`.

Expected result: 4 of 5 beats agree. The `offer` beat disagrees: the simulated
evaluator passes it at 0.64 confidence while the fictional viewer flags the
deadline as ambiguous. This shows the shape of the disagreement the pipeline is
built to surface. It is not a finding.

## Known limits

- One fixture, one fictional viewer, one simulated evaluator record. No agreement
  statistic is meaningful at this size.
- The fixture is a text script, not playable media.
- `compare.py` uses a documented placeholder rule (viewer confidence >= 3 and no
  ambiguity flag) instead of an independent coder. A separate coder who did not
  watch the ad replaces it in Sprint 2.
- This package does not use the shared repository's data contracts. Sprint 2
  moves Team C onto `data/public_intent` (clip01-04, sealed intent records) and
  the lab's annotation and export flow.
