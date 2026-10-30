"""Event->coloured-line mapper for ONE Claude Code subagent transcript.

Claude Code persists every Task subagent as an append-only JSONL at
``~/.claude/projects/<project>/<session>/subagents/agent-<id>.jsonl`` with a small
sidecar ``agent-<id>.meta.json`` (``{agentType, description, name, toolUseId}``).

This module renders that transcript two ways, and the difference matters:

* :func:`render` — one coloured line per event (thinking / text / tool call / tool
  result), every field collapsed to a single line and truncated to the terminal
  width. Dense, scannable, and what the boards use.
* :func:`render_detail` — the same events in full: reasoning wrapped and intact,
  every tool argument rather than the one guessed to be most informative, and
  tool output resolved from its spill file via
  :func:`resolve_persisted_output` when the transcript holds only a ~2 KB
  preview. For reading a subagent's work rather than watching its pulse.

The second exists because the first is not a substitute for it. Watching an agent
through a width-truncated feed shows commands without their reasoning and results
without their output, which leaves opening the transcript by hand as the only way
to see what actually happened. Where a cap still applies, it says how much it
withheld and where the rest is, rather than cutting silently.

It only ever READS the file, so it is safe to run against an agent the live
Claude Code instance is still writing.

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
import textwrap
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
                out.append(f"{GREY}{ts}  * {txt}{R}")
        elif t == "text":
            txt = _one_line(b.get("text", ""), body)
            if txt:
                out.append(f"{GREY}{ts}{R}  {GREEN}> {txt}{R}")
        elif t == "tool_use":
            name = b.get("name", "?")
            out.append(
                f"{GREY}{ts}{R}  {CYAN}+ {BOLD}{name}{R}{CYAN}  "
                f"{_tool_summary(name, b.get('input', {}), body)}{R}"
            )
        elif t == "tool_result":
            rc = b.get("content")
            s = rc if isinstance(rc, str) else json.dumps(rc, ensure_ascii=False)
            col = RED if b.get("is_error") else YEL
            glyph = "✗" if b.get("is_error") else "↳"
            out.append(f"{GREY}{ts}{R}  {col}{glyph}{R} {DIM}{_one_line(s, body)}{R}")
    return out


#: Default bytes of tail read by :func:`read_tail_entries`. Kept as the historical
#: value so existing callers see no change; the detail view asks for more, because
#: "I cannot see earlier output" is partly this window.
TAIL_WINDOW_BYTES = 200_000


def resolve_persisted_output(entry: dict) -> tuple[str | None, str | None]:
    """Full tool output for a spilled result: ``(text, path)``.

    Claude Code spills a large tool result to a sidecar file and leaves only a
    ~2 KB preview in the transcript, wrapped in a ``persisted-output`` notice.
    Every monitor in this repo renders that preview and stops, which is half of
    "I cannot see the previous output". The structured pointer is
    ``toolUseResult.persistedOutputPath`` — read that, rather than regexing the
    human-facing prose, which is not an interface.

    Returns ``(None, None)`` when the entry has no spill, and ``(None, path)``
    when it claims one that cannot be read — a caller should say the output is
    unavailable and name the path, never silently show the preview as if whole.
    """
    tur = entry.get("toolUseResult")
    if not isinstance(tur, dict):
        return None, None
    path = tur.get("persistedOutputPath")
    if not isinstance(path, str) or not path:
        return None, None
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read(), path
    except OSError:
        return None, path


def _wrap(text: str, width: int, gutter: str) -> list[str]:
    """Wrap text to width, preserving its own line breaks, prefixed by gutter.

    Deliberately keeps blank lines and paragraph structure: reasoning is prose,
    and collapsing it to one line is the bug this exists to fix.
    """
    width = max(20, width)
    out: list[str] = []
    for raw in str(text).splitlines() or [""]:
        if not raw.strip():
            out.append(gutter)
            continue
        # textwrap.wrap only returns [] for blank input, which the branch above
        # already took, so no empty-result fallback is needed here.
        out.extend(gutter + seg for seg in textwrap.wrap(raw, width=width))
    return out


def _capped(lines: list[str], max_lines: int | None, note: str) -> list[str]:
    """Apply a line cap, SAYING so when it bites.

    The point of this module's rewrite is that nothing is silently cut. A cap is
    still needed — a single tool result can be megabytes — so when it applies it
    announces how much was withheld and where the rest lives.
    """
    if max_lines is None or len(lines) <= max_lines:
        return lines
    kept = lines[:max_lines]
    kept.append(f"{DIM}… {len(lines) - max_lines} more line(s){note}{R}")
    return kept


def render_detail(
    entry: dict,
    width: int,
    *,
    max_lines: int | None = 400,
    resolve_persisted: bool = True,
) -> list[str]:
    """Full, wrapped, untruncated rendering of one transcript entry.

    The counterpart to :func:`render`, which is a one-line-per-event feed and
    stays as it is for the boards that want density. This one is for reading:
    reasoning in full, every tool argument rather than the single most
    informative one, and tool output resolved from its spill file when the
    transcript only holds a preview.

    ``signature`` on a thinking block is never rendered: it is opaque ciphertext,
    not text. When a block carries a signature but no thinking (older
    transcripts, where the prose was not retained) that is stated, so an empty
    reasoning pane is never mistaken for an agent that did not think.
    """
    raw_msg = entry.get("message")
    msg = raw_msg if isinstance(raw_msg, dict) else {}
    ts = fmt_ts(entry.get("timestamp"))
    content = msg.get("content")
    blocks = (
        content
        if isinstance(content, list)
        else ([{"type": "text", "text": content}] if isinstance(content, str) else [])
    )
    body = max(20, width - 4)
    out: list[str] = []
    for b in blocks:
        if not isinstance(b, dict):
            out.extend(_wrap(b, body, f"{GREY}  {R}"))
            continue
        t = b.get("type")
        if t == "thinking":
            think = b.get("thinking") or ""
            if think:
                out.append(f"{GREY}{ts}  * reasoning{R}")
                out.extend(_capped(_wrap(think, body, f"{GREY}  {R}"), max_lines, ""))
            elif b.get("signature"):
                out.append(
                    f"{GREY}{ts}  * reasoning not retained in this transcript{R}"
                )
        elif t == "text":
            txt = b.get("text") or ""
            if txt:
                out.append(f"{GREY}{ts}{R}  {GREEN}> message{R}")
                out.extend(_capped(_wrap(txt, body, f"{GREEN}  {R}"), max_lines, ""))
        elif t == "tool_use":
            name = b.get("name", "?")
            out.append(f"{GREY}{ts}{R}  {CYAN}+ {BOLD}{name}{R}")
            inp = b.get("input")
            if isinstance(inp, dict):
                for key in sorted(inp):
                    val = inp[key]
                    shown = (
                        val
                        if isinstance(val, str)
                        else json.dumps(val, ensure_ascii=False, indent=2)
                    )
                    out.append(f"{DIM}    {key}:{R}")
                    out.extend(
                        _capped(
                            _wrap(shown, body - 4, f"{DIM}      {R}"), max_lines, ""
                        )
                    )
            elif inp is not None:
                out.extend(_wrap(inp, body, f"{DIM}    {R}"))
        elif t == "tool_result":
            out.extend(
                _render_result_detail(b, entry, ts, body, max_lines, resolve_persisted)
            )
    return out


def _render_result_detail(
    block: dict,
    entry: dict,
    ts: str,
    body: int,
    max_lines: int | None,
    resolve_persisted: bool,
) -> list[str]:
    """One ``tool_result`` block, with its spilled output pulled in if there is one."""
    err = bool(block.get("is_error"))
    col = RED if err else YEL
    glyph = "✗" if err else "↳"
    rc = block.get("content")
    inline = rc if isinstance(rc, str) else json.dumps(rc, ensure_ascii=False, indent=2)
    out = [f"{GREY}{ts}{R}  {col}{glyph} result{R}"]
    note = ""
    if resolve_persisted:
        full, path = resolve_persisted_output(entry)
        if full is not None:
            inline = full
            note = f", full output at {path}"
            out.append(f"{DIM}    (resolved {len(full)} bytes from {path}){R}")
        elif path is not None:
            # Claimed a spill we could not read: say so rather than presenting
            # the truncated preview as though it were the whole result.
            out.append(f"{RED}    (persisted output unreadable: {path}){R}")
    out.extend(_capped(_wrap(inline, body, f"{DIM}    {R}"), max_lines, note))
    return out


def read_tail_entries(path: str, n: int, window: int = TAIL_WINDOW_BYTES) -> list[dict]:
    """Last n complete JSON entries (for opening backfill).

    ``window`` is how far back to read. A transcript can be hundreds of MB, so
    this stays a bounded tail rather than a full parse; pass a larger window to
    reach further back.
    """
    try:
        sz = os.path.getsize(path)
        with open(path, "rb") as fh:
            fh.seek(max(0, sz - max(1, window)))
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


def _follow_step(path, state, width, idle, *, now, out=print, renderer=None):
    """One poll iteration: emit newly-appended events; return the updated follow state.

    ``state`` is ``(pos, buf, last_event, idle_announced)``. New complete lines past ``pos``
    are parsed + rendered; a truncated/rotated file restarts from the top; a quiet stretch
    past ``idle`` seconds prints a single idle notice. A transient ``OSError`` (share lock)
    leaves the state unchanged for the next poll.

    ``renderer`` defaults to :func:`render`; pass :func:`render_detail` (or a
    partial of it) to follow with full reasoning and output.
    """
    draw = render if renderer is None else renderer
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
                for ln in draw(entry, width):
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
    path, width, poll, idle, *, sleep, now=time.time, renderer=None
) -> int:
    state = (os.path.getsize(path), b"", now(), False)
    while True:
        try:
            state = _follow_step(path, state, width, idle, now=now, renderer=renderer)
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
    ap.add_argument(
        "--detail",
        action="store_true",
        help="full reasoning and full tool output instead of one truncated line each",
    )
    ap.add_argument(
        "--max-lines",
        type=int,
        default=400,
        help="per-block line cap in --detail mode; 0 for no cap",
    )
    ap.add_argument(
        "--window",
        type=int,
        default=TAIL_WINDOW_BYTES,
        help="bytes of transcript tail to read for the backfill",
    )
    a = ap.parse_args(argv)

    if not _wait_for_file(a.jsonl, sleep=sleep):
        return 1

    cap = None if a.max_lines == 0 else a.max_lines

    def show(entry: dict) -> list[str]:
        if a.detail:
            return render_detail(entry, a.width, max_lines=cap)
        return render(entry, a.width)

    header(a.jsonl, a.width)
    if a.backfill:
        print(f"{DIM}── last {a.backfill} events ──{R}")
        for e in read_tail_entries(a.jsonl, a.backfill, a.window):
            for ln in show(e):
                print(ln)
        print(f"{DIM}── live ──{R}")

    return _follow_forever(
        a.jsonl,
        a.width,
        a.poll,
        a.idle,
        sleep=sleep,
        renderer=(lambda e, w: show(e)) if a.detail else None,
    )


if __name__ == "__main__":  # pragma: no cover -- module CLI entrypoint
    raise SystemExit(main())
