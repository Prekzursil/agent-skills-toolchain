"""wfmon_export.cli - the ``wfmon export`` entry point + the shared ``run_export``.

``run_export`` is the ONE code path behind both the ``wfmon export`` CLI and the
cockpit ``e`` keybind: it collects the run (``model.collect_run`` - the only
filesystem reader), maps it to the generic ``ReportDoc`` (``model.export_model``),
then hands off to the shared ``monitorcore.export.export_report`` pipeline (render →
write → feature-detected PDF ladder), under a READ-ONLY out-guard that refuses to
write anywhere beneath ``~/.claude/projects`` (8.3 short-name paths such as
``PREKZU~1`` included, even when the target does not exist yet). The out-guard
*mechanism* (short-name/junction expansion + containment) and the export pipeline now
live in ``monitorcore``; this module keeps only the Claude-Code specifics — the guarded
root, the ``--projects`` default, the ``wf id`` argument surface, and ``run_export``.
Stdlib-only at import time.

``main`` strips a single leading ``export`` token (so ``wfmon export <id>``,
``python -m wfmon_export export <id>`` and ``python -m wfmon_export <id>`` all
parse), then dispatches through the pipeline, printing the written path, the PDF
engine used, and the redaction status. Exit codes: ``0`` success · ``1`` a
render/write error (a forced PDF that could only degrade to HTML included) · ``2``
bad args / out-guard violation / unknown ``wf_id`` / unknown agent label.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile

import workflow_run as wr
from monitorcore.export import ExportResult, export_report, under_root

from .model import collect_run, export_model

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


# ───────────────────────── label parsing ─────────────────────────
def _split_labels(raw: str) -> list[str]:
    """Split a ``--agents`` value into stripped, non-empty labels (label-set input)."""
    return [a.strip() for a in raw.split(",") if a.strip()]


# ───────────────────────── read-only out-guard root (CC-specific) ─────────────────────────
def _claude_projects_root() -> str:
    """The read-only fleet root the exporter must never write beneath."""
    return os.path.join(os.path.expanduser("~"), ".claude", "projects")


# ───────────────────────── the shared export core ─────────────────────────
def _basename(wf_id: str, scope: str) -> str:
    """``<wf_id>`` for a whole-run export, ``<wf_id>.<scope>`` for a scoped one."""
    return wf_id if scope == "run" else f"{wf_id}.{scope}"


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
) -> ExportResult:
    out_dir = out or os.path.join(tempfile.gettempdir(), _DEFAULT_OUT_DIRNAME)
    if under_root(out_dir, _claude_projects_root()):
        raise ValueError(
            f"refusing to write under the read-only ~/.claude/projects tree: {out_dir}"
        )

    model = collect_run(wf_id, projects=projects, scope=scope, agents=agents)
    if not redact:
        # keep the audit-banner label + provenance consistent under --no-redact
        model.redaction_mode = "off"
        model.provenance["redaction_mode"] = "off"

    doc = export_model(model)
    return export_report(
        doc,
        out_dir,
        _basename(wf_id, scope),
        fmt=fmt,
        tools=tools,
        thinking=thinking,
        redact=redact,
        pdf_engine=pdf_engine,
    )


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
    """Collect, map, render, (optionally) PDF, and write one run export; return the abs path.

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
