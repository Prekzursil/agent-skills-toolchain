"""wfmon_export.render_md - PURE Markdown renderer for an ``ExportModel``.

``render_markdown(model)`` is a total function of its ``ExportModel`` argument: it
opens no files, mutates no globals, and is idempotent. Everything it needs was
materialised up-front by ``model.collect_run`` (the only filesystem reader in the
export path); the renderer merely lays that snapshot out as Markdown.

Document shape (top to bottom):

* YAML front-matter mirroring ``model.provenance`` (schema-pinned).
* a redaction **audit banner** (``N masked`` when strict, ``redaction: off`` when
  the caller passes ``redact=False``) and, when the run is still non-terminal, a
  ``run still active - snapshot`` banner.
* a scoped rollup line + per-state badges.
* an anchor **table of contents** (phase + agent links).
* a **fan-out DAG** - a ``mermaid`` ``flowchart TD`` built from
  ``phase -> agent`` + sequential ``phase[i] -> phase[i+1]`` edges, plus an
  indented ASCII fallback for viewers without mermaid.
* per-phase, per-agent cards: task blockquote, ordered transcript timeline
  (thinking / text / collapsible ``<details>`` tool blocks), then the clean
  output.

Every free-form transcript string (task, output, thinking, text, tool input +
output) is routed through ``Redactor`` then the ``textsafe`` helpers
(``strip_ansi`` -> ``elide_base64`` -> ``truncate_block`` -> ``safe_fence``) *in
the render path*, so redaction, base64 elision and truncation are guaranteed for
real content, not merely unit-tested in isolation. Structural manifest metadata
(phase titles, agent labels) is sanitised for its target syntax (mermaid label /
Markdown heading) but not counted as redactable transcript content.
"""

from __future__ import annotations

import json
import re

from workflow_run import pair_tool_calls

from .redact import Redactor
from .textsafe import elide_base64, safe_fence, strip_ansi, truncate_block

# Per-artifact byte cap for a single tool input/output or agent output block. Past
# this many UTF-8 bytes ``truncate_block`` collapses the middle to a head + a
# byte-offset marker + a tail (referenced by the end-to-end truncation test).
TOOL_OUTPUT_CAP = 8000

_WS_RE = re.compile(r"\s+")


# ───────────────────────── small pure helpers ─────────────────────────
def _inline(s: str) -> str:
    """Collapse a manifest string to a single safe line (headings / TOC / ASCII)."""
    return _WS_RE.sub(" ", strip_ansi(s)).strip()


def _mm(s: str) -> str:
    """Sanitise a label for a mermaid ``["..."]`` node: drop quotes + newlines."""
    return _WS_RE.sub(" ", strip_ansi(s).replace('"', "'")).strip()[:80]


def _fence_block(text: str, red: Redactor) -> str:
    """Redact + ansi-strip + base64-elide + truncate ``text``, then wrap in a safe fence.

    The fence delimiter is one backtick longer than the longest run inside the
    (post-processing) content, so transcript back-ticks can never close it early.
    """
    body = truncate_block(elide_base64(strip_ansi(red(text))), TOOL_OUTPUT_CAP)
    fence = safe_fence(body)
    return f"{fence}\n{body}\n{fence}"


def _blockquote(text: str, red: Redactor) -> str:
    """Render ``text`` as a redacted, ansi-stripped Markdown blockquote."""
    clean = strip_ansi(red(text))
    return "\n".join("> " + ln for ln in clean.splitlines()) or "> "


def _one_line(text: str, red: Redactor) -> str:
    """First non-empty (redacted) line of ``text`` - the tool ``summary`` view."""
    body = truncate_block(elide_base64(strip_ansi(red(text))), TOOL_OUTPUT_CAP)
    for ln in body.splitlines():
        if ln.strip():
            return ln.strip()
    return ""


# ───────────────────────── front-matter + banners ─────────────────────────
_FM_KEYS = (
    "wf_id",
    "name",
    "session",
    "scope",
    "redaction_mode",
    "generated_at",
    "schema_version",
)


def _front_matter(model) -> str:
    prov = model.provenance
    lines = ["---"]
    for key in _FM_KEYS:
        lines.append(f"{key}: {json.dumps(str(prov.get(key, '')))}")
    lines.append("---")
    return "\n".join(lines)


def _redaction_banner(redact: bool, count: int) -> str:
    if redact:
        return f"> **redaction: strict** - {count} masked"
    return "> **redaction: off** - secrets NOT masked (`--no-redact`)"


def _rollup_line(model) -> str:
    r = model.rollup
    return (
        f"**Agents:** {r['total']} total - {r['done']} done - {r['error']} error - "
        f"{r['running']} running - {r['idle']} idle - {r['tokens']:,} tokens"
    )


