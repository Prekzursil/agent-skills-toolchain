"""wfmon Markdown adapter — maps an ``ExportModel`` onto the generic ``ReportDoc`` and
renders it through the shared :func:`monitorcore.render_md.render_md`.

The Markdown rendering logic itself now lives in ``monitorcore`` (a generic, source-neutral
renderer over ``ReportDoc``); this module is the thin wfmon-specific seam: it threads the
``ExportModel → ReportDoc`` mapping (``export_model``) and keeps the historical
``render_markdown(model, …)`` surface (and the ``TOOL_OUTPUT_CAP`` re-export) that the cockpit
``e`` keybind, the CLI, and the skill test-suite import. Byte-identical to PR-A for a given
model + flags (guarded by the golden-output harness).
"""

from __future__ import annotations

from monitorcore.render_md import TOOL_OUTPUT_CAP, render_md

from .model import ExportModel, export_model

__all__ = ["render_markdown", "TOOL_OUTPUT_CAP"]


def render_markdown(
    model: ExportModel,
    *,
    tools: str = "full",
    thinking: bool = True,
    redact: bool = True,
) -> str:
    """Render an ``ExportModel`` to Markdown via the shared generic renderer.

    ``tools`` ∈ {``full``, ``summary``, ``none``}; ``thinking=False`` drops thinking events;
    ``redact=False`` disables masking and flips the audit banner. Pure and deterministic.
    """
    return render_md(export_model(model), tools=tools, thinking=thinking, redact=redact)
