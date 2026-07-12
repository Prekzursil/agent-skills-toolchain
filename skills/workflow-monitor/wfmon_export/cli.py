"""wfmon_export.cli - the ``wfmon export`` entry point + the shared ``run_export``.

``run_export`` is the ONE code path behind both the ``wfmon export`` CLI and the
cockpit ``e`` keybind: it collects the run (``model.collect_run`` - the only
filesystem reader), renders the requested format with the PURE renderers,
optionally drives the feature-detected PDF ladder, and writes the artifact under a
READ-ONLY out-guard that refuses to write anywhere beneath ``~/.claude/projects``
(8.3 short-name paths such as ``PREKZU~1`` included, even when the target does not
exist yet). Stdlib-only at import time.

``main`` strips a single leading ``export`` token (so ``wfmon export <id>``,
``python -m wfmon_export export <id>`` and ``python -m wfmon_export <id>`` all
parse), then dispatches through ``run_export``, printing the written path, the PDF
engine used, and the redaction status. Exit codes: ``0`` success · ``1`` a
render/write error (a forced PDF that could only degrade to HTML included) · ``2``
bad args / out-guard violation / unknown ``wf_id`` / unknown agent label.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from typing import NamedTuple

import workflow_run as wr

from .model import collect_run
from .pdf import render_pdf
from .render_html import render_html
from .render_md import render_markdown

__all__ = ["build_parser", "run_export", "main"]

_DEFAULT_OUT_DIRNAME = "wfmon-exports"
_SCOPES = ("run", "subset", "agent")
_FORMATS = ("md", "html", "pdf")
_TOOLS = ("full", "summary", "none")
_PDF_ENGINES = (
    "typst",
    "playwright",
    "edge",
    "chrome",
    "pandoc",
    "xhtml2pdf",
    "fpdf2",
    "html",
)
_EXT = {"md": ".md", "html": ".html", "pdf": ".pdf"}

# Anchored to the exact audit-banner strings the renderers emit
# (``... N masked``): render_md -> ``> **redaction: strict** - N masked`` and
# render_html -> ``redaction: strict &mdash; N masked``. The off-banners carry no
# ``<digits> masked`` run, so a miss means "redaction: off". The banner precedes any
# transcript content, so ``search`` (first match) reads the banner, not the body.
_MASKED_RE = re.compile(r"redaction:.{0,40}?(\d+)\s+masked", re.IGNORECASE | re.DOTALL)


# ───────────────────────── label parsing ─────────────────────────
def _split_labels(raw: str) -> list[str]:
    """Split a ``--agents`` value into stripped, non-empty labels (label-set input)."""
    return [a.strip() for a in raw.split(",") if a.strip()]


# ───────────────────────── read-only out-guard ─────────────────────────
def _resolve_for_guard(path: str) -> str:
    """Resolve ``path`` for the read-only out-guard comparison.

    Walk up to the nearest EXISTING ancestor, ``realpath`` it (expanding 8.3 short
    names like ``PREKZU~1`` -> ``Prekzursil`` plus any junctions/symlinks), rejoin
    the non-existent tail, then ``normcase``. This makes the guard robust even when
    the requested ``--out`` directory does not exist yet (the common case).
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


def _claude_projects_root() -> str:
    """The read-only fleet root the exporter must never write beneath."""
    return os.path.join(os.path.expanduser("~"), ".claude", "projects")


def _under_read_only_root(out: str) -> bool:
    """True if ``out`` resolves to, or under, the guarded ``~/.claude/projects`` tree."""
    root = _resolve_for_guard(_claude_projects_root())
    target = _resolve_for_guard(out)
    return target == root or target.startswith(root + os.sep)


# ───────────────────────── the shared export core ─────────────────────────
class _Export(NamedTuple):
    """Internal export result: the written path, the PDF rung used ('' for md/html),
    and the mask count parsed from the artifact ('None' => redaction off)."""

    path: str
    engine: str
    masked: int | None


def _basename(wf_id: str, scope: str) -> str:
    """``<wf_id>`` for a whole-run export, ``<wf_id>.<scope>`` for a scoped one."""
    return wf_id if scope == "run" else f"{wf_id}.{scope}"


def _extract_masked(rendered: str) -> int | None:
    """Read the mask count straight off the rendered audit banner (single source of
    truth); ``None`` when the banner reports ``redaction: off``."""
    match = _MASKED_RE.search(rendered)
    return int(match.group(1)) if match else None


