$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$generated = Join-Path $root "contracts/generated"
if (-not (Test-Path -LiteralPath $generated)) {
    Write-Output "No generated contracts yet; I1 will create them."
    exit 0
}
uv run python -m soc_ot.cli contracts export --check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
uv run python -m soc_ot.cli contracts export-openapi --check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
npm --prefix frontend run generate:api -- --check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
