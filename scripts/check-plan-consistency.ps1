$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$projectPlan = Get-Content -Raw (Join-Path $root "PROJECT_PLAN.md")
$master = Get-Content -Raw (Join-Path $root "docs/readiness/01_MASTER_EXECUTION_PLAN.md")
$readiness = Get-Content -Raw (Join-Path $root "docs/readiness/00_IMPLEMENTATION_READINESS_RESULT.md")
$contract = Get-Content -Raw (Join-Path $root "docs/readiness/08_CANONICAL_TERMS_AND_API_CONTRACT.md")
$multiRole = Get-Content -Raw (Join-Path $root "backend/src/soc_ot/application/multi_role.py")
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
    "fixtures/projects",
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
$projectFixtures = @(Get-ChildItem -LiteralPath (
    Join-Path $root "fixtures/projects"
) -Filter "PROJECT-*.yaml" -File)
if ($projectFixtures.Count -ne 3) {
    throw "OPS-B project corpus must contain exactly 3 projects; found $($projectFixtures.Count)."
}
@(
    "fixtures/projects/manifest.yaml",
    "contracts/generated/development-project.v1.schema.json"
) | ForEach-Object {
    if (-not (Test-Path -LiteralPath (Join-Path $root $_) -PathType Leaf)) {
        throw "Missing OPS-B artifact: $_"
    }
}
if ($projectPlan -notmatch "corpus v2: development regression 8, validation 2, sealed unseen 2") {
    throw "PROJECT_PLAN.md does not describe the canonical 8/2/2 evaluation partition."
}
@("keep_b3", "release_b2", "release_b1", "release_b0") | ForEach-Object {
    if (-not $projectPlan.Contains($_)) {
        throw "PROJECT_PLAN.md is missing topology stop rule: $_"
    }
}
if ($projectPlan -notmatch "release topology: B2 independent routed Role Agents") {
    throw "PROJECT_PLAN.md does not record the Step 5 B2 activation."
}
if ($multiRole -notmatch 'RELEASE_DOSSIER_TOPOLOGY: DossierTopology = "B2"') {
    throw "Runtime release topology is not the approved B2 value."
}
if ($master -notmatch 'PostgreSQL migration head is `0021_decision_responses`') {
    throw "Master plan does not record the UX-J migration head."
}
@("project-attention.v1", "project-risk-order.v1") | ForEach-Object {
    if (-not $contract.Contains($_)) {
        throw "Canonical contract is missing OPS-C policy version: $_"
    }
}

@(
    "frontend/src/features/projects/ProjectPortfolioPage.tsx",
    "frontend/src/features/projects/ProjectSituationPage.tsx"
) | ForEach-Object {
    if (-not (Test-Path -LiteralPath (Join-Path $root $_) -PathType Leaf)) {
        throw "Missing OPS-D Frontend artifact: $_"
    }
}
$frontendRoutes = Get-Content -Raw (Join-Path $root "frontend/src/app/App.tsx")
@('/projects', '/projects/:projectId') | ForEach-Object {
    if (-not $frontendRoutes.Contains($_)) {
        throw "Frontend is missing canonical OPS-D route: $_"
    }
}
if ($master -notmatch 'OPS-D implementation record') {
    throw "Master plan does not record the OPS-D implementation Gate."
}
@(
    "frontend/src/features/projects/ProjectRiskDetailPage.tsx",
    "frontend/src/features/decisions/DecisionWorkspacePage.tsx"
) | ForEach-Object {
    if (-not (Test-Path -LiteralPath (Join-Path $root $_) -PathType Leaf)) {
        throw "Missing OPS-E Frontend artifact: $_"
    }
}
if (-not $frontendRoutes.Contains('/projects/:projectId/risks/:riskId')) {
    throw "Frontend is missing the canonical OPS-E Risk Detail route."
}
if ($master -notmatch 'OPS-E implementation record') {
    throw "Master plan does not record the OPS-E implementation Gate."
}
@(
    "fixtures/usability/OPS-F-20260722.protocol.v2.yaml",
    "fixtures/usability/PROJECT-OPERATIONS.baseline-pack.v2.yaml",
    "fixtures/usability/OPS-F-20260722.release.v1.yaml",
    "fixtures/usability/UX-I-20260724.release.v1.yaml",
    "fixtures/usability/UX-J-20260724.release.v1.yaml",
    "fixtures/usability/OPS-F-20260722.reviewer-rubric.v1.yaml",
    "contracts/generated/usability-study-protocol.v2.schema.json",
    "contracts/generated/usability-project-baseline-pack.v2.schema.json",
    "contracts/generated/usability-study-release.v1.schema.json",
    "contracts/generated/usability-reviewer-rubric.v1.schema.json",
    "frontend/tests/project-operations.spec.ts"
) | ForEach-Object {
    if (-not (Test-Path -LiteralPath (Join-Path $root $_) -PathType Leaf)) {
        throw "Missing OPS-F protocol v2 artifact: $_"
    }
}
if (-not (Get-ChildItem -LiteralPath (Join-Path $root "internal_docs") -File |
    Where-Object { $_.Name -like "26.07.23 OPS-F Study Release*.md" })) {
    throw "Missing OPS-F study release and company-readiness report."
}
if (-not (Get-ChildItem -LiteralPath (Join-Path $root "internal_docs") -File |
    Where-Object { $_.Name -like "26.07.23 UX*.md" })) {
    throw "Missing UX completion and enterprise transition plan."
}
if (-not (Get-ChildItem -LiteralPath (Join-Path $root "internal_docs") -File |
    Where-Object { $_.Name -like "26.07.23 OPS-F Human Observation*.md" })) {
    throw "Missing OPS-F human observation deferral decision."
}
$uxiDocs = @(Get-ChildItem -LiteralPath (Join-Path $root "internal_docs") -File |
    Where-Object { $_.Name -like "26.07.24 UX-I Engineering Proxy *.md" })
if ($uxiDocs.Count -lt 2) {
    throw "Missing UX-I engineering-proxy backlog or implementation report."
}
if ($master -notmatch 'OPS-F implementation record') {
    throw "Master plan does not record the OPS-F implementation state."
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
    "/api/v1/projects",
    "/api/v1/projects/{project_id}/situation",
    "/api/v1/projects/{project_id}/risks",
    "/api/v1/projects/{project_id}/risks/{risk_id}",
    "/api/v1/projects/{project_id}/timeline",
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

Write-Output "Plan consistency check passed: I0-I7, OPS-F protocol v2, corpora, terms, and canonical API agree."
