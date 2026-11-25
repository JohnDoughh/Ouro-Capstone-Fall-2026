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
| Cross-rater contamination | Assignment-bound access; no public aggregate endpoint during collection. Offline agreement requires local database access and a separate release decision. |
| Metric shopping | Pre-register primary metrics and priority defect families |
| Synthetic results mistaken for findings | Prominent labels in UI, reports, and documentation |
| Production access drift | No production SDKs, URLs, credentials, or network adapters |

## Intent fidelity study (Team C)

| Risk | Control |
|---|---|
| Viewers see the intended answers | Records are sealed as SHA-256 commitments; `reveal` refuses until responses are frozen; the viewer API returns no record, artifact ID, path or hash |
| Responses changed after the reveal | Append-only `intent_responses`; the freeze hash is recorded before reveal and bound into every report |
| Coders influenced by viewer identity or by each other | Coder sheets hide viewer IDs, certainty and other coders' codes; a coder never gets a clip they saw as a viewer |
| Codes overwritten | Append-only `intent_codings`; a changed code is refused; adjudication will be a separate table |
| Unequal exposure | Server-held play limit that survives reload |
| Personal data in free recall | Contact details rejected at submit; reports and the HTML view carry no free text and no viewer or coder IDs |
| Answer leakage through files | The README next to the clips is not shown in the UI; sessions run from the UI only (exposure log not built) |
| Pilot numbers read as findings | The pilot and every report say synthetic and not a research finding; the pilot report also says its viewers and coders are simulated |
| Report and inputs drift apart | The report binds the freeze, commitments, records and codes by SHA-256; the HTML view binds its report by SHA-256 |
| Coding drifts from the codebook | Anchor sets are bound to the codebook version and its LF-normalized SHA-256, and pinned by their own SHA-256; a changed codebook refuses the set until re-bound; anchors are invented, so they cannot reveal study answers |
| Operator runs a step out of order | `intent-status` (read-only, no IDs or text) names the stage and the next command; `serve --study intent` refuses a database with no ingested clips |

## Release checklist

- Run `make check` (it includes `make intent-pilot`).
- Inspect all new artifacts and Git history for forbidden content.
- Confirm every manifest hash from a clean checkout.
- Confirm reports say `synthetic_demo: true` when synthetic fixtures are used.
- Obtain the narrow confidentiality review before public release when any Ouro-supplied material was involved.
