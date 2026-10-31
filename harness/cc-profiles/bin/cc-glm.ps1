$env:CC_ACTIVE_PROFILE = 'glm'
$tok = [Environment]::GetEnvironmentVariable('ZAI_API_KEY','User')
if (-not $tok) { Write-Error 'ZAI_API_KEY missing at User scope (failover mesh owns it) - cannot launch GLM'; exit 1 }
$env:ANTHROPIC_BASE_URL = 'https://api.z.ai/api/anthropic'
$env:ANTHROPIC_AUTH_TOKEN = $tok
$s = "$env:USERPROFILE/.claude/profiles/state/cc-active-profile"
$cur = if (Test-Path $s) { (Get-Content $s -Raw).Trim().ToLower() } else { 'glm' }
$payload = "$env:USERPROFILE/.claude/profiles/glm-session.json"
if ($cur -ne 'glm' -and (Test-Path $payload)) { & claude --settings $payload @args }
else { & claude @args }
