$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$projectPlan = Get-Content -Raw (Join-Path $root "PROJECT_PLAN.md")
$master = Get-Content -Raw (Join-Path $root "docs/readiness/01_MASTER_EXECUTION_PLAN.md")
$readiness = Get-Content -Raw (Join-Path $root "docs/readiness/00_IMPLEMENTATION_READINESS_RESULT.md")
$contract = Get-Content -Raw (Join-Path $root "docs/readiness/08_CANONICAL_TERMS_AND_API_CONTRACT.md")
$openApi = Get-Content -Raw (Join-Path $root "contracts/generated/openapi.json") | ConvertFrom-Json

if ($readiness -notmatch "READY FOR I0 SCAFFOLD") {
    throw "Implementation readiness authority is not active."
}
if ($master -notmatch "(?m)^> Status: (APPROVED|IMPLEMENTED)") {
    throw "Master execution plan has no active status."
}

$requiredLayout = @(
    "backend/src/soc_ot/domain",
    "backend/src/soc_ot/application",
    "backend/src/soc_ot/agents",
    "backend/src/soc_ot/infrastructure",
    "backend/src/soc_ot/api",
    "backend/src/soc_ot/worker",
    "backend/src/soc_ot/cli",
    "backend/tests",
    "frontend/src/app",
    "frontend/src/features",
    "frontend/src/api",
    "frontend/src/components",
    "frontend/src/design",
    "frontend/tests",
    "contracts/generated",
    "contracts/snapshots",
    "fixtures/world",
    "fixtures/cases/observable",
    "fixtures/cases/development",
    "fixtures/cases/hidden",
    "fixtures/expected",
    "fixtures/manifests",
    "fixtures/dictionaries",
    "docs/architecture",
    "docs/decisions",
    "docs/agents",
    "docs/evaluation",
    "docs/ui",
    "docs/operations"
)
$requiredLayout | ForEach-Object {
    if (-not (Test-Path -LiteralPath (Join-Path $root $_) -PathType Container)) {
        throw "Missing canonical repository directory: $_"
    }
}
@("src/soc_ot", "ui", "tests") | ForEach-Object {
    if (Test-Path -LiteralPath (Join-Path $root $_)) {
        throw "Forbidden duplicate source/test directory: $_"
    }
}

0..7 | ForEach-Object {
    if ($master -notmatch "### I$($_)\.") {
        throw "Missing canonical stage I$($_)"
    }
}

$decisionTypes = @(
    "APPROVE",
    "APPROVE_WITH_GUARDRAILS",
    "RUN_REVERSIBLE_TRIAL",
    "COLLECT_MINIMUM_EVIDENCE",
    "DEFER_UNTIL_TRIGGER",
    "REJECT",
    "ESCALATE"
)
$versions = @(
    "fixture_version",
    "aggregate_version",
    "contract_version",
    "policy_version",
    "prompt_bundle_version"
)
($decisionTypes + $versions) | ForEach-Object {
    if (-not $contract.Contains($_)) {
        throw "Missing canonical contract term: $_"
    }
}

$manifestCases = Select-String -Path (
    Join-Path $root "fixtures/manifests/eval-2026-07-14.2.yaml"
) -Pattern '^- case_id: '
if ($manifestCases.Count -ne 12) {
    throw "Evaluation manifest v2 must contain exactly 12 cases; found $($manifestCases.Count)."
}
$historicalCases = Select-String -Path (
    Join-Path $root "fixtures/manifests/eval-2026-07-14.1.yaml"
) -Pattern '^- case_id: '
if ($historicalCases.Count -ne 8) {
    throw "Historical evaluation manifest must remain at 8 cases; found $($historicalCases.Count)."
}
$developmentCases = @(Get-ChildItem -LiteralPath (
    Join-Path $root "fixtures/cases/development"
) -Filter "CASE-DT-*.yaml" -File)
if ($developmentCases.Count -ne 4) {
    throw "Step 2 development corpus must contain exactly 4 cases; found $($developmentCases.Count)."
}
if ($projectPlan -notmatch "corpus v2: development regression 8, validation 2, sealed unseen 2") {
    throw "PROJECT_PLAN.md does not describe the canonical 8/2/2 evaluation partition."
}
@("keep_b3", "release_b2", "release_b1", "release_b0") | ForEach-Object {
    if (-not $projectPlan.Contains($_)) {
        throw "PROJECT_PLAN.md is missing topology stop rule: $_"
    }
}

$requiredPaths = @(
    "/api/v1/decision-cases",
    "/api/v1/decision-cases/{case_id}/workspace",
    "/api/v1/decision-cases/{case_id}/timeline",
    "/api/v1/decision-cases/{case_id}/evidence",
    "/api/v1/decision-cases/{case_id}/evaluation",
    "/api/v1/decision-cases/{case_id}/review-runs",
    "/api/v1/decision-cases/{case_id}/simulated-decisions",
    "/api/v1/decision-cases/{case_id}/outcome-advances",
    "/api/v1/decision-cases/{case_id}/evaluations",
    "/api/v1/runs/{run_id}",
    "/api/v1/runs/{run_id}/events",
    "/api/v1/runs/{run_id}/cancel",
    "/api/v1/runs/{run_id}/retry"
)
$actualPaths = @($openApi.paths.PSObject.Properties.Name)
$requiredPaths | ForEach-Object {
    if ($_ -notin $actualPaths) { throw "OpenAPI is missing canonical path: $_" }
}
if ($actualPaths | Where-Object { $_ -match "hidden" }) {
    throw "OpenAPI exposes a forbidden hidden resource."
}

Write-Output "Plan consistency check passed: I0-I7, 12-case v2, 8-case historical release, terms, and canonical API agree."
