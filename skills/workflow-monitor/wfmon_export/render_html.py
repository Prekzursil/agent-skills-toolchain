"""``render_html`` - a pure, self-contained, XSS-safe HTML renderer of an ``ExportModel``.

The output is a single ``.html`` file with **all** CSS and JavaScript inlined and **zero**
external references (no CDN scripts, stylesheets, fonts, or remote images) so it renders
identically offline and doubles as the guaranteed PDF fallback. It is a *pure* function of the
model: no filesystem, no globals, deterministic for a given model + flags.

Safety contract (mirrors ``render_md`` where it makes sense, HTML-specialised where it must):

* Every untrusted transcript string - agent output, tool *input*, tool *result* - is routed
  through :func:`_safe` (``strip_ansi`` -> ``Redactor`` -> ``elide_base64`` -> ``truncate_block``
  -> ``html_escape``) so no channel can inject markup and no oversized/base64 blob bloats the file.
* Manifest *metadata* (agent labels, phase titles, provenance) is HTML-escaped (never a secret
  channel) so the redaction count reflects transcript content only.
* ``tools`` (``full`` | ``summary`` | ``none``) and ``thinking`` are honoured identically to the
  Markdown renderer; ``redact`` toggles masking and flips the audit banner label.

Interactivity is inline and dependency-free: a sticky control bar with a client-side agent
filter + expand/collapse-all, a sticky table of contents, and a ``@media print`` rule paired
with a ``window.onbeforeprint`` hook that expands every ``<details>`` for browser print-to-PDF.
"""

from __future__ import annotations

import json

from .model import ExportModel
from monitorcore.redact import Redactor
from monitorcore.textsafe import elide_base64, html_escape, strip_ansi, truncate_block
from monitorcore.timeline import pair_tool_calls

__all__ = ["render_html", "TOOL_OUTPUT_CAP"]

# Per-string byte cap applied in the render path (head+tail with a byte-offset marker). Large
# enough to keep ordinary transcript text intact, small enough to bound a pathological blob.
TOOL_OUTPUT_CAP = 8000

# Provenance keys surfaced both as inline <meta> tags and a visible header definition list.
_PROV_KEYS = (
    "wf_id",
    "name",
    "session",
    "scope",
    "redaction_mode",
    "generated_at",
    "schema_version",
)

