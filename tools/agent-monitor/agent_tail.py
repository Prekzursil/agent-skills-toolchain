#!/usr/bin/env python3
"""Live, read-only pretty-tail of ONE Claude Code subagent transcript.

Claude Code persists every Task subagent as an append-only JSONL at
  ~/.claude/projects/<project>/<session>/subagents/agent-<id>.jsonl
with a small sidecar agent-<id>.meta.json ({agentType, description, name, toolUseId}).

This renders that transcript as a clean, colored, realtime feed — one line per
event (thinking / text / tool call / tool result). It only ever READS the file,
so it is safe to run against an agent that the live Claude Code instance is
still writing, and it sidesteps the glitchy inline TUI entirely.

Usage:
  python agent_tail.py <path-to-agent-*.jsonl> [--backfill N] [--poll S] [--width W]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time

# ── ANSI colors (enable VT on Windows consoles) ──────────────────────────────
def _enable_vt() -> None:
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")  # survive cp1252 consoles
        except Exception:
            pass
    if os.name == "nt":
        try:
            import ctypes
            k = ctypes.windll.kernel32
            h = k.GetStdHandle(-11)
            mode = ctypes.c_uint32()
            if k.GetConsoleMode(h, ctypes.byref(mode)):
                k.SetConsoleMode(h, mode.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
        except Exception:
            pass


R = "\033[0m"; BOLD = "\033[1m"; DIM = "\033[2m"
GREY = "\033[90m"; RED = "\033[91m"; GREEN = "\033[92m"
YEL = "\033[93m"; BLUE = "\033[94m"; MAG = "\033[95m"; CYAN = "\033[96m"


def fmt_ts(iso: str | None) -> str:
    """ISO-8601 (UTC) -> local HH:MM:SS."""
    if not iso:
        return "--:--:--"
    try:
        d = dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone()
        return d.strftime("%H:%M:%S")
    except Exception:
        return iso[-9:-1] if len(iso) > 9 else iso


def _one_line(s: str, width: int) -> str:
    s = " ".join(str(s).split())
    return s if len(s) <= width else s[: width - 1] + "…"


# tool_use input -> the single most informative argument
_KEY_ARGS = ("command", "file_path", "path", "pattern", "query", "url",
             "description", "prompt", "subagent_type", "old_string")


def _tool_summary(name: str, inp: dict, width: int) -> str:
    if not isinstance(inp, dict):
        return _one_line(inp, width)
    for k in _KEY_ARGS:
        if k in inp and inp[k]:
            val = inp[k]
            return f"{DIM}{k}={R}{_one_line(val, width)}"
    return _one_line(json.dumps(inp, ensure_ascii=False), width)


def render(entry: dict, width: int) -> list[str]:
    """Turn one transcript JSON entry into 0+ printable colored lines."""
    msg = entry.get("message") if isinstance(entry.get("message"), dict) else {}
    ts = fmt_ts(entry.get("timestamp"))
    content = msg.get("content")
    out: list[str] = []

    blocks = content if isinstance(content, list) else ([{"type": "text", "text": content}]
                                                        if isinstance(content, str) else [])
    body = max(20, width - 16)
    for b in blocks:
        if not isinstance(b, dict):
            out.append(f"{GREY}{ts}{R}  {_one_line(b, body)}")
            continue
        t = b.get("type")
        if t == "thinking":
            txt = _one_line(b.get("thinking", ""), body)
            if txt:
                out.append(f"{GREY}{ts}  💭 {txt}{R}")
        elif t == "text":
            txt = _one_line(b.get("text", ""), body)
            if txt:
                out.append(f"{GREY}{ts}{R}  {GREEN}📝 {txt}{R}")
        elif t == "tool_use":
            name = b.get("name", "?")
            out.append(f"{GREY}{ts}{R}  {CYAN}🔧 {BOLD}{name}{R}{CYAN}  "
                       f"{_tool_summary(name, b.get('input', {}), body)}{R}")
        elif t == "tool_result":
            rc = b.get("content")
            s = rc if isinstance(rc, str) else json.dumps(rc, ensure_ascii=False)
            col = RED if b.get("is_error") else YEL
            glyph = "✗" if b.get("is_error") else "↳"
            out.append(f"{GREY}{ts}{R}  {col}{glyph}{R} {DIM}{_one_line(s, body)}{R}")
    return out


def read_tail_entries(path: str, n: int) -> list[dict]:
    """Last n complete JSON entries (for opening backfill)."""
    try:
        sz = os.path.getsize(path)
        with open(path, "rb") as fh:
            fh.seek(max(0, sz - 200_000))
            data = fh.read().decode("utf-8", "ignore")
    except OSError:
        return []
    rows = []
    for line in data.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows[-n:]


def load_meta(jsonl_path: str) -> dict:
    meta = os.path.splitext(jsonl_path)[0] + ".meta.json"
    try:
        with open(meta, encoding="utf-8", errors="ignore") as fh:
            return json.load(fh)
    except Exception:
        return {}


def header(jsonl_path: str, width: int) -> None:
    m = load_meta(jsonl_path)
    name = m.get("name") or os.path.basename(jsonl_path)
    bar = "═" * min(width, 100)
    print(f"{BOLD}{MAG}{bar}{R}")
    print(f"{BOLD}{MAG}║ {name}{R}  {DIM}({m.get('agentType', 'agent')}){R}")
    if m.get("description"):
        print(f"{MAG}║{R} {m['description']}")
    print(f"{DIM}║ {os.path.basename(jsonl_path)}{R}")
    print(f"{BOLD}{MAG}{bar}{R}")


def main() -> int:
    _enable_vt()
    ap = argparse.ArgumentParser(description="Live pretty-tail of one Claude Code subagent.")
    ap.add_argument("jsonl", help="path to agent-<id>.jsonl")
    ap.add_argument("--backfill", type=int, default=8, help="recent events to show on open")
    ap.add_argument("--poll", type=float, default=0.6, help="poll interval seconds")
    ap.add_argument("--idle", type=float, default=20.0, help="seconds of silence before an idle notice")
    try:
        import shutil
        default_w = shutil.get_terminal_size((140, 40)).columns
    except Exception:
        default_w = 140
    ap.add_argument("--width", type=int, default=default_w)
    a = ap.parse_args()

    path = a.jsonl
    # Wait for the file to appear (agent may not have written yet).
    waited = 0
    while not os.path.exists(path):
        if waited == 0:
            print(f"{YEL}Waiting for {path} …{R}")
        time.sleep(0.5); waited += 1
        if waited > 240:
            print(f"{RED}File never appeared: {path}{R}"); return 1

    header(path, a.width)
    if a.backfill:
        print(f"{DIM}── last {a.backfill} events ──{R}")
        for e in read_tail_entries(path, a.backfill):
            for ln in render(e, a.width):
                print(ln)
        print(f"{DIM}── live ──{R}")

    # Seek to current EOF, then poll for appended bytes.
    buf = b""
    pos = os.path.getsize(path)
    last_event = time.time()
    idle_announced = False
    while True:
        try:
            sz = os.path.getsize(path)
            if sz < pos:          # file truncated / rotated -> restart from top
                pos = 0; buf = b""
            if sz > pos:
                with open(path, "rb") as fh:
                    fh.seek(pos)
                    chunk = fh.read()
                pos = sz
                buf += chunk
                *lines, buf = buf.split(b"\n")
                for raw in lines:
                    raw = raw.strip()
                    if not raw.startswith(b"{"):
                        continue
                    try:
                        entry = json.loads(raw.decode("utf-8", "ignore"))
                    except Exception:
                        continue
                    for ln in render(entry, a.width):
                        print(ln, flush=True)
                        last_event = time.time(); idle_announced = False
            else:
                if not idle_announced and (time.time() - last_event) > a.idle:
                    age = int(time.time() - last_event)
                    print(f"{DIM}… idle {age}s (no new events; agent may be done or thinking){R}",
                          flush=True)
                    idle_announced = True
        except KeyboardInterrupt:
            print(f"\n{DIM}stopped watching{R}"); return 0
        except OSError:
            pass  # transient share/lock; retry next poll
        time.sleep(a.poll)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
