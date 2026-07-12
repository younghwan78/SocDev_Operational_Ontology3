$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
  docker compose -f deploy/local/compose.yaml up -d postgres
  if ($LASTEXITCODE -ne 0) { throw "docker compose failed" }
  uv sync --all-groups --locked
  if ($LASTEXITCODE -ne 0) { throw "uv sync failed" }
  uv run alembic upgrade head
  if ($LASTEXITCODE -ne 0) { throw "migration failed" }
  & scripts/check-migrations.ps1
  uv run soc-ot fixtures validate --include-hidden
  if ($LASTEXITCODE -ne 0) { throw "fixture validation failed" }
  uv run soc-ot evaluation validate-release
  if ($LASTEXITCODE -ne 0) { throw "manifest validation failed" }
  uv run soc-ot contracts export --check
  if ($LASTEXITCODE -ne 0) { throw "contract check failed" }
  uv run soc-ot contracts export-openapi --check
  if ($LASTEXITCODE -ne 0) { throw "OpenAPI check failed" }
  uv run ruff check backend/src backend/tests
  if ($LASTEXITCODE -ne 0) { throw "Ruff failed" }
  uv run mypy backend/src
  if ($LASTEXITCODE -ne 0) { throw "mypy failed" }
  uv run pytest -p no:cacheprovider
  if ($LASTEXITCODE -ne 0) { throw "pytest failed" }
  uv run soc-ot evaluation run
  if ($LASTEXITCODE -ne 0) { throw "Replay evaluation failed" }
  & scripts/check-plan-consistency.ps1
  & scripts/check-architecture-boundary.ps1
  & scripts/check-hidden-boundary.ps1
  & scripts/check-secrets.ps1
  & scripts/check-markdown-links.ps1
  & scripts/check-generated-contracts.ps1
  Push-Location frontend
  try {
    npm ci
    if ($LASTEXITCODE -ne 0) { throw "npm ci failed" }
    npm run typecheck
    if ($LASTEXITCODE -ne 0) { throw "Frontend typecheck failed" }
    npm run lint
    if ($LASTEXITCODE -ne 0) { throw "Frontend lint failed" }
    npm run test:unit
    if ($LASTEXITCODE -ne 0) { throw "Frontend unit tests failed" }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed" }
    npm run test:e2e
    if ($LASTEXITCODE -ne 0) { throw "Frontend E2E failed" }
  } finally {
    Pop-Location
  }
} finally {
  Pop-Location
}