_CSS = """
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body { font-family: system-ui, -apple-system, Segoe UI, sans-serif; margin: 0;
  padding: 1rem 1.25rem 4rem; line-height: 1.5; }
.prov h1 { margin: 0 0 .25rem; font-size: 1.4rem; }
.prov dl { display: grid; grid-template-columns: max-content 1fr; gap: .05rem .75rem;
  font-size: .82rem; opacity: .85; margin: .25rem 0; }
.prov dt { font-weight: 600; }
.rollup { font-size: .82rem; opacity: .85; margin: .25rem 0 .5rem; }
.banner { padding: .5rem .75rem; border-radius: .4rem; margin: .4rem 0; font-weight: 600; }
.banner.audit { background: #e8ecff; }
.banner.active { background: #ffefc2; }
.controls { position: sticky; top: 0; background: Canvas; padding: .5rem 0;
  display: flex; gap: .5rem; z-index: 6; border-bottom: 1px solid rgba(127,127,127,.3); }
.controls input { flex: 1; padding: .35rem .5rem; }
.controls button { padding: .35rem .7rem; cursor: pointer; }
.toc { position: sticky; top: 3.4rem; max-height: 72vh; overflow: auto; font-size: .84rem;
  padding: .25rem 0; }
.toc ul { margin: .15rem 0; padding-left: 1rem; }
.dag { margin: .75rem 0; }
.dag-flow { display: flex; flex-direction: column; gap: .3rem; max-width: 34rem; }
.dag-phase { border: 1px solid rgba(127,127,127,.5); border-radius: .4rem; padding: .4rem .6rem; }
.dag-phase-title { font-weight: 600; }
.dag-phase ul { margin: .2rem 0 0; padding-left: 1.1rem; }
.dag-arrow { text-align: center; font-size: 1.1rem; opacity: .7; }
.phase { margin-top: 1.25rem; }
.agent-card { border: 1px solid rgba(127,127,127,.5); border-radius: .5rem;
  padding: .6rem .85rem; margin: .8rem 0; }
.agent-card h3 { margin: 0 0 .3rem; }
.meta { font-size: .8rem; opacity: .8; margin: 0 0 .4rem; }
.headline { font-weight: 600; margin: 0 0 .4rem; }
.badge { font-size: .7rem; padding: .06rem .45rem; border-radius: .3rem; margin-left: .4rem;
  text-transform: uppercase; letter-spacing: .03em; }
.badge-done { background: #c9efc9; } .badge-error { background: #f3c9c9; }
.badge-running { background: #c9e2f5; } .badge-idle { background: #dcdcdc; }
h4, h5 { margin: .5rem 0 .25rem; font-size: .82rem; text-transform: uppercase; opacity: .75; }
blockquote { margin: 0; padding: .3rem .7rem; border-left: 3px solid rgba(127,127,127,.5);
  opacity: .95; }
pre { white-space: pre-wrap; word-break: break-word; background: rgba(127,127,127,.12);
  padding: .5rem; border-radius: .3rem; overflow-x: auto; margin: .2rem 0; }
.tool { margin: .35rem 0; }
.tool summary { cursor: pointer; font-weight: 600; }
.tool.error summary { color: #b00020; }
.tool-error { color: #b00020; font-weight: 700; }
.tool-summary { font-family: ui-monospace, monospace; font-size: .84rem; margin: .2rem 0; }
.empty { opacity: .6; font-style: italic; }
@media (prefers-color-scheme: dark) {
  .banner.audit { background: #23283f; } .banner.active { background: #4a3c17; }
  .badge-done { background: #234a23; } .badge-error { background: #4d2020; }
  .badge-running { background: #1f3b52; } .badge-idle { background: #3a3a3a; }
}
@media print {
  .controls, .toc { display: none; }
  .agent-card { break-inside: avoid; }
  body { padding: 0; }
}
""".strip()

_JS = """
function wfmonFilter(q){
  q = (q || '').toLowerCase();
  var cards = document.querySelectorAll('.agent-card');
  for (var i = 0; i < cards.length; i++){
    var c = cards[i];
    c.style.display = c.textContent.toLowerCase().indexOf(q) >= 0 ? '' : 'none';
  }
}
function wfmonSetAll(open){
  var ds = document.querySelectorAll('details');
  for (var i = 0; i < ds.length; i++){ ds[i].open = open; }
}
function wfmonExpandAll(){ wfmonSetAll(true); }
function wfmonCollapseAll(){ wfmonSetAll(false); }
window.onbeforeprint = function(){ wfmonExpandAll(); };
""".strip()


# ───────────────────────── the last-mile safe pipeline ─────────────────────────
def _safe(red: Redactor, s: str) -> str:
    """Render-path guard for one untrusted string: ansi-strip, redact, elide base64, cap, escape."""
    t = strip_ansi(s)
    t = red(t)
    t = elide_base64(t)
    t = truncate_block(t, TOOL_OUTPUT_CAP)
    return html_escape(t)


def _first_line(s: str) -> str:
    """First non-blank line (stripped); ``""`` when the string has no visible content."""
    for ln in s.splitlines():
        if ln.strip():
            return ln.strip()
    return ""


# ───────────────────────── head / provenance / banners ─────────────────────────
def _render_head(model: ExportModel) -> str:
    prov = model.provenance
    metas = "\n".join(
        f'<meta name="wfmon:{k}" content="{html_escape(str(prov.get(k, "")))}">'
        for k in _PROV_KEYS
    )
    return (
        "<!doctype html>\n"
        '<html lang="en">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>wfmon export &mdash; {html_escape(model.wf_id)}</title>\n"
        f"{metas}\n"
        f"<style>\n{_CSS}\n</style>\n"
        "</head>\n<body>"
    )


