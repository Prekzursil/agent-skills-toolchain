# AUD-0018 planted live-to-repo control (models scripts/sync-from-live.ps1).
# Direction: live ~/.claude -> repo. Verbatim Copy-Item -Force. No named guards.
# MUST NOT be executed against a live tree; dry-run is interpreted only.
$Live = Join-Path $HOME '.claude'
Copy-Item -Path (Join-Path $Live 'rules\*') -Destination 'rules' -Force
