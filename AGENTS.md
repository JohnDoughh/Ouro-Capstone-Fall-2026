# Repository instructions

This repository is a public-safe university research environment.

## Hard boundaries

- Use only synthetic or separately approved sanitized artifacts.
- Never copy source, prompts, credentials, customer data, production URLs, evaluator implementation, thresholds, routing, repair logic, commercial performance data, or hidden reasoning from Ouro systems.
- Evaluators are identified only by anonymous version aliases.
- Do not add network connectivity to Ouro production systems.
- Do not commit human participant PII. Use pseudonymous rater IDs.

## Research integrity

- Preserve raw annotations and disagreement.
- Store adjudication separately; never overwrite a rater's judgment.
- Bind artifacts and outputs with SHA-256.
- Record seeds, versions, and analysis parameters.
- Label synthetic/demo results as synthetic and not research findings.
- Add regression tests for metric or contract changes.

## Change workflow

- Work on a feature branch and use a pull request.
- Run `make check` before requesting review.
- Update contracts and documentation together when schemas change.
- Keep the mandatory spine viable before adding stretch features.
