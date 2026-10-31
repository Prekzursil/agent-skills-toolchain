# SELFTEST EVIDENCE -- claude-code-mcp-guard (G-3b/G-2c)

- Date: 2026-09-22T20:27:59
- guard.py sha256: `832d113dff059e9f1b2fe999d382d54e279f0cdd5cea7baaa8da80f90b6c18d6`
- python: 3.14.6 | runner: selftest.py (subprocess stdin pipe per case)
- Signal contract: subagent context == `agent_id` non-empty string in hook stdin (PROBE-depth-dial.md par4, measured 2.1.277, both states).
- DENY = exit 0 + JSON `hookSpecificOutput.permissionDecision:"deny"`; ALLOW = exit 0 + empty stdout.

| id | case | expected | measured | exit | pass |
|----|------|----------|----------|------|------|
| T01 | subagent x mcp__claude-code-mcp__ tool -> DENY | DENY | DENY | 0 | PASS |
| T02 | main (no agent_id) x mcp__claude-code-mcp__ tool -> silent allow | ALLOW | ALLOW | 0 | PASS |
| T03 | subagent x mcp__McpHub__claude-code-mcp__ tool -> DENY | DENY | DENY | 0 | PASS |
| T04 | main x mcp__McpHub__claude-code-mcp__ tool -> silent allow | ALLOW | ALLOW | 0 | PASS |
| T05 | subagent x unrelated MCP tool (mcp__github__) -> silent allow | ALLOW | ALLOW | 0 | PASS |
| T06 | garbage stdin 'not-json{{{' -> fail open | ALLOW | ALLOW | 0 | PASS |
| T07 | empty stdin -> fail open | ALLOW | ALLOW | 0 | PASS |
| T08 | empty JSON object '{}' -> fail open | ALLOW | ALLOW | 0 | PASS |
| T09 | missing tool_name (subagent context) -> fail open | ALLOW | ALLOW | 0 | PASS |
| T10 | tool_name null -> fail open | ALLOW | ALLOW | 0 | PASS |
| T11 | JSON array payload (non-dict) -> fail open | ALLOW | ALLOW | 0 | PASS |
| T12 | agent_id empty string x guarded tool -> treated as no signal, silent allow | ALLOW | ALLOW | 0 | PASS |
| T13 | near-miss server 'mcp__claude-code-mcp2__' (strict prefix) -> silent allow | ALLOW | ALLOW | 0 | PASS |

## Deny-path output (T01 subprocess stdout, truncated to 160 chars by runner; FULL deny JSON in the pipe-test section below)
```
{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "claude-code-mcp-guard: subagent context (agent
```

## Literal shell pipe tests (PowerShell pipe -> python guard.py, post-registration, 2026-09-22)
- subagent-shaped payload (agent_id `a56f73158ab7e18ea` + agent_type `general-purpose`, keyset per PROBE-depth-dial.md par4) -> exit 0, stdout:
  `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "claude-code-mcp-guard: subagent context (agent_id present in hook payload) may not invoke nested claude-code-mcp tools. This MCP server is bypass-permissions-by-default and its upstream is archived (2026-05-15); nested delegation is governed by G-3b/G-2c. Main-loop access is unaffected. Decision log: ~/.agents/GRILL-DECISIONS_workflow-delegation_2026-09-22.md"}}`
- main-shaped payload (same keyset minus agent_id/agent_type) -> exit 0, stdout empty (silent allow).

## settings.json registration + validation (measured, 2 independent signals)
- MERGE: one matcher-group APPENDED to the existing hooks.PreToolUse array; nothing removed.
  Measured totals: 14 groups after merge (13 pre-existing + 1 new), confirmed by BOTH
  jq (`'.hooks.PreToolUse | length'` -> 14, exit 0) and PowerShell ConvertFrom-Json (14; matching groups: 1).
- matcher: `mcp__claude-code-mcp__.*|mcp__McpHub__claude-code-mcp__.*`
- command (read back via jq --arg select AND ConvertFrom-Json): `python "C:/Users/Prekzursil/.claude/hooks/claude-code-mcp-guard/guard.py"` | timeout 8
- jq empty (full-file JSON validity): exit 0.
- Recorded detector failure: a plain jq select with embedded double quotes failed under Windows
  PowerShell 5.1 native-argument quote-stripping (exit 3, compile error) -- instrument bug, not absence;
  re-probed quote-safe with `--arg` binding and cross-checked with ConvertFrom-Json.
- NOTE (G-3a interaction): `permissions.deny` already carries `mcp__claude-code-mcp__*` /
  `mcp__McpHub__claude-code-mcp__*` and `deniedMcpServers` carries `claude-code-mcp` (flat deny
  G-3a, landed earlier). Until the owner lifts G-3a, main-loop calls are ALSO denied at the
  permission layer; the hook implements the G-3b subagent-only layer independently and takes over
  if/when G-3a is relaxed. Per the task NEVER-rule, permission rules were not touched.
- Backup: `C:\Users\Prekzursil\.claude\settings.json.bak-claude-code-mcp-guard-20260922`

## Verdict
ALL 13 CASES PASS (discrimination + chaos fail-open) AND both literal pipe tests behave as
specified (subagent -> deny JSON; main -> silent allow) AND the settings.json registration
verifies under two independent probes. Repo mirror: agent-skills-toolchain/hooks/claude-code-mcp-guard/
(see reconcile note in task output).
