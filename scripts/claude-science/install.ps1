# install -- one-shot setup for the Claude Science local tooling. No admin needed.
# Unifies what used to be scattered/incomplete (audit 2026-07-07): installs ALL scripts (not a
# subset -- cs-maintain/cs-backup/cs-restore/cs-supervisor were silently skipped before), seeds the
# WSL ~/.profile PATH (recovery/maintenance were command-not-found no-ops without it), wires the
# in-WSL [boot] supervisor, applies the browser tab-death regfix, drops a one-click shortcut,
# registers the watchdog+maintenance tasks, and prints a first-run health check.
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
# cs.conf (via cs-lib.ps1) is the single source for the distro name; it used to be a literal here.
. (Join-Path $here 'cs-lib.ps1')
$distro = $script:CSDistro

# --- 1. Windows scripts -> ~\.local\bin (kept together so $PSScriptRoot cross-refs resolve) ---
# cs.conf MUST travel with them: cs-lib.ps1 resolves it via $PSScriptRoot, so a deploy that omitted
# it would silently fall back to the in-script defaults and the config seam would be a no-op.
# test-cs-backup-readonly.py is here for the same reason its .ps1 sibling is: SKILL.md documents
# `python ~/.local/bin/test-cs-backup-readonly.py` as the falsification recipe for the read-only
# claim, and until 2026-08-12 this list did not contain it -- the file existed on this box only
# because it had been hand-copied, so a fresh install left the documented probe pointing at
# nothing. cs_wiring_check.py's W4 now compares this list against every ~/.local/bin path the
# docs name, so the two cannot drift apart again silently.
$winDir = Join-Path $env:USERPROFILE '.local\bin'
New-Item -ItemType Directory -Force -Path $winDir | Out-Null
foreach ($f in 'cs.ps1', 'cs.cmd', 'cs-lib.ps1', 'cs.conf', 'cs-doctor.ps1', 'cs-watchdog.ps1', 'cs-recover.ps1', 'cs-recover.cmd', 'cs-start.ps1', 'cs-start.cmd', 'register-tasks.ps1', 'test-cs-doctor-failclosed.ps1', 'test-cs-backup-readonly.py') {
  $src = Join-Path $here $f
  if (Test-Path $src) { Copy-Item $src (Join-Path $winDir $f) -Force; Write-Information -InformationAction Continue "[win] $f" }
}

# --- 2. WSL scripts -> ~/.local/bin (ALL of them; CR-stripped, extension-less, +x) ---
foreach ($f in 'cs-start.sh', 'cs-recover.sh', 'cs-restore.sh', 'cs-backup.sh', 'cs-maintain.sh', 'cs-supervisor.sh', 'cs-install.sh', 'cs-serve-prep.sh', 'cs-finish.sh') {
  $src = Join-Path $here $f
  if (Test-Path $src) {
    $name = [IO.Path]::GetFileNameWithoutExtension($f)
    $wslSrc = ($src -replace '\\', '/') -replace '^C:', '/mnt/c'
    wsl.exe -d $distro -- bash -lc "mkdir -p ~/.local/bin && tr -d '\r' < '$wslSrc' > ~/.local/bin/$name && chmod +x ~/.local/bin/$name && echo '[wsl] $name'"
  }
}

# --- 2b. WSL config seam -> ~/.local/bin, NAME PRESERVED (no extension strip, not executable) ---
# The loop above deliberately strips extensions so `cs-backup.sh` becomes the command `cs-backup`.
# These two are sourced BY NAME (`. "$(dirname "${BASH_SOURCE[0]}")/cs-lib.sh"`), so stripping
# would break every shell script that reads the config. Separate loop, extension kept.
foreach ($f in 'cs-lib.sh', 'cs.conf') {
  $src = Join-Path $here $f
  if (Test-Path $src) {
    $wslSrc = ($src -replace '\\', '/') -replace '^C:', '/mnt/c'
    wsl.exe -d $distro -- bash -lc "mkdir -p ~/.local/bin && tr -d '\r' < '$wslSrc' > ~/.local/bin/$f && echo '[wsl] $f'"
  }
}

# --- 3. Seed WSL ~/.profile PATH (idempotent) so cs-recover/cs-maintain aren't command-not-found ---
wsl.exe -d $distro -- bash -lc 'grep -q ".local/bin" ~/.profile 2>/dev/null || echo "export PATH=\$HOME/.local/bin:\$PATH" >> ~/.profile; echo "[wsl] ~/.profile PATH ok"'

