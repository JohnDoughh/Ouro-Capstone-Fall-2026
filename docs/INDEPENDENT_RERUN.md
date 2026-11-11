# Independent rerun

A person who did not build the analysis performs this procedure.

1. Start from a clean checkout and record the commit SHA.
2. Run `make check`.
3. Run `make clean && make bootstrap && make benchmark`.
4. Verify the manifest's artifact hashes independently:
   `python -m ouro_eval_lab.cli verify --manifest data/fixtures/manifest.json`.
5. Record Python/OS versions, seed, manifest hash, evaluator-output hash, and report hash.
6. Compare the generated report byte-for-byte with the expected release artifact, or document every explained difference.
7. Confirm `synthetic_demo` is correct and that no prohibited fields appear.
8. Sign and date the rerun record in the release notes.

The builder should not coach the rerunner through undocumented steps. Any missing step is a handoff defect and should be fixed in the repository.

## Orbit comparison human-evaluator (card #532)

Run by someone who did not build it, from a fresh clone, with no help from the builder.

1. `git clone https://github.com/JohnDoughh/Ouro-Capstone-Fall-2026.git`, then `cd Ouro-Capstone-Fall-2026`, and record `git rev-parse HEAD`, OS and Python version.
2. `python -m ouro_eval_lab.cli verify --manifest data/public_playable/manifest.json` must report `"verified": 2`.
3. Download the saved response export linked on card #813. Hash it (`sha256sum` or PowerShell `Get-FileHash`) and confirm it matches the hash recorded on #813.
4. `python -m ouro_eval_lab.cli compare --manifest data/public_playable/manifest.json --outputs data/public_playable/simulated_evaluator_outputs.json --responses <export.json> --out data/exports/orbit-compare.json`
5. `outputs_sha256` in the report must be `baf609996dc1ee5c88e307b66193994f466cd4f079f98e0673787ca41be94c90`.
6. Print the report SHA-256 with `sha256sum data/exports/orbit-compare.json` or, in PowerShell, `Get-FileHash data\exports\orbit-compare.json` (PowerShell prints it in uppercase). It must equal the report hash recorded on #532.

Record every step that failed or needed help.

Use a separate report output path: the command refuses paths (including
symbolic or hard-link aliases) that would overwrite the manifest, evaluator
outputs, saved responses or media. JSON inputs are UTF-8 on every platform.

Limitations: evaluator outputs are simulated test data, not AVC. The response is a teammate practice rating, not research data. The comparison measures human vs evaluator agreement, not accuracy against ground truth. Do not regenerate or edit the frozen outputs or the saved export. The report contains evaluator verdicts per artifact hash, so keep it away from anyone who has not finished rating.

## Intent fidelity pilot (Team C)

Run by someone who did not build it, from a fresh clone, with no help from the builder.
Everything here is synthetic: fictional records, simulated viewers and simulated coders.
The result shows the protocol is reproducible. It is not a research finding.

1. Clone the repository, then record `git rev-parse HEAD`, OS and Python version (3.11 or later).
2. `python -m ouro_eval_lab.cli intent-pilot --out data/exports/intent-pilot.json --html data/exports/intent-pilot.html --expect team_c/intent_pilot/EXPECTED_SHA256`
   (or `make intent-pilot` where `make` exists).
3. It must print `matches team_c/intent_pilot/EXPECTED_SHA256`. The printed `sha256` is the report hash;
   check it yourself with `sha256sum data/exports/intent-pilot.json` or, in PowerShell,
   `Get-FileHash data\exports\intent-pilot.json` (uppercase output).
4. Run step 2 again: the hash must be the same.
5. Open `data/exports/intent-pilot.html` in a browser with the network off. Confirm the
   "Synthetic demo. Not a research finding." banner, that its footer lists the report hash from
   step 3, and that no viewer or coder IDs or free-text answers appear.
6. Optional: add `--workdir <empty directory>` to keep the pilot's fictional clips, sealed records,
   commitments, response freeze and database for inspection.

Record every step that failed or needed help.

What the pilot runs, in order, through the same code as a real study: fictional clips and
sealed records with SHA-256 commitments, `ingest`, viewer responses with server-held play
counts, the response freeze, `reveal`, two coders' blinded sheets and code import, and
`intent-report`. For the length of the run only, the lab's random IDs and clock are replaced
by values derived from the seed, so the bytes repeat. The pilot records `pilot-unbound` as the
code commit, so the hash does not change with each commit; record `git rev-parse HEAD` yourself.

If a code change alters the pilot report on purpose, the same commit must update
`team_c/intent_pilot/EXPECTED_SHA256` and say why.
