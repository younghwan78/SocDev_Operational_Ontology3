$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$files = Get-ChildItem -Path $root -Recurse -File |
    Where-Object {
        $_.FullName -notmatch "[\\/](node_modules|\.venv|\.git)[\\/]" -and
        $_.Extension -in ".py", ".ts", ".tsx", ".md", ".yaml", ".yml", ".json", ".toml"
    }
$matches = $files | Select-String -Pattern "sk-[A-Za-z0-9_-]{20,}"
if ($matches) {
    $matches | ForEach-Object { Write-Error $_.ToString() }
    throw "Potential API secret found."
}
Write-Output "Secret scan passed."

