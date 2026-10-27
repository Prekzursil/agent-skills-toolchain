#requires -Version 5.1
<#
  World Watch  (daily Scheduled Task: 'World-Watch')  -- ANTICIPATORY layer producer.

  Change-detects a small CURATED list (world-watch.yaml) of EXTERNAL signals and appends
  ONE dated BACKGROUND-DIGEST line per watcher ONLY when its fingerprint CHANGES from the
  stored baseline. Targets the documented "upstream changed and silently broke me" class:
  BC app-version bumps (offset re-derivation / HGT risk), upstream repos that clobber the
  user's patches on pull (HexStrike / BCSFE / tbcml / insta-mcp), and curated vendor pages.

  Signals are native CLIs (gh / adb / HTTP / file hash) -- a Scheduled Task cannot reach
  in-session MCP servers, so firecrawl_monitor_* is intentionally NOT used here.

  LOG + SURFACE + PROPOSE ONLY. Never edits/pulls/patches anything; the digest line carries
  a PROPOSED manual action (mirrors the mcp-drift-audit.ps1 doctrine). First observation of a
  watcher records a baseline SILENTLY (no fire). Every watcher fail-opens independently: one
  that cannot be evaluated is logged + skipped, its baseline is kept, and it never fires a
  false change. Whole script is fail-open and can only ever exit 0.

  Built 2026-06-29.
#>

[CmdletBinding()]
param(
    [string]$ConfigFile = 'C:\Users\Prekzursil\scripts\world-watch.yaml',
    [string]$StateFile  = 'C:\Users\Prekzursil\scripts\world-watch.state.json',
    [string]$DigestFile = 'C:\Users\Prekzursil\.claude\BACKGROUND-DIGEST.md',
    [string]$LogFile    = 'C:\Users\Prekzursil\scripts\world-watch.log'
)

$MaxLogLines = 300

function Get-Stamp { (Get-Date).ToString('yyyy-MM-dd HH:mm:ss') }

