# verify-entry.ps1 -- quote-safe verification of the claude-code-mcp-guard registration.
# Two independent signals: jq (--arg binding, no embedded quotes) + PowerShell ConvertFrom-Json.

$ErrorActionPreference = 'Continue'
$s = 'C:\Users\Prekzursil\.claude\settings.json'
$m = 'mcp__claude-code-mcp__.*|mcp__McpHub__claude-code-mcp__.*'

jq -e -r --arg m $m '.hooks.PreToolUse[] | select(.matcher == $m) | .hooks[0].command' $s
"jq-arg-entry-exit: $LASTEXITCODE"

$j = Get-Content -Raw -LiteralPath $s | ConvertFrom-Json
"psjson-total-pretooluse: $(@($j.hooks.PreToolUse).Count)"
$hit = @($j.hooks.PreToolUse | Where-Object { $_.matcher -eq $m })
"psjson-matching-groups: $($hit.Count)"
"psjson-command: $($hit[0].hooks[0].command)"
"psjson-timeout: $($hit[0].hooks[0].timeout)"
"psjson-statusmessage: $($hit[0].hooks[0].statusMessage)"
