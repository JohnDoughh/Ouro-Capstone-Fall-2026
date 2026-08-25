# Threat model and release boundary

## Protected assets

- Ouro source and pre-existing technology;
- customer, campaign, and production data;
- credentials and production connectivity;
- private prompts, evaluator implementation, routing, thresholds, repair logic, and hidden reasoning;
- participant identity and raw operational metadata.

## Trust boundaries

1. **Ouro private environment:** never connected to this lab.
2. **Sanitization boundary:** an Ouro-controlled process creates synthetic or approved sanitized artifacts plus frozen public-contract outputs.
3. **Student lab:** stores public-safe benchmark data and pseudonymous annotations.
4. **Public export:** allow-list validation removes operational fields and rejects unknown keys.

## Primary risks and controls

| Risk | Control |
|---|---|
| Secret or customer-data leakage | Synthetic-only default, deny-list scanner, manual release review |
| Model identity/implementation leakage | Anonymous aliases and a frozen minimal output contract |
| Hash substitution | Verify size and SHA-256 on every ingest and benchmark run |
| Rater bias | Blind truth and evaluator output until submission |
| Repeat-item gaming | Hide repeat markers in the UI and randomize order |
| Overwriting disagreement | Append-only annotation/adjudication separation |
| Cross-rater contamination | Assignment-bound access and no aggregate results during collection |
| Metric shopping | Pre-register primary metrics and priority defect families |
| Synthetic results mistaken for findings | Prominent labels in UI, reports, and documentation |
| Production access drift | No production SDKs, URLs, credentials, or network adapters |

## Release checklist

- Run `make check`.
- Inspect all new artifacts and Git history for forbidden content.
- Confirm every manifest hash from a clean checkout.
- Confirm reports say `synthetic_demo: true` when synthetic fixtures are used.
- Obtain the narrow confidentiality review before public release when any Ouro-supplied material was involved.
