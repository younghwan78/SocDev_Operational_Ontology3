$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$compose = @("compose", "-f", "deploy/local/compose.yaml", "exec", "-T", "postgres")
$priorUrl = $env:SOC_OT_MIGRATION_DATABASE_URL

function Invoke-Checked([string]$File, [string[]]$Arguments) {
  & $File @Arguments
  if ($LASTEXITCODE -ne 0) { throw "$File failed with exit code $LASTEXITCODE" }
}

function Test-MigrationPath(
  [string]$Database,
  [string]$StartRevision,
  [bool]$SeedLegacyDecision = $false
) {
  if ($Database -notmatch '^soc_ot_mig_[0-9]+_[ab]$') { throw "Unsafe migration DB name" }
  try {
    Invoke-Checked docker ($compose + @(
      "psql", "-U", "soc_ot_admin", "-d", "postgres", "-v", "ON_ERROR_STOP=1",
      "-c", "CREATE DATABASE $Database"
    ))
    $init = @"
CREATE SCHEMA observable AUTHORIZATION soc_ot_admin;
CREATE SCHEMA hidden AUTHORIZATION soc_ot_admin;
CREATE SCHEMA audit AUTHORIZATION soc_ot_admin;
GRANT CONNECT ON DATABASE $Database TO soc_ot_runtime, soc_ot_outcome;
GRANT USAGE ON SCHEMA observable, audit TO soc_ot_runtime;
GRANT USAGE ON SCHEMA observable, hidden, audit TO soc_ot_outcome;
ALTER DEFAULT PRIVILEGES FOR ROLE soc_ot_admin IN SCHEMA observable GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO soc_ot_runtime, soc_ot_outcome;
ALTER DEFAULT PRIVILEGES FOR ROLE soc_ot_admin IN SCHEMA hidden GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO soc_ot_outcome;
ALTER DEFAULT PRIVILEGES FOR ROLE soc_ot_admin IN SCHEMA audit GRANT SELECT, INSERT ON TABLES TO soc_ot_runtime, soc_ot_outcome;
"@
    Invoke-Checked docker ($compose + @(
      "psql", "-U", "soc_ot_admin", "-d", $Database, "-v", "ON_ERROR_STOP=1",
      "-c", $init
    ))
    $env:SOC_OT_MIGRATION_DATABASE_URL = `
      "postgresql+psycopg://soc_ot_admin:admin_local@127.0.0.1:15432/$Database"
    if ($StartRevision) { Invoke-Checked uv @("run", "alembic", "upgrade", $StartRevision) }
    if ($SeedLegacyDecision) {
      $legacyDecision = @'
INSERT INTO observable.simulation_states (case_id, current_step, aggregate_version)
VALUES ('CASE-MIGRATION', 12, 1);
INSERT INTO observable.simulated_decisions (
  command_id, idempotency_key, command_fingerprint, case_id, aggregate_version,
  review_run_id, actor_id, payload
) VALUES (
  'CMD-MIGRATION', 'IDEMPOTENCY-MIGRATION', repeat('0', 64), 'CASE-MIGRATION', 1,
  'RUN-MIGRATION', 'migration-test',
  jsonb_build_object('decision', jsonb_build_object(
    'schema_version', 'simulated-decision.v1',
    'case_id', 'CASE-MIGRATION',
    'decision_type', 'COLLECT_MINIMUM_EVIDENCE',
    'selected_option_id', NULL,
    'rationale', 'legacy',
    'safeguards', '[]'::jsonb,
    'dissent_acknowledged', '[]'::jsonb,
    'decision_source', 'simulated_chair',
    'simulated', true
  ))
);
'@
      Invoke-Checked docker ($compose + @(
        "psql", "-U", "soc_ot_admin", "-d", $Database, "-v", "ON_ERROR_STOP=1",
        "-c", $legacyDecision
      ))
    }
    Invoke-Checked uv @("run", "alembic", "upgrade", "head")
    if ($SeedLegacyDecision) {
      $upgradeAssertion = @'
DO $migration$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM observable.simulated_decisions
    WHERE command_id = 'CMD-MIGRATION'
      AND payload #>> '{decision,schema_version}' = 'simulated-decision.v2'
      AND payload #>> '{decision,action_plan,action_type}' = 'collect_evidence'
      AND (payload #>> '{decision,action_plan,due_at_step}')::int = 12
      AND jsonb_array_length(payload #> '{decision,action_plan,evidence_required}') = 1
  ) THEN
    RAISE EXCEPTION 'v1 decision upgrade assertion failed';
  END IF;
END
$migration$;
'@
      Invoke-Checked docker ($compose + @(
        "psql", "-U", "soc_ot_admin", "-d", $Database, "-v", "ON_ERROR_STOP=1",
        "-c", $upgradeAssertion
      ))
      Invoke-Checked uv @("run", "alembic", "downgrade", "0016_agent_run_budget_plan")
      $downgradeAssertion = @'
DO $migration$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM observable.simulated_decisions
    WHERE command_id = 'CMD-MIGRATION'
      AND payload #>> '{decision,schema_version}' = 'simulated-decision.v1'
      AND NOT ((payload #> '{decision}') ? 'action_plan')
  ) THEN
    RAISE EXCEPTION 'v2 decision downgrade assertion failed';
  END IF;
END
$migration$;
'@
      Invoke-Checked docker ($compose + @(
        "psql", "-U", "soc_ot_admin", "-d", $Database, "-v", "ON_ERROR_STOP=1",
        "-c", $downgradeAssertion
      ))
      Invoke-Checked uv @("run", "alembic", "upgrade", "head")
    }
    Invoke-Checked uv @("run", "alembic", "current", "--check-heads")
  } finally {
    Invoke-Checked docker ($compose + @(
      "psql", "-U", "soc_ot_admin", "-d", "postgres", "-v", "ON_ERROR_STOP=1",
      "-c", "DROP DATABASE IF EXISTS $Database WITH (FORCE)"
    ))
  }
}

Push-Location $root
try {
  Invoke-Checked docker @("compose", "-f", "deploy/local/compose.yaml", "up", "-d", "postgres")
  Test-MigrationPath "soc_ot_mig_$PID`_a" ""
  Test-MigrationPath "soc_ot_mig_$PID`_b" "0001_case_store"
  Test-MigrationPath "soc_ot_mig_$PID`_a" "0016_agent_run_budget_plan" $true
  Write-Output "Empty, oldest-supported, and v1 decision data migration paths passed."
} finally {
  if ($null -eq $priorUrl) {
    Remove-Item Env:SOC_OT_MIGRATION_DATABASE_URL -ErrorAction SilentlyContinue
  } else {
    $env:SOC_OT_MIGRATION_DATABASE_URL = $priorUrl
  }
  Pop-Location
}
