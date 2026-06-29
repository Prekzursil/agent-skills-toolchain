#!/usr/bin/env python3
r"""file-scope/set_scope.py — CLI to write, update, or clear scope sidecars.

The orchestrator calls this to register a per-agent write scope BEFORE (or
shortly after) launching a sub-agent.  The hook check.py then enforces it.

Usage
-----
Set scope by session-id (most common when orchestrator knows the session):
    python set_scope.py --session <id>  --allow "src/**/*.py" --allow "tests/**"

Set scope by agent-name (orchestrator also sets FILE_SCOPE_AGENT=<name> env
var in the sub-agent's launch environment — highest-priority lookup in check.py):
    python set_scope.py --agent-name coder-1  --allow "src/feature_a/**"

Set scope by cwd (when each sub-agent runs in an isolated working directory):
    python set_scope.py --cwd C:/project/workspace  --allow "src/**"

Clear a scope sidecar:
    python set_scope.py --session <id> --clear
    python set_scope.py --agent-name coder-1 --clear

Garbage-collect expired sidecars:
    python set_scope.py --gc

List active (non-expired) sidecars:
    python set_scope.py --list

Options:
    --ttl-hours N   Sidecar TTL in hours (default 24; 0 = never-expire).
                    WARNING: 0 / never-expire is dangerous for session/cwd
                    keys — a forgotten sidecar will silently block or
                    over-permit writes for every agent sharing that session
                    or cwd, potentially forever.  Prefer the default 24h.

Key selection (exactly one of --session / --agent-name / --cwd required,
except for --gc / --list which need none):

  --session <id>       → scopes/session-<safe(id)>.json
  --agent-name <name>  → scopes/agent-<safe(name)>.json
  --cwd <path>         → scopes/cwd-<sha1(path)[:12]>.json

ISOLATION NOTE (M6): session/cwd keys affect ALL agents sharing the same
session_id or cwd — including the main agent and siblings.  Only agent-name
keying (--agent-name + FILE_SCOPE_AGENT env var) is isolation-safe when
sub-agents share a session.  See check.py docstring for details.

Output: SUCCESS:<key> or FAILED:<key> <reason>  (AGENTS.md §4 terminal state)

FAIL-OPEN on all I/O errors: exits 0 with FAILED marker.  Pure stdlib.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))
import _common as C  # noqa: E402


# ---------------------------------------------------------------------------
# Garbage collection
# ---------------------------------------------------------------------------

def _gc(sd: Path) -> int:
    """Remove expired sidecars from *sd*.  Non-JSON and non-expired files are kept."""
    removed = 0
    kept = 0
    if not sd.exists():
        print("SUCCESS:gc nothing-to-gc")
        return 0
    for f in sorted(sd.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            ttl = float(data.get("ttl_hours") or 0)
            if ttl > 0:
                created = float(data.get("created_at") or 0)
                if created and (created + ttl * 3600.0) < time.time():
                    f.unlink(missing_ok=True)
                    removed += 1
                    continue
            kept += 1
        except Exception:
            kept += 1  # bad JSON / I/O error → leave it, fail-open
    print(f"SUCCESS:gc removed={removed} kept={kept}")
    return 0


def _list(sd: Path) -> int:
    """Print all active (non-expired) sidecars to stdout."""
    if not sd.exists():
        print("SUCCESS:list count=0")
        return 0
    rows: list[dict] = []
    now = time.time()
    for f in sorted(sd.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            ttl = float(data.get("ttl_hours") or 0)
            if ttl > 0:
                created = float(data.get("created_at") or 0)
                if created and (created + ttl * 3600.0) < now:
                    continue  # expired — skip
            rows.append({
                "file": f.name,
                "key_type": data.get("key_type", "?"),
                "key": data.get("key", "?"),
                "allow": data.get("allow", []),
                "ttl_hours": ttl,
            })
        except Exception:
            pass
    for row in rows:
        globs = ", ".join(row["allow"]) if row["allow"] else "(none — blocks all writes)"
        print(f"  {row['key_type']}:{row['key']}  globs=[{globs}]"
              f"  ttl={row['ttl_hours']}h  ({row['file']})")
    print(f"SUCCESS:list count={len(rows)}")
    return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="set_scope.py",
        description="Write / clear per-agent file-scope sidecars for check.py",
    )
    key_grp = ap.add_mutually_exclusive_group()
    key_grp.add_argument("--session", metavar="ID",
                         help="Key by session_id (matches hook payload session_id)")
    key_grp.add_argument("--agent-name", metavar="NAME",
                         help="Key by agent name (orchestrator also sets "
                              "FILE_SCOPE_AGENT=<NAME> in the sub-agent's env)")
    key_grp.add_argument("--cwd", metavar="PATH",
                         help="Key by working directory path (sha1-slugged)")
    ap.add_argument("--allow", action="append", default=[],
                    metavar="GLOB",
                    help="Allowed glob pattern (repeat for multiple). "
                         "Empty list = block all writes.")
    ap.add_argument("--clear", action="store_true",
                    help="Remove the sidecar instead of writing it")
    ap.add_argument("--gc", action="store_true",
                    help="Remove all expired sidecars")
    ap.add_argument("--list", action="store_true",
                    help="List all active (non-expired) sidecars and their allow-lists")
    ap.add_argument("--ttl-hours", type=float, default=24.0, metavar="N",
                    help="Sidecar TTL in hours (default 24; 0 = never-expire — "
                         "avoid for session/cwd keys, see module docstring)")

    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        # argparse calls sys.exit on --help or bad args; re-raise cleanly.
        raise

    sd = C.scopes_dir(THIS)

    # --gc and --list are standalone: no key required.
    if args.gc:
        return _gc(sd)
    if args.list:
        return _list(sd)

    # All other operations require exactly one key.
    if args.session:
        key_type, key = "session", args.session
    elif args.agent_name:
        key_type, key = "agent", args.agent_name
    elif args.cwd:
        key_type, key = "cwd", args.cwd
    else:
        ap.error("one of --session / --agent-name / --cwd is required (or --gc)")
        return 1  # unreachable but satisfies type checkers

    path = C.sidecar_path(sd, key_type, key)
    label = f"{key_type}:{key}"

    if args.clear:
        try:
            path.unlink(missing_ok=True)
            print(f"SUCCESS:{label} cleared")
            return 0
        except Exception as exc:
            print(f"FAILED:{label} clear-error: {exc}")
            return 0  # fail-open

    # Write the sidecar.
    ok = C.write_sidecar(path, key=key, key_type=key_type,
                          allow=args.allow, ttl_hours=args.ttl_hours)
    if ok:
        print(f"SUCCESS:{label} globs={args.allow!r} ttl={args.ttl_hours}h")
        return 0
    else:
        print(f"FAILED:{label} could not write sidecar")
        return 0  # fail-open (orchestrator should not crash on I/O errors)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        print("FAILED:set_scope unexpected error")
        sys.exit(0)  # fail-open
