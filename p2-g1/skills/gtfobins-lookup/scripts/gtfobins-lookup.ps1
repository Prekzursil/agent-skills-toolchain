#requires -version 5.1
<#
.SYNOPSIS
  Linux living-off-the-land lookup over the local GTFOBins corpus (+ optional live GTFOArgs),
  pairing each abuse vector with its DETECTION and HARDENING note. Defensive framing:
  know-it-to-detect-it. For authorized pentest, blue-team, CTF, RE, and education only.
.DESCRIPTION
  GTFOBins entries are extensionless YAML under D:\knowledge\gtfobins\_gtfobins\. Parsing is
  dependency-free (line/block based), so it runs on stock PowerShell 5.1 with no YAML module.
  For every function the binary exposes (shell, file-read, file-write, suid/sudo/capabilities
  contexts, library-load, ...) the tool prints: the abuse code, its MITRE ATT&CK technique, and
  the matching blue-team detection + hardening guidance (from functions.yml + linux-privesc KB).

  GTFOBins is fully OFFLINE (local clone). GTFOArgs (CLI argument-injection analog) has no local
  mirror, so -Args performs an OPT-IN network fetch of gtfoargs.github.io/api.json (cached).
.EXAMPLE
  pwsh gtfobins-lookup.ps1 find
.EXAMPLE
  pwsh gtfobins-lookup.ps1 tar -Function sudo        # only entries usable in a sudo context
.EXAMPLE
  pwsh gtfobins-lookup.ps1 -List
.EXAMPLE
  pwsh gtfobins-lookup.ps1 tar -Args               # also query GTFOArgs (network, opt-in)
#>
[CmdletBinding()]
param(
  [Parameter(Position = 0)][string]$Name,
  [ValidateSet('any', 'shell', 'command', 'reverse-shell', 'bind-shell', 'file-read', 'file-write',
    'upload', 'download', 'library-load', 'privilege-escalation', 'sudo', 'suid', 'capabilities')]
  [string]$Function = 'any',
  [switch]$List,
  [switch]$GtfoArgs,
  [switch]$Quiet,        # suppress the detection/hardening block (raw abuse vectors only)
  [int]$Max = 10,
  [string]$Root = $(if ($env:SEC_CORPORA_ROOT) { $env:SEC_CORPORA_ROOT } else { 'D:\knowledge' })
)
$ErrorActionPreference = 'Stop'

$gtfoDir = Join-Path $Root 'gtfobins\_gtfobins'

