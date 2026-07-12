# Repository guidance

## Scope

- Implement only the current I-stage in `docs/readiness/01_MASTER_EXECUTION_PLAN.md`.
- Keep company data, Jira, Confluence, authentication, and write-back out of the local PoC.
- Never copy the legacy repository without an accepted ADR and new tests.

## Architecture

- Domain code cannot import FastAPI, SQLAlchemy, OpenAI, or UI labels.
- Agents receive only a validated `ObservableCasePacket`.
- Hidden fixtures are available only to authoring CLI, Outcome, and Evaluation code.
- Use canonical states, endpoints, time, and version names from `docs/readiness/08_CANONICAL_TERMS_AND_API_CONTRACT.md`.

## Required verification

```powershell
uv run ruff check backend/src backend/tests
uv run mypy backend/src
uv run pytest -m "not postgres" -p no:cacheprovider
powershell -File scripts/check-plan-consistency.ps1
powershell -File scripts/check-hidden-boundary.ps1
powershell -File scripts/check-secrets.ps1
```

Run PostgreSQL, Frontend, and E2E checks when the changed stage depends on them.