def _render_header(model: ExportModel) -> str:
    prov = model.provenance
    rows = "".join(
        f"<dt>{k}</dt><dd>{html_escape(str(prov.get(k, '')))}</dd>" for k in _PROV_KEYS
    )
    r = model.rollup
    rollup = (
        f'<p class="rollup">running: {r["running"]} &middot; done: {r["done"]} '
        f"&middot; error: {r['error']} &middot; idle: {r['idle']} "
        f"&middot; total: {r['total']} &middot; tokens: {r['tokens']}</p>"
    )
    return (
        f'<header class="prov"><h1>{html_escape(model.name)}</h1>'
        f"<dl>{rows}</dl>{rollup}</header>"
    )


def _render_banners(model: ExportModel, red: Redactor) -> str:
    if red.enabled:
        audit = (
            f'<div class="banner audit">redaction: {html_escape(model.redaction_mode)} '
            f"&mdash; {red.count} masked</div>"
        )
    else:
        audit = '<div class="banner audit">redaction: off</div>'
    active = (
        '<div class="banner active">run still active &mdash; snapshot</div>'
        if model.active
        else ""
    )
    return audit + active


def _render_controls() -> str:
    return (
        '<div class="controls">'
        '<input type="text" placeholder="filter agents..." '
        'oninput="wfmonFilter(this.value)" aria-label="filter agents">'
        '<button type="button" onclick="wfmonExpandAll()">Expand all</button>'
        '<button type="button" onclick="wfmonCollapseAll()">Collapse all</button>'
        "</div>"
    )


def _render_toc(model: ExportModel) -> str:
    parts = ['<nav class="toc" aria-label="contents"><h2>Contents</h2><ul>']
    for ph in model.phases:
        parts.append(
            f'<li><a href="#phase-{ph.index}">P{ph.index}: {html_escape(ph.title)}</a><ul>'
        )
        for ag in ph.agents:
            parts.append(
                f'<li><a href="#{html_escape(ag.agent_id)}">{html_escape(ag.label)}</a></li>'
            )
        parts.append("</ul></li>")
    parts.append("</ul></nav>")
    return "\n".join(parts)


# ───────────────────────── fan-out DAG (inline HTML, no mermaid/CDN) ─────────────────────────
def _render_dag(model: ExportModel) -> str:
    parts = [
        '<section class="dag" aria-label="fan-out"><h2>Fan-out</h2><div class="dag-flow">'
    ]
    last = len(model.phases) - 1
    for i, ph in enumerate(model.phases):
        nodes = "".join(
            f"<li>{html_escape(ag.label)} "
            f'<span class="badge badge-{html_escape(ag.state)}">{html_escape(ag.state)}</span></li>'
            for ag in ph.agents
        )
        parts.append(
            f'<div class="dag-phase"><div class="dag-phase-title">'
            f"P{ph.index}: {html_escape(ph.title)}</div><ul>{nodes}</ul></div>"
        )
        if i < last:
            parts.append('<div class="dag-arrow">&darr;</div>')
    parts.append("</div></section>")
    return "".join(parts)


# ───────────────────────── tool blocks ─────────────────────────
def _render_tool(use, result, tools: str, red: Redactor) -> str:
    name = html_escape(use.name) or "tool"
    is_err = result is not None and result.is_error

    if tools == "summary":
        if result is None:
            line = "no result"
        else:
            fl = _first_line(result.output)
            line = _safe(red, fl) if fl else "no output"
        err = " (error)" if is_err else ""
        return f'<div class="tool-summary">{name}: {line}{err}</div>'

    # full
    err_cls = " error" if is_err else ""
    err_lbl = ' <span class="tool-error">error</span>' if is_err else ""
    inp = _safe(red, json.dumps(use.tool_input, ensure_ascii=False, indent=2))
    if result is None:
        res_html = '<p class="empty">no result</p>'
    elif not result.output.strip():
        res_html = '<p class="empty">no output</p>'
    else:
        res_html = f"<pre>{_safe(red, result.output)}</pre>"
    return (
        f'<details class="tool{err_cls}"><summary>{name}{err_lbl}</summary>'
        f'<div class="tool-input"><h5>input</h5><pre>{inp}</pre></div>'
        f'<div class="tool-output"><h5>result</h5>{res_html}</div></details>'
    )