# ---- Function -> MITRE ATT&CK + blue-team detection/hardening (from _data/functions.yml + linux-privesc.md) ----
$FUNC = @{
  'shell'                = @{ mitre = 'T1059'; abuse = 'Spawns an interactive system shell.';
    detect = 'auditd/EDR execve of /bin/sh|/bin/bash whose parent is this binary, esp. from cron/service/web contexts; Falco "shell spawned by unexpected/privileged binary".';
    harden = 'Remove shell-escapable binaries from sudoers and the SUID set; sudo NOEXEC; confine via AppArmor/SELinux.' }
  'command'              = @{ mitre = 'T1059'; abuse = 'Runs non-interactive system commands.';
    detect = 'auditd execve where the child command-line is attacker-controlled and the parent is this binary; command-line anomaly hunting.';
    harden = 'Strip the binary from privileged invocation paths; least-privilege sudoers; NoNewPrivileges.' }
  'reverse-shell'        = @{ mitre = 'T1059,T1071'; abuse = 'Sends a reverse shell to a listening attacker.';
    detect = 'Egress monitoring: outbound connect() from a server/service account to a non-business IP; auditd connect syscall; netflow to rare destinations.';
    harden = 'Default-deny egress firewall / allowlist; block outbound init from service accounts.' }
  'bind-shell'           = @{ mitre = 'T1059,T1071'; abuse = 'Binds a shell to a local port for an attacker to connect.';
    detect = 'Baseline-diff listening sockets (ss -tulnp vs golden); Falco "unexpected listen on port"; new bind by a non-network daemon.';
    harden = 'Host firewall default-deny inbound; restrict which processes may bind.' }
  'file-write'           = @{ mitre = 'T1565'; abuse = 'Writes data to local files (overwrite/append).';
    detect = 'auditd watch on /etc/passwd,/etc/shadow,/etc/sudoers*,/etc/cron*,/etc/ld.so.* ; FIM (AIDE/Tripwire) integrity alerts.';
    harden = 'Least privilege; mount user-writable FS nosuid; remove file-write capability from the SUID/sudo set.' }
  'file-read'            = @{ mitre = 'T1005'; abuse = 'Reads data from local files.';
    detect = 'auditd read of /etc/shadow, SSH private keys, app secrets; alert on privileged read of credential files.';
    harden = 'Tighten file perms/ownership; remove file-read from the SUID/sudo set; encrypt secrets at rest.' }
  'upload'               = @{ mitre = 'T1041'; abuse = 'Uploads/exfiltrates local data.';
    detect = 'Egress/exfil monitoring, DLP, netflow volume anomalies from a host that should not initiate outbound.';
    harden = 'Egress allowlist; block exfil-capable LOLBins on servers.' }
  'download'             = @{ mitre = 'T1105'; abuse = 'Downloads remote data (tool/ingress transfer).';
    detect = 'Proxy logs, Falco "outbound connect by service proc", ingress of new tooling onto a host.';
    harden = 'Egress allowlist; block downloader LOLBins; application allowlisting.' }
  'library-load'         = @{ mitre = 'T1574'; abuse = 'Loads a shared library to run arbitrary code in-context.';
    detect = 'LD_PRELOAD/LD_LIBRARY_PATH present in a sudo env; new .so appearing in a writable rpath/runpath dir; auditd on library opens.';
    harden = 'Never env_keep LD_* / BASH_ENV; clear RPATH/RUNPATH on SUID bins (readelf -d); mount nosuid; secure boot / IMA.' }
  'privilege-escalation' = @{ mitre = 'T1548'; abuse = 'Indirectly grants elevation (sets SUID bit, chowns, etc.).';
    detect = 'auditd setuid/setgid/setcap syscalls and chmod +s; new SUID or cap-granted file vs baseline.';
    harden = 'Minimize SUID set; CapabilityBoundingSet=; NoNewPrivileges=yes; periodic SUID/cap baseline diff.' }
  'inherit'              = @{ mitre = '-'; abuse = 'Inherits the abuse functions of another binary (see that entry).';
    detect = 'See the inherited binary.'; harden = 'See the inherited binary.' }
}

# ---- Privilege CONTEXT -> detection/hardening (added when the function applies in that context) ----
$CTX = @{
  'suid'         = @{ note = 'SUID context (effective privs not dropped).';
    detect = 'Diff `find / -perm -4000 -type f` against a golden baseline; auditd setuid syscall; alert on execution of a non-baseline SUID binary.';
    harden = 'Minimize the SUID set; mount user-writable FS nosuid; prefer file capabilities; NoNewPrivileges; remove SUID from interpreters/editors.' }
  'sudo'         = @{ note = 'Sudo context (privileged run via sudo, privs not dropped).';
    detect = 'Sudo I/O logging (Defaults log_input,log_output); alert on shell escape from a NOPASSWD rule, on `sudo -u#-1`, and on LD_*/BASH_ENV in the sudo env.';
    harden = 'Least-privilege sudoers (no shell-escapable binaries); NOEXEC; Defaults use_pty,requiretty,!visiblepw; never env_keep LD_*/BASH_ENV/PATH; keep sudo patched.' }
  'capabilities' = @{ note = 'Capabilities context (kernel checks bypassed via file caps).';
    detect = 'Baseline-diff `getcap -r / 2>/dev/null`; auditd setcap syscall; decode CapEff (not just getcap) on execution.';
    harden = 'Grant the minimum cap, ambient-off; never cap_setuid/cap_dac_*/cap_sys_admin/cap_sys_module on general-purpose interpreters; drop via CapabilityBoundingSet=.' }
  'unprivileged' = @{ note = 'Works as any unprivileged user (no special privilege needed).'; detect = ''; harden = '' }
}

