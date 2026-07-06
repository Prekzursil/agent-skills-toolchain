#!/usr/bin/env python3
r"""bg-registry/register.py — write-ahead registry of background/sub-agent spawns.

THE problem this solves (durability spine T1.1): when a sub-agent / background job is
launched and Claude Code is later restarted or crashes, that work is SILENTLY killed —
no artifact, no error, just gone. We never notice until much later. The fix is a durable
EXTERNAL ledger written the instant work is spawned, reconciled on the next SessionStart
(see reconcile.py).

This file is the WRITE side. Two entry points:

  * Hook mode  (PreToolUse, matcher "Task"):  python register.py
      Reads the hook JSON on stdin and appends a record for the dispatched sub-agent.
  * CLI  mode  (other launchers — longrun.ps1, run_in_background Bash, agent dispatch):
      python register.py --kind background --id longrun-cov --pid 1234 \
             --artifact D:/out/cov.log --scope "src/**" --cmd "jest --coverage"
      Appends a record with a real OS pid + declared artifact so reconcile can later
      check pid-liveness + artifact existence.

Record shape (one NDJSON line):
  {id, kind, cmd, subagent_type?, name?, desc?, pid, expected_artifact, declared_scope,
   started_ts, status:"running", sync, session}

`sync` distinguishes synchronous sub-agents (a normal Task() the orchestrator awaits —
done the moment the turn ends) from async/background work (forks, longrun, background
Bash — only done when the artifact lands or the pid dies). done_marker.py uses it.

FAIL-OPEN: any error -> exit 0, nothing written. Opt-out: BG_REGISTRY=off or a .disabled
file. NEVER blocks and (in hook mode) NEVER injects — it is a silent recorder.
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))
import _common as C  # noqa: E402

DISABLED = THIS / ".disabled"


def _disabled() -> bool:
    return DISABLED.exists() or os.environ.get("BG_REGISTRY", "").lower() in (
        "off",
        "0",
        "false",
    )


def _excerpt(s, n: int = 200) -> str:
    s = str(s or "").strip().replace("\n", " ")
    return s[:n]


def _gen_id(seed: str, prefix: str) -> str:
    # nosemgrep: python.lang.security.insecure-hash-algorithms.insecure-hash-algorithm-sha1 -- non-cryptographic id generation (background-task slug), not a security control
    h = hashlib.sha1(
        (seed + str(C.now())).encode("utf-8", "replace"), usedforsecurity=False
    ).hexdigest()[:10]
    return f"{prefix}-{h}"


def build_task_record(data: dict) -> dict:
    """Build a registry record from a PreToolUse(Task) hook payload."""
    ti = data.get("tool_input") or {}
    prompt = str(ti.get("prompt") or "")
    desc = str(ti.get("description") or "")
    sub = str(ti.get("subagent_type") or "")
    name = str(ti.get("name") or "")
    # A fork / explicitly-backgrounded sub-agent is async (no synchronous turn-end done).
    is_async = (
        (sub == "fork")
        or bool(ti.get("run_in_background"))
        or bool(ti.get("background"))
    )
    rid = (
        str(data.get("tool_use_id") or "").strip()
        or name
        or _gen_id(prompt + desc, sub or "task")
    )
    return {
        "id": rid,
        "kind": "Task",
        "subagent_type": sub or None,
        "name": name or None,
        "desc": _excerpt(desc, 120),
        "cmd": _excerpt(prompt, 200),
        "pid": None,
        "expected_artifact": None,
        "declared_scope": None,
        "started_ts": C.now(),
        "status": "running",
        "sync": (not is_async),
        "session": C.session_id(data),
    }


def run_hook() -> int:
    data = C.read_stdin()
    tn = str(data.get("tool_name") or "")
    if tn not in ("Task", "Agent"):  # defensive (matcher already scopes this)
        return 0
    C.append_record(C.session_id(data), build_task_record(data))
    return 0


def run_cli(argv) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="register.py", add_help=True)
    ap.add_argument("--id", default="")
    ap.add_argument("--kind", default="background")
    ap.add_argument("--pid", default=None)
    ap.add_argument("--artifact", default=None)
    ap.add_argument("--scope", default=None)
    ap.add_argument("--cmd", default="")
    ap.add_argument("--session", default="cli")
    ap.add_argument(
        "--sync",
        action="store_true",
        help="mark as a synchronous job (done when the turn ends)",
    )
    a = ap.parse_args(argv)
    try:
        pid = int(a.pid) if a.pid not in (None, "", "None") else None
    except (TypeError, ValueError):
        pid = None
    rid = a.id.strip() or _gen_id(a.cmd, a.kind)
    rec = {
        "id": rid,
        "kind": a.kind,
        "cmd": _excerpt(a.cmd, 200),
        "pid": pid,
        "expected_artifact": a.artifact or None,
        "declared_scope": a.scope or None,
        "started_ts": C.now(),
        "status": "running",
        "sync": bool(a.sync),
        "session": a.session,
    }
    ok = C.append_record(a.session, rec)
    # Terminal-state marker (AGENTS.md s4) so a launcher script can confirm wiring.
    print(
        f"SUCCESS:bg-registry registered {rid}"
        if ok
        else "FAILED:bg-registry could not write record"
    )
    return 0


def main(argv) -> int:
    try:
        if _disabled():
            return 0
        # Any leading "--flag" means CLI mode; otherwise it's the PreToolUse hook.
        if any(str(x).startswith("--") for x in argv):
            return run_cli(argv)
        return run_hook()
    except SystemExit:
        # argparse --help / bad args: stay fail-open for the hot path.
        return 0
    except Exception:
        return 0  # fail-open


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