def _export(
    wf_id: str,
    *,
    scope: str = "run",
    agents: list[str] | None = None,
    fmt: str = "md",
    pdf_engine: str | None = None,
    tools: str = "full",
    thinking: bool = True,
    redact: bool = True,
    out: str | None = None,
    projects: str = wr.DEFAULT_PROJECTS,
) -> _Export:
    out_dir = out or os.path.join(tempfile.gettempdir(), _DEFAULT_OUT_DIRNAME)
    if _under_read_only_root(out_dir):
        raise ValueError(
            f"refusing to write under the read-only ~/.claude/projects tree: {out_dir}"
        )

    model = collect_run(wf_id, projects=projects, scope=scope, agents=agents)
    if not redact:
        # keep the audit-banner label + provenance consistent under --no-redact
        model.redaction_mode = "off"
        model.provenance["redaction_mode"] = "off"

    os.makedirs(out_dir, exist_ok=True)  # created on demand
    base = _basename(wf_id, scope)

    if fmt == "md":
        text = render_markdown(model, tools=tools, thinking=thinking, redact=redact)
        path = os.path.join(out_dir, base + _EXT["md"])
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return _Export(os.path.abspath(path), "", _extract_masked(text))

    if fmt == "html":
        text = render_html(model, tools=tools, thinking=thinking, redact=redact)
        path = os.path.join(out_dir, base + _EXT["html"])
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return _Export(os.path.abspath(path), "", _extract_masked(text))

    # pdf: render BOTH channels (html for the browser/xhtml rungs, md for pandoc/typst)
    html = render_html(model, tools=tools, thinking=thinking, redact=redact)
    md = render_markdown(model, tools=tools, thinking=thinking, redact=redact)
    out_path = os.path.join(out_dir, base + _EXT["pdf"])
    engine, written = render_pdf(html, md, out_path, engine=pdf_engine)
    return _Export(os.path.abspath(written), engine, _extract_masked(html))


def run_export(
    wf_id: str,
    *,
    scope: str = "run",
    agents: list[str] | None = None,
    fmt: str = "md",
    pdf_engine: str | None = None,
    tools: str = "full",
    thinking: bool = True,
    redact: bool = True,
    out: str | None = None,
    projects: str = wr.DEFAULT_PROJECTS,
) -> str:
    """Collect, render, (optionally) PDF, and write one run export; return the abs path.

    Shared by the ``wfmon export`` CLI and the cockpit ``e`` keybind. Raises
    ``LookupError`` (unknown ``wf_id``), ``ValueError`` (unknown label / scope
    without labels / out-guard violation), or ``OSError`` (write failure). The PDF
    ladder never raises - it always degrades to a self-contained HTML artifact.
    """
    return _export(
        wf_id,
        scope=scope,
        agents=agents,
        fmt=fmt,
        pdf_engine=pdf_engine,
        tools=tools,
        thinking=thinking,
        redact=redact,
        out=out,
        projects=projects,
    ).path


# ───────────────────────── argument parser ─────────────────────────
def build_parser() -> argparse.ArgumentParser:
    """Build the ``wfmon export`` argument parser (full flag surface)."""
    parser = argparse.ArgumentParser(
        prog="wfmon export",
        description="Export a workflow run to Markdown / HTML / PDF "
        "(read-only over ~/.claude; strict secret redaction by default).",
    )
    parser.add_argument(
        "wf_id", help="workflow run id (matched against discovered manifests)"
    )
    parser.add_argument(
        "--scope",
        choices=_SCOPES,
        default="run",
        help="run (all agents) | subset | agent (subset/agent require --agents)",
    )
    parser.add_argument(
        "--agents",
        type=_split_labels,
        default=None,
        metavar="LABEL1,LABEL2",
        help="comma-separated agent LABELS (case-insensitive; label-set semantics)",
    )
    parser.add_argument(
        "--format",
        dest="fmt",
        choices=_FORMATS,
        default="md",
        help="output format (default md)",
    )
    parser.add_argument(
        "--pdf-engine",
        dest="pdf_engine",
        choices=_PDF_ENGINES,
        default=None,
        help="force a PDF rung (else best-available; ignored unless --format pdf)",
    )
    parser.add_argument(
        "--tools",
        choices=_TOOLS,
        default="full",
        help="tool-block fidelity (honored by md + html)",
    )
    parser.add_argument(
        "--no-thinking",
        dest="thinking",
        action="store_false",
        help="drop thinking events (honored by md + html)",
    )
    parser.add_argument(
        "--no-redact",
        dest="redact",
        action="store_false",
        help="opt out of STRICT redaction (prints an explicit 'redaction: off' banner)",
    )
    parser.add_argument(
        "--out",
        default=None,
        metavar="DIR",
        help="output directory (default <tempdir>/wfmon-exports, created on demand)",
    )
    parser.add_argument(
        "--projects",
        default=wr.DEFAULT_PROJECTS,
        metavar="DIR",
        help="fleet root override (default ~/.claude/projects)",
    )
    return parser


# ───────────────────────── main ─────────────────────────
def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns the process exit code (see module docstring)."""
    args = list(sys.argv[1:] if argv is None else argv)
    # wfmon.cmd forwards the whole tail incl the leading 'export' token; strip ONE.
    if args and args[0] == "export":
        args = args[1:]

    ns = build_parser().parse_args(args)  # argparse raises SystemExit(2) on bad args

    try:
        result = _export(
            ns.wf_id,
            scope=ns.scope,
            agents=ns.agents,
            fmt=ns.fmt,
            pdf_engine=ns.pdf_engine,
            tools=ns.tools,
            thinking=ns.thinking,
            redact=ns.redact,
            out=ns.out,
            projects=ns.projects,
        )
    except (LookupError, ValueError) as exc:  # unknown wf_id / label / out-guard
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:  # write failure
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(result.path)
    if ns.fmt == "pdf":
        print(f"engine: {result.engine}")
    if result.masked is None:
        print("redaction: off")
    else:
        print(f"{result.masked} masked")
    # a forced/auto PDF that could only degrade to HTML is a soft render error
    return 1 if (ns.fmt == "pdf" and result.engine == "html") else 0
