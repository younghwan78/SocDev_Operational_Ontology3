# SoC operational decision twin

This repository implements a fixture-first decision operations twin for SoC development. The local product models development state, incomplete evidence, role-based advice, a simulated decision, and deterministic outcomes without company data.

## Current stage

Implementation follows `docs/readiness/01_MASTER_EXECUTION_PLAN.md`. Check `docs/implementation/IMPLEMENTATION_STATUS.md` for the latest verified gate.

## Local prerequisites

- Python 3.11 or newer
- uv
- Node.js 22.12 or newer
- Docker Desktop with Compose

## Quality commands

```powershell
uv sync --all-groups
uv run ruff check backend/src backend/tests
uv run mypy backend/src
uv run pytest -p no:cacheprovider

Set-Location frontend
npm ci
npm run typecheck
npm run lint
npm run test:unit
npm run build
npm run test:e2e
```

For the complete Replay gate, run `scripts/verify-i7.ps1` and
`scripts/smoke-replay.ps1`. Use
[the local runbook](docs/readiness/07_LOCAL_DEVELOPMENT_RUNBOOK.md) for service commands,
ports, immutable evaluation artifacts, and the separately authorized live-provider gate.
