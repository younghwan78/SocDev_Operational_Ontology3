$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$errors = [System.Collections.Generic.List[string]]::new()

Get-ChildItem -Path $root -Recurse -File -Filter *.md |
    Where-Object { $_.FullName -notmatch "[\\/](node_modules|\.venv|\.git)[\\/]" } |
    ForEach-Object {
    $file = $_
    $text = Get-Content -Raw -LiteralPath $file.FullName
    [regex]::Matches($text, '\[[^\]]+\]\(([^)#]+\.md)(?:#[^)]+)?\)') | ForEach-Object {
        if ($_.Groups[1].Value -match '^https?://') { return }
        $target = Join-Path $file.DirectoryName $_.Groups[1].Value
        if (-not (Test-Path -LiteralPath $target)) {
            $errors.Add("$($file.FullName) -> $($_.Groups[1].Value)")
        }
    }
}

if ($errors.Count -gt 0) {
    $errors | ForEach-Object { Write-Error $_ }
    throw "Broken Markdown links found."
}
Write-Output "Markdown link check passed."
