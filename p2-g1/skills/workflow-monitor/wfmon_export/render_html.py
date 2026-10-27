"""wfmon HTML adapter — maps an ``ExportModel`` onto the generic ``ReportDoc`` and renders it
through the shared :func:`monitorcore.render_html.render_html`.

The self-contained, XSS-safe HTML rendering logic now lives in ``monitorcore`` (a generic,
source-neutral renderer over ``ReportDoc``); this module is the thin wfmon-specific seam: it
threads the ``ExportModel → ReportDoc`` mapping (``export_model``) and keeps the historical
``render_html(model, …)`` surface (and the ``TOOL_OUTPUT_CAP`` re-export) that the CLI and the
skill test-suite import. Byte-identical to PR-A for a given model + flags (guarded by the
golden-output harness).
"""

from __future__ import annotations

from monitorcore.render_html import TOOL_OUTPUT_CAP
from monitorcore.render_html import render_html as _render_html

from .model import ExportModel, export_model

__all__ = ["render_html", "TOOL_OUTPUT_CAP"]


def render_html(
    model: ExportModel,
    *,
    tools: str = "full",
    thinking: bool = True,
    redact: bool = True,
) -> str:
    """Render an ``ExportModel`` to a self-contained, XSS-safe HTML document via the shared
    generic renderer.

    ``tools`` selects tool-block fidelity (``full`` / ``summary`` / ``none``);
    ``thinking=False`` drops thinking events; ``redact`` toggles masking + the audit-banner
    label. Pure and deterministic.
    """
    return _render_html(
        export_model(model), tools=tools, thinking=thinking, redact=redact
    )
