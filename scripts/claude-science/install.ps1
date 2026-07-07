# install -- one-shot setup for the Claude Science local tooling. No admin needed.
# Unifies what used to be scattered/incomplete (audit 2026-07-07): installs ALL scripts (not a
# subset -- cs-maintain/cs-backup/cs-restore/cs-supervisor were silently skipped before), seeds the
# WSL ~/.profile PATH (recovery/maintenance were command-not-found no-ops without it), wires the
# in-WSL [boot] supervisor, applies the browser tab-death regfix, drops a one-click shortcut,
# registers the watchdog+maintenance tasks, and prints a first-run health check.
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$distro = 'Ubuntu'

# --- 1. Windows scripts -> ~\.local\bin (kept together so $PSScriptRoot cross-refs resolve) ---
$winDir = Join-Path $env:USERPROFILE '.local\bin'
New-Item -ItemType Directory -Force -Path $winDir | Out-Null
foreach ($f in 'cs.ps1', 'cs.cmd', 'cs-lib.ps1', 'cs-doctor.ps1', 'cs-watchdog.ps1', 'cs-recover.ps1', 'cs-recover.cmd', 'cs-start.ps1', 'cs-start.cmd') {
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

# --- 6. One-click shortcut (Desktop + Start Menu) -> flash-free `cs open` via a tiny VBS ---
$vbs = Join-Path $winDir 'cs-open.vbs'
@"
Set s = CreateObject("WScript.Shell")
s.Run "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File ""$winDir\cs.ps1"" open", 0, False
"@ | Set-Content -Encoding ascii $vbs
$ws = New-Object -ComObject WScript.Shell
foreach ($dir in @([Environment]::GetFolderPath('Desktop'), (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'))) {
  $lnk = $ws.CreateShortcut((Join-Path $dir 'Claude Science.lnk'))
  $lnk.TargetPath = 'wscript.exe'; $lnk.Arguments = "`"$vbs`""; $lnk.IconLocation = 'shell32.dll,13'
  $lnk.Description = 'Open Claude Science (ensures the daemon is up first)'; $lnk.Save()
}
Write-Information -InformationAction Continue '[ok] "Claude Science" shortcut on Desktop + Start Menu (flash-free -> cs open)'

# --- 7. Register the always-on tasks (watchdog + weekly maintenance) ---
& (Join-Path $here 'register-tasks.ps1')

# --- 8. First-run health check ---
Write-Information -InformationAction Continue "`nDone. Ensure $winDir is on your Windows user PATH (so 'cs' works everywhere)."
Write-Information -InformationAction Continue "Apply the [boot] supervisor now with:  wsl --shutdown   (next start self-heals)."
Write-Information -InformationAction Continue "`n--- first-run health check (cs doctor) ---"
try { & (Join-Path $winDir 'cs.ps1') doctor } catch { Write-Information -InformationAction Continue "run 'cs doctor' after a fresh shell." }