function Write-DetectHarden([string[]]$funcs, [System.Collections.Generic.HashSet[string]]$ctxs) {
  if ($Quiet) { return }
  $seen = New-Object System.Collections.Generic.HashSet[string]
  "  --- BLUE TEAM (know-it-to-detect-it) ---"
  foreach ($f in ($funcs | Select-Object -Unique)) {
    $m = $FUNC[$f]; if (-not $m) { continue }
    "  [$f] ATT&CK $($m.mitre) -- $($m.abuse)"
    if ($m.detect) { "    DETECT : $($m.detect)" }
    if ($m.harden) { "    HARDEN : $($m.harden)" }
  }
  foreach ($c in @('suid', 'sudo', 'capabilities')) {
    if ($ctxs.Contains($c)) {
      $m = $CTX[$c]
      "  [ctx:$c] $($m.note)"
      if ($m.detect) { "    DETECT : $($m.detect)" }
      if ($m.harden) { "    HARDEN : $($m.harden)" }
    }
  }
}

function Show-Gtfo([System.IO.FileInfo]$file) {
  $lines = Get-Content -LiteralPath $file.FullName
  # Index the top-level function headers (exactly 2-space indent, empty value).
  $hdr = @()
  for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match '^  ([a-z0-9][a-z0-9_-]*):\s*$') { $hdr += [pscustomobject]@{ idx = $i; name = $Matches[1] } }
  }
  if (-not $hdr) { return }

  $allFuncs = @(); $allCtx = New-Object System.Collections.Generic.HashSet[string]
  $blocks = @()
  for ($h = 0; $h -lt $hdr.Count; $h++) {
    $fn = $hdr[$h].name
    $start = $hdr[$h].idx + 1
    $end = $(if ($h + 1 -lt $hdr.Count) { $hdr[$h + 1].idx } else { $lines.Count }) - 1

    # Collect this function's contexts (lines at 6-space indent under a contexts: map).
    $fnCtx = New-Object System.Collections.Generic.HashSet[string]
    for ($i = $start; $i -le $end; $i++) {
      if ($lines[$i] -match '^      (unprivileged|sudo|suid|capabilities):') { [void]$fnCtx.Add($Matches[1]) }
    }

    # Function-level filter (also matches by privilege context, e.g. -Function sudo).
    if ($Function -ne 'any' -and $Function -ne $fn -and -not $fnCtx.Contains($Function)) { continue }

    $allFuncs += $fn
    foreach ($c in $fnCtx) { [void]$allCtx.Add($c) }

    # Pull the primary code block(s) for this function.
    $codes = @()
    for ($i = $start; $i -le $end; $i++) {
      if ($lines[$i] -match '^\s*-?\s*code:\s*\|') {
        $base = $lines[$i].IndexOf('code:')
        $j = $i + 1; $buf = @()
        while ($j -le $end -and ($lines[$j] -match '^\s*$' -or (($lines[$j] -replace '\S.*$', '').Length -gt $base))) {
          if ($lines[$j].Trim()) { $buf += $lines[$j].Trim() }
          $j++
        }
        if ($buf) { $codes += , $buf }
      }
    }
    $ctxTag = if ($fnCtx.Count) { " {$(($fnCtx | Sort-Object) -join ',')}" } else { '' }
    $blocks += "  ($fn$ctxTag)"
    foreach ($c in $codes) { foreach ($ln in $c) { $blocks += "      $ln" } }
  }
  if (-not $allFuncs) { return }  # filtered out entirely

  "===== [GTFOBins] $($file.Name) -- functions: $((($allFuncs | Select-Object -Unique) -join ', '))"
  $blocks
  Write-DetectHarden $allFuncs $allCtx
  ''
  $script:hits++
}

