"""Schema-agnostic timeline IR — the ordered event stream renderers consume.

These symbols are PURE and domain-neutral: they operate on already-parsed event
records / plain strings and carry zero back-dependency on the Claude-Code manifest
readers (``WFAgent``/``WFRun``/``parse_manifest`` …) that live in the wfmon adapter.
They are the shared vocabulary the generic export renderers read.

- ``TimelineEvent`` — one ordered event (thinking / text / tool_use / tool_result).
- ``_flatten_content`` — total, never-raising flatten of a tool_result payload → text.
- ``report_headline`` — the one-line title of a report body.
- ``pair_tool_calls`` — nest each ``tool_result`` under its originating ``tool_use``.

The wfmon adapter's transcript readers (``agent_timeline``/``agent_task``) build
``TimelineEvent`` streams and re-export these symbols for back-compat.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class TimelineEvent:
    """One ordered event drilled out of an agent transcript (assistant + user records).

    ``kind`` ∈ {'thinking', 'text', 'tool_use', 'tool_result'}; ``seq`` is the 0-based
    emission index in file order (the stable pairing/ordering key for renderers).
    """

    kind: str
    seq: int
    text: str = ""  # thinking / text
    name: str = ""  # tool_use
    tool_input: dict = field(default_factory=dict)  # tool_use
    tool_id: str = ""  # tool_use.id OR tool_result.tool_use_id (the pairing key)
    output: str = ""  # tool_result (flattened content)
    is_error: bool = False  # tool_result


def _flatten_content(content) -> str:
    """Flatten a tool_result / advisor content payload to text. Pure, total (never raises).

    ``str`` → passthrough; ``list`` → per block ({type:text,text} → text, any other → json.dumps),
    joined with newlines; ``dict`` → normalized to a single-element list then reuse the list path
    (so the real ``advisor_tool_result`` {type:text,text} dict yields its text, arbitrary dicts → json);
    anything else → ``str(content)``.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        content = [content]
    if isinstance(content, list):
        parts = []
        for b in content:
            if isinstance(b, dict) and b.get("type") == "text":
                parts.append(str(b.get("text", "")))
            else:
                parts.append(json.dumps(b, ensure_ascii=False))
        return "\n".join(parts)
    return str(content)


def report_headline(text: str) -> str:
    """First markdown heading (the report title), else first non-empty line — good for a one-line id."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return ""
    head = next((ln for ln in lines if ln.lstrip().startswith("#")), lines[0])
    return head.lstrip("# ").strip()


def pair_tool_calls(
    events: list[TimelineEvent],
) -> list[tuple[TimelineEvent, TimelineEvent | None]]:
    """One ``(tool_use, tool_result_or_None)`` pair per tool_use, in file order.

    Matched by ``tool_id`` to the first later ``tool_result`` with the same id (``None`` = orphan /
    run ended first). Pure. Renderers derive ``{u.tool_id: r for u, r in pair_tool_calls(tl)}`` to
    nest each result under its use and skip the standalone tool_result while iterating the timeline.
    """
    results = [e for e in events if e.kind == "tool_result"]
    pairs: list[tuple[TimelineEvent, TimelineEvent | None]] = []
    for e in events:
        if e.kind != "tool_use":
            continue
        match = next(
            (r for r in results if r.tool_id == e.tool_id and r.seq > e.seq), None
        )
        pairs.append((e, match))
    return pairs
