#!/usr/bin/env python3
"""
claude-code-mcp-guard -- G-3b/G-2c subagent-scoped PreToolUse deny hook (2026-09-22).

Policy owner: ~/.agents/GRILL-DECISIONS_workflow-delegation_2026-09-22.md
  G-3 = a+b: flat deny NOW, hook-gated subagent-only deny (main keeps access).
  G-10 = b: claude-code-mcp fork+container is the sanctioned lane for exotics.
Rationale: emergent nested-Claude delegation via claude-code-mcp (upstream archived
2026-05-15, bypass-permissions-by-default) caused incident wf_c8e4c79c-1c8
(2/20 agents, 12 nested claude_code calls, prompt-only guards).

Subagent-context discriminator (PROBE-depth-dial.md par4, measured on Claude Code
2.1.277, both states, hooklog + agent metas as independent signals):
  Hook stdin JSON carries `agent_id` (16-hex) and `agent_type` ONLY in subagent
  contexts. `session_id` and `transcript_path` are ALWAYS the root session's and
  MUST NOT be used for discrimination. No spawnDepth / env marker exists in the
  payload.

Behavior:
  - tool_name starts with a guarded prefix AND subagent signal present
      -> emit PreToolUse permissionDecision "deny" with reason (exit 0).
  - main-loop calls to guarded tools, and all non-matching tools
      -> allow silently (exit 0, no output).
  - ANY parse error, non-dict payload, missing/unusable tool_name, or missing
    subagent signal -> FAIL-OPEN (exit 0, no output). Never blocks on ambiguity.
"""

import json
import sys

GUARDED_PREFIXES = (
    "mcp__claude-code-mcp__",
    "mcp__McpHub__claude-code-mcp__",
)

DENY_REASON = (
    "claude-code-mcp-guard: subagent context (agent_id present in hook payload) "
    "may not invoke nested claude-code-mcp tools. This MCP server is bypass-"
    "permissions-by-default and its upstream is archived (2026-05-15); nested "
    "delegation is governed by G-3b/G-2c. Main-loop access is unaffected. "
    "Decision log: ~/.agents/GRILL-DECISIONS_workflow-delegation_2026-09-22.md"
)


def is_subagent_context(payload):
    """Probe-verified discriminator: `agent_id` present AND non-empty string.

    Empty/None/missing values are treated as 'no signal' -> fail open.
    """
    agent_id = payload.get("agent_id")
    return isinstance(agent_id, str) and agent_id.strip() != ""


def main():
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            return  # fail open: non-object payload
        tool_name = payload.get("tool_name")
        if not isinstance(tool_name, str) or tool_name == "":
            return  # fail open: missing or unusable tool_name
        if not tool_name.startswith(GUARDED_PREFIXES):
            return  # non-matching tool: allow silently
        if not is_subagent_context(payload):
            return  # main loop (no agent_id): allow silently
        decision = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": DENY_REASON,
            }
        }
        sys.stdout.write(json.dumps(decision) + "\n")
    except Exception:
        # Fail-open: garbage stdin, truncated JSON, unexpected shape -> allow.
        pass


if __name__ == "__main__":
    main()
