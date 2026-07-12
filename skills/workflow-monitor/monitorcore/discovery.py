"""Flat-Task + workflow subagent discovery (ported from agent_monitor.py).

Discovers EVERY subagent transcript a Claude Code session produces — the flat
``subagents/agent-*.jsonl`` (which the wfmon cockpit does NOT surface: its known gap) AND the
nested ``subagents/workflows/<wf>/agent-*.jsonl`` — and summarises each row with a cheap
last-event line. Pure and read-only, so it is safe against a live session and reaches 100%
branch coverage against a fixture dir with an injected clock.
"""

from __future__ import annotations

import glob
import json
import os
import time

__all__ = [
    "find_subagent_dirs",
    "last_event_summary",
    "newest_mtime",
    "pick_active_dir",
    "scan",
]

PROJECTS = os.path.expanduser(r"~/.claude/projects")


def find_subagent_dirs(projects: str = PROJECTS) -> list[str]:
    """All ``<project>/<session>/subagents`` dirs holding agent transcripts (incl. nested workflow agents)."""
    pat = os.path.join(projects, "*", "*", "subagents")
    return [
        d
        for d in glob.glob(pat)
        if glob.glob(os.path.join(d, "**", "agent-*.jsonl"), recursive=True)
    ]


def newest_mtime(d: str) -> float:
    """Most recent mtime of any ``agent-*.jsonl`` under ``d`` (recursively), or ``0.0``."""
    return max(
        (
            os.path.getmtime(p)
            for p in glob.glob(os.path.join(d, "**", "agent-*.jsonl"), recursive=True)
        ),
        default=0.0,
    )


def pick_active_dir(projects: str = PROJECTS) -> str | None:
    """The subagents dir with the most recent activity, or ``None`` if none exist."""
    dirs = find_subagent_dirs(projects)
    return max(dirs, key=newest_mtime) if dirs else None


def _one_line(s: object, width: int) -> str:
    s = " ".join(str(s).split())
    return s if len(s) <= width else s[: width - 1] + "…"


def last_event_summary(jsonl: str, width: int) -> str:
    """Cheap: read the tail and summarize the most recent meaningful event (or ``""``)."""
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
            obj = json.loads(line)
        except Exception:
            continue
        msg = obj.get("message") if isinstance(obj.get("message"), dict) else {}
        content = msg.get("content")
        blocks = (
            content
            if isinstance(content, list)
            else (
                [{"type": "text", "text": content}] if isinstance(content, str) else []
            )
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


def scan(
    subdir: str,
    active_secs: float,
    width: int,
    *,
    now: float | None = None,
) -> list[dict]:
    """Every agent transcript under ``subdir`` as a summary row, most-recently-active first.

    Each row carries the transcript path, name/type/description (from the ``.meta.json``
    sidecar), the owning workflow id (``""`` for a flat Task agent), size, age, a
    ``running`` flag (mtime within ``active_secs``), and the cheap ``last`` event line.
    ``now`` is injectable so age/running are deterministic in tests.
    """
    rows = []
    clock = time.time() if now is None else now
    for jsonl in glob.glob(os.path.join(subdir, "**", "agent-*.jsonl"), recursive=True):
        meta_p = os.path.splitext(jsonl)[0] + ".meta.json"
        meta = {}
        try:
            with open(meta_p, encoding="utf-8", errors="ignore") as fh:
                meta = json.load(fh)
        except Exception:
            pass
        mtime = os.path.getmtime(jsonl)
        age = clock - mtime
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