function Get-GtfoArgs([string]$bin) {
  # OPT-IN network: GTFOArgs (CLI argument-injection analog) has no local mirror. Cached api.json.
  $cacheDir = Join-Path $env:LOCALAPPDATA 'gtfobins-lookup'
  $cache = Join-Path $cacheDir 'gtfoargs-api.json'
  $fresh = (Test-Path $cache) -and ((Get-Date) - (Get-Item $cache).LastWriteTime).TotalDays -lt 7
  if (-not $fresh) {
    try {
      if (-not (Test-Path $cacheDir)) { New-Item -ItemType Directory -Path $cacheDir -Force | Out-Null }
      Invoke-WebRequest -Uri 'https://gtfoargs.github.io/api.json' -UseBasicParsing -TimeoutSec 15 -OutFile $cache
    } catch {
      "===== [GTFOArgs] network fetch failed -- query manually: https://gtfoargs.github.io/gtfoargs/$bin/"
      "  (GTFOArgs = argument-injection abuse: a binary that lets attacker-controlled CLI args reach a"
      "   dangerous primitive. DETECT: auditd execve arg inspection for injected flags. HARDEN: never pass"
      "   untrusted input as raw CLI args; use -- end-of-options; validate/escape; drop the binary from sudoers.)"
      return
    }
  }
  try {
    $api = Get-Content -LiteralPath $cache -Raw | ConvertFrom-Json
    $exes = $api.executables
    $match = $exes.PSObject.Properties | Where-Object { $_.Name -like "*$bin*" } | Select-Object -First $Max
    if (-not $match) { "===== [GTFOArgs] no entry matching '$bin' (cache: $cache)"; return }
    foreach ($e in $match) {
      "===== [GTFOArgs] $($e.Name) -- functions: $(($e.Value.functions.PSObject.Properties.Name) -join ', ')"
      foreach ($fp in $e.Value.functions.PSObject.Properties) {
        foreach ($ex in $fp.Value) { if ($ex.code) { "  ($($fp.Name)) $($ex.code -replace '\r?\n', ' ; ')" } }
      }
      if (-not $Quiet) {
        "  --- BLUE TEAM ---"
        "    DETECT : auditd execve argument inspection for injected flags reaching this binary; command-line anomaly hunting on wrapper scripts."
        "    HARDEN : never pass untrusted input as raw CLI args; use '--' end-of-options; validate/allowlist arguments; drop shell-escapable binaries from sudoers."
      }
      ''
    }
  } catch {
    "===== [GTFOArgs] could not parse api.json ($cache); query https://gtfoargs.github.io/gtfoargs/$bin/"
  }
}

# ---- main ----
if ($List) {
  if (Test-Path $gtfoDir) {
    $f = Get-ChildItem -LiteralPath $gtfoDir -File
    "# GTFOBins ($($f.Count) entries) under $gtfoDir :"
    ($f | Select-Object -ExpandProperty Name) -join ' '
  } else {
    "GTFOBins corpus not found at $gtfoDir. Refresh with the sec-corpora-update skill."
  }
  exit 0
}

if (-not $Name) { Write-Error "Provide a binary name (e.g. find, tar, vim) or -List. Optional: -Function <suid|sudo|shell|...>, -Args (GTFOArgs, network)."; exit 1 }

$script:hits = 0
if (Test-Path $gtfoDir) {
  Get-ChildItem -LiteralPath $gtfoDir -File |
    Where-Object { $_.Name -like "*$Name*" } | Sort-Object Name | Select-Object -First $Max |
    ForEach-Object { Show-Gtfo $_ }
} else {
  "GTFOBins corpus not found at $gtfoDir (set `$env:SEC_CORPORA_ROOT or run sec-corpora-update)."
}

if ($GtfoArgs) { Get-GtfoArgs $Name }

if ($script:hits -eq 0 -and -not $GtfoArgs) {
  "No GTFOBins entry matching '$Name'$(if ($Function -ne 'any') { " with function/context '$Function'" }) under $Root."
  "Tip: -Args also queries GTFOArgs (argument-injection analog); gtfobins.github.io / gtfoargs.github.io for the canonical pages."
}
