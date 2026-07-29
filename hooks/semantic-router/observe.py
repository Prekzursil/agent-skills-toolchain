#!/usr/bin/env python
"""PostToolUse hook — success-alignment observer for the semantic router.

Closes the loop: when the agent actually INVOKES something the router suggested this session
(a Skill, a Task subagent, or an MCP tool), credit it (used++ in success.json). route.py then
gives historically-acted-on units a small ranking nudge (success.boost). This is the cheap,
durable Memento-Skills signal — no transcript scraping, no model calls.

Matched in settings.json for Skill / Task / mcp__* tools. Inject-nothing, exit 0, fail-open.

OUTCOME GATE (N07). Credit means "this suggestion PAID OFF", so an invocation that came back
as an explicit failure must not earn it. Arrival of the PostToolUse event is NOT a success
predicate in this harness: memory-spool/_common.py:178-195 and tool-result-sentinel/
sentinel.py:289-305 both classify `isError`/`error`/`success:false` PostToolUse payloads as
failures. Measured before this gate existed: an `mcp__claude_ai_Tavily__tavily_search`
response of `{"isError": true, "content":[{"type":"text","text":"not connected"}]}` still
produced `{"suggested": 1, "used": 1}` and `success.boost(alpha=0.4) == +0.1333` -- a dead
endpoint was being ranked UP. The test below is deliberately CONSERVATIVE: only an explicit
failure marker suppresses the credit, so every ambiguous or unrecognised shape keeps the
previous behaviour and no real use is silently dropped.
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
            if ":" in s:  # plugin-namespaced -> also try bare name
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
        c = (
            (tn.lstrip("/") if tn != "SlashCommand" else str(ti.get("command") or ""))
            .strip()
            .lstrip("/")
        )
        if c:
            keys.append(f"command:{c.split()[0]}")
    return keys


def explicitly_failed(tool_response) -> bool:
    """True only for an UNAMBIGUOUS failure marker in a PostToolUse ``tool_response``.

    Conservative by design (see the OUTCOME GATE note in the module docstring): an unknown,
    empty or merely odd shape returns False and keeps the pre-existing credit behaviour, so
    this can never silently stop crediting real uses. It suppresses credit only when the
    payload SAYS it failed -- the same markers memory-spool/_common.py:178-195 and
    tool-result-sentinel/sentinel.py:289-305 already treat as failures.
    """
    if isinstance(tool_response, dict):
        if (
            tool_response.get("isError") is True
            or tool_response.get("is_error") is True
        ):
            return True
        if tool_response.get("success") is False or tool_response.get("ok") is False:
            return True
        if tool_response.get("interrupted") is True:
            return True
        if str(tool_response.get("status") or "").lower() in (
            "error",
            "failed",
            "failure",
        ):
            return True
        err = tool_response.get("error")
        if err and not isinstance(err, bool):
            if str(err).strip().lower() not in ("", "none", "null", "false", "0"):
                return True
        for key in ("result", "output", "response"):
            nested = tool_response.get(key)
            if isinstance(nested, dict) and explicitly_failed(nested):
                return True
    return False


def main():
    try:
        data = json.loads(sys.stdin.read() or "{}")
        sid = data.get("session_id") or "default"
        tool_name = data.get("tool_name")
        tool_input = data.get("tool_input") or {}
        response = data.get("tool_response")
        if response is None:
            response = data.get("tool_output")
        if explicitly_failed(response):
            return 0  # a failed invocation earns no routing credit
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
