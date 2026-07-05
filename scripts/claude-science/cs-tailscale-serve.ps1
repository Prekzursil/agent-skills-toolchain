# cs-tailscale-serve — expose Claude Science over HTTPS to YOUR tailnet (phone/other laptop).
# Prereq: run 'tailscale up' ONCE first (that's your account login — this script can't do it).
# Keeps the daemon on 127.0.0.1 and puts Tailscale Serve (WireGuard-private, auto-HTTPS) in front.
# Persists the --allow-origin to ~/.cs-serve-extra so it survives watchdog auto-recoveries.
$ErrorActionPreference = 'Stop'
$tsExe = (Get-Command tailscale -EA SilentlyContinue).Source
if (-not $tsExe) { $tsExe = 'C:\Program Files\Tailscale\tailscale.exe' }
if (-not (Test-Path $tsExe)) { throw "Tailscale not installed. Install it, then run 'tailscale up' before this." }

$status = & $tsExe status --json | ConvertFrom-Json
if (-not $status.Self.DNSName) { throw "Not logged in to a tailnet. Run 'tailscale up' first (your account login)." }
$dns = $status.Self.DNSName.TrimEnd('.')          # e.g. laptop.tailXXXX.ts.net
Write-Host "tailnet host: $dns"

# 1) Serve the daemon over HTTPS on the tailnet (background)
& $tsExe serve --bg --https=443 http://localhost:8000
Write-Host "[ok] tailscale serve -> https://$dns  (tailnet-only; NOT public)"

# 2) Persist the allowed Origin so every (re)start of the daemon accepts tailnet WebSocket upgrades
$origin = "--allow-origin https://$dns"
wsl -d Ubuntu -e sh -lc "printf '%s' '$origin' > `$HOME/.cs-serve-extra"
Write-Host "[ok] persisted origin -> ~/.cs-serve-extra"

# 3) Restart the daemon so it picks up --allow-origin (via cs-recover, which honors the origin file)
wsl -d Ubuntu -e sh -lc 'cs-recover' 2>$null | Out-Null
Write-Host "[ok] daemon restarted with tailnet origin"
Write-Host ""
Write-Host "Reach Claude Science from any device on your tailnet:  https://$dns"
Write-Host "On your phone: open that URL (real HTTPS) -> browser menu -> Install app (PWA)."
Write-Host "To stop exposing:  tailscale serve --https=443 off   (and: rm ~/.cs-serve-extra)"
