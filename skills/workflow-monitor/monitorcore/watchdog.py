"""Freeze-watchdog for Claude Code autonomous loops (ported to monitorcore).

The SSE-hang class (Claude Code issues #33949 / #25979 / #54434 — "5 stalls in 26 min",
no client-side read timeout) is upstream-unfixed. This external watchdog is the only
defense: it polls the newest subagent transcript's mtime; if it goes stale beyond
``--stale-min`` while the work is supposedly still running, it ALERTS (alert-first; ``--kill``
optional).

F4 injectable-runner refactor: :func:`alert` (a PowerShell toast) and :func:`maybe_kill`
(``taskkill`` on the ``claude.exe`` tree) take an injected ``runner`` (default
``subprocess.run``) so tests drive every branch with a FAKE runner — no real toast, no real
``taskkill`` that would kill the live ``claude.exe``. The continuous poll loop is the sole
irreducible, interactive boundary and is the only ``# pragma: no cover`` here.

Usage:
  python -m monitorcore.watchdog                    # autodetect newest subagents dir, alert
  python -m monitorcore.watchdog --dir "<path>" --stale-min 25 --poll 60
  python -m monitorcore.watchdog --kill             # also terminate the stalled child
  python -m monitorcore.watchdog --once             # single check (cron), exit 2 if frozen
"""

from __future__ import annotations

import argparse
import glob
import os
import subprocess
import sys
import time

__all__ = [
    "alert",
    "autodetect_subagents_dir",
    "check_once",
    "main",
    "maybe_kill",
    "newest_jsonl_mtime",
]

_TOAST_ARGV = [
    "powershell",
    "-NoProfile",
    "-Command",
    "[void][System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms');"
    "[System.Windows.Forms.MessageBox]::Show('Claude Code agent appears frozen "
    "(SSE hang). Send any message to revive the stream.','Watchdog')",
]


def newest_jsonl_mtime(d: str) -> tuple[str | None, float]:
    """``(path, mtime)`` of the most recently modified ``agent-*.jsonl`` under ``d``, or ``(None, 0.0)``."""
    files = glob.glob(os.path.join(d, "agent-*.jsonl"))
    if not files:
        return None, 0.0
    p = max(files, key=os.path.getmtime)
    return p, os.path.getmtime(p)


def autodetect_subagents_dir() -> str | None:
    """Pick the subagents dir with the most recent activity under ``~/.claude/projects``."""
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


def alert(msg: str, *, runner=subprocess.run) -> None:
    """Print the freeze banner and fire a best-effort Windows toast via ``runner``.

    Never fails the watchdog: any ``runner`` exception (no PowerShell, non-Windows) is swallowed.
    """
    line = "=" * 60
    print(f"\n{line}\n[WATCHDOG FREEZE ALERT] {msg}\n{line}", flush=True)
    try:
        runner(_TOAST_ARGV, timeout=5)
    except Exception:
        pass


def maybe_kill(jsonl_path: str | None, *, runner=subprocess.run) -> None:
    """Best-effort: kill the ``claude.exe`` process tree via ``runner`` (opt-in ``--kill``)."""
    try:
        runner(
            ["taskkill", "/IM", "claude.exe", "/T", "/F"],
            timeout=10,
            capture_output=True,
        )
        print("[WATCHDOG] sent taskkill to claude.exe tree", flush=True)
    except Exception as e:
        print(f"[WATCHDOG] kill failed: {e}", flush=True)


def check_once(d: str, stale_s: float) -> tuple[bool, str | None, float]:
    """Return ``(frozen, path, age_s)`` for the newest transcript under ``d``."""
    p, m = newest_jsonl_mtime(d)
    if p is None:
        return False, None, 0.0
    age = time.time() - m
    return age > stale_s, p, age


def _build_parser() -> argparse.ArgumentParser:
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
    return ap


def _watch_forever(  # pragma: no cover -- interactive continuous poll loop (no real terminal state in tests)
    d: str,
    stale_s: float,
    stale_min: float,
    *,
    kill: bool,
    poll: float,
    runner,
    sleep,
) -> int:
    alerted_for = None  # throttle: one alert per freeze episode
    while True:
        try:
            frozen, p, age = check_once(d, stale_s)
            if frozen and p != alerted_for:
                alert(
                    f"{os.path.basename(p or '?')} idle {age / 60:.1f} min (> {stale_min}). "
                    f"Send any message to revive the SSE stream.",
                    runner=runner,
                )
                if kill:
                    maybe_kill(p, runner=runner)
                alerted_for = p
            elif not frozen:
                alerted_for = None
            sleep(poll)
        except KeyboardInterrupt:
            print("\n[WATCHDOG] stopped.")
            return 0
        except Exception as e:
            print(f"[WATCHDOG] non-fatal: {e}", flush=True)
            sleep(poll)


def main(argv=None, *, runner=subprocess.run, sleep=time.sleep) -> int:
    a = _build_parser().parse_args(argv)

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
                f"{os.path.basename(p or '?')} idle {age / 60:.1f} min (> {a.stale_min}).",
                runner=runner,
            )
            if a.kill:
                maybe_kill(p, runner=runner)
            return 2
        print(f"[WATCHDOG] ok — newest activity {age:.0f}s ago")
        return 0

    return _watch_forever(
        d,
        stale_s,
        a.stale_min,
        kill=a.kill,
        poll=a.poll,
        runner=runner,
        sleep=sleep,
    )


if __name__ == "__main__":  # pragma: no cover -- module CLI entrypoint
    sys.exit(main())
