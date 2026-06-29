#!/usr/bin/env python
"""PostToolUse hook — success-alignment observer for the semantic router.

Closes the loop: when the agent actually INVOKES something the router suggested this session
(a Skill, a Task subagent, or an MCP tool), credit it (used++ in success.json). route.py then
gives historically-acted-on units a small ranking nudge (success.boost). This is the cheap,
durable Memento-Skills signal — no transcript scraping, no model calls.

Matched in settings.json for Skill / Task / mcp__* tools. Inject-nothing, exit 0, fail-open.
"""
import json
import sys
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))


def _keys_for(tool_name, tool_input):
    """Candidate success-keys ('kind:name') this tool invocation could be crediting."""
    keys = []
    tn = str(tool_name or "")
    ti = tool_input if isinstance(tool_input, dict) else {}
    if tn == "Skill":
        s = str(ti.get("skill") or ti.get("name") or "").strip()
        if s:
            keys.append(f"skill:{s}")
            if ":" in s:                       # plugin-namespaced -> also try bare name
                keys.append(f"skill:{s.split(':')[-1]}")
    elif tn == "Task":
        a = str(ti.get("subagent_type") or "").strip()
        if a:
            keys.append(f"agent:{a}")
            if ":" in a:
                keys.append(f"agent:{a.split(':')[-1]}")
    elif tn.startswith("mcp__"):
        parts = tn.split("__")
        if len(parts) >= 2 and parts[1]:
            keys.append(f"mcp:{parts[1]}")
    elif tn.startswith("/") or tn == "SlashCommand":
        c = (tn.lstrip("/") if tn != "SlashCommand" else str(ti.get("command") or "")).strip().lstrip("/")
        if c:
            keys.append(f"command:{c.split()[0]}")
    return keys


def main():
    try:
        data = json.loads(sys.stdin.read() or "{}")
        sid = data.get("session_id") or "default"
        tool_name = data.get("tool_name")
        tool_input = data.get("tool_input") or {}
        keys = _keys_for(tool_name, tool_input)
        if keys:
            import success as _succ
            for k in keys:
                if _succ.record_used(k, sid):
                    break  # credit once per invocation
    except Exception:
        pass  # fail-open
    return 0


if __name__ == "__main__":
    sys.exit(main())
