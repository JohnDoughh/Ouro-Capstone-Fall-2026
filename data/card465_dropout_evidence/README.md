# Card #465 reproducible dropout evidence package

This public-safe package integrates Team B's timestamped human annotation with one explicitly simulated evaluator output for the synthetic `dropout.wav` practice artifact. It is a pipeline demonstration, not an Ouro performance claim or research finding.

`human_annotation.json` is an actual course observation recorded against this synthetic practice artifact; it is not a fabricated evaluator record or an observation of private blinded media. The package intentionally omits the reviewer's identity. Any human observation made against real or private course media must remain in the approved private evidence location and must not be copied into this repository.

## Pinned artifact identity

- Artifact ID: `syn-tone-b`
- SHA-256: `9f4f1593b2b5c7f24495f9e1f12d55920cde80d8608916bbb5d70d72e8d10478`
- Source: `data/public_audio/dropout.wav`
- Synthetic defect: one second of silence at `[4.000, 5.000)` seconds

The same artifact ID and SHA-256 appear in the preserved human annotation, simulated evaluator output, comparison, and combined export.

## Contents

- `human_annotation.json`: preserved course observation of the synthetic practice artifact, with reviewer identity omitted, timestamp, HOLD verdict, severity `3` on the `0-3` scale, and confidence `5` on the `1-5` scale.
- `simulated_evaluator_output.json`: explicitly fictional deterministic comparison input. It is not a real evaluator result.
- `exports/comparison.json`: human-versus-simulated verdict comparison.
- `exports/dropout-evidence-package.json`: shareable combined export.
- `exports/SHA256SUMS`: hashes for both generated JSON outputs.

## Reproduce and verify

From the repository root, using Python 3.11 or newer:

```bash
python3 scripts/build_card465_dropout_evidence.py
python3 scripts/build_card465_dropout_evidence.py
python3 -m unittest tests.test_card465_dropout_evidence -v
make check
```

The builder first verifies the source audio's pinned byte length and SHA-256. It then rejects a mismatched artifact identity, invalid confidence or severity scale, missing human timestamp, or evaluator input that is not labeled `simulated-test-only`. Running it repeatedly produces byte-identical JSON outputs.

On systems with `sha256sum`, the generated files can also be checked directly:

```bash
cd data/card465_dropout_evidence/exports
sha256sum -c SHA256SUMS
```

## Cross-team handoff

The shareable envelope uses the repository's public contract conventions: artifact identity is bound with SHA-256, human confidence is kept on its separate `1-5` ordinal scale, simulated evaluator confidence remains `0-1`, raw human judgment is preserved, and synthetic provenance is explicit. Teams A and C can consume `exports/dropout-evidence-package.json` without accessing the local annotation database.
