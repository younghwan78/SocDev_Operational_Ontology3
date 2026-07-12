$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$source = Join-Path $root "backend/src"

$routeRoots = @(
    (Join-Path $source "soc_ot/api"),
    (Join-Path $root "frontend/src")
)
$forbiddenRoute = Get-ChildItem -Path $routeRoots -Recurse -File -Include *.py,*.ts,*.tsx |
    Where-Object { $_.FullName -notmatch "[\\/](node_modules|\.venv|\.git)[\\/]" } |
    Select-String -SimpleMatch "/hidden"
if ($forbiddenRoute) {
    $forbiddenRoute | ForEach-Object { Write-Error $_.ToString() }
    throw "A hidden HTTP route or client path was found."
}

$agentImports = Get-ChildItem -Path (Join-Path $source "soc_ot/agents") -Recurse -File -Filter *.py |
    Select-String -Pattern "hidden|OutcomeRepository|EvaluationRepository"
if ($agentImports) {
    $agentImports | ForEach-Object { Write-Error $_.ToString() }
    throw "Agent code references a hidden repository."
}

Write-Output "Hidden boundary check passed."
