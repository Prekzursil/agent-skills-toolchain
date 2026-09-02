# ARC-0026 PowerShell process enumeration.
# Mechanically independent of MCP JSON parsing: reads the live process table.
$ErrorActionPreference = "Continue"
$scanned = 0
$hits = New-Object System.Collections.Generic.List[object]

function Redact([string]$raw) {
    if ([string]::IsNullOrEmpty($raw)) { return "" }
    $s = [regex]::Replace($raw, '(?i)(api[_-]?key|token|secret|bearer|sk-)[=: ]\S+', '$1=<redacted>')
    if ($s.Length -gt 180) { return $s.Substring(0, 180) }
    return $s
}

if (Test-Path -LiteralPath "/proc") {
    Get-ChildItem -LiteralPath "/proc" -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        if ($_.Name -notmatch '^\d+$') { return }
        $script:scanned++
        $cmdPath = Join-Path $_.FullName "cmdline"
        if (-not (Test-Path -LiteralPath $cmdPath)) { return }
        try {
            $bytes = [System.IO.File]::ReadAllBytes($cmdPath)
            $raw = [System.Text.Encoding]::UTF8.GetString($bytes).Replace([char]0, " ")
        } catch {
            return
        }
        $low = $raw.ToLowerInvariant()
        if ($low -match "mcp" -or $low -match "/usr/bin/npx") {
            $hits.Add([pscustomobject]@{ pid = $_.Name; cmd = (Redact $raw) }) | Out-Null
        }
    }
} else {
    Get-Process -ErrorAction SilentlyContinue | ForEach-Object {
        $script:scanned++
        $name = [string]$_.ProcessName
        if ($name -match "mcp|npx") {
            $hits.Add([pscustomobject]@{ pid = [string]$_.Id; cmd = (Redact $name) }) | Out-Null
        }
    }
}

$result = [ordered]@{
    engine  = "pwsh"
    scanned = $scanned
    count   = $hits.Count
    hits    = @($hits)
}
$result | ConvertTo-Json -Compress -Depth 6
