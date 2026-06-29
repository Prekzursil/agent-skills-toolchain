#!/usr/bin/env python3
"""Overview dashboard + per-terminal spawner for Claude Code subagents.

Finds the active session's subagents directory, lists every Task subagent with a
live status (RUNNING / done by mtime recency), and can open ONE terminal per
running agent — each live-tailing that agent via agent_tail.py.

Examples:
  python agent_monitor.py                 # print the table once
  python agent_monitor.py --watch         # live-refreshing dashboard (this window)
  python agent_monitor.py --spawn         # open one terminal per RUNNING agent
  python agent_monitor.py --spawn --all   # ... including finished agents
  python agent_monitor.py --spawn --tabs  # tabs in one Windows-Terminal window
  python agent_monitor.py --dir "<...\\subagents>"   # point at a specific dir
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TAIL = os.path.join(HERE, "agent_tail.py")
PROJECTS = os.path.expanduser(r"~/.claude/projects")
_NEW_CONSOLE = getattr(
    subprocess, "CREATE_NEW_CONSOLE", 0
)  # child gets its own window (Windows)

R = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREY = "\033[90m"
RED = "\033[91m"
GREEN = "\033[92m"
YEL = "\033[93m"
BLUE = "\033[94m"
MAG = "\033[95m"
CYAN = "\033[96m"


def _enable_vt() -> None:
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(
                encoding="utf-8", errors="replace"
            )  # survive cp1252 consoles
        except Exception:
            pass
    if os.name == "nt":
        try:
            import ctypes

            k = ctypes.windll.kernel32
            h = k.GetStdHandle(-11)
            mode = ctypes.c_uint32()
            if k.GetConsoleMode(h, ctypes.byref(mode)):
                k.SetConsoleMode(h, mode.value | 0x0004)
        except Exception:
            pass


def find_subagent_dirs() -> list[str]:
    """All <project>/<session>/subagents dirs with agent transcripts (incl. nested workflow agents)."""
    pat = os.path.join(PROJECTS, "*", "*", "subagents")
    return [
        d
        for d in glob.glob(pat)
        if glob.glob(os.path.join(d, "**", "agent-*.jsonl"), recursive=True)
    ]


def newest_mtime(d: str) -> float:
    return max(
        (
            os.path.getmtime(p)
            for p in glob.glob(os.path.join(d, "**", "agent-*.jsonl"), recursive=True)
        ),
        default=0.0,
    )


def pick_active_dir() -> str | None:
    dirs = find_subagent_dirs()
    return max(dirs, key=newest_mtime) if dirs else None


def _one_line(s: str, width: int) -> str:
    s = " ".join(str(s).split())
    return s if len(s) <= width else s[: width - 1] + "…"


def last_event_summary(jsonl: str, width: int) -> str:
    """Cheap: read the tail and summarize the most recent meaningful event."""
    try:
        sz = os.path.getsize(jsonl)
        with open(jsonl, "rb") as fh:
            fh.seek(max(0, sz - 40_000))
            data = fh.read().decode("utf-8", "ignore")
    except OSError:
        return ""
    for line in reversed(data.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            o = json.loads(line)
        except Exception:
            continue
        msg = o.get("message") if isinstance(o.get("message"), dict) else {}
        c = msg.get("content")
        blocks = (
            c
            if isinstance(c, list)
            else ([{"type": "text", "text": c}] if isinstance(c, str) else [])
        )
        for b in reversed(blocks):
            if not isinstance(b, dict):
                continue
            t = b.get("type")
            if t == "tool_use":
                return _one_line(
                    f"🔧 {b.get('name')} "
                    + json.dumps(b.get("input", {}), ensure_ascii=False),
                    width,
                )
            if t == "text" and b.get("text", "").strip():
                return _one_line("📝 " + b["text"], width)
            if t == "tool_result":
                rc = b.get("content")
                s = rc if isinstance(rc, str) else json.dumps(rc, ensure_ascii=False)
                return _one_line(("✗ " if b.get("is_error") else "↳ ") + s, width)
            if t == "thinking":
                return _one_line("💭 " + b.get("thinking", ""), width)
    return ""


def human_age(secs: float) -> str:
    s = int(secs)
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m{s % 60:02d}s"
    return f"{s // 3600}h{(s % 3600) // 60:02d}m"


def scan(subdir: str, active_secs: float, width: int) -> list[dict]:
    rows = []
    now = time.time()
    for jsonl in glob.glob(os.path.join(subdir, "**", "agent-*.jsonl"), recursive=True):
        meta_p = os.path.splitext(jsonl)[0] + ".meta.json"
        meta = {}
        try:
            with open(meta_p, encoding="utf-8", errors="ignore") as fh:
                meta = json.load(fh)
        except Exception:
            pass
        mtime = os.path.getmtime(jsonl)
        age = now - mtime
        # workflow agents live under subagents/workflows/<wf-id>/agent-*.jsonl
        parts = os.path.relpath(jsonl, subdir).replace("\\", "/").split("/")
        wf = parts[parts.index("workflows") + 1] if "workflows" in parts[:-1] else ""
        rows.append(
            {
                "jsonl": jsonl,
                "name": meta.get("name") or os.path.basename(jsonl)[6:14],
                "type": meta.get("agentType", "?"),
                "desc": meta.get("description", ""),
                "wf": wf,
                "size": os.path.getsize(jsonl),
                "age": age,
                "running": age <= active_secs,
                "last": last_event_summary(jsonl, max(20, width - 64)),
            }
        )
    rows.sort(key=lambda r: r["age"])  # most-recently-active first
    return rows


def print_table(rows: list[dict], subdir: str, width: int) -> None:
    sess = os.path.basename(os.path.dirname(subdir))
    running = sum(1 for r in rows if r["running"])
    wfn = sum(1 for r in rows if r.get("wf"))
    print(
        f"{BOLD}{MAG}Claude Code subagents{R}  {DIM}session {sess[:8]} · "
        f"{len(rows)} total · {R}{GREEN}{running} running{R}{DIM} · {wfn} in workflows{R}"
    )
    print(f"{DIM}{'─' * min(width, 120)}{R}")
    for r in rows:
        if r["running"]:
            dot, col = f"{GREEN}●{R}", GREEN
        else:
            dot, col = f"{GREY}○{R}", GREY
        name = f"{col}{r['name'][:18]:<18}{R}"
        age = f"{r['age'] and human_age(r['age']):>7}"
        typ = f"{DIM}{r['type'][:15]:<15}{R}"
        wf_tag = f"{CYAN}[{r['wf'][:12]}]{R} " if r.get("wf") else ""
        desc = wf_tag + r["desc"][:40]
        print(f" {dot} {name} {DIM}{age}{R} {typ} {desc}")
        if r["running"] and r["last"]:
            print(f"     {DIM}└ {r['last']}{R}")
    print(f"{DIM}{'─' * min(width, 120)}{R}")


def spawn(rows: list[dict], use_wt: bool, tabs: bool) -> int:
    py = sys.executable or "python"
    n = 0
    for r in rows:
        title = f"{r['name']}"
        if use_wt:
            if tabs:
                args = [
                    "wt",
                    "-w",
                    "agentmon",
                    "new-tab",
                    "--title",
                    title,
                    py,
                    TAIL,
                    r["jsonl"],
                ]
            else:
                args = ["wt", "-w", "new", "--title", title, py, TAIL, r["jsonl"]]
            try:
                subprocess.Popen(args, close_fds=True)
            except Exception as e:
                print(f"{RED}wt spawn failed ({e}); falling back to powershell{R}")
                use_wt = False
        if not use_wt:
            # Own console window per agent via CREATE_NEW_CONSOLE — no shell, no `start`.
            t = title.replace("'", "''")
            p = py.replace("'", "''")
            j = r["jsonl"].replace("'", "''")
            inner = f"$host.UI.RawUI.WindowTitle='{t}'; & '{p}' '{TAIL}' '{j}'"
            try:
                subprocess.Popen(
                    ["powershell", "-NoExit", "-NoProfile", "-Command", inner],
                    creationflags=_NEW_CONSOLE,
                    close_fds=True,
                )
            except (
                FileNotFoundError
            ):  # no powershell -> run the tailer directly in a new console
                subprocess.Popen(
                    [py, TAIL, r["jsonl"]], creationflags=_NEW_CONSOLE, close_fds=True
                )
        n += 1
        time.sleep(0.35)  # stagger so terminals don't race the window manager
    return n


def main() -> int:
    _enable_vt()
    ap = argparse.ArgumentParser(description="Claude Code subagent monitor / spawner.")
    ap.add_argument(
        "--dir", help="explicit <session>/subagents dir (default: most recently active)"
    )
    ap.add_argument(
        "--session", help="match a session id substring instead of auto-pick"
    )
    ap.add_argument(
        "--watch", action="store_true", help="live-refresh the dashboard in this window"
    )
    ap.add_argument(
        "--spawn", action="store_true", help="open one terminal per agent and tail it"
    )
    ap.add_argument(
        "--all", action="store_true", help="include finished agents (not just running)"
    )
    ap.add_argument(
        "--match",
        action="append",
        default=[],
        metavar="SUBSTR",
        help="spawn the most-recent agent whose name/description contains SUBSTR "
        "(repeatable; ignores the running filter)",
    )
    ap.add_argument(
        "--tabs",
        action="store_true",
        help="spawn as tabs in one Windows-Terminal window",
    )
    ap.add_argument(
        "--no-wt",
        action="store_true",
        help="force classic PowerShell windows (no wt.exe)",
    )
    ap.add_argument(
        "--active-secs",
        type=float,
        default=150.0,
        help="age under which an agent counts as running",
    )
    ap.add_argument(
        "--interval", type=float, default=2.0, help="--watch refresh seconds"
    )
    a = ap.parse_args()

    try:
        width = shutil.get_terminal_size((140, 40)).columns
    except Exception:
        width = 140

    subdir = a.dir
    if not subdir and a.session:
        cand = [d for d in find_subagent_dirs() if a.session in d]
        subdir = max(cand, key=newest_mtime) if cand else None
    if not subdir:
        subdir = pick_active_dir()
    if not subdir or not os.path.isdir(subdir):
        print(f"{RED}No subagents directory found under {PROJECTS}.{R}")
        print(f"{DIM}Spawn a Task subagent in Claude Code first, or pass --dir.{R}")
        return 1

    if a.spawn:
        rows = scan(subdir, a.active_secs, width)  # sorted most-recently-active first
        if a.match:
            targets, seen = [], set()
            for m in (x.lower() for x in a.match):
                for r in rows:  # first hit per phrase = most recent matching agent
                    if (
                        m in (r["name"] + " " + r["desc"]).lower()
                        and r["jsonl"] not in seen
                    ):
                        targets.append(r)
                        seen.add(r["jsonl"])
                        break
        else:
            targets = rows if a.all else [r for r in rows if r["running"]]
        if not targets:
            print(f"{YEL}No {'agents' if a.all else 'RUNNING agents'} in {subdir}.{R}")
            if not a.watch:
                return 0
        else:
            use_wt = bool(shutil.which("wt")) and not a.no_wt
            how = (
                "Windows-Terminal " + ("tabs" if a.tabs else "windows")
                if use_wt
                else "PowerShell windows"
            )
            print(f"{CYAN}Opening {len(targets)} {how} (one per agent)…{R}")
            spawn(targets, use_wt, a.tabs)

    if a.watch:
        try:
            while True:
                sys.stdout.write("\033[2J\033[H")  # clear + home
                print_table(scan(subdir, a.active_secs, width), subdir, width)
                print(
                    f"{DIM}refresh {a.interval}s · Ctrl-C to quit · spawn: "
                    f"python agent_monitor.py --spawn{R}"
                )
                time.sleep(a.interval)
        except KeyboardInterrupt:
            return 0
    elif not a.spawn:
        print_table(scan(subdir, a.active_secs, width), subdir, width)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
