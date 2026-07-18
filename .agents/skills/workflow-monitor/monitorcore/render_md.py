"""Generic Markdown renderer — turns a :class:`~monitorcore.report_doc.ReportDoc` into a
single, self-contained Markdown document.

``render_md(doc)`` is a total function of its ``ReportDoc`` argument: it opens no files,
mutates no globals, and is idempotent for a given ``doc`` + flags. Every free-form
string carried by a block (task, output, timeline text, tool input/output, redactable
``Text``/``Code``) is routed through ``Redactor`` then the ``textsafe`` helpers
(``strip_ansi`` → ``elide_base64`` → ``truncate_block`` → ``safe_fence``) *in the render
path*; a single ``Redactor`` is threaded so the audit banner reports the real mask
count. Structural metadata (headings, labels, group titles) is sanitised for its target
syntax but never counted as redactable content.

Document shape (wfmon's, generalised over ``ReportDoc``): YAML front-matter from
``doc.meta`` · an ``H1`` title · a redaction audit banner (+ an active-run banner) · a
rollup line · an anchor table-of-contents · a ``mermaid`` fan-out graph with an ASCII
fallback · then the body blocks (group ``Section`` s render as phases of entity cards;
the generic ``Heading``/``Text``/``Code``/``KV``/``Table`` primitives render inline).
"""

from __future__ import annotations

import json
import re

from .redact import Redactor
from .report_doc import Block, Code, Heading, KV, ReportDoc, Section, Table, Text
from .textsafe import (
    TOOL_OUTPUT_CAP,
    elide_base64,
    safe_fence,
    strip_ansi,
    truncate_block,
)
from .timeline import TimelineEvent, pair_tool_calls

# ``TOOL_OUTPUT_CAP`` is the shared per-artifact byte cap defined once in ``textsafe`` and
# re-exported here for back-compat (``from monitorcore.render_md import TOOL_OUTPUT_CAP``).

_WS_RE = re.compile(r"\s+")


# ───────────────────────── small pure helpers ─────────────────────────
def _inline(s: str) -> str:
    """Collapse a structural string to a single safe line (headings / TOC / ASCII)."""
    return _WS_RE.sub(" ", strip_ansi(s)).strip()


def _mm(s: str) -> str:
    """Sanitise a label for a mermaid ``["..."]`` node: drop quotes + newlines."""
    return _WS_RE.sub(" ", strip_ansi(s).replace('"', "'")).strip()[:80]


def _fence_block(text: str, red: Redactor) -> str:
    """Redact + ansi-strip + base64-elide + truncate ``text``, then wrap in a safe fence."""
    body = truncate_block(elide_base64(strip_ansi(red(text))), TOOL_OUTPUT_CAP)
    fence = safe_fence(body)
    return f"{fence}\n{body}\n{fence}"


def _blockquote(text: str, red: Redactor) -> str:
    """Render ``text`` as a redacted, ansi-stripped Markdown blockquote."""
    clean = strip_ansi(red(text))
    return "\n".join("> " + ln for ln in clean.splitlines()) or "> "


def _one_line(text: str, red: Redactor) -> str:
    """First non-empty (redacted) line of ``text`` — the tool ``summary`` view."""
    body = truncate_block(elide_base64(strip_ansi(red(text))), TOOL_OUTPUT_CAP)
    for ln in body.splitlines():
        if ln.strip():
            return ln.strip()
    return ""


# ───────────────────────── front-matter + banners ─────────────────────────
def _front_matter(doc: ReportDoc) -> str:
    lines = ["---"]
    for key, value in doc.meta:
        lines.append(f"{key}: {json.dumps(str(value))}")
    lines.append("---")
    return "\n".join(lines)


def _redaction_banner(redact: bool, count: int) -> str:
    if redact:
        return f"> **redaction: strict** - {count} masked"
    return "> **redaction: off** - secrets NOT masked (`--no-redact`)"


def _rollup_line(doc: ReportDoc) -> str:
    r = dict(doc.rollup)
    return (
        f"**Agents:** {r['total']} total - {r['done']} done - {r['error']} error - "
        f"{r['running']} running - {r['idle']} idle - {r['tokens']:,} tokens"
    )


# ───────────────────────── groups / cards helpers ─────────────────────────
def _groups(doc: ReportDoc) -> list[Section]:
    """The top-level group sections (phases) — TOC + fan-out are derived from these."""
    return [b for b in doc.blocks if isinstance(b, Section) and not b.card]


