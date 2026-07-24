$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$domain = Join-Path $root "backend/src/soc_ot/domain"
$agents = Join-Path $root "backend/src/soc_ot/agents"

$domainForbidden = Get-ChildItem -Path $domain -Recurse -File -Filter *.py |
    Select-String -Pattern "fastapi|sqlalchemy|(^|\s)openai(\s|\.|$)|soc_ot\.api|soc_ot\.infrastructure"
if ($domainForbidden) {
    $domainForbidden | ForEach-Object { Write-Error $_.ToString() }
    throw "Domain code imports a forbidden framework, provider, or infrastructure dependency."
}

$agentForbidden = Get-ChildItem -Path $agents -Recurse -File -Filter *.py |
    Select-String -Pattern "soc_ot\.application\.repositories|soc_ot\.infrastructure|CaseRepository|FixtureRepository|HiddenCaseReader|OutcomeRepository|EvaluationRepository"
if ($agentForbidden) {
    $agentForbidden | ForEach-Object { Write-Error $_.ToString() }
    throw "Agent code references a repository, fixture loader, or infrastructure adapter."
}

$packetImports = Get-ChildItem -Path $agents -Recurse -File -Filter *.py |
    Select-String -SimpleMatch "ObservableCasePacket"
if (-not $packetImports) {
    throw "Agent code has no validated ObservableCasePacket boundary."
}

$enterpriseFiles = @(
    (Join-Path $root "backend/src/soc_ot/application/enterprise_ingestion.py"),
    (Join-Path $root "backend/src/soc_ot/application/enterprise_mapping.py"),
    (Join-Path $root "backend/src/soc_ot/application/enterprise_sync.py"),
    (Join-Path $root "backend/src/soc_ot/application/ports.py")
)
$enterpriseForbidden = Select-String -Path $enterpriseFiles `
    -Pattern "fastapi|sqlalchemy|(^|\s)openai(\s|\.|$)|soc_ot\.api|soc_ot\.infrastructure|atlassian|jira|confluence"
if ($enterpriseForbidden) {
    $enterpriseForbidden | ForEach-Object { Write-Error $_.ToString() }
    throw "Enterprise source contracts import a framework, infrastructure, or vendor dependency."
}

Write-Output "Architecture boundary check passed."
