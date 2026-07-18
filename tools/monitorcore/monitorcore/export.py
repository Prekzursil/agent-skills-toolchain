"""Generic export pipeline — render a :class:`~monitorcore.report_doc.ReportDoc` to a
Markdown / HTML / PDF artifact on disk, plus the read-only out-guard *mechanism*.

``export_report`` is the one code path a monitor source drives to persist a report: it
renders the requested format with the shared generic renderers, for PDF descends the
feature-detected engine ladder (``render_pdf``, which never raises and always degrades to
a self-contained HTML rung), writes the artifact, and reports the written path, the PDF
rung used, and the mask count parsed straight off the rendered audit banner.

The out-guard *mechanism* lives here (``resolve_for_guard`` — 8.3 short-name + junction
expansion; ``under_root`` — containment even for a not-yet-existing target). The guarded
*root* and the caller-facing refusal message stay with the source (e.g. wfmon guards
``~/.claude/projects``), so this module imposes no Claude-Code-specific policy.
"""

from __future__ import annotations

import os
import re
import subprocess
from typing import Callable, NamedTuple

from .pdf import render_pdf
from .render_html import render_html
from .render_md import render_md
from .report_doc import ReportDoc

__all__ = [
    "ExportResult",
    "export_report",
    "extract_masked",
    "resolve_for_guard",
    "under_root",
]

_EXT = {"md": ".md", "html": ".html", "pdf": ".pdf"}

# Anchored to the audit-banner strings the renderers emit (``... N masked``); the
# off-banners carry no ``<digits> masked`` run, so a miss means "redaction: off". The
# banner precedes any transcript content, so the first match is always the banner.
_MASKED_RE = re.compile(r"redaction:.{0,40}?(\d+)\s+masked", re.IGNORECASE | re.DOTALL)


class ExportResult(NamedTuple):
    """One export outcome: the written path, the PDF rung used ('' for md/html), and the
    mask count parsed from the artifact (``None`` ⇒ redaction off)."""

    path: str
    engine: str
    masked: int | None


# ───────────────────────── read-only out-guard mechanism ─────────────────────────
def resolve_for_guard(path: str) -> str:
    """Resolve ``path`` for a read-only out-guard comparison.

    Walk up to the nearest EXISTING ancestor, ``realpath`` it (expanding 8.3 short names
    like ``PREKZU~1`` → ``Prekzursil`` plus any junctions/symlinks), rejoin the
    non-existent tail, then ``normcase`` — so the guard is robust even when the requested
    directory does not exist yet (the common case).
    """
    head = os.path.abspath(path)
    tail: list[str] = []
    while not os.path.exists(head):
        parent, part = os.path.split(head)
        if parent == head:  # reached a (non-existent) filesystem root; stop ascending
            break
        tail.append(part)
        head = parent
    resolved = os.path.join(os.path.realpath(head), *reversed(tail))
    return os.path.normcase(resolved)


def under_root(out: str, root: str) -> bool:
    """True if ``out`` resolves to, or under, ``root`` (both 8.3/junction-expanded)."""
    resolved_root = resolve_for_guard(root)
    target = resolve_for_guard(out)
    return target == resolved_root or target.startswith(resolved_root + os.sep)


# ───────────────────────── mask-count parse ─────────────────────────
def extract_masked(rendered: str) -> int | None:
    """Read the mask count straight off the rendered audit banner (single source of
    truth); ``None`` when the banner reports ``redaction: off``."""
    match = _MASKED_RE.search(rendered)
    return int(match.group(1)) if match else None


# ───────────────────────── the pipeline ─────────────────────────
def export_report(
    doc: ReportDoc,
    out_dir: str,
    base: str,
    *,
    fmt: str = "md",
    tools: str = "full",
    thinking: bool = True,
    redact: bool = True,
    pdf_engine: str | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> ExportResult:
    """Render ``doc`` in ``fmt`` and write ``<out_dir>/<base>.<ext>``; return the outcome.

    ``md``/``html`` write the rendered text directly. ``pdf`` renders BOTH channels (HTML
    for the browser/xhtml rungs, Markdown for pandoc/typst), descends the ``render_pdf``
    ladder (``runner`` is injectable for tests), and reports the rung used; the mask count
    is always parsed from the HTML channel. Raises ``OSError`` only on a write failure.
    """
    os.makedirs(out_dir, exist_ok=True)  # created on demand

    if fmt == "md":
        text = render_md(doc, tools=tools, thinking=thinking, redact=redact)
        path = os.path.join(out_dir, base + _EXT["md"])
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return ExportResult(os.path.abspath(path), "", extract_masked(text))

    if fmt == "html":
        text = render_html(doc, tools=tools, thinking=thinking, redact=redact)
        path = os.path.join(out_dir, base + _EXT["html"])
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return ExportResult(os.path.abspath(path), "", extract_masked(text))

    # pdf: render BOTH channels (html for browser/xhtml rungs, md for pandoc/typst)
    html = render_html(doc, tools=tools, thinking=thinking, redact=redact)
    md = render_md(doc, tools=tools, thinking=thinking, redact=redact)
    out_path = os.path.join(out_dir, base + _EXT["pdf"])
    engine, written = render_pdf(html, md, out_path, engine=pdf_engine, runner=runner)
    return ExportResult(os.path.abspath(written), engine, extract_masked(html))
