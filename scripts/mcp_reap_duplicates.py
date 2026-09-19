#!/usr/bin/env python3
"""RAM-ceiling duplicate reaper -- audit-driven, EXACT-PID, never name-matched.

Per-session MCP stdio children pile up (the 41-npx class) and pin RAM.
`mcp_doctor.py audit` already detects the condition as `process-pileup`
findings that carry the EXACT PIDs above ceiling. `mcp_doctor.py reap`
plans by NEEDLE, and needles have a measured collision history
(2026-08-14: three hub servers derived the same needle 'hub', which
substring-matched 43 processes incl. a live git.exe -- see
re-harness/test_needle_collision.py). This reaper therefore NEVER matches
a name: it consumes the auditor's exact PIDs and re-validates each one
against a FRESH snapshot + listener map before any kill.

Kill rails -- ALL must pass; ANY doubt keeps the process alive:
  R1 exact-PID source   candidates come ONLY from finding["pids"] of
                        kind=="process-pileup"; no cmdline/name matching.
  R2 still-alive        PID exists in the fresh post-audit snapshot (TOCTOU).
  R3 host-image only    image in _ALLOWED_IMAGES (node/python/uv/deno/bun).
  R4 true orphan        direct parent absent from the fresh snapshot;
                        unknown/None/0/self ppid => KEEP (fail-safe).
  R5 owns no listener   PID owns NO socket in LISTEN state (protects every
                        port-holding daemon without importing any catalog).
  R6 age >= min         created older than --min-age-min minutes (default 10);
                        unparseable/missing timestamp => KEEP.
  R7 not our tree       PID is neither this process nor any ancestor of it.

Fail-closed: doctor missing, unparseable audit JSON, empty process
snapshot, or an unavailable listener map => FAILED:reap-dup, exit 1, ZERO
kills. Legitimately zero findings is SUCCESS (killing nothing is safe).

Usage:
    python mcp_reap_duplicates.py [--json]              # DRY-RUN (default)
    python mcp_reap_duplicates.py --apply [--json]      # actually kill
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

HARNESS = Path(os.environ.get(
    "RE_HARNESS_ROOT", r"C:\Users\Prekzursil\.local\opt\re-harness"))
DOCTOR = HARNESS / "mcp_doctor.py"
DEFAULT_LOG = Path(
    r"C:\Users\Prekzursil\source\agent-skills-toolchain\harness-audits\health\reap-log.jsonl")

_ALLOWED_IMAGES = {
    "node.exe", "python.exe", "pythonw.exe",
    "uv.exe", "uvx.exe", "deno.exe", "bun.exe",
}

sys.path.insert(0, str(HARNESS))
from lib import mcp_procscan  # noqa: E402
from lib import proc_registry  # noqa: E402


class ReapError(Exception):
    pass


def run_audit(timeout: int = 300) -> dict:
    if not DOCTOR.is_file():
        raise ReapError(f"mcp_doctor.py not found at {DOCTOR}")
    try:
        proc = subprocess.run(
            [sys.executable, str(DOCTOR), "audit", "--json"],
            capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ReapError(f"audit subprocess failed: {exc}") from exc
    raw = (proc.stdout or "").strip()
    try:
        report = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ReapError(
            f"audit JSON unparseable (rc={proc.returncode}): {raw[:180]!r}") from exc
    if (not isinstance(report, dict)
            or not isinstance(report.get("findings"), list)):
        raise ReapError("audit JSON lacks a 'findings' list")
    return report


_PS_LISTENERS = (
    "Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | "
    "Select-Object LocalPort, OwningProcess | ConvertTo-Json -Compress"
)


def listening_ports_by_pid() -> dict[int, set[int]]:
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive",
             "-Command", _PS_LISTENERS],
            capture_output=True, text=True, timeout=90)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ReapError(f"listener query failed: {exc}") from exc
    if out.returncode != 0:
        raise ReapError(f"listener query rc={out.returncode}")
    raw = (out.stdout or "").strip()
    if not raw:
        return {}
    try:
        rows = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ReapError("listener query returned unparseable JSON") from exc
    if isinstance(rows, dict):
        rows = [rows]
    ports: dict[int, set[int]] = {}
    for row in rows:
        try:
            ports.setdefault(
                int(row["OwningProcess"]), set()).add(int(row["LocalPort"]))
        except (KeyError, TypeError, ValueError):
            continue
    return ports


def _age_minutes(created: str, now: datetime) -> Optional[float]:
    try:
        dt = datetime.fromisoformat(created)
    except (ValueError, TypeError):
        return None
    try:
        return (now - dt.astimezone(timezone.utc)).total_seconds() / 60.0
    except (ValueError, OSError):
        return None


def _is_orphan(proc, live_pids: set[int]) -> bool:
    ppid = proc.ppid
    if ppid is None or ppid == 0 or ppid == proc.pid:
        return False
    return ppid not in live_pids


def _self_tree(procs) -> set[int]:
    tree = {os.getpid(), os.getppid()}
    by_pid = {p.pid: p for p in procs}
    cur, seen = os.getpid(), set()
    while cur and cur not in seen:
        seen.add(cur)
        tree.add(cur)
        nxt = by_pid.get(cur)
        cur = nxt.ppid if (nxt and nxt.ppid) else 0
    return tree


def plan_from(
    findings: list[dict],
    procs,
    listeners: dict[int, set[int]],
    *,
    now: datetime,
    min_age_min: float,
    max_kill: int,
    self_pids: set[int],
) -> dict:
    live = {p.pid for p in procs}
    by_pid = {p.pid: p for p in procs}
    pileups = sorted(
        (f for f in findings if f.get("kind") == "process-pileup"),
        key=lambda f: (0 if f.get("severity") == "HIGH" else 1,
                       str(f.get("server"))))

    seen_pids: set[int] = set()
    candidates: list[dict] = []
    skipped: list[dict] = []
    for f in pileups:
        server = str(f.get("server") or "?")
        for raw_pid in (f.get("pids") or []):
            try:
                pid = int(raw_pid)
            except (TypeError, ValueError):
                continue
            if pid in seen_pids:
                continue
            seen_pids.add(pid)
            proc = by_pid.get(pid)
            if proc is None:
                skipped.append({"pid": pid, "server": server,
                                "reason": "R2 vanished-since-audit"})
            elif (proc.name or "").lower() not in _ALLOWED_IMAGES:
                skipped.append({"pid": pid, "server": server,
                                "reason": f"R3 image-not-host ({proc.name})"})
            elif listeners.get(pid):
                skipped.append({"pid": pid, "server": server, "reason":
                                f"R5 owns-listener {sorted(listeners[pid])}"})
            elif not _is_orphan(proc, live):
                skipped.append({"pid": pid, "server": server,
                                "reason": "R4 parent-alive (live session child)"})
            else:
                age = _age_minutes(proc.created, now)
                if age is None:
                    skipped.append({"pid": pid, "server": server,
                                    "reason": "R6 age-unknown (fail-safe keep)"})
                elif age < min_age_min:
                    skipped.append({"pid": pid, "server": server,
                                    "reason":
                                    f"R6 too-young ({age:.1f}m < {min_age_min}m)"})
                elif pid in self_pids:
                    skipped.append({"pid": pid, "server": server,
                                    "reason": "R7 in-own-process-tree"})
                else:
                    candidates.append({
                        "pid": pid, "server": server, "ws_mb": proc.ws_mb,
                        "created": proc.created, "age_min": round(age, 1)})

    candidates.sort(key=lambda c: -c["ws_mb"])
    kill_plan = candidates[:max_kill]
    skipped.extend({"pid": c["pid"], "server": c["server"],
                    "reason": "max-kill cap deferred"}
                   for c in candidates[max_kill:])
    return {
        "kill_plan": kill_plan,
        "skipped": skipped,
        "candidate_total": len(seen_pids),
        "freed_mb_plan": sum(c["ws_mb"] for c in kill_plan),
    }


def write_log(record: dict, path: Path, keep: int) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        lines = path.read_text(encoding="utf-8",
                               errors="replace").splitlines()
        if len(lines) > keep:
            tmp = path.with_suffix(".jsonl.tmp")
            tmp.write_text("\n".join(lines[-keep:]) + "\n",
                           encoding="utf-8")
            os.replace(tmp, path)
    except OSError:
        pass


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="RAM-ceiling exact-PID duplicate reaper (dry-run default)")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--max-kill", type=int, default=10)
    ap.add_argument("--min-age-min", type=float, default=10.0)
    ap.add_argument("--log-file", type=Path, default=DEFAULT_LOG)
    ap.add_argument("--log-keep", type=int, default=1000)
    args = ap.parse_args(argv)

    try:
        report = run_audit()
        procs = mcp_procscan.scan_processes()
        if not procs:
            raise ReapError("process snapshot empty/unavailable")
        listeners = listening_ports_by_pid()
    except ReapError as exc:
        print(f"FAILED:reap-dup {exc}")
        return 1

    plan = plan_from(
        report["findings"], procs, listeners,
        now=datetime.now(timezone.utc),
        min_age_min=args.min_age_min, max_kill=args.max_kill,
        self_pids=_self_tree(procs))

    killed: list[dict] = []
    if args.apply:
        for c in plan["kill_plan"]:
            ok = proc_registry.ProcRegistry._kill(c["pid"])
            killed.append({"pid": c["pid"], "server": c["server"],
                           "ok": bool(ok)})

    record = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": "apply" if args.apply else "dry-run",
        "candidate_total": plan["candidate_total"],
        "kill_plan": plan["kill_plan"],
        "skipped": plan["skipped"],
        "killed": killed,
        "freed_mb_plan": plan["freed_mb_plan"],
    }
    write_log(record, args.log_file, args.log_keep)

    n_ok = sum(1 for k in killed if k["ok"])
    if args.json:
        print(json.dumps({**record, "killed_ok": n_ok}))
    else:
        for c in plan["kill_plan"]:
            print(f"would-kill pid={c['pid']} server={c['server']} "
                  f"ws={c['ws_mb']}MB age={c['age_min']}m")
        for s in plan["skipped"][:20]:
            print(f"skip      pid={s['pid']} reason={s['reason']}")
    mode = (f"applied killed={n_ok}/{len(killed)}"
            if args.apply else "dry-run")
    print(f"SUCCESS:reap-dup {mode} "
          f"kill_plan={len(plan['kill_plan'])} "
          f"skipped={len(plan['skipped'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