function Write-WwLog {
    param([string]$Line)
    try {
        $dir = Split-Path -Parent $LogFile
        if ($dir -and -not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
        Add-Content -LiteralPath $LogFile -Value $Line -Encoding utf8
        $all = @(Get-Content -LiteralPath $LogFile -ErrorAction SilentlyContinue)
        if ($all.Count -gt $MaxLogLines) {
            $all | Select-Object -Last $MaxLogLines | Set-Content -LiteralPath $LogFile -Encoding utf8
        }
    } catch { }
}

function Add-DigestLine {
    param([string]$Source, [string]$Message, [string]$Propose)
    try {
        $dir = Split-Path -Parent $DigestFile
        if ($dir -and -not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
        $clean = ($Message -replace '\r?\n', ' ').Trim()
        $line = "[{0}] [{1}] {2}" -f (Get-Stamp), $Source, $clean
        if ($Propose) { $line = "$line  | PROPOSE: $(($Propose -replace '\r?\n',' ').Trim())" }
        Add-Content -LiteralPath $DigestFile -Value $line -Encoding utf8
        return $true
    } catch { return $false }
}

function Resolve-Python {
    foreach ($c in @('C:\Python314\python.exe', 'C:\Python313\python.exe', 'C:\Python312\python.exe')) {
        if (Test-Path -LiteralPath $c) { return $c }
    }
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

function Read-Config {
    # YAML -> JSON via python+pyyaml (already present), then ConvertFrom-Json. Fail-open -> $null.
    param([string]$Path)
    try {
        if (-not (Test-Path -LiteralPath $Path)) { Write-WwLog "[$(Get-Stamp)] ERROR config not found: $Path"; return $null }
        $py = Resolve-Python
        if (-not $py) { Write-WwLog "[$(Get-Stamp)] ERROR no python interpreter for YAML parse"; return $null }
        # Feed the converter via STDIN (python -) rather than -c: PowerShell 5.1's native-arg
        # quoting mangles the embedded double-quotes in a -c string (pwsh 7 does not), so a -c
        # one-liner silently fails under 5.1. STDIN keeps the quotes off the command line.
        # utf-8-sig transparently strips an optional BOM and still reads BOM-less UTF-8.
        $code = @'
import sys, json, yaml
with open(sys.argv[1], encoding="utf-8-sig") as f:
    print(json.dumps(yaml.safe_load(f)))
'@
        $json = $code | & $py - $Path 2>$null | Out-String
        if (-not $json -or -not $json.Trim()) { Write-WwLog "[$(Get-Stamp)] ERROR empty YAML parse (pyyaml present?)"; return $null }
        return ($json | ConvertFrom-Json)
    } catch { Write-WwLog "[$(Get-Stamp)] ERROR YAML parse: $($_.Exception.Message)"; return $null }
}

function Read-State {
    $h = @{}
    try {
        if (Test-Path -LiteralPath $StateFile) {
            $o = Get-Content -LiteralPath $StateFile -Raw -ErrorAction Stop | ConvertFrom-Json
            if ($o -and $o.watchers) {
                foreach ($p in $o.watchers.PSObject.Properties) { $h[$p.Name] = [string]$p.Value }
            }
        }
    } catch { }
    return $h
}

function Write-State {
    param([hashtable]$Map)
    try {
        $dir = Split-Path -Parent $StateFile
        if ($dir -and -not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
        $obj = [ordered]@{ watchers = $Map; last_run = (Get-Stamp) }
        ($obj | ConvertTo-Json -Depth 5) | Set-Content -LiteralPath $StateFile -Encoding utf8
    } catch { Write-WwLog "[$(Get-Stamp)] ERROR write-state: $($_.Exception.Message)" }
}

# ---- hang-proof native call ------------------------------------------------
# A HIDDEN scheduled task hitting gh/adb over the network must NOT be able to wedge the daily
# run (observed: a gh call stalled the hidden-session run while a direct run took 5s). Every
# external call therefore runs under a HARD timeout and fails open ($null) on timeout/error.
# Success is keyed on NON-EMPTY stdout (gh/adb write the value to stdout, errors to stderr) to
# sidestep the Start-Process -PassThru ExitCode-is-sometimes-null gotcha.
function Invoke-NativeCapture {
    param([string]$Exe, [string[]]$Arguments, [int]$TimeoutSec = 25)
    $cmd = Get-Command $Exe -ErrorAction SilentlyContinue
    $exePath = if ($cmd) { $cmd.Source } else { $null }
    if (-not $exePath) {
        $fallbacks = @{ 'gh' = 'C:\Program Files\GitHub CLI\gh.exe'; 'adb' = 'C:\ADB\adb.exe' }
        if ($fallbacks.ContainsKey($Exe) -and (Test-Path -LiteralPath $fallbacks[$Exe])) { $exePath = $fallbacks[$Exe] }
    }
    if (-not $exePath) { return $null }
    $outFile = [System.IO.Path]::GetTempFileName()
    $errFile = [System.IO.Path]::GetTempFileName()
    try {
        # PS5.1 -ArgumentList joins the array WITHOUT quoting -> a value containing a space would
        # corrupt the command line and silently fail. Quote only space-bearing args (current
        # config has none, so this is a no-op today; future-proofs new watchers).
        $quoted = @($Arguments | ForEach-Object {
            if ($_ -match '\s') { '"' + ($_ -replace '"', '\"') + '"' } else { [string]$_ }
        })
        $p = Start-Process -FilePath $exePath -ArgumentList $quoted -NoNewWindow -PassThru `
             -RedirectStandardOutput $outFile -RedirectStandardError $errFile
        if (-not $p.WaitForExit($TimeoutSec * 1000)) {
            try { $p.Kill() } catch { }
            return $null
        }
        $out = Get-Content -LiteralPath $outFile -Raw -ErrorAction SilentlyContinue
        if ([string]::IsNullOrWhiteSpace($out)) { return $null }
        return $out.Trim()
    } catch { return $null }
    finally {
        foreach ($f in @($outFile, $errFile)) { try { [System.IO.File]::Delete($f) } catch { } }
    }
}

# ---- fingerprint samplers (each returns a string, or $null on failure/timeout -> skip) ----
function FP-GhCommit {
    param($w)
    $branch = if ($w.branch) { [string]$w.branch } else { 'HEAD' }
    return (Invoke-NativeCapture -Exe 'gh' -Arguments @('api', ("repos/{0}/commits/{1}" -f $w.repo, $branch), '-q', '.sha'))
}

function FP-GhRelease {
    param($w)
    return (Invoke-NativeCapture -Exe 'gh' -Arguments @('release', 'view', '--repo', [string]$w.repo, '--json', 'tagName', '-q', '.tagName'))
}

function FP-AdbVersion {
    param($w)
    $out = Invoke-NativeCapture -Exe 'adb' -Arguments @('shell', 'dumpsys', 'package', [string]$w.package) -TimeoutSec 15
    if ($out) {
        $m = [regex]::Match($out, '(?im)versionName=([^\s]+)')
        if ($m.Success) { return $m.Groups[1].Value.Trim() }
    }
    return $null
}

function FP-HttpEtag {
    param($w)
    try {
        $r = Invoke-WebRequest -Uri $w.url -Method Head -UseBasicParsing -TimeoutSec 20 -ErrorAction Stop
        $et = $r.Headers['ETag']; if ($et) { return "etag:$et" }
        $lm = $r.Headers['Last-Modified']; if ($lm) { return "lm:$lm" }
        if ($w.hash_fallback -eq $true) {
            $g = Invoke-WebRequest -Uri $w.url -UseBasicParsing -TimeoutSec 30 -ErrorAction Stop
            $bytes = [System.Text.Encoding]::UTF8.GetBytes([string]$g.Content)
            $sha256 = [System.Security.Cryptography.SHA256]::Create()
            try { $sha = $sha256.ComputeHash($bytes) } finally { $sha256.Dispose() }
            return 'sha:' + (-join ($sha | ForEach-Object { $_.ToString('x2') }))
        }
    } catch { }
    return $null
}

function FP-FileHash {
    param($w)
    try {
        if (Test-Path -LiteralPath $w.path) {
            return 'sha:' + (Get-FileHash -LiteralPath $w.path -Algorithm SHA256 -ErrorAction Stop).Hash.ToLower()
        }
    } catch { }
    return $null
}

function Get-Fingerprint {
    param($w)
    switch ([string]$w.type) {
        'gh_commit'           { return (FP-GhCommit $w) }
        'gh_release'          { return (FP-GhRelease $w) }
        'adb_package_version' { return (FP-AdbVersion $w) }
        'http_etag'           { return (FP-HttpEtag $w) }
        'file_hash'           { return (FP-FileHash $w) }
        default               { return $null }
    }
}

function Short {
    # Sanitize for SAFE display. External fingerprints (a gh_release TAG NAME, an adb
    # versionName) are attacker-influenceable and land verbatim in the model's SessionStart
    # context, so strip anything outside a conservative allowlist (alnum + . - _ :) -- this
    # removes whitespace/newlines/punctuation an injection would need -- then cap length.
    # State comparison uses the RAW fingerprint elsewhere; this is display-only.
    param([string]$s)
    if (-not $s) { return '' }
    $clean = ($s -replace '[^A-Za-z0-9.\-_:]', '?')
    if ($clean.Length -gt 16) { return $clean.Substring(0, 16) }
    return $clean
}

function Default-Propose {
    param($w)
    if ($w.propose) { return [string]$w.propose }
    switch ([string]$w.type) {
        'gh_commit'           { return 'diff upstream vs your local patches before pulling' }
        'gh_release'          { return 'review the release notes before adopting' }
        'adb_package_version' { return 're-derive committed offsets before running hooks (HGT risk)' }
        default               { return 'review before adopting the change' }
    }
}

# ---------------------------------------------------------------------------
try {
    $stamp = Get-Stamp
    $cfg = Read-Config -Path $ConfigFile
    if (-not $cfg -or -not $cfg.watchers) {
        Write-WwLog "[$stamp] SKIP no usable config/watchers"
        return
    }

    $state = Read-State
    $checked = 0; $changed = 0; $baseline = 0; $skipped = 0

    foreach ($w in @($cfg.watchers)) {
        $id = [string]$w.id
        if (-not $id) { continue }
        $checked++
        $fp = Get-Fingerprint $w
        if (-not $fp) {
            $skipped++
            Write-WwLog "[$stamp] SKIP  $id ($($w.type)) - could not determine fingerprint (kept baseline)"
            continue
        }
        $prev = if ($state.ContainsKey($id)) { [string]$state[$id] } else { $null }
        if ($null -eq $prev) {
            $baseline++
            $state[$id] = $fp
            Write-WwLog "[$stamp] BASE  $id = $(Short $fp) (first observation; no fire)"
        }
        elseif ($prev -ne $fp) {
            $changed++
            $state[$id] = $fp
            $target = if ($w.repo) { $w.repo } elseif ($w.package) { $w.package } elseif ($w.url) { $w.url } elseif ($w.path) { $w.path } else { '' }
            $msg = "{0} changed {1} -> {2} ({3} {4}): {5}" -f $id, (Short $prev), (Short $fp), $w.type, $target, [string]$w.note
            $ok = Add-DigestLine -Source 'world-watch' -Message $msg -Propose (Default-Propose $w)
            Write-WwLog "[$stamp] CHANGE $id $(Short $prev) -> $(Short $fp)  digest=$(if($ok){'ok'}else{'FAILED'})"
        }
        else {
            Write-WwLog "[$stamp] SAME  $id = $(Short $fp)"
        }
    }

    Write-State -Map $state
    Write-WwLog "[$stamp] DONE  checked=$checked changed=$changed baseline=$baseline skipped=$skipped"
}
catch {
    try { Write-WwLog "[$(Get-Stamp)] ERROR unhandled: $($_.Exception.Message)" } catch { }
}

exit 0   # deterministic success code: a trailing failed gh/adb native call must not make
         # Task Scheduler report 0x1 for a run we handled gracefully.