# ───────────────────────── table of contents ─────────────────────────
def _toc(doc: ReportDoc) -> str:
    lines = ["## Contents", ""]
    for group in _groups(doc):
        lines.append(f"- [{_inline(group.title)}](#{group.anchor})")
        for card in group.children:
            if isinstance(card, Section):
                lines.append(f"  - [{_inline(card.title)}](#{card.anchor})")
    return "\n".join(lines)


# ───────────────────────── fan-out DAG ─────────────────────────
def _fanout(doc: ReportDoc) -> str:
    groups = _groups(doc)
    stmts: list[str] = []
    for group in groups:
        stmts.append(f'P{group.index}["{_mm(group.title)}"]')
    for a, b in zip(groups, groups[1:]):
        stmts.append(f"P{a.index} --> P{b.index}")
    counter = 0
    for group in groups:
        for card in group.children:
            if isinstance(card, Section):
                stmts.append(f'P{group.index} --> A{counter}["{_mm(card.title)}"]')
                counter += 1

    if stmts:
        inner = "flowchart TD; " + stmts[0]
        if len(stmts) > 1:
            inner += "\n" + "\n".join("    " + s for s in stmts[1:])
    else:
        inner = "flowchart TD"
    mermaid = f"```mermaid\n{inner}\n```"

    ascii_lines: list[str] = []
    for group in groups:
        ascii_lines.append(_inline(group.title))
        cards = [c for c in group.children if isinstance(c, Section)]
        for j, card in enumerate(cards):
            connector = "└─" if j == len(cards) - 1 else "├─"
            ascii_lines.append(f"{connector} {_inline(card.title)} [{card.badge}]")
    ascii_block = "```\n" + "\n".join(ascii_lines) + "\n```" if ascii_lines else ""

    parts = ["## Fan-out", "", mermaid]
    if ascii_block:
        parts += ["", "_Text fallback:_", ascii_block]
    return "\n".join(parts)


# ───────────────────────── tool blocks ─────────────────────────
def _fmt_input(tool_input: dict) -> str:
    if not tool_input:
        return ""
    try:
        return json.dumps(tool_input, ensure_ascii=False, indent=2)
    except (TypeError, ValueError):
        return str(tool_input)


def _tool_full(use: TimelineEvent, result: TimelineEvent | None, red: Redactor) -> str:
    name = use.name or "tool"
    err = result is not None and result.is_error
    head = f"<summary>🔧 {name}" + (" - error" if err else "") + "</summary>"
    lines = ["<details>", head, ""]
    inp = _fmt_input(use.tool_input)
    if inp:
        lines += ["Input:", _fence_block(inp, red), ""]
    if result is None:
        lines.append("_(no result)_")
    elif not strip_ansi(red(result.output)).strip():
        lines.append("_(no output)_")
    else:
        lines += ["Output:", _fence_block(result.output, red)]
    lines.append("</details>")
    return "\n".join(lines)


def _tool_summary(
    use: TimelineEvent, result: TimelineEvent | None, red: Redactor
) -> str:
    name = use.name or "tool"
    if result is None:
        detail = "_(no result)_"
    else:
        one = _one_line(result.output, red)
        if not one:
            detail = "_(no output)_"
        elif result.is_error:
            detail = f"error: {one}"
        else:
            detail = one
    return f"- **{name}** -> {detail}"


# ───────────────────────── per-card + per-group ─────────────────────────
def _timeline(
    events: tuple[TimelineEvent, ...], red: Redactor, *, tools: str, thinking: bool
) -> str:
    results_by_id = {u.tool_id: r for u, r in pair_tool_calls(list(events))}
    parts: list[str] = []
    for e in events:
        if e.kind == "thinking":
            if thinking and e.text.strip():
                parts.append("*thinking:*")
                parts.append(_fence_block(e.text, red))
        elif e.kind == "text":
            if e.text.strip():
                parts.append(_fence_block(e.text, red))
        elif e.kind == "tool_use":
            if tools == "none":
                continue
            result = results_by_id.get(e.tool_id)
            if tools == "summary":
                parts.append(_tool_summary(e, result, red))
            else:
                parts.append(_tool_full(e, result, red))
        # standalone tool_result events are nested via pairing above; skip here.
    return "\n\n".join(parts)


