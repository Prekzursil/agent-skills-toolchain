#!/usr/bin/env python
"""Freeze-watchdog for Claude Code autonomous loops.

The SSE-hang class (Claude Code issues #33949 / #25979 / #54434 — "5 stalls in 26 min",
no client-side read timeout) is upstream-unfixed. This external watchdog is the only
defense: it polls the newest subagent transcript's mtime; if it goes stale beyond
--stale-min while the work is supposedly still running, it ALERTS (alert-first; --kill
optional). Reuses the mtime-liveness primitive from agent_monitor.py.

Usage:
  python watchdog.py                       # autodetect newest subagents dir, 25-min stale, alert
  python watchdog.py --dir "<path>" --stale-min 25 --poll 60
  python watchdog.py --kill                # also terminate the stalled child (default: alert only)
  python watchdog.py --once                # single check (for cron/scripts), exit 2 if frozen
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
import time


def newest_jsonl_mtime(d: str):
    """(path, mtime) of the most recently modified agent-*.jsonl under d, or (None, 0)."""
    files = glob.glob(os.path.join(d, "agent-*.jsonl"))
    if not files:
        return None, 0.0
    p = max(files, key=os.path.getmtime)
    return p, os.path.getmtime(p)


def autodetect_subagents_dir():
    """Pick the subagents dir with the most recent activity under ~/.claude/projects."""
    base = os.path.join(os.path.expanduser("~"), ".claude", "projects")
    cands = glob.glob(os.path.join(base, "*", "*", "subagents")) + glob.glob(
        os.path.join(base, "*", "*", "subagents", "workflows", "*")
    )
    best, best_m = None, -1.0
    for d in cands:
        _, m = newest_jsonl_mtime(d)
        if m > best_m:
            best, best_m = d, m
    return best


def alert(msg: str):
    line = "=" * 60
    print(f"\n{line}\n[WATCHDOG FREEZE ALERT] {msg}\n{line}", flush=True)
    # best-effort Windows toast; never fail the watchdog if it's unavailable
    try:
        import subprocess

        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "[void][System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms');"
                "[System.Windows.Forms.MessageBox]::Show('Claude Code agent appears frozen "
                "(SSE hang). Send any message to revive the stream.','Watchdog')",
            ],
            timeout=5,
        )
    except Exception:
        pass


def maybe_kill(jsonl_path: str):
    """Best-effort: kill the claude process tree (opt-in). A new user message also revives the stream."""
    try:
        import subprocess

        subprocess.run(
            ["taskkill", "/IM", "claude.exe", "/T", "/F"],
            timeout=10,
            capture_output=True,
        )
        print("[WATCHDOG] sent taskkill to claude.exe tree", flush=True)
    except Exception as e:
        print(f"[WATCHDOG] kill failed: {e}", flush=True)


def check_once(d: str, stale_s: float):
    """Return (frozen: bool, path, age_s)."""
    p, m = newest_jsonl_mtime(d)
    if p is None:
        return False, None, 0.0
    age = time.time() - m
    return age > stale_s, p, age


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=None, help="subagents dir (default: autodetect)")
    ap.add_argument("--stale-min", type=float, default=25.0)
    ap.add_argument("--poll", type=float, default=60.0)
    ap.add_argument(
        "--kill",
        action="store_true",
        help="also terminate the stalled child (default: alert only)",
    )
    ap.add_argument(
        "--once", action="store_true", help="single check then exit (2 if frozen)"
    )
    a = ap.parse_args()

    d = a.dir or autodetect_subagents_dir()
    if not d or not os.path.isdir(d):
        print(
            "[WATCHDOG] no subagents dir found — pass --dir <path>. Nothing to watch."
        )
        return 1
    stale_s = a.stale_min * 60.0
    print(
        f"[WATCHDOG] watching {d} | stale>{a.stale_min}min | poll={a.poll}s | kill={a.kill}"
    )

    if a.once:
        frozen, p, age = check_once(d, stale_s)
        if frozen:
            alert(
                f"{os.path.basename(p or '?')} idle {age / 60:.1f} min (> {a.stale_min})."
            )
            if a.kill:
                maybe_kill(p)
            return 2
        print(f"[WATCHDOG] ok — newest activity {age:.0f}s ago")
        return 0

    alerted_for = None  # throttle: one alert per freeze episode
    while True:
        try:
            frozen, p, age = check_once(d, stale_s)
            if frozen and p != alerted_for:
                alert(
                    f"{os.path.basename(p or '?')} idle {age / 60:.1f} min (> {a.stale_min}). "
                    f"Send any message to revive the SSE stream."
                )
                if a.kill:
                    maybe_kill(p)
                alerted_for = p
            elif not frozen:
                alerted_for = None  # reset once activity resumes
            time.sleep(a.poll)
        except KeyboardInterrupt:
            print("\n[WATCHDOG] stopped.")
            return 0
        except Exception as e:
            print(f"[WATCHDOG] non-fatal: {e}", flush=True)
            time.sleep(a.poll)


if __name__ == "__main__":
    sys.exit(main())
