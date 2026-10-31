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
from collections.abc import Iterator

__all__ = [
    "ERROR_GLYPH",
    "find_subagent_dirs",
    "last_event_summary",
    "newest_mtime",
    "pick_active_dir",
    "scan",
]

PROJECTS = os.path.expanduser(r"~/.claude/projects")

#: The prefix :func:`last_event_summary` puts on a FAILED ``tool_result``. Exported because
#: :mod:`monitorcore.agents_source` classifies a row as errored by testing for it — a
#: consumer coupled to a producer's literal must read the literal, not re-type it.
ERROR_GLYPH = "✗"


def _iter_transcripts(root: str) -> Iterator[os.DirEntry[str]]:
    """Lazily yield every ``agent-*.jsonl`` :class:`os.DirEntry` under ``root``, recursively.

    ``os.scandir`` rather than ``glob('**/agent-*.jsonl', recursive=True)`` for two reasons,
    both measured on this box (12,492 transcripts across 39 session dirs):

    1. **The entry carries a cached stat.** On Windows the directory enumeration already
       returns size and mtime, so :meth:`os.DirEntry.stat` costs no extra syscall — where the
       glob form paid a separate ``os.path.getmtime``/``getsize`` per file.
    2. **It is lazy.** A caller that only needs to know *whether* a transcript exists stops at
       the first yield instead of materialising the whole nested tree.

    An unreadable/absent directory is skipped rather than raised: discovery runs against a
    LIVE session tree where a session dir can vanish mid-walk, and a monitor that dies because
    one directory disappeared is worse than one that reports the rest.
    """
    stack = [root]
    while stack:
        try:
            entries = list(os.scandir(stack.pop()))
        except OSError:
            continue
        for e in entries:
            if e.name.startswith("agent-") and e.name.endswith(".jsonl"):
                yield e
            elif e.is_dir(follow_symlinks=False):
                stack.append(e.path)


def _subagent_dir_candidates(projects: str) -> list[str]:
    """The ``<project>/<session>/subagents`` paths, without inspecting their contents.

    Kept as a plain ``glob`` — the pattern is non-recursive (two single-star segments), so it
    enumerates a bounded number of directories and never descends into transcript trees.
    """
    return glob.glob(os.path.join(projects, "*", "*", "subagents"))


def find_subagent_dirs(projects: str = PROJECTS) -> list[str]:
    """All ``<project>/<session>/subagents`` dirs holding agent transcripts (incl. nested workflow agents)."""
    return [d for d in _subagent_dir_candidates(projects) if any(_iter_transcripts(d))]


def newest_mtime(d: str) -> float:
    """Most recent mtime of any ``agent-*.jsonl`` under ``d`` (recursively), or ``0.0``."""
    return max((e.stat().st_mtime for e in _iter_transcripts(d)), default=0.0)


def pick_active_dir(projects: str = PROJECTS) -> str | None:
    """The subagents dir with the most recent activity, or ``None`` if none exist.

    ONE walk per candidate dir. The retired implementation called
    :func:`find_subagent_dirs` (a full recursive walk per dir, to answer a yes/no question)
    and then :func:`newest_mtime` as a ``max`` key (a second full recursive walk per dir).
    Measured on the 4-directory fixture in ``test_pick_active_dir_walks_each_dir_exactly_once``
    that was **27** directory enumerations where 8 suffice.

    A dir with no transcripts has ``newest == 0.0`` and can never win, so the non-emptiness
    filter is subsumed by the mtime comparison — ``None`` still comes back when nothing is
    found, because ``best`` is only ever assigned from a dir that yielded a transcript.
    """
    best: str | None = None
    best_mtime = 0.0
    for d in _subagent_dir_candidates(projects):
        newest = 0.0
        found = False
        for e in _iter_transcripts(d):
            found = True
            m = e.stat().st_mtime
            if m > newest:
                newest = m
        if found and (best is None or newest > best_mtime):
            best, best_mtime = d, newest
    return best


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
                    f"+ {b.get('name')} "
                    + json.dumps(b.get("input", {}), ensure_ascii=False),
                    width,
                )
            if t == "text" and b.get("text", "").strip():
                return _one_line("> " + b["text"], width)
            if t == "tool_result":
                rc = b.get("content")
                s = rc if isinstance(rc, str) else json.dumps(rc, ensure_ascii=False)
                return _one_line(
                    (f"{ERROR_GLYPH} " if b.get("is_error") else "↳ ") + s, width
                )
            if t == "thinking":
                return _one_line("* " + b.get("thinking", ""), width)
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
    for entry in _iter_transcripts(subdir):
        jsonl = entry.path
        meta_p = os.path.splitext(jsonl)[0] + ".meta.json"
        meta = {}
        try:
            with open(meta_p, encoding="utf-8", errors="ignore") as fh:
                meta = json.load(fh)
        except Exception:
            pass
        # One cached stat off the directory entry, not a getmtime + getsize pair.
        st = entry.stat()
        mtime = st.st_mtime
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
                "size": st.st_size,
                "age": age,
                "running": age <= active_secs,
                "last": last_event_summary(jsonl, max(20, width - 64)),
            }
        )
    # Most-recently-active first. Path is the tiebreak so equal-age rows render in a stable
    # order: directory-enumeration order is not guaranteed, and a board whose rows reshuffle
    # between frames reads as activity that did not happen.
    rows.sort(key=lambda r: (r["age"], r["jsonl"]))
    return rows