def _render_timeline(agent, tools: str, thinking: bool, red: Redactor) -> str:
    results_by_id = {u.tool_id: r for u, r in pair_tool_calls(agent.timeline)}
    parts = ['<div class="timeline">']
    for ev in agent.timeline:
        if ev.kind == "thinking":
            if not thinking:
                continue
            parts.append(
                f'<div class="ev thinking"><h4>thinking</h4><pre>{_safe(red, ev.text)}</pre></div>'
            )
        elif ev.kind == "text":
            parts.append(f'<div class="ev text"><pre>{_safe(red, ev.text)}</pre></div>')
        elif ev.kind == "tool_use":
            if tools == "none":
                continue
            parts.append(_render_tool(ev, results_by_id.get(ev.tool_id), tools, red))
        # tool_result events are rendered under their tool_use (or skipped if standalone)
    parts.append("</div>")
    return "".join(parts)


# ───────────────────────── agent card / phase ─────────────────────────
def _render_agent(agent, tools: str, thinking: bool, red: Redactor) -> str:
    parts = [
        f'<article class="agent-card" id="{html_escape(agent.agent_id)}">',
        f"<h3>{html_escape(agent.label)}"
        f'<span class="badge badge-{html_escape(agent.state)}">{html_escape(agent.state)}</span></h3>',
        f'<p class="meta">model: {html_escape(agent.model)} &middot; tokens: {agent.tokens} '
        f"&middot; tool-calls: {agent.tool_calls} &middot; attempt: {agent.attempt} "
        f"&middot; {agent.duration_ms} ms</p>",
    ]
    if agent.headline:
        parts.append(f'<p class="headline">{_safe(red, agent.headline)}</p>')
    parts.append("<h4>task</h4>")
    if agent.task.strip():
        parts.append(f"<blockquote>{_safe(red, agent.task)}</blockquote>")
    else:
        parts.append('<p class="empty">no task</p>')
    parts.append(_render_timeline(agent, tools, thinking, red))
    parts.append("<h4>output</h4>")
    if agent.output.strip():
        parts.append(f"<pre>{_safe(red, agent.output)}</pre>")
    else:
        parts.append('<p class="empty">no output</p>')
    parts.append("</article>")
    return "".join(parts)


def _render_phases(
    model: ExportModel, tools: str, thinking: bool, red: Redactor
) -> str:
    parts = []
    for ph in model.phases:
        parts.append(
            f'<section class="phase" id="phase-{ph.index}">'
            f"<h2>Phase {ph.index}: {html_escape(ph.title)}</h2>"
        )
        for ag in ph.agents:
            parts.append(_render_agent(ag, tools, thinking, red))
        parts.append("</section>")
    return "".join(parts)


# ───────────────────────── public renderer ─────────────────────────
def render_html(
    model: ExportModel,
    *,
    tools: str = "full",
    thinking: bool = True,
    redact: bool = True,
) -> str:
    """Render ``model`` to a single self-contained, XSS-safe HTML document.

    ``tools`` selects tool-block fidelity (``full`` input+result / ``summary`` one-line /
    ``none``); ``thinking=False`` drops thinking events; ``redact`` toggles strict masking and
    the audit-banner label. Pure: no filesystem, deterministic for a given model + flags.
    """
    red = Redactor(enabled=redact)

    # Content-bearing sections are rendered FIRST so ``red.count`` is final before the banner.
    dag = _render_dag(model)  # metadata only (no redaction)
    toc = _render_toc(model)  # metadata only (no redaction)
    phases = _render_phases(model, tools, thinking, red)

    banners = _render_banners(model, red)  # reads the now-final red.count

    return "\n".join(
        (
            _render_head(model),
            _render_header(model),
            banners,
            _render_controls(),
            toc,
            dag,
            phases,
            f"<script>\n{_JS}\n</script>",
            "</body>\n</html>",
        )
    )
