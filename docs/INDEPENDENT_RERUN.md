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
