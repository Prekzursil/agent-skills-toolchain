<#
  vm-backup.ps1  -- dated, repeatable VM->home harness backup over the rclone Tailscale link.
  Copies the divergent Claude/harness surface from OFFLOAD-W2025 to home
  (desktop-a60s9gp) at  homeC:/Users/Prekzursil/Downloads/BACKUPS VM/vm-backup-<date>/.
  Reinstallable bulk is excluded; secrets are quarantined under SECRETS/.
  No large local archive is built (VM has ~5.6 GB free) -- rclone streams file-by-file, resumable.

  Usage:
    pwsh -File vm-backup.ps1 -Date 2026-09-25 -DryRun    # size/precheck only, transfers nothing
    pwsh -File vm-backup.ps1 -Date 2026-09-25            # real run
#>
param(
  [string]$Date = (Get-Date -Format 'yyyy-MM-dd'),
  [switch]$DryRun,
  [string]$Rclone = 'C:\Users\prekzursil\.local\bin\rclone.exe',
  [string]$DestBase = 'homeC:/Users/Prekzursil/Downloads/BACKUPS VM'
)
$ErrorActionPreference = 'Continue'
$scratch = 'C:\Users\PREKZU~1\AppData\Local\Temp\2\claude\C--Users-prekzursil\027fa5cb-1562-482e-a2e1-6a2f57530cb6\scratchpad'
$dest = "$DestBase/vm-backup-$Date"
$P    = 'C:\suite\payload\Users\Prekzursil'      # real junction/symlink target root
$U    = 'C:\Users\prekzursil'                    # live user profile
$rcCommon = @('--transfers','6','--checkers','12','--sftp-set-modtime=false','--stats','20s','--stats-one-line','--retries','3','--low-level-retries','10')

# ---- global exclude filter (reinstallable / regenerable / secret-routed-elsewhere) ----
$filter = @'
- .git/**
- **/node_modules/**
- **/.venv/**
- **/.venvs/**
- **/venv/**
- **/site-packages/**
- **/__pycache__/**
- **/.pytest_cache/**
- **/.ruff_cache/**
- **/.mypy_cache/**
- **/*.pyc
- **/dist/**
- **/build/**
- **/.hf/**
- **/.models/**
- **/deploy-backups/**
- **/Cache/**
- **/Code Cache/**
- **/GPUCache/**
- **/DawnGraphiteCache/**
- **/DawnWebGPUCache/**
- **/GrShaderCache/**
- **/ShaderCache/**
- **/GPUCache/**
- plugins/**
- cache/**
- tmp/**
- desat-*.tar.gz
- refusal-scrub-*.tar.gz
- fp-recovery-backup-*/*-shards/**
- logs/cursor-afterfileedit.jsonl
- secrets/**
- secure-evidence/**
- zai-key-state.json
- apps/**
'@
$filterFile = Join-Path $scratch 'backup-filter.txt'
Set-Content -LiteralPath $filterFile -Value $filter -Encoding ascii

# ---- MAIN (non-secret) sources: @{Src; Dst} ----
$MAIN = @(
  @{ Src="$U\.claude";                              Dst='claude' }
  @{ Src="$P\.agents";                              Dst='agents' }
  @{ Src="D:\basic-memory";                         Dst='basic-memory/vault'; Inc='*.md' }
  @{ Src="$U\.basic-memory";                        Dst='basic-memory/control' }
  @{ Src="$P\source\agent-skills-toolchain";        Dst='source-toolchain' }
  @{ Src="$U\.cursor";                              Dst='external-configs/cursor' }
  @{ Src="$U\.tooluniverse";                        Dst='external-configs/tooluniverse' }
  @{ Src="$U\.remember";                            Dst='external-configs/remember' }
  @{ Src="$U\.grokbot";                             Dst='external-configs/grokbot' }   # note: contains a credential -> also flagged
)

# ---- SECRET sources -> SECRETS/ ----
$SECRETS = @(
  @{ Src="$U\.claude\.credentials.json";            Dst='SECRETS/claude-credentials.json'; File=$true }
  @{ Src="$P\.claude.json";                         Dst='SECRETS/claude.json';             File=$true }
  @{ Src="$P\.agents\secrets";                      Dst='SECRETS/agents-secrets' }
  @{ Src="$P\.agents\secure-evidence";              Dst='SECRETS/agents-secure-evidence' }
  @{ Src="$P\.agents\zai-key-state.json";           Dst='SECRETS/zai-key-state.json';      File=$true }
  @{ Src="$U\.ssh";                                 Dst='SECRETS/ssh' }
  @{ Src="$P\.codex";                               Dst='SECRETS/codex' }
  @{ Src="$U\.gemini";                              Dst='SECRETS/gemini' }
  @{ Src="$U\.cline\data";                          Dst='SECRETS/cline-data' }
  @{ Src="$P\source\agent-skills-toolchain\mitm_mcp_traffic.db"; Dst='SECRETS/mitm_mcp_traffic.db'; File=$true }
)

# ---- plugin reinstall manifest (tiny) ----
$PLUGMAN = @(
  @{ Src="$U\.claude\plugins\installed_plugins.json";  Dst='plugins-manifest/installed_plugins.json'; File=$true }
  @{ Src="$U\.claude\plugins\known_marketplaces.json"; Dst='plugins-manifest/known_marketplaces.json'; File=$true }
)

function Do-Copy($src,$dstsub,$isFile,$inc){
  if(-not (Test-Path -LiteralPath $src)){ Write-Host "SKIP(absent): $src"; return }
  $target = "$dest/$dstsub"
  $sel = if($inc){ @('--include',$inc) } else { @('--filter-from',$filterFile) }
  if($DryRun){
    Write-Host "--- SIZE $src $(if($inc){"(include $inc)"})---"
    if($isFile){ '{0} bytes (single file)' -f (Get-Item -LiteralPath $src).Length | Write-Host }
    else { & $Rclone size $src @sel 2>&1 | Where-Object { $_ -notmatch 'NOTICE|host key' } | Write-Host }
    return
  }
  Write-Host ">>> COPY $src -> $target"
  if($isFile){
    & $Rclone copyto $src $target @rcCommon 2>&1 | Where-Object { $_ -notmatch 'NOTICE: .*host key' }
  } else {
    & $Rclone copy $src $target @sel @rcCommon 2>&1 | Where-Object { $_ -notmatch 'NOTICE: .*host key' }
  }
  if($LASTEXITCODE -eq 0){ Write-Host "SUCCESS:copy $dstsub" } else { Write-Host "FAILED:copy $dstsub exit=$LASTEXITCODE" }
}

Write-Host "==== VM->HOME BACKUP  date=$Date  dryrun=$DryRun ===="
Write-Host "dest = $dest"
if(-not $DryRun){ & $Rclone mkdir $dest 2>&1 | Where-Object { $_ -notmatch 'NOTICE' } }

Write-Host "`n#### MAIN SURFACES ####"
foreach($s in $MAIN){ Do-Copy $s.Src $s.Dst $false $s.Inc }

Write-Host "`n#### PLUGIN MANIFEST ####"
foreach($s in $PLUGMAN){ Do-Copy $s.Src $s.Dst $true }

Write-Host "`n#### SECRETS (quarantined) ####"
foreach($s in $SECRETS){ Do-Copy $s.Src $s.Dst ([bool]$s.File) }

Write-Host "`n==== DONE date=$Date dryrun=$DryRun ===="