# --- 4. Wire the in-WSL [boot] supervisor (self-heal on every VM start; no systemd) ---
# /etc/wsl.conf needs root; `wsl -u root` runs as root without a password. We build the new file
# in PowerShell and write it via base64 to avoid nested PowerShell->wsl->bash quoting (the su/sed
# form breaks: single quotes + $ in the [boot] command). Idempotent (skips if already wired).
$me = ("$(wsl.exe -d $distro -- bash -lc 'echo $USER')").Trim()
$already = ("$(wsl.exe -d $distro -u root -- bash -c 'grep -c cs-supervisor /etc/wsl.conf 2>/dev/null || echo 0')").Trim()
if ($already -ne '0') {
  Write-Information -InformationAction Continue '[wsl] [boot] supervisor already wired'
} else {
  $existing = ("$(wsl.exe -d $distro -u root -- bash -c 'cat /etc/wsl.conf 2>/dev/null')").TrimEnd()
  $boot = "`n`n[boot]`ncommand = su - $me -c 'setsid nohup /home/$me/.local/bin/cs-supervisor >> /home/$me/.claude-science/supervisor.log 2>&1 &'"
  $b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes(($existing + $boot + "`n")))
  try { wsl.exe -d $distro -u root -- bash -c "echo $b64 | base64 -d > /etc/wsl.conf" | Out-Null; Write-Information -InformationAction Continue '[wsl] wired [boot] cs-supervisor (takes effect after: wsl --shutdown)' }
  catch { Write-Information -InformationAction Continue "[warn] could not edit /etc/wsl.conf as root: $($_.Exception.Message). Add the [boot] line manually." }
}

# --- 5. Browser tab-death regfix (HKCU policy, no admin): exempt Claude sites from tab discard ---
$sites = @('claude.ai', '[*.]claude.ai', 'localhost', '127.0.0.1')
function Set-TabExempt {
  [CmdletBinding(SupportsShouldProcess)]
  param([string]$base)
  if (-not $PSCmdlet.ShouldProcess($base, 'apply tab-discard exemption policy')) { return }
  New-Item -Path $base -Force | Out-Null
  $i = 1; foreach ($s in $sites) { New-ItemProperty -Path $base -Name "$i" -Value $s -PropertyType String -Force | Out-Null; $i++ }
}
try {
  Set-TabExempt 'HKCU:\SOFTWARE\Policies\Google\Chrome\TabDiscardingExceptions'
  Set-TabExempt 'HKCU:\SOFTWARE\Policies\Microsoft\Edge\SleepingTabsBlockedForUrls'
  Write-Information -InformationAction Continue '[reg] tab-death exceptions applied (Chrome + Edge)'
} catch { Write-Information -InformationAction Continue "[warn] regfix skipped: $($_.Exception.Message)" }

# --- 6. One-click shortcut (Desktop + Start Menu) -> flash-free `cs open` via conhost --headless.
# NOT wscript+.vbs: VBScript is deprecated and REMOVED on Win11 24H2+/Canary (build 28xxx has no
# ".vbs" script engine), so the old launcher silently no-ops there ("no script engine for .vbs").
# conhost --headless is the VBScript-free flash-free replacement (Win10 1809+/Win11): it runs the
# hidden daemon-ensure with no console window while the browser opens visibly.
$conhost = Join-Path $env:SystemRoot 'System32\conhost.exe'
$lnkArgs = "--headless powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$winDir\cs.ps1`" open"
$ws = New-Object -ComObject WScript.Shell
foreach ($dir in @([Environment]::GetFolderPath('Desktop'), (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'))) {
  $lnk = $ws.CreateShortcut((Join-Path $dir 'Claude Science.lnk'))
  $lnk.TargetPath = $conhost; $lnk.Arguments = $lnkArgs; $lnk.WorkingDirectory = $winDir
  $lnk.IconLocation = 'shell32.dll,13'
  $lnk.Description = 'Open Claude Science (ensures the daemon is up first)'; $lnk.Save()
}
# retire any dead VBScript launcher left by a prior install
$oldVbs = Join-Path $winDir 'cs-open.vbs'
if (Test-Path $oldVbs) { Remove-Item $oldVbs -Force -ErrorAction SilentlyContinue }
Write-Information -InformationAction Continue '[ok] "Claude Science" shortcut on Desktop + Start Menu (flash-free via conhost --headless -> cs open)'

# --- 7. Register the always-on tasks (watchdog + weekly maintenance) ---
# -WatchdogPath is EXPLICIT and points at the DEPLOYED copy, not at $here. Without it, running this
# installer from a checkout registered the always-on supervisor against that checkout: measured
# 2026-08-12, the live task launched cs-watchdog.ps1 out of a linked git worktree that a
# `git worktree remove` would have deleted, while the identical file in $winDir went unused.
& (Join-Path $here 'register-tasks.ps1') -WatchdogPath (Join-Path $winDir 'cs-watchdog.ps1')

# --- 8. First-run health check ---
Write-Information -InformationAction Continue "`nDone. Ensure $winDir is on your Windows user PATH (so 'cs' works everywhere)."
Write-Information -InformationAction Continue "Apply the [boot] supervisor now with:  wsl --shutdown   (next start self-heals)."
Write-Information -InformationAction Continue "`n--- first-run health check (cs doctor) ---"
try { & (Join-Path $winDir 'cs.ps1') doctor } catch { Write-Information -InformationAction Continue "run 'cs doctor' after a fresh shell." }
