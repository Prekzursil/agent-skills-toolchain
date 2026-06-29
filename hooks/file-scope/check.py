#!/usr/bin/env python3
r"""file-scope/check.py — PreToolUse hook: per-agent file write-scope enforcement.

Enforces write scope when a scope sidecar exists for the current agent/session.
If NO sidecar is present the hook exits 0 — fail-open; unscoped agents are
unrestricted, preserving current behaviour.

BLOCK (exit 2): a sidecar exists for this agent AND the target file_path does
NOT match any allowed glob in that sidecar.
ALLOW (exit 0): no sidecar | path matches an allowed glob | any error.

Opt-out:
  • create  <hook_dir>/.disabled
  • or set  FILE_SCOPE=off  (also accepts "0", "false")

Keying — lookup order (first match wins):
  1. FILE_SCOPE_AGENT env var  → scopes/agent-<name>.json
     Set this env var before launching the sub-agent so it picks up its own
     narrow scope.  The orchestrator controls this:
       FILE_SCOPE_AGENT=coder-1 python subagent.py …
  2. session_id from payload  → scopes/session-<id>.json
     Useful when the orchestrator knows the sub-agent's session_id in advance
     (e.g. from a pre-registered scope set before the agent starts) or after
     the fact (bg-registry records it on first Task dispatch).
  3. cwd from payload         → scopes/cwd-<sha1>.json
     Useful when each sub-agent is isolated to its own working directory.

ISOLATION NOTE (M6): session_id and cwd keying affect EVERY agent running
under the same session/cwd — this includes the main agent and all siblings.
In Claude Code, sub-agents commonly inherit the parent's session_id or cwd,
so a session/cwd sidecar can silently block (or over-permit) writes for the
entire shared session.  FILE_SCOPE_AGENT keying is the ONLY isolation-safe
path when agents share a session_id or cwd.  The orchestrator must set the
FILE_SCOPE_AGENT env var in the sub-agent's launch environment AND call
  set_scope.py --agent-name <name> --allow <glob> …
before starting the sub-agent.

Wire spec:
  Event:   PreToolUse
  Matcher: Edit|Write|MultiEdit|NotebookEdit
  Command: python C:/Users/Prekzursil/.claude/hooks/file-scope/check.py
  Exit:    0 (allow) | 2 (block — reason on stderr)

FAIL-OPEN: any unhandled error → exit 0.  Pure stdlib.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))
import _common as C  # noqa: E402

DISABLED = THIS / ".disabled"
WRITE_TOOLS = frozenset({"Edit", "Write", "MultiEdit", "NotebookEdit"})


def _disabled() -> bool:
    return DISABLED.exists() or os.environ.get("FILE_SCOPE", "").lower() in ("off", "0", "false")


def _find_sidecar(session_id: str, cwd: str, sd: Path) -> dict | None:
    """Return the first sidecar found under any supported key, or None."""
    # 1. Agent-name (highest specificity): set by orchestrator via env var.
    agent = os.environ.get("FILE_SCOPE_AGENT", "").strip()
    if agent:
        s = C.try_sidecar(C.sidecar_path(sd, "agent", agent))
        if s is not None:
            return s

    # 2. Session-level.
    if session_id and session_id != "default":
        s = C.try_sidecar(C.sidecar_path(sd, "session", session_id))
        if s is not None:
            return s

    # 3. CWD-level.
    if cwd:
        s = C.try_sidecar(C.sidecar_path(sd, "cwd", cwd))
        if s is not None:
            return s

    return None  # no sidecar found → no enforcement


def main() -> int:
    try:
        if _disabled():
            return 0

        payload = C.read_stdin()
        tool = str(payload.get("tool_name") or "")
        if tool not in WRITE_TOOLS:
            return 0

        ti = payload.get("tool_input") or {}
        # NotebookEdit uses notebook_path; all others use file_path.
        fp = str(ti.get("file_path") or ti.get("notebook_path") or "").strip()
        if not fp:
            return 0  # no path to check → fail-open

        cwd = str(payload.get("cwd") or os.getcwd())
        # Resolve relative paths against cwd.
        fp_norm = fp.replace("\\", "/")
        is_abs = fp_norm.startswith("/") or (len(fp_norm) >= 2 and fp_norm[1] == ":")
        if not is_abs:
            fp = str(Path(cwd) / fp)

        session_id = C.extract_session_id(payload)
        sd = C.scopes_dir(THIS)

        sidecar = _find_sidecar(session_id, cwd, sd)
        if sidecar is None:
            return 0  # no sidecar → unrestricted (fail-open)

        allow = sidecar.get("allow") or []
        if C.matches_any(fp, allow):
            return 0

        # BLOCK — write a clear, actionable message to stderr.
        sys.stderr.write(
            f"FILE-SCOPE BLOCK: '{fp}' is out of declared file scope.\n"
            f"Allowed globs: {allow}\n"
            f"To fix: extend the sidecar with set_scope.py --session "
            f"{session_id} --allow '<pattern>', or check the agent's "
            f"FILE_SCOPE_AGENT setting.\n"
        )
        sys.stderr.flush()
        return 2

    except Exception:
        return 0  # fail-open — never block on an internal error


if __name__ == "__main__":
    sys.exit(main())