# ───────────────────────── table of contents ─────────────────────────
def _toc(model) -> str:
    lines = ["## Contents", ""]
    for phase in model.phases:
        lines.append(f"- [{_inline(phase.title)}](#phase-{phase.index})")
        for ag in phase.agents:
            lines.append(f"  - [{_inline(ag.label)}](#{ag.agent_id})")
    return "\n".join(lines)


# ───────────────────────── fan-out DAG ─────────────────────────
def _fanout(model) -> str:
    phases = model.phases
    stmts: list[str] = []
    for phase in phases:
        stmts.append(f'P{phase.index}["{_mm(phase.title)}"]')
    for a, b in zip(phases, phases[1:]):
        stmts.append(f"P{a.index} --> P{b.index}")
    counter = 0
    for phase in phases:
        for ag in phase.agents:
            stmts.append(f'P{phase.index} --> A{counter}["{_mm(ag.label)}"]')
            counter += 1

    if stmts:
        # Keep the first ``["`` node on the same physical line as ``flowchart TD``
        # (no newline before it) so the diagram stays valid and label-safe.
        inner = "flowchart TD; " + stmts[0]
        if len(stmts) > 1:
            inner += "\n" + "\n".join("    " + s for s in stmts[1:])
    else:
        inner = "flowchart TD"
    mermaid = f"```mermaid\n{inner}\n```"

    ascii_lines: list[str] = []
    for phase in phases:
        ascii_lines.append(_inline(phase.title))
        for j, ag in enumerate(phase.agents):
            connector = "└─" if j == len(phase.agents) - 1 else "├─"
            ascii_lines.append(f"{connector} {_inline(ag.label)} [{ag.state}]")
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


def _tool_full(use, result, red: Redactor) -> str:
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


def _tool_summary(use, result, red: Redactor) -> str:
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


# ───────────────────────── per-agent + per-phase ─────────────────────────
def _timeline(agent, red: Redactor, *, tools: str, thinking: bool) -> str:
    results_by_id = {u.tool_id: r for u, r in pair_tool_calls(agent.timeline)}
    parts: list[str] = []
    for e in agent.timeline:
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


def _agent_card(agent, red: Redactor, *, tools: str, thinking: bool) -> str:
    state = _inline(agent.state) or "idle"
    lines = [f'### <a id="{agent.agent_id}"></a>{_inline(agent.label)} - {state}']
    meta = []
    if agent.model:
        meta.append(f"`{_inline(agent.model)}`")
    meta.append(f"{agent.tokens:,} tokens")
    meta.append(f"{agent.tool_calls} tool calls")
    if agent.attempt and agent.attempt != 1:
        meta.append(f"attempt {agent.attempt}")
    lines.append(" - ".join(meta))
    if agent.headline.strip():
        lines.append(f"_{_inline(agent.headline)}_")

    lines.append("")
    lines.append("**Task:**")
    if agent.task.strip():
        lines.append(_blockquote(agent.task, red))
    else:
        lines.append("_(no task)_")

    tl = _timeline(agent, red, tools=tools, thinking=thinking)
    if tl:
        lines += ["", "**Transcript:**", "", tl]

    lines += ["", "**Output:**"]
    if agent.output.strip():
        lines.append(_fence_block(agent.output, red))
    else:
        lines.append("_(no output)_")
    return "\n".join(lines)


def _phase_section(phase, red: Redactor, *, tools: str, thinking: bool) -> str:
    lines = [f'## <a id="phase-{phase.index}"></a>{_inline(phase.title)}']
    for ag in phase.agents:
        lines += ["", _agent_card(ag, red, tools=tools, thinking=thinking)]
    return "\n".join(lines)


# ───────────────────────── public renderer ─────────────────────────
def render_markdown(
    model,
    *,
    tools: str = "full",
    thinking: bool = True,
    redact: bool = True,
) -> str:
    """Render an ``ExportModel`` to a self-contained Markdown document.

    ``tools`` ∈ {``full`` (input + output, collapsible ``<details>``), ``summary``
    (name + one-line result), ``none`` (omit tool blocks)}. ``thinking=False``
    drops thinking events. ``redact=False`` disables masking and flips the audit
    banner to ``redaction: off`` (the raw transcript is emitted verbatim). Pure:
    no filesystem access, deterministic for a given model.
    """
    red = Redactor(enabled=redact)

    # Render every red-consuming section first so the audit banner can report the
    # final mask count, then assemble the document top-down.
    body = "\n\n".join(
        _phase_section(p, red, tools=tools, thinking=thinking) for p in model.phases
    )

    title = f"# {_inline(model.name) or model.wf_id} (`{model.wf_id}`)"
    parts = [
        _front_matter(model),
        title,
        _redaction_banner(redact, red.count),
    ]
    if model.active:
        parts.append("> ⚠ run still active - snapshot only (data may be incomplete)")
    parts.append(_rollup_line(model))
    parts.append(_toc(model))
    parts.append(_fanout(model))
    if body:
        parts.append(body)
    return "\n\n".join(parts) + "\n"
