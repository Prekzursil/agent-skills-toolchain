$ErrorActionPreference = 'Stop'

# ---- port migration map ----
$map = [ordered]@{
  '31380' = '31100'   # sliver
  '31381' = '31101'   # sliver-full
  '31410' = '31110'   # github-security
  '31411' = '31111'   # cve
  '31412' = '31112'   # osint
  '31413' = '31113'   # hexstrike-ai
  '31414' = '31114'   # firecrawl
  '31415' = '31115'   # hacktricks
  '31416' = '31116'   # metasploit
  '31417' = '31117'   # nuclei
  '31418' = '31118'   # cloud-audit
  '31419' = '31119'   # semgrep
}

$stamp = '20260907-0130'
$bdir = "D:\opt\cyberstrike-mcp\backups\portband-$stamp"
New-Item -ItemType Directory -Path $bdir -Force | Out-Null

$files = @(
  'D:\opt\cyberstrike-mcp\cyberstrike-mcp-lib.ps1',
  'D:\opt\cyberstrike-mcp\mcp-ssot.json',
  'D:\opt\cyberstrike-mcp\reconcile-cyberstrike-mcp-config.py',
  'D:\opt\cyberstrike-mcp\probe-mcp-http.py',
  'D:\opt\cyberstrike-mcp\sliver-client-mcp-http.cmd',
  'D:\opt\cyberstrike-mcp\sliver-full-mcp-http.cmd',
  'D:\opt\cyberstrike-mcp\sliver-full-http.py',
  'D:\opt\cyberstrike-mcp\generated\tui-mcp-inventory.json',
  'D:\opt\cyberstrike-mcp\generated\cursor-mcp-full-heavy.json',
  'C:\Users\Prekzursil\.config\cyberstrike\cyberstrike.json'
)

$total = 0
foreach ($f in $files) {
  if (-not (Test-Path $f)) { "SKIP missing: $f"; continue }
  Copy-Item $f (Join-Path $bdir (($f -replace '[:\\]','_'))) -Force
  $text = [IO.File]::ReadAllText($f)
  $n = 0
  foreach ($k in $map.Keys) {
    $new = $text -replace $k, $map[$k]
    if ($new -ne $text) { $n++ }
    $text = $new
  }
  [IO.File]::WriteAllText($f, $text)
  $hits = ([regex]::Matches($text, '311(0[01]|1[0-9])')).Count
  "MIGRATED $f (changed-ports=$n, new-band-refs=$hits)"
  $total += $n
}
""
"total port tokens migrated: $total"
"backups in: $bdir"

# sanity: no stale 314xx / 3138x left in edited files
""
"--- residual check (should list nothing) ---"
foreach ($f in $files) {
  if (Test-Path $f) {
    $m = Select-String -Path $f -Pattern '3141[0-9]|3138[01]' -AllMatches
    if ($m) { "STALE in ${f}:"; $m | ForEach-Object { "  line $($_.LineNumber): $($_.Line.Trim().Substring(0,[Math]::Min(90,$_.Line.Trim().Length)))" } }
  }
}
"done"
