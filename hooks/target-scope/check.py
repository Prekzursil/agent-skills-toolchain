#!/usr/bin/env python3
r"""target-scope/check.py — PreToolUse hook: per-agent tool-argument scope.

The argument-scope sibling of file-scope. file-scope enforces WHERE an agent
may write (file_path); this enforces WHAT external targets a tool call may
reach — the host / URL / path strings inside tool_input. It is harness safety
in the same family as file-scope and the Ulysses tripwires: a scoped sub-agent
declares an allowlist of targets it is permitted to touch, and a call aimed
outside that list is blocked before it runs.

If NO sidecar is present the hook exits 0 — FAIL-OPEN; unscoped agents are
unrestricted, preserving current behaviour.

BLOCK (exit 2): a sidecar exists for this agent AND at least one extracted
target (host/URL/path) matches NONE of the allowed globs in that sidecar.
ALLOW (exit 0): no sidecar | no targets found | every target matches an
allowed glob | any error.

Opt-out:
  • create  <hook_dir>/.disabled
  • or set  TARGET_SCOPE=off  (also accepts "0", "false")

Keying — lookup order (first match wins), identical to file-scope:
  1. TARGET_SCOPE_AGENT env var → scopes/agent-<name>.json   (isolation-safe)
  2. session_id from payload    → scopes/session-<id>.json
  3. cwd from payload           → scopes/cwd-<sha1>.json

ISOLATION NOTE: session_id and cwd keying affect EVERY agent under the same
session/cwd. When sub-agents share a session, TARGET_SCOPE_AGENT keying is the
only isolation-safe path — the orchestrator sets that env var in the
sub-agent's launch environment and registers the scope with set_scope.py first.

Allow-list authoring (globs; ** spans path components, * stays within one):
  *.example.com                 → any sub-domain host
  api.example.com               → one host (covers every URL on it)
  https://api.example.com/v1/** → only that URL prefix
  /tmp/**                       → any path under /tmp

Wire spec:
  Event:   PreToolUse
  Matcher: Bash|PowerShell|WebFetch|WebSearch|mcp__.*  (broad; hook self-skips
           calls with no host/URL/path arguments)
  Exit:    0 (allow) | 2 (block — reason on stderr)

FAIL-OPEN: any unhandled error → exit 0. Pure stdlib. No network.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))
import _common as C  # noqa: E402

DISABLED = THIS / ".disabled"


def _disabled() -> bool:
    return DISABLED.exists() or os.environ.get("TARGET_SCOPE", "").lower() in (
        "off",
        "0",
        "false",
    )


def main() -> int:
    try:
        if _disabled():
            return 0

        payload = C.read_stdin()
        sd = C.scopes_dir(THIS)
        verdict = C.evaluate(payload, sd)

        if verdict.get("enforced") and verdict.get("decision") == "block":
            allow = verdict.get("allow") or []
            unmatched = verdict.get("unmatched") or []
            session_id = C.extract_session_id(payload)
            sys.stderr.write(
                "TARGET-SCOPE BLOCK: "
                f"{', '.join(unmatched)} out of declared target scope.\n"
                f"Allowed globs: {allow}\n"
                f"To fix: extend the sidecar with set_scope.py --session "
                f"{session_id} --allow '<host-or-url-or-path glob>', or check the "
                f"agent's TARGET_SCOPE_AGENT setting.\n"
            )
            sys.stderr.flush()
            return 2

        return 0

    except Exception:
        return 0  # fail-open — never block on an internal error


if __name__ == "__main__":
    sys.exit(main())
