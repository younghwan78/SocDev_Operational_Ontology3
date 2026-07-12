$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$compose = @("compose", "-f", "deploy/local/compose.yaml", "exec", "-T", "postgres")
$priorUrl = $env:SOC_OT_MIGRATION_DATABASE_URL

function Invoke-Checked([string]$File, [string[]]$Arguments) {
  & $File @Arguments
  if ($LASTEXITCODE -ne 0) { throw "$File failed with exit code $LASTEXITCODE" }
}

function Test-MigrationPath([string]$Database, [string]$StartRevision) {
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
    Invoke-Checked uv @("run", "alembic", "upgrade", "head")
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
  Write-Output "Empty and oldest-supported migration paths passed."
} finally {
  if ($null -eq $priorUrl) {
    Remove-Item Env:SOC_OT_MIGRATION_DATABASE_URL -ErrorAction SilentlyContinue
  } else {
    $env:SOC_OT_MIGRATION_DATABASE_URL = $priorUrl
  }
  Pop-Location
}
