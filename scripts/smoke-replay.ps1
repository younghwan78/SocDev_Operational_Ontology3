$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$api = $null
Push-Location $root
try {
  uv run alembic upgrade head
  Get-ChildItem fixtures/cases/observable/*.yaml | ForEach-Object {
    uv run soc-ot fixtures import --case-id $_.BaseName
  }
  $priorAuthoring = $env:SOC_OT_AUTHORING_MODE
  try {
    $env:SOC_OT_AUTHORING_MODE = "1"
    uv run soc-ot fixtures import-hidden
    if ($LASTEXITCODE -ne 0) { throw "hidden fixture import failed" }
  } finally {
    if ($null -eq $priorAuthoring) {
      Remove-Item Env:SOC_OT_AUTHORING_MODE -ErrorAction SilentlyContinue
    } else {
      $env:SOC_OT_AUTHORING_MODE = $priorAuthoring
    }
  }
  $python = Join-Path $root ".venv/Scripts/python.exe"
  $api = Start-Process -FilePath $python -ArgumentList @(
    "-m", "uvicorn", "soc_ot.api.main:app", "--app-dir", "backend/src",
    "--host", "127.0.0.1", "--port", "18080"
  ) -PassThru -WindowStyle Hidden
  $ready = $false
  for ($attempt = 0; $attempt -lt 20; $attempt++) {
    try {
      Invoke-RestMethod http://127.0.0.1:18080/health/ready | Out-Null
      $ready = $true
      break
    } catch {
      Start-Sleep -Milliseconds 500
    }
  }
  if (-not $ready) { throw "API did not become ready" }
  $key = "smoke-$([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds())"
  $workspace = Invoke-RestMethod `
    http://127.0.0.1:18080/api/v1/decision-cases/CASE-VR-001/workspace
  $commandHeaders = @{
    "Idempotency-Key" = "$key-review"
    "If-Match" = '"' + $workspace.aggregate_version + '"'
  }
  $run = Invoke-RestMethod -Method Post `
    -Headers $commandHeaders `
    http://127.0.0.1:18080/api/v1/decision-cases/CASE-VR-001/review-runs
  uv run python -m soc_ot.worker --once
  $completed = Invoke-RestMethod "http://127.0.0.1:18080/api/v1/runs/$($run.run_id)"
  if ($completed.status -ne "COMPLETED") { throw "Replay worker did not complete" }
  $attemptCount = docker compose -f deploy/local/compose.yaml exec -T postgres `
    psql -U soc_ot_admin -d soc_ot -At -c `
    "SELECT count(*) FROM audit.agent_attempts WHERE run_id = '$($run.run_id)'"
  if ($LASTEXITCODE -ne 0 -or [int]$attemptCount -lt 1) {
    throw "Provider attempt audit row was not persisted"
  }
  $decisionHeaders = @{
    "Idempotency-Key" = "$key-decision"
    "If-Match" = '"' + $workspace.aggregate_version + '"'
  }
  $decisionUrl = "http://127.0.0.1:18080/api/v1/decision-cases/CASE-VR-001/simulated-decisions?review_run_id=$($run.run_id)"
  $decision = Invoke-RestMethod -Method Post `
    -Headers $decisionHeaders `
    $decisionUrl
  $toStep = [Math]::Max($workspace.current_step + 1, 15)
  $advanceBody = @{
    command_schema_version = "outcome-advance-command.v1"
    from_step = $workspace.current_step
    to_step = $toStep
    decision = $decision.decision
  } | ConvertTo-Json -Depth 20
  $advance = Invoke-RestMethod -Method Post -ContentType "application/json" `
    -Body $advanceBody `
    -Headers @{
      "Idempotency-Key" = "$key-advance"
      "If-Match" = '"' + $workspace.aggregate_version + '"'
    } `
    http://127.0.0.1:18080/api/v1/decision-cases/CASE-VR-001/outcome-advances
  $advancedWorkspace = Invoke-RestMethod `
    http://127.0.0.1:18080/api/v1/decision-cases/CASE-VR-001/workspace
  $decisionReplay = Invoke-RestMethod -Method Post -Headers $decisionHeaders $decisionUrl
  if (($decisionReplay | ConvertTo-Json -Depth 20 -Compress) -ne `
      ($decision | ConvertTo-Json -Depth 20 -Compress)) {
    throw "Simulated decision idempotent replay changed after aggregate advance"
  }
  $evaluationHeaders = @{
    "Idempotency-Key" = "$key-evaluation"
    "If-Match" = '"' + $advancedWorkspace.aggregate_version + '"'
  }
  $evaluation = Invoke-RestMethod -Method Post `
    -Headers $evaluationHeaders `
    http://127.0.0.1:18080/api/v1/decision-cases/CASE-VR-001/evaluations
  $evaluationReplay = Invoke-RestMethod -Method Post `
    -Headers $evaluationHeaders `
    http://127.0.0.1:18080/api/v1/decision-cases/CASE-VR-001/evaluations
  $evaluationLatest = Invoke-RestMethod `
    http://127.0.0.1:18080/api/v1/decision-cases/CASE-VR-001/evaluation
  if (($evaluationReplay | ConvertTo-Json -Depth 20 -Compress) -ne `
      ($evaluationLatest | ConvertTo-Json -Depth 20 -Compress)) {
    throw "Persisted evaluation latest result differs from idempotent replay"
  }
  $artifact = [ordered]@{
    checked_at = [DateTimeOffset]::UtcNow.ToString("o")
    run_status = $completed.status
    provider_attempt_audit_count = [int]$attemptCount
    decision_type = $decision.decision.decision_type
    advance_step = $advance.current_step
    guardrail_state = $advance.guardrail_state
    executed_actions = $advance.executed_actions
    evaluation_passed = $evaluation.passed
    decision_idempotent_replay = $true
    evaluation_persisted_replay = $true
  }
  New-Item -ItemType Directory -Force output/smoke | Out-Null
  $artifact | ConvertTo-Json | Set-Content -Encoding utf8 output/smoke/replay.json
  $artifact
} finally {
  if ($null -ne $api -and -not $api.HasExited) { Stop-Process -Id $api.Id -Force }
  Pop-Location
}
