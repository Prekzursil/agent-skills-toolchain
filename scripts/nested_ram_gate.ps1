#Requires -Version 5.1
<#
.SYNOPSIS
  G-12 RAM pre-flight gate for nested delegation (the T0 delegate() program).
  Owned by the delegate-primitive skill (C:\Users\Prekzursil\.agents\skills\delegate-primitive\SKILL.md).

.DESCRIPTION
  Owner decision G-12a (2026-09-22, GRILL-DECISIONS_workflow-delegation_2026-09-22.md):
  nested calls count as fleet for the G-26/G-99 pre-flight. Before ANY nested
  delegation wave (workflow launch, Task fan-out, nested claude spawn), run this
  gate and require exit 0.

  Flow:
    1. run mcp_ram_audit.ps1, parse free RAM (GB) + MCP-class process count
    2. if free RAM < -MinFreeGB OR MCP-class count > -MaxMcpProcs:
         reap orphans via reap_orphan_mcp.ps1 (SAFE policy: dead-root ancestry
         kills only; whitelists mcp-hub/basic-memory/agent-mail/auth2api/
         actions-runner/cc-gateway/socat), then re-run the audit
    3. decide on the post-reap (or pre-, if no reap fired) measurement

  The decimal separator of the audit's "free RAM GB: X" line is culture-formatted
  (comma on ro-RO), so it is normalized before parsing.

  Exit codes (terminal states):
    0   GATE:PASS      free RAM >= floor (or GATE:OVERRIDE when -Override used)
    1   GATE:FAILED-TO-RUN  audit dependency missing or its output unparseable.
                        Fail-closed: an unreadable measurement is never a PASS.
    2   GATE:BLOCK     free RAM still < floor after the reap attempt.

.PARAMETER MinFreeGB
  Free-RAM floor in GB. Default 8 (G-26 / mcp-process-hygiene rule 2: no
  multi-agent fleets below 8 GB free).

.PARAMETER MaxMcpProcs
  MCP-class process count above which a reap fires (G-99 threshold: 150).

.PARAMETER Override
  Owner-directive bypass of the free-RAM floor. -Override is NOT an agent
  convenience: every use must be an owner decision RECORDED in
  C:\Users\Prekzursil\.agents\GRILL-DECISIONS_workflow-delegation_2026-09-22.md
  (G-12). Precedent: the 2026-09-22 T0 build wave itself ran under such a
  recorded owner override (~1.9 GB free). With -Override the gate still reaps,
  re-checks and reports, but exits 0 with GATE:OVERRIDE when below floor.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\Prekzursil\.agents\scripts\nested_ram_gate.ps1
  if ($LASTEXITCODE -ne 0) { throw "nested fleet blocked by RAM gate ($LASTEXITCODE)" }

.NOTES
  Exit-code contract is load-bearing for callers: only 0 is GO. The MCP-class
  count is advisory (reap trigger); an unparseable count (-1) degrades the reap
  decision to RAM-only, it does not fail the gate. An unparseable free-RAM
  reading DOES fail the gate (exit 1) - the floor is the contract.
#>
param(
    [double]$MinFreeGB = 8,
    [int]$MaxMcpProcs = 150,
    [switch]$Override
)

$ErrorActionPreference = 'Stop'
$AuditScript  = 'C:\Users\Prekzursil\.agents\scripts\mcp_ram_audit.ps1'
$ReaperScript = 'C:\Users\Prekzursil\.agents\scripts\reap_orphan_mcp.ps1'

foreach ($p in @($AuditScript, $ReaperScript)) {
    if (-not (Test-Path -LiteralPath $p)) {
        Write-Output "GATE:FAILED-TO-RUN dependency missing: $p"
        exit 1
    }
}

function Invoke-RamAudit {
    param([string]$Path)
    $raw = & $Path 2>&1 | Out-String
    if (-not $raw) { return $null }
    $free = $null
    $mcp  = $null
    if ($raw -match 'free RAM GB:\s*([0-9]+(?:[.,][0-9]+)?)') {
        $norm = $Matches[1] -replace ',', '.'
        $free = [double]::Parse($norm, [Globalization.CultureInfo]::InvariantCulture)
    }
    if ($raw -match 'MCP-class process count:\s*([0-9]+)') {
        $mcp = [int]$Matches[1]
    }
    if ($null -eq $free) { return $null }   # unparseable floor metric -> fail-closed
    if ($null -eq $mcp)  { $mcp = -1 }      # advisory metric missing -> RAM-only reap decision
    [pscustomobject]@{ FreeGB = $free; McpCount = $mcp }
}

# --- 1. pre measurement ---
$pre = Invoke-RamAudit -Path $AuditScript
if (-not $pre) {
    Write-Output "GATE:FAILED-TO-RUN mcp_ram_audit.ps1 output unparseable (no 'free RAM GB:' line)"
    exit 1
}
Write-Output ("PRE  : free={0:N2} GB  mcp-class={1}" -f $pre.FreeGB, $pre.McpCount)

# --- 2. reap when below floor / over the G-99 process threshold, then re-check ---
$final = $pre
$needReap = ($pre.FreeGB -lt $MinFreeGB) -or (($pre.McpCount -ge 0) -and ($pre.McpCount -gt $MaxMcpProcs))
if ($needReap) {
    Write-Output "REAP : threshold floor=$MinFreeGB GB / mcp-max=$MaxMcpProcs - running reap_orphan_mcp.ps1"
    $reapOut = & $ReaperScript 2>&1 | Out-String
    $reapLine = ($reapOut -split "`r?`n" | Where-Object { $_ -match '^RESULT:' } | Select-Object -First 1)
    if ($reapLine) { Write-Output ("REAP : " + $reapLine.Trim()) }
    else           { Write-Output "REAP : no RESULT line parsed from reaper output" }
    $post = Invoke-RamAudit -Path $AuditScript
    if ($post) {
        $final = $post
        Write-Output ("POST : free={0:N2} GB  mcp-class={1}" -f $final.FreeGB, $final.McpCount)
    }
    else {
        Write-Output "POST : audit unparseable after reap - deciding on PRE measurement (fail-closed)"
    }
}

# --- 3. decide ---
if ($final.FreeGB -ge $MinFreeGB) {
    Write-Output ("GATE:PASS free={0:N2} GB >= {1} GB  (mcp-class={2})" -f $final.FreeGB, $MinFreeGB, $final.McpCount)
    exit 0
}
if ($Override.IsPresent) {
    Write-Output ("GATE:OVERRIDE free={0:N2} GB < {1} GB - proceeding per OWNER DIRECTIVE recorded in GRILL-DECISIONS_workflow-delegation_2026-09-22.md (G-12). Log this run in the decision log." -f $final.FreeGB, $MinFreeGB)
    exit 0
}
Write-Output ("GATE:BLOCK free={0:N2} GB < {1} GB after reap attempt (mcp-class={2}). Do NOT launch the nested fleet. Free RAM first (reap again, close idle sessions), or obtain an owner -Override directive recorded in the decision log." -f $final.FreeGB, $MinFreeGB, $final.McpCount)
exit 2
