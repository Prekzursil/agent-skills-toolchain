---
title: BOTH-STATES-VERIFICATION_2026-09-22
type: note
permalink: dqverify-repo-20261013/hooks/claude-code-mcp-guard/both-states-verification-2026-09-22
---

# BOTH-STATES verification — claude-code-mcp-guard (G-3b/G-2c) — 2026-09-22

Unit: wf_c8e4c79c-1c8 both-states probe unit. Provenance: disk-verified (driver output
re-read from the run captured below; artifacts on disk at the paths listed).
Driver: `bothstates_probe.py` (same directory) — pipes payloads into the EXACT hook path
registered in settings.json via subprocess stdin, capturing exit/stdout/stderr verbatim.

## Verdict: SUCCESS:bothstates — 8/8 cases PASS (4 required states + 4 bonus chaos), 0 blockers

## State matrix (measured 2026-09-22, interpreter `python` -> C:\Python314\python.EXE)

| id | payload shape | tool | expected | exit | stdout | verdict |
|----|---------------|------|----------|------|--------|---------|
| a  | subagent-shaped (agent_id 3f2a9c1d8e4b7605 + agent_type workflow-subagent) | mcp__claude-code-mcp__claude_code | deny | 0 | deny JSON (below) | PASS |
| a2 | subagent-shaped | mcp__McpHub__claude-code-mcp__claude_code | deny | 0 | deny JSON (below) | PASS |
| b  | main-shaped (no agent_id/agent_type) | mcp__claude-code-mcp__claude_code | allow | 0 | empty | PASS |
| c  | subagent-shaped | Read (unrelated) | allow | 0 | empty | PASS |
| d  | garbage non-JSON (`{{{ not json ]]` + NUL byte) | n/a | fail open | 0 | empty | PASS |
| d2 | garbage empty stdin (0 bytes) | n/a | fail open | 0 | empty | PASS |
| d3 | garbage JSON array `[1,2,3]` (non-dict) | n/a | fail open | 0 | empty | PASS |
| d4 | garbage dict without tool_name | n/a | fail open | 0 | empty | PASS |

stderr length = 0 on every case. Deny stdout (states a/a2, identical, verbatim after
JSON key ordering; single trailing CRLF from Windows text-mode stdout — json.loads
parses it cleanly, harness trims hook stdout, benign):

```
{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "claude-code-mcp-guard: subagent context (agent_id present in hook payload) may not invoke nested claude-code-mcp tools. This MCP server is bypass-permissions-by-default and its upstream is archived (2026-05-15); nested delegation is governed by G-3b/G-2c. Main-loop access is unaffected. Decision log: ~/.agents/GRILL-DECISIONS_workflow-delegation_2026-09-22.md"}}
```

## settings.json validation (jq) — PASS

- `jq empty C:\Users\Prekzursil\.claude\settings.json` -> exit 0, stderr empty (full-file JSON valid).
- `jq -r '.hooks.PreToolUse[].matcher'` -> 14 matcher groups; guard group present exactly once.

## Matcher string confirmation — PASS (3 independent signals)

Signal 1 (Grep): `C:\Users\Prekzursil\.claude\settings.json:355` carries verbatim
`"matcher": "mcp__claude-code-mcp__.*|mcp__McpHub__claude-code-mcp__.*"`.

Signal 2 (jq, extraction above): guard matcher last of 14 groups, `group_count: 14`,
`guard_matcher_present: true`.

Signal 3 (Python stdlib json.load of settings.json): `parse: OK`,
`pretooluse_group_count: 14`, `guard_entry_count: 1`, entry shape:

```json
{"matcher": "mcp__claude-code-mcp__.*|mcp__McpHub__claude-code-mcp__.*",
 "hooks": [{"type": "command",
            "command": "python \"C:/Users/Prekzursil/.claude/hooks/claude-code-mcp-guard/guard.py\"",
            "timeout": 8,
            "statusMessage": "claude-code-mcp-guard: deny nested claude-code-mcp from subagents (G-3b)"}]}
```

The registered command path is byte-identical to the file this probe executed.

## Honest caveats

1. UNVERIFIED-live (in-harness firing): payloads are synthetic, matching the
   probe-captured keysets (agent_id/agent_type present only in subagent context; root
   session_id/transcript_path in both). A live subagent invoking the MCP tool through
   the real harness was NOT run — it would require the global MCP registry (forbidden
   freeze pattern under ~1.9GB free). Settling experiment: one --strict-mcp-config
   spawn when RAM floor passes, with hooklog as second signal.
2. G-3a flat deny is STILL active (settings.json:89-90 permissions.deny
   `mcp__claude-code-mcp__*` / `mcp__McpHub__claude-code-mcp__*`; :105
   deniedMcpServers claude-code-mcp), so main-loop access is currently masked at the
   permission layer; this hook is the independent G-3b layer that governs once G-3a
   is lifted. Permission rules untouched (NEVER-rule).
3. Deny stdout ends CRLF (Windows text-mode). Parsed fine by json.loads; noted only
   as an observation, not a defect.
4. `python` resolves via PATH to C:\Python314\python.EXE in this probe — the same
   `python` token the registered command uses (high confidence; harness PATH could
   theoretically differ).

COVERAGE: all sections measured; no UNKNOWNs remain. If any section above were still
UNKNOWN the unit died and nothing here could be cited — it did not.

Artifacts (disk-verified):
- Live-receipt: this file (workflow scratch) + `bothstates_probe.py` driver, both at
  C:\Users\Prekzursil\.claude\projects\C--Users-Prekzursil\682da5f0-62c5-4c76-826b-fdf5508e20a9\subagents\workflows\wf_c8e4c79c-1c8\
- Repo-canon mirror: C:\Users\Prekzursil\source\agent-skills-toolchain\hooks\claude-code-mcp-guard\BOTH-STATES-VERIFICATION_2026-09-22.md
  (untracked; orchestrator commits per NEVER-rule)