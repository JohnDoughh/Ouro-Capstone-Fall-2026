# Contributing to the FIU Evaluation Lab

This repository is a public-safe research environment. Read `AGENTS.md`,
`CURRENT_STATUS.md`, and your ratified team slice before changing code or data.

## First setup

```bash
git clone https://github.com/JohnDoughh/Ouro-Capstone-Fall-2026.git
cd Ouro-Capstone-Fall-2026
make bootstrap
make check
```

Run the application with `make run`, then open <http://localhost:8080>.

Docker is optional:

```bash
docker compose up --build
```

The container initializes an empty data volume automatically and exposes a health
check at `/api/health`.

## Work sequence

1. Select or create an issue with bounded acceptance criteria.
2. Create a feature branch. Do not work directly on `main`.
3. Keep each pull request owned by one vertical slice unless it changes a shared contract.
4. For shared-contract changes, obtain review from each team's integration delegate.
5. Add or update tests and documentation in the same pull request.
6. Run `make check` and the relevant end-to-end demonstration.
7. Open a pull request using the repository template.

## Definition of done

A change is not done until:

- its issue acceptance criteria are satisfied;
- affected contracts and rubric versions are explicit;
- tests cover success, rejection, and blinding behavior where applicable;
- raw annotations and disagreements remain immutable;
- synthetic outputs remain labeled as demonstrations;
- public-boundary checks pass;
- another contributor can reproduce the result from a clean checkout;
- limitations and unresolved risks are documented.

## Data boundary

Do not commit participant PII, customer or campaign data, Ouro source or private
prompts, credentials, production URLs, evaluator internals, model identities,
thresholds, routing, repair logic, spend, ROAS, or live performance information.

Only deterministic synthetic artifacts or artifacts that passed the separately
approved sanitized-release process may enter the repository. No real participant
annotation begins before FIU records the applicable human-subjects determination.

## Getting unstuck

Raise a blocking issue that states:

- the exact command or workflow attempted;
- expected and actual behavior;
- the relevant commit SHA;
- whether synthetic or approved sanitized data was involved;
- the smallest decision needed from FIU, Ouro, or another team.

Do not request production access to work around a research-environment blocker.
