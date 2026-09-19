"""Universal MCP doctor -- health-watchdog + drift-auditor for the MCP fleet.

A single command to KEEP the MCP fleet healthy and curated -- the cure for
"curation keeps reappearing" plus silent hangs and per-session process
pile-ups. Generalizes the RE-harness primitives (port_probe / proc_registry /
mcp config-safety discipline) from one tool to the whole fleet.

Usage:
    python mcp_doctor.py status [--json]
    python mcp_doctor.py audit  [--json]
    python mcp_doctor.py reap   [--json] [--apply]

  status  read ~/.mcp.json (active) + ~/.mcp.disabled.json (parked) +
          ~/.claude.json; per ACTIVE server show tier / transport / a
          lightweight liveness probe. Table + optional JSON.
  audit   drift auditor vs mcp_budget.yaml: undocumented re-appeared servers,
          duplicate tool-surface, heavy resident engines, per-session pile-up.
          Emits a SUCCESS:/FAILED: terminal marker + prioritized findings.
  reap    safely kill duplicate/orphaned MCP processes keeping ONE per server,
          gated like the RE-harness teardown (NEVER kills the live GUI IDA on
          :13337). DRY-RUN by default; pass --apply to actually kill.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import mcp_doctor_core as core  # noqa: E402


def _fmt_table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    sep = "  ".join("-" * widths[i] for i in range(len(headers)))
    body = [
        "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row))
        for row in rows
    ]
    return "\n".join([line, sep, *body])


def _liveness_cell(live: dict) -> str:
    kind = live.get("kind", "?")
    inst = live.get("instances", 0)
    if kind in ("http-local", "backend-port"):
        up = live.get("up")
        # http-local carries a richer state incl. 'dead-listening' (TCP up but
        # the MCP handshake fails) -- surface it verbatim rather than just UP.
        state = live.get("state") or ("UP" if up else "down")
        state = state.upper() if state in ("up", "down") else state
        return f"{kind}:{live.get('port')} {state} (x{inst} proc)"
    if kind == "http-remote":
        return "remote (not probed)"
    res = live.get("resolvable")
    flag = "cmd-ok" if res else ("cmd-MISSING" if res is False else "cmd?")
    return f"stdio {flag} (x{inst} proc)"


def _emit(report: dict, marker: str, rc: int, want_json: bool) -> int:
    """In JSON mode embed the marker as a field (keeps stdout pure-parseable);
    in text mode the caller already printed the human view -- add the marker."""
    if want_json:
        print(json.dumps({**report, "marker": marker}, indent=2))
    else:
        print(marker)
    return rc


def cmd_status(args: argparse.Namespace) -> int:
    rep = core.build_status()
    if rep["errors"]:
        marker, rc = "FAILED:status config-parse-error", 1
    else:
        marker = f"SUCCESS:status {rep['active_count']} active servers reported"
        rc = 0
    if not args.json:
        rows = [
            [r["name"], r["tier"], r["transport"], r["domain"],
             "yes" if r["in_manifest"] else "NO", _liveness_cell(r["liveness"])]
            for r in rep["servers"]
        ]
        print(_fmt_table(
            ["server", "tier", "transport", "domain", "in-manifest", "liveness"],
            rows,
        ))
        print()
        print(
            f"active={rep['active_count']} parked={rep['disabled_count']} "
            f"host={rep['host_count']} procs-scanned={rep['total_processes']}"
        )
        if rep["errors"]:
            print(f"CONFIG ERRORS: {rep['errors']}")
    return _emit(rep, marker, rc, args.json)


def cmd_audit(args: argparse.Namespace) -> int:
    rep = core.build_audit()
    c = rep["counts"]
    n = sum(c.values())
    if c["CRITICAL"] or c["HIGH"]:
        marker = f"FAILED:audit {c['CRITICAL']} critical / {c['HIGH']} high of {n}"
        rc = 1
    else:
        marker = f"SUCCESS:audit {n} findings, none high/critical"
        rc = 0
    if not args.json:
        for f in rep["findings"]:
            print(f"[{f['severity']:8}] {f['kind']}: {f['detail']}")
        print()
        print(
            f"findings: CRITICAL={c['CRITICAL']} HIGH={c['HIGH']} "
            f"MEDIUM={c['MEDIUM']} LOW={c['LOW']}"
        )
    return _emit(rep, marker, rc, args.json)


def cmd_reap(args: argparse.Namespace) -> int:
    plan = core.plan_reap()
    result = core.execute_reap(plan, apply=args.apply)
    mode = "APPLIED" if args.apply else "DRY-RUN"
    marker = f"SUCCESS:reap {mode} kill_candidates={plan['kill_total']}"
    if not args.json:
        print(f"protected port owners (never reaped): {plan['protected_ports']}")
        for srv in plan["servers"]:
            keep = srv["keep"]
            keep_pid = keep["pid"] if keep else "none"
            print(
                f"{srv['server']:18} total={srv['total']} keep={keep_pid} "
                f"would_kill={[t['pid'] for t in srv['would_kill']]} "
                f"protected={[t['pid'] for t in srv['protected']]}"
            )
        print()
    return _emit({"plan": plan, "result": result}, marker, 0, args.json)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Universal MCP doctor")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("status", "audit", "reap"):
        sp = sub.add_parser(name)
        sp.add_argument("--json", action="store_true", help="emit JSON")
        if name == "reap":
            sp.add_argument(
                "--apply", action="store_true",
                help="actually kill (default is a dry-run)",
            )
    args = parser.parse_args(argv)
    return {"status": cmd_status, "audit": cmd_audit, "reap": cmd_reap}[
        args.cmd
    ](args)


if __name__ == "__main__":
    raise SystemExit(main())
