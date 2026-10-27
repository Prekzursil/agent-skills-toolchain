#requires -version 5.1
<#
.SYNOPSIS
  Structured living-off-the-land lookup over local GTFOBins (Unix) + LOLBAS (Windows) corpora.
  Maps a binary name to its abuse techniques and ready commands. No network.
.DESCRIPTION
  GTFOBins entries are extensionless YAML under D:\knowledge\gtfobins\_gtfobins\; LOLBAS entries are
  *.yml under D:\knowledge\lolbas\yml\. Parsing is dependency-free (line-based), so it works on stock
  PowerShell 5.1 with no YAML module.
.EXAMPLE
  pwsh lolbin-lookup.ps1 nmap
.EXAMPLE
  pwsh lolbin-lookup.ps1 certutil -Source lolbas
.EXAMPLE
  pwsh lolbin-lookup.ps1 -List
#>
param(
  [Parameter(Position = 0)][string]$Name,
  [ValidateSet('both', 'gtfobins', 'lolbas')][string]$Source = 'both',
  [switch]$List,
  [int]$Max = 10,
  [string]$Root = $(if ($env:SEC_CORPORA_ROOT) { $env:SEC_CORPORA_ROOT } else { 'D:\knowledge' })
)
$ErrorActionPreference = 'Stop'

$gtfoDir = Join-Path $Root 'gtfobins\_gtfobins'
$lolDir = Join-Path $Root 'lolbas\yml'

function Show-Gtfo([System.IO.FileInfo]$file) {
  $lines = Get-Content -LiteralPath $file.FullName
  # Function/technique keys sit at exactly 2-space indent with an empty value.
  $techs = foreach ($l in $lines) {
    if ($l -match '^  ([a-z0-9][a-z0-9_-]*):\s*$') { $Matches[1] }
  }
  "===== [GTFOBins] $($file.Name) — techniques: $((($techs | Select-Object -Unique) -join ', '))"
  # Print each code block (the actual command) with its enclosing technique.
  $curTech = ''
  for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match '^  ([a-z0-9][a-z0-9_-]*):\s*$') { $curTech = $Matches[1]; continue }
    if ($lines[$i] -match '^\s*-?\s*code:\s*\|') {
      $base = $lines[$i].IndexOf('code:')  # column of the 'code:' token (handles "- code:" list items)
      $j = $i + 1
      while ($j -lt $lines.Count -and ($lines[$j] -match '^\s*$' -or (($lines[$j] -replace '\S.*$', '').Length -gt $base))) {
        if ($lines[$j].Trim()) { "  ($curTech) $($lines[$j].Trim())" }
        $j++
      }
    }
  }
  ''
}

function Show-Lol([System.IO.FileInfo]$file) {
  $lines = Get-Content -LiteralPath $file.FullName
  $name = ($lines | Where-Object { $_ -match '^Name:\s*(.+)$' } | Select-Object -First 1) -replace '^Name:\s*', ''
  "===== [LOLBAS] $($file.BaseName) ($name)"
  $cmd = $null; $cat = '?'; $mit = '?'
  $flush = { if ($cmd) { "  cmd [$cat / $mit]: $cmd" } }
  foreach ($l in $lines) {
    if ($l -match '^\s*-?\s*Command:\s*(.+)$') { & $flush; $cmd = $Matches[1].Trim(); $cat = '?'; $mit = '?' }
    elseif ($l -match '^\s*Category:\s*(.+)$') { $cat = $Matches[1].Trim() }
    elseif ($l -match '^\s*MitreID:\s*(.+)$') { $mit = $Matches[1].Trim() }
  }
  & $flush
  ''
}

if ($List) {
  if ($Source -ne 'lolbas' -and (Test-Path $gtfoDir)) {
    "# GTFOBins ($((Get-ChildItem -LiteralPath $gtfoDir -File).Count) entries):"
    (Get-ChildItem -LiteralPath $gtfoDir -File | Select-Object -ExpandProperty Name) -join ' '
    ''
  }
  if ($Source -ne 'gtfobins' -and (Test-Path $lolDir)) {
    $lol = Get-ChildItem -LiteralPath $lolDir -Recurse -Filter *.yml
    "# LOLBAS ($($lol.Count) entries):"
    ($lol | Select-Object -ExpandProperty BaseName) -join ' '
  }
  exit 0
}

if (-not $Name) { Write-Error "Provide a binary name (e.g. nmap, certutil) or -List."; exit 1 }

$hits = 0
if ($Source -ne 'lolbas' -and (Test-Path $gtfoDir)) {
  Get-ChildItem -LiteralPath $gtfoDir -File |
    Where-Object { $_.Name -like "*$Name*" } | Select-Object -First $Max |
    ForEach-Object { Show-Gtfo $_; $script:hits++ }
}
if ($Source -ne 'gtfobins' -and (Test-Path $lolDir)) {
  Get-ChildItem -LiteralPath $lolDir -Recurse -Filter *.yml |
    Where-Object { $_.BaseName -like "*$Name*" } | Select-Object -First $Max |
    ForEach-Object { Show-Lol $_; $script:hits++ }
}
if ($hits -eq 0) { "No GTFOBins/LOLBAS entry matching '$Name' under $Root." }
