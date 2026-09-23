#!/usr/bin/env python3
r"""security-action/audit.py — PreToolUse hook: append-only audit of tool calls.

The OBSERVE half of the target-scope rail. check.py (hooks/target-scope)
ENFORCES — it can exit 2 to block an out-of-scope target. This hook only
OBSERVES: for every matched tool call it records one redacted JSONL line
(timestamp, tool name, redacted args, allow/block decision, reason) via
ledger.py, and ALWAYS exits 0. Blocking is target-scope's job; recording is
this hook's job, so the two can be wired independently.

The allow/block label is authentic: this hook reuses the SAME pure evaluator
(hooks/target-scope/_common.evaluate) that check.py uses, so the audit trail
agrees with what the enforcer decided. If target-scope is unavailable, the
record is still written with decision "observe" and enforced=false — the audit
rail degrades but never disappears.

Opt-out:
  • create  <hook_dir>/.disabled
  • or set  SECURITY_ACTION=off  (also accepts "0", "false")

Wire spec:
  Event:   PreToolUse
  Matcher: Bash|PowerShell|WebFetch|WebSearch|mcp__.*  (same broad matcher as
           target-scope; the record is a no-op-ish line when no targets exist)
  Exit:    0 always (audit-only; never blocks)

FAIL-OPEN and non-blocking: any error → exit 0, nothing written. Pure stdlib.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))
import ledger  # noqa: E402

DISABLED = THIS / ".disabled"
TARGET_SCOPE_DIR = THIS.parent / "target-scope"


def _disabled() -> bool:
    return DISABLED.exists() or os.environ.get("SECURITY_ACTION", "").lower() in (
        "off",
        "0",
        "false",
    )


def _read_stdin() -> dict:
    try:
        return json.loads(sys.stdin.read() or "{}")
    except Exception:
        return {}


def _evaluate_with_target_scope(payload: dict) -> dict | None:
    """Best-effort reuse of target-scope's pure evaluator. None if unavailable."""
    try:
        ts_dir = str(TARGET_SCOPE_DIR)
        if ts_dir not in sys.path:
            sys.path.insert(0, ts_dir)
        import _common as TC  # noqa: PLC0415 — lazy, fail-open

        sd = TC.scopes_dir(TARGET_SCOPE_DIR)
        return TC.evaluate(payload, sd)
    except Exception:
        return None


def main() -> int:
    try:
        if _disabled():
            return 0

        payload = _read_stdin()
        tool = str(payload.get("tool_name") or "")
        args = payload.get("tool_input") or {}
        project = str(payload.get("cwd") or os.getcwd())

        verdict = _evaluate_with_target_scope(payload)
        if verdict is not None:
            record = {
                "tool": tool,
                "args": args,
                "decision": verdict.get("decision", "allow"),
                "enforced": bool(verdict.get("enforced")),
                "reason": verdict.get("reason", ""),
                "targets": verdict.get("targets", []),
                "unmatched": verdict.get("unmatched", []),
            }
        else:
            record = {
                "tool": tool,
                "args": args,
                "decision": "observe",
                "enforced": False,
                "reason": "target-scope-unavailable",
                "targets": [],
                "unmatched": [],
            }

        ledger.append_record(record, project_path=project)
    except Exception:
        pass  # audit must never break a session
    return 0  # audit-only: never blocks


if __name__ == "__main__":
    sys.exit(main())
