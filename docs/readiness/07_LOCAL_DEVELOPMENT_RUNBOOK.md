# Windows local development runbook

> Status: IMPLEMENTATION CONTRACT  
> Date: 2026-07-11  
> Current state: Replay workflow executable through I7

## 1. Purpose

This is the target local workflow for developing the fixture-only PoC at home. ReplayProvider is the default, so ordinary setup and CI do not require Confluence, Jira, a company network, or an OpenAI API key.

## 2. Prerequisites

- Windows 11 and PowerShell 7+
- Python 3.11+
- `uv`
- Node.js 22.12+ and npm
- Docker Desktop with Docker Compose
- Git, once the repository is initialized

Verify:

```powershell
python --version
uv --version
node --version
npm --version
docker version
docker compose version
```

## 3. Fixed local ports

|Service|Binding|Purpose|
|---|---|---|
|PostgreSQL|`127.0.0.1:15432`|local persistence|
|FastAPI|`127.0.0.1:18080`|API and SSE|
|Vite|`127.0.0.1:15173`|Frontend development server|
|Worker|no listening port|PostgreSQL-backed Agent jobs|

Do not bind PostgreSQL to a LAN interface.

## 4. Environment template

I0 creates `.env.example` with at least:

```dotenv
SOC_OT_ENV=local
SOC_OT_AUTHORING_MODE=0
SOC_OT_DATABASE_URL=postgresql+psycopg://soc_ot_runtime:runtime_local@127.0.0.1:15432/soc_ot
SOC_OT_OUTCOME_DATABASE_URL=postgresql+psycopg://soc_ot_outcome:outcome_local@127.0.0.1:15432/soc_ot
SOC_OT_API_HOST=127.0.0.1
SOC_OT_API_PORT=18080
SOC_OT_FRONTEND_PORT=15173
SOC_OT_CORS_ALLOWED_ORIGINS=http://127.0.0.1:15173
SOC_OT_LLM_MODE=replay
OPENAI_API_KEY=
SOC_OT_ROLE_MODEL=gpt-5.4-mini
SOC_OT_CHALLENGER_MODEL=gpt-5.5
SOC_OT_CHAIR_MODEL=gpt-5.5
SOC_OT_MAX_CASE_RUNTIME_SECONDS=900
SOC_OT_MAX_CASE_COST_USD=2.00
SOC_OT_MAX_EVALUATION_COST_USD=25.00
SOC_OT_RAW_PROVIDER_RETENTION_DAYS=30
VITE_SOC_OT_API_BASE_URL=http://127.0.0.1:18080
```

Copy it to ignored `.env.local`. Do not insert a real key in the committed example.

API, worker, and CLI use one root settings loader that reads `.env.local`. Vite reads only `VITE_` variables. FastAPI permits exactly the configured local origin; do not use wildcard CORS with credentials.

## 5. First setup

From `E:\59_Codex_SoC_Operational_Ontology`:

```powershell
Copy-Item .env.example .env.local
docker compose --env-file .env.local -f deploy/local/compose.yaml up -d postgres
uv sync --all-groups
uv run alembic upgrade head
uv run python -m soc_ot.cli fixtures validate --root fixtures
Get-ChildItem fixtures/cases/observable/*.yaml | ForEach-Object {
  uv run soc-ot fixtures import --case-id $_.BaseName
}
Set-Location frontend
npm ci
Set-Location ..
```

## 6. Start development services

Use three PowerShell terminals.

Terminal 1 — API:

```powershell
uv run uvicorn soc_ot.api.main:app --app-dir backend/src --host 127.0.0.1 --port 18080 --reload
```

Terminal 2 — worker:

```powershell
uv run python -m soc_ot.worker
```

Terminal 3 — Frontend:

```powershell
Set-Location frontend
npm run dev -- --host 127.0.0.1 --port 15173
```

Open `http://127.0.0.1:15173`.

## 7. Smoke checks

```powershell
Invoke-RestMethod http://127.0.0.1:18080/health/live
Invoke-RestMethod http://127.0.0.1:18080/health/ready
Invoke-RestMethod http://127.0.0.1:18080/api/v1/decision-cases
Invoke-RestMethod http://127.0.0.1:18080/api/v1/decision-cases/CASE-VR-001/workspace
```

Expected readiness response includes PostgreSQL connectivity and compatible migration revision. It must not require the live LLM provider in replay mode.

Start a replay review after I4:

```powershell
$workspace = Invoke-RestMethod `
  http://127.0.0.1:18080/api/v1/decision-cases/CASE-VR-001/workspace
$run = Invoke-RestMethod -Method Post `
  -ContentType "application/json" `
  -Body '{"command_schema_version":"review-run-command.v1","scope":"dossier"}' `
  -Headers @{
    "Idempotency-Key" = "replay-case-vr-001-001"
    "If-Match" = "`"$($workspace.aggregate_version)`""
  } `
  http://127.0.0.1:18080/api/v1/decision-cases/CASE-VR-001/review-runs
$run
Invoke-RestMethod "http://127.0.0.1:18080/api/v1/runs/$($run.run_id)"
```

