$env:CC_ACTIVE_PROFILE = 'claude'
$env:RECALL_GATE = 'off'
$cleanAgents = "$env:USERPROFILE/.claude/profiles/AGENTS.claude-clean.md"   # cc-cc: clean (no-cyber) AGENTS doctrine   # cc-cc: silence the local-tree recall-gate hook (estate prior-art)
foreach ($v in 'ANTHROPIC_BASE_URL','ANTHROPIC_AUTH_TOKEN','ANTHROPIC_API_KEY','ANTHROPIC_DEFAULT_HAIKU_MODEL','ANTHROPIC_DEFAULT_SONNET_MODEL','ANTHROPIC_DEFAULT_OPUS_MODEL') {
  Remove-Item "Env:$v" -ErrorAction SilentlyContinue
}
$s = "$env:USERPROFILE/.claude/profiles/state/cc-active-profile"
$cur = if (Test-Path $s) { (Get-Content $s -Raw).Trim().ToLower() } else { 'glm' }
$clean = "$env:USERPROFILE/.claude/profiles/clean-mcp.json"
$payload = "$env:USERPROFILE/.claude/profiles/claude-session.json"
$extra = @()
if (Test-Path $cleanAgents) { $extra += @('--append-system-prompt-file', $cleanAgents) }
if ($cur -ne 'claude' -and (Test-Path $payload)) { & claude --strict-mcp-config --mcp-config $clean --settings $payload @extra @args }
else { & claude --strict-mcp-config --mcp-config $clean @extra @args }