def _card(card: Section, red: Redactor, *, tools: str, thinking: bool) -> str:
    state = _inline(card.badge) or "idle"
    lines = [f'### <a id="{card.anchor}"></a>{_inline(card.title)} - {state}']
    meta = []
    if card.model:
        meta.append(f"`{_inline(card.model)}`")
    meta.append(f"{card.tokens:,} tokens")
    meta.append(f"{card.tool_calls} tool calls")
    if card.attempt and card.attempt != 1:
        meta.append(f"attempt {card.attempt}")
    lines.append(" - ".join(meta))
    if card.lead.strip():
        lines.append(f"_{_inline(card.lead)}_")

    lines.append("")
    lines.append("**Task:**")
    if card.task.strip():
        lines.append(_blockquote(card.task, red))
    else:
        lines.append("_(no task)_")

    tl = _timeline(card.timeline, red, tools=tools, thinking=thinking)
    if tl:
        lines += ["", "**Transcript:**", "", tl]

    lines += ["", "**Output:**"]
    if card.output.strip():
        lines.append(_fence_block(card.output, red))
    else:
        lines.append("_(no output)_")
    return "\n".join(lines)


def _group(group: Section, red: Redactor, *, tools: str, thinking: bool) -> str:
    lines = [f'## <a id="{group.anchor}"></a>{_inline(group.title)}']
    for card in group.children:
        lines += ["", _render_block(card, red, tools=tools, thinking=thinking)]
    return "\n".join(lines)


# ───────────────────────── generic block primitives ─────────────────────────
def _kv(block: KV) -> str:
    return "\n".join(f"- **{_inline(k)}:** {_inline(v)}" for k, v in block.pairs)


def _table(block: Table) -> str:
    head = "| " + " | ".join(_inline(h) for h in block.headers) + " |"
    sep = "| " + " | ".join("---" for _ in block.headers) + " |"
    body = ["| " + " | ".join(_inline(c) for c in row) + " |" for row in block.rows]
    return "\n".join([head, sep, *body])


def _render_block(block: Block, red: Redactor, *, tools: str, thinking: bool) -> str:
    if isinstance(block, Section):
        if block.card:
            return _card(block, red, tools=tools, thinking=thinking)
        return _group(block, red, tools=tools, thinking=thinking)
    if isinstance(block, Heading):
        anchor = f'<a id="{block.anchor}"></a>' if block.anchor else ""
        return f"{'#' * block.level} {anchor}{_inline(block.text)}"
    if isinstance(block, Text):
        content = red(block.text) if block.redact else block.text
        clean = strip_ansi(content)
        if block.variant == "blockquote":
            return "\n".join("> " + ln for ln in clean.splitlines()) or "> "
        if block.variant == "emphasis":
            return f"_{_inline(clean)}_"
        return clean
    if isinstance(block, Code):
        label = f"*{_inline(block.label)}:*\n\n" if block.label else ""
        body = block.text
        if block.redact:
            return label + _fence_block(body, red)
        safe = truncate_block(elide_base64(strip_ansi(body)), TOOL_OUTPUT_CAP)
        fence = safe_fence(safe)
        return f"{label}{fence}\n{safe}\n{fence}"
    if isinstance(block, KV):
        return _kv(block)
    return _table(block)


# ───────────────────────── public renderer ─────────────────────────
def render_md(
    doc: ReportDoc,
    *,
    tools: str = "full",
    thinking: bool = True,
    redact: bool = True,
) -> str:
    """Render a ``ReportDoc`` to a self-contained Markdown document.

    ``tools`` ∈ {``full``, ``summary``, ``none``} controls tool-block fidelity;
    ``thinking=False`` drops thinking events; ``redact=False`` disables masking and flips
    the audit banner to ``redaction: off``. Pure and deterministic for a given doc.
    """
    red = Redactor(enabled=redact)

    # Render every red-consuming block first so the audit banner reports the final mask
    # count, then assemble the document top-down.
    body = "\n\n".join(
        _render_block(b, red, tools=tools, thinking=thinking) for b in doc.blocks
    )

    title = f"# {_inline(doc.title) or doc.subtitle} (`{doc.subtitle}`)"
    parts = [
        _front_matter(doc),
        title,
        _redaction_banner(redact, red.count),
    ]
    if doc.active:
        parts.append("> ⚠ run still active - snapshot only (data may be incomplete)")
    if doc.rollup:
        parts.append(_rollup_line(doc))
    parts.append(_toc(doc))
    parts.append(_fanout(doc))
    if body:
        parts.append(body)
    return "\n\n".join(parts) + "\n"