The API resolves the local audit actor from `SOC_OT_LOCAL_ACTOR_ID`; it is not accepted
from a browser-supplied identity header.

## 8. Live OpenAI mode

Live mode is optional until I7.

```powershell
$env:SOC_OT_LLM_MODE = "openai"
$env:OPENAI_API_KEY = "your_openai_api_key_here"
$env:SOC_OT_ROLE_INPUT_COST_PER_MILLION_USD = "verify-current-price"
$env:SOC_OT_ROLE_OUTPUT_COST_PER_MILLION_USD = "verify-current-price"
uv run python -m soc_ot.cli agent preflight
uv run python -m soc_ot.worker
```

Replace the placeholder only in the worker terminal. Stop the Replay worker first, then run `preflight` and the live worker in that same terminal so it receives the key. The API does not call the provider directly. `preflight` checks key presence, model configuration, budget, and provider reachability without exposing the key. Do not paste the key into fixtures, commands committed to docs, or screenshots.

## 9. Authoring hidden fixtures

Hidden inspection is CLI-only and off by default.

```powershell
$env:SOC_OT_AUTHORING_MODE = "1"
uv run python -m soc_ot.cli dev inspect-hidden --case-id CASE-VR-001
Remove-Item Env:SOC_OT_AUTHORING_MODE
```

Never run the API or worker with authoring mode enabled.
Successful hidden import/inspection prints an `AUTHORING/HIDDEN` banner and writes the
configured local actor, action, and case ID to `audit.hidden_authoring_audits`.

## 10. Test and evaluation

```powershell
uv run ruff check backend/src backend/tests
uv run mypy backend/src
uv run pytest -p no:cacheprovider
uv run soc-ot evaluation validate-release --manifest fixtures/manifests/eval-2026-07-11.1.yaml
uv run soc-ot evaluation run --manifest fixtures/manifests/eval-2026-07-11.1.yaml --provider replay --topology B3
powershell -File scripts/check-architecture-boundary.ps1

Set-Location frontend
npm run typecheck
npm run lint
npm run test:unit
npm run build
npm run test:e2e
Set-Location ..
```

Replay evaluation writes an immutable directory under
`output/evaluations/eval-2026-07-11.1/<run-id>/` with manifest, environment,
normalized results, separate Process/Outcome scores, policy violations, and `report.md`.

## 11. Stop and preserve data

```powershell
docker compose --env-file .env.local -f deploy/local/compose.yaml stop postgres
```

This preserves the database volume. Do not make a data-deleting reset part of normal development. A future `scripts/reset-local.ps1` must require explicit `-ConfirmDataLoss` and print the resolved project/volume names before deletion.

## 12. Logs and artifacts

```text
output/logs/api.jsonl
output/logs/worker.jsonl
output/agent-runs/<run-id>/
output/evaluations/<release-id>/<run-id>/
```

All files follow the redaction and retention rules in `05_AGENT_RUNTIME_AND_SECURITY_POLICY.md`.

## 13. Troubleshooting

|Symptom|Check|Action|
|---|---|---|
|PostgreSQL connection refused|`docker compose --env-file .env.local -f deploy/local/compose.yaml ps`|start `postgres`; verify port 15432 is free|
|Database revision mismatch|`uv run alembic current`|run `uv run alembic upgrade head`|
|Worker does not claim run|worker log and DB readiness|start worker; verify same database URL|
|UI cannot call API|API health and Frontend env|use `127.0.0.1:18080`; restart Vite|
|Replay output differs|fixture/prompt/contract hashes|run generated-contract and manifest checks|
|Live provider fails|`agent preflight`|check key, model access, budget, and network|
|Docker named-pipe denied|Docker Desktop status/permissions|start Docker Desktop and retry in an authorized terminal|

## 14. One-command I7 verification

```powershell
& scripts/verify-i7.ps1
& scripts/smoke-replay.ps1
```

The first command verifies contracts, migrations, all Backend/Frontend tests, the frozen corpus, repository scans, and the Replay evaluation. The second starts a temporary API process, executes an actual PostgreSQL-backed worker run, simulated decision, and outcome evaluation, then writes `output/smoke/replay.json`.

Live stability is separate because it incurs external cost:

```powershell
uv run soc-ot agent preflight
uv run soc-ot evaluation ablate --provider openai --partitions validation,sealed-unseen --acknowledge-cost
uv run soc-ot evaluation stability --provider openai --partition validation --repeat 5 --acknowledge-cost
uv run soc-ot evaluation stability --provider openai --partition sealed-unseen --repeat 3 --acknowledge-cost
```

Each live command prints its maximum runs, semantic calls, timeout envelope, and cost
before the first provider call. It aborts when the configured batch envelope is exceeded.

See `docs/implementation/KNOWN_LIMITATIONS.md` before interpreting Replay results as business-value evidence.
