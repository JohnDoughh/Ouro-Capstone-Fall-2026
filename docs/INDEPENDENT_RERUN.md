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

## Family 4 reference and timing check (card #870)

A separate report run after the #813 response is frozen. It does not change
`cli compare`, its report, or anything under `data/public_playable`.

1. Use the same downloaded #813 export as the comparison and confirm its SHA-256 matches the hash recorded on #813. Do not re-export.
2. `python -m ouro_eval_lab.cli family4-check --manifest data/public_playable/manifest.json --responses <export.json> --reference data/public_playable/reference.sha256 --out data/exports/orbit-family4-check.json`
3. `approved_reference_sha256` in the report must equal the digest in `data/public_playable/reference.sha256`; the command refuses to run if the reference image bytes do not match it.
4. Print the report SHA-256 (`sha256sum` or PowerShell `Get-FileHash`) and compare it with the hash recorded on #870.

For each `HOLD` the report gives:

- `reference`: `match`, `mismatch` or `missing` against the approved reference digest. A blind response keeps the reference hidden, so `missing` is expected there and is not a failed rating.
- `timing`: `overlaps`, `misses` or `unparsed` against the documented `[2.500, 3.500)` s window of the defective clip, or `no_defect_window` for a `HOLD` on the clean clip. Timestamps are whole seconds, so `00:03` covers that full second and `00:03 - 00:04` runs to the end of second 4.

`PASS` and `UNSURE` rows are counted and skipped. Rows are identified by
`annotation_id` and artifact hash; rater IDs and source artifact IDs are not
copied into the report.

Limitations: timing overlap is not detection accuracy. The check reads the
hidden truth and defect window, so run it only after the response is frozen and
keep the report away from anyone who has not finished rating. The response is a
teammate practice rating, not research data.
