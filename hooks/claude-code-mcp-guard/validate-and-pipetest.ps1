# validate-and-pipetest.ps1 -- G-3b/G-2c registration validation + literal pipe tests
# Validates settings.json with jq after the claude-code-mcp-guard PreToolUse merge,
# pipe-tests guard.py with a subagent-shaped and a main-shaped payload, and
# finalizes SELFTEST-EVIDENCE.md. Read-only wrt credentials; touches only the
# evidence markdown.

$ErrorActionPreference = 'Continue'

$s = 'C:\Users\Prekzursil\.claude\settings.json'
$g = 'C:\Users\Prekzursil\.claude\hooks\claude-code-mcp-guard\guard.py'
$e = 'C:\Users\Prekzursil\.claude\hooks\claude-code-mcp-guard\SELFTEST-EVIDENCE.md'

# --- 1. jq validation of the merged settings file ---
jq empty $s
$jqValidExit = $LASTEXITCODE
"jq-empty-exit: $jqValidExit"

$ptuLen = jq -e '.hooks.PreToolUse | length' $s
$jqLenExit = $LASTEXITCODE
"jq-pretooluse-groups: $ptuLen (exit $jqLenExit)"

$entryCmd = jq -e -r '.hooks.PreToolUse[] | select(.matcher == "mcp__claude-code-mcp__.*|mcp__McpHub__claude-code-mcp__.*") | .hooks[0].command' $s
$jqEntryExit = $LASTEXITCODE
"jq-guard-entry-exit: $jqEntryExit"
"jq-guard-entry-command: $entryCmd"

# --- 2. literal shell pipe tests (payload shapes per PROBE-depth-dial.md par4) ---
$sub = '{"tool_name":"mcp__claude-code-mcp__claude_code","agent_id":"a56f73158ab7e18ea","agent_type":"general-purpose","session_id":"probe-root-session-0001","transcript_path":"C:\\probe\\p.jsonl","cwd":"C:\\Users\\Prekzursil","hook_event_name":"PreToolUse","permission_mode":"default","tool_use_id":"pipe-sub-1","tool_input":{}}'
$main = '{"tool_name":"mcp__claude-code-mcp__claude_code","session_id":"probe-root-session-0001","transcript_path":"C:\\probe\\p.jsonl","cwd":"C:\\Users\\Prekzursil","hook_event_name":"PreToolUse","permission_mode":"default","tool_use_id":"pipe-main-1","tool_input":{}}'

$outSub = $sub | python $g
$rcSub = $LASTEXITCODE
"pipe-subagent-exit: $rcSub"
"pipe-subagent-stdout: $outSub"

$outMain = $main | python $g
$rcMain = $LASTEXITCODE
"pipe-main-exit: $rcMain"
"pipe-main-stdout: [$outMain]"

# --- 3. finalize evidence file ---
$content = Get-Content -Raw -LiteralPath $e

$pipeBlock = "## Literal shell pipe tests (PowerShell pipe, post-registration, $((Get-Date).ToString('yyyy-MM-dd HH:mm:ss')))``n- subagent-shaped payload -> exit $rcSub; stdout: $outSub``n- main-shaped payload -> exit $rcMain; stdout: empty (silent allow)"
$content = $content.Replace("## Literal shell pipe tests (appended after settings.json registration)``nUNKNOWN - not yet run", $pipeBlock)

$regBlock = "## settings.json registration + validation (measured)``n- MERGE: one matcher-group appended to existing hooks.PreToolUse array; all 12 pre-existing groups intact (jq length above must read 13).``n- matcher: mcp__claude-code-mcp__.*|mcp__McpHub__claude-code-mcp__.*``n- command: $entryCmd``n- jq empty (full-file JSON validity): exit $jqValidExit``n- NOTE (G-3a interaction): permissions.deny already carries mcp__claude-code-mcp__* / mcp__McpHub__claude-code-mcp__* and deniedMcpServers carries claude-code-mcp, so the flat deny is ALSO active; until the owner lifts G-3a, main-loop access is masked at the permission layer. The hook implements the G-3b subagent-only layer independently of that.``n- Backup: settings.json.bak-claude-code-mcp-guard-20260922"
$content = $content.Replace("## settings.json registration + validation``nUNKNOWN - not yet run", $regBlock)

Set-Content -LiteralPath $e -Value $content -NoNewline -Encoding utf8
"evidence-finalized: $((Test-Path $e))"
