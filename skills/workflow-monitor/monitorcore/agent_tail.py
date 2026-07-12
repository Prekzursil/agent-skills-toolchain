"""Event->coloured-line mapper for ONE Claude Code subagent transcript.

Claude Code persists every Task subagent as an append-only JSONL at
``~/.claude/projects/<project>/<session>/subagents/agent-<id>.jsonl`` with a small
sidecar ``agent-<id>.meta.json`` (``{agentType, description, name, toolUseId}``).

This module renders that transcript as clean, coloured, one-line-per-event feed lines
(thinking / text / tool call / tool result). It only ever READS the file, so it is safe
to run against an agent the live Claude Code instance is still writing.

Vendored into ``monitorcore`` (from the personal ``agent-monitor`` tool) so consumers
import it as ``monitorcore.agent_tail`` instead of a hardcoded personal-directory
sys.path hack. The wfmon cockpit uses only ``render(entry, width)`` + ``read_tail_entries(path, n)``;
``header``/``fmt_ts``/``_enable_vt`` support the standalone one-agent-per-terminal tail.
Being stdlib-only, it stays importable under a consuming skill's plain Python.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import sys
import time


# ── ANSI colors (enable VT on Windows consoles) ──────────────────────────────
def _enable_vt() -> None:
    """Enable UTF-8 output + ANSI/VT processing on Windows consoles (no-op elsewhere)."""
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(  # pyright: ignore[reportAttributeAccessIssue]
                encoding="utf-8", errors="replace"
            )  # survive cp1252 consoles
        except Exception:
            pass
    if os.name == "nt":
        try:
            import ctypes

            # ``windll`` only exists on Windows; fetch dynamically so the type
            # checker does not flag it on the (non-Windows) CI runner.
            k = getattr(ctypes, "windll").kernel32
            h = k.GetStdHandle(-11)
            mode = ctypes.c_uint32()
            if k.GetConsoleMode(h, ctypes.byref(mode)):
                k.SetConsoleMode(
                    h, mode.value | 0x0004
                )  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
        except Exception:
            pass


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


def fmt_ts(iso: str | None) -> str:
    """ISO-8601 (UTC) -> local HH:MM:SS."""
    if not iso:
        return "--:--:--"
    try:
        d = dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone()
        return d.strftime("%H:%M:%S")
    except Exception:
        return iso[-9:-1] if len(iso) > 9 else iso


def _one_line(s: object, width: int) -> str:
    s = " ".join(str(s).split())
    return s if len(s) <= width else s[: width - 1] + "…"


# tool_use input -> the single most informative argument
_KEY_ARGS = (
    "command",
    "file_path",
    "path",
    "pattern",
    "query",
    "url",
    "description",
    "prompt",
    "subagent_type",
    "old_string",
)


def _tool_summary(name: str, inp: object, width: int) -> str:
    if not isinstance(inp, dict):
        return _one_line(inp, width)
    for k in _KEY_ARGS:
        if k in inp and inp[k]:
            val = inp[k]
            return f"{DIM}{k}={R}{_one_line(val, width)}"
    return _one_line(json.dumps(inp, ensure_ascii=False), width)


def render(entry: dict, width: int) -> list[str]:
    """Turn one transcript JSON entry into 0+ printable colored lines."""
    raw_msg = entry.get("message")
    msg = raw_msg if isinstance(raw_msg, dict) else {}
    ts = fmt_ts(entry.get("timestamp"))
    content = msg.get("content")
    out: list[str] = []

    blocks = (
        content
        if isinstance(content, list)
        else ([{"type": "text", "text": content}] if isinstance(content, str) else [])
    )
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
            out.append(
                f"{GREY}{ts}{R}  {CYAN}🔧 {BOLD}{name}{R}{CYAN}  "
                f"{_tool_summary(name, b.get('input', {}), body)}{R}"
            )
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


# ── live-tail CLI (spawn target: ``python -m monitorcore.agent_tail <jsonl>``) ─
def _default_width() -> int:
    """Terminal width, defaulting to 140 when it can't be determined."""
    try:
        return shutil.get_terminal_size((140, 40)).columns
    except Exception:
        return 140


def _wait_for_file(
    path: str, *, sleep, exists=os.path.exists, limit: int = 240
) -> bool:
    """Block until ``path`` exists; return ``False`` if it never appears within ``limit`` polls."""
    waited = 0
    while not exists(path):
        if waited == 0:
            print(f"{YEL}Waiting for {path} …{R}")
        sleep(0.5)
        waited += 1
        if waited > limit:
            print(f"{RED}File never appeared: {path}{R}")
            return False
    return True


def _follow_step(path, state, width, idle, *, now, out=print):
    """One poll iteration: emit newly-appended events; return the updated follow state.

    ``state`` is ``(pos, buf, last_event, idle_announced)``. New complete lines past ``pos``
    are parsed + rendered; a truncated/rotated file restarts from the top; a quiet stretch
    past ``idle`` seconds prints a single idle notice. A transient ``OSError`` (share lock)
    leaves the state unchanged for the next poll.
    """
    pos, buf, last_event, idle_announced = state
    try:
        sz = os.path.getsize(path)
        if sz < pos:  # file truncated / rotated -> restart from top
            pos, buf = 0, b""
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
                for ln in render(entry, width):
                    out(ln)
                    last_event = now()
                    idle_announced = False
        elif not idle_announced and (now() - last_event) > idle:
            age = int(now() - last_event)
            out(f"{DIM}… idle {age}s (no new events; agent may be done or thinking){R}")
            idle_announced = True
    except OSError:
        pass  # transient share/lock; retry next poll
    return (pos, buf, last_event, idle_announced)


def _follow_forever(  # pragma: no cover -- interactive live poll loop (no real terminal state in tests)
    path, width, poll, idle, *, sleep, now=time.time
) -> int:
    state = (os.path.getsize(path), b"", now(), False)
    while True:
        try:
            state = _follow_step(path, state, width, idle, now=now)
        except KeyboardInterrupt:
            print(f"\n{DIM}stopped watching{R}")
            return 0
        sleep(poll)


def main(argv=None, *, sleep=time.sleep) -> int:
    """Live pretty-tail of one subagent transcript (header + backfill + follow loop)."""
    _enable_vt()
    ap = argparse.ArgumentParser(
        description="Live pretty-tail of one Claude Code subagent."
    )
    ap.add_argument("jsonl", help="path to agent-<id>.jsonl")
    ap.add_argument(
        "--backfill", type=int, default=8, help="recent events to show on open"
    )
    ap.add_argument("--poll", type=float, default=0.6, help="poll interval seconds")
    ap.add_argument(
        "--idle",
        type=float,
        default=20.0,
        help="seconds of silence before an idle notice",
    )
    ap.add_argument("--width", type=int, default=_default_width())
    a = ap.parse_args(argv)

    if not _wait_for_file(a.jsonl, sleep=sleep):
        return 1

    header(a.jsonl, a.width)
    if a.backfill:
        print(f"{DIM}── last {a.backfill} events ──{R}")
        for e in read_tail_entries(a.jsonl, a.backfill):
            for ln in render(e, a.width):
                print(ln)
        print(f"{DIM}── live ──{R}")

    return _follow_forever(a.jsonl, a.width, a.poll, a.idle, sleep=sleep)


if __name__ == "__main__":  # pragma: no cover -- module CLI entrypoint
    raise SystemExit(main())
