"""wfmon_export - stdlib-only workflow-run export package.

Import-time is strictly stdlib-only; optional third-party deps (PDF engines) are
guarded inside functions, never imported here.

``model.py`` is the ONLY filesystem reader in the export path (``collect_run`` fully
materializes an ``ExportModel``); the renderers are pure functions of that model.

Public package-level re-exports (all stdlib-safe at import time):
``collect_run`` + the ``ExportModel`` / ``AgentExport`` / ``PhaseExport`` dataclasses
(the model surface), ``render_markdown`` (Markdown renderer), ``detect_engines`` /
``render_pdf`` (the feature-detected PDF ladder), and ``run_export`` (the shared CLI
+ keybind entry point).

``render_html`` (function) is deliberately NOT re-exported at package level because it
would SHADOW the ``wfmon_export.render_html`` submodule attribute of the same name
(which ``tests/test_render_html.py`` imports as a module), breaking
``from wfmon_export import render_html as <module>``. Import it directly instead::

    from wfmon_export.render_html import render_html

The redaction primitives now live in the vendored ``monitorcore`` package (extracted
from this skill as a shared leaf); import them from there::

    from monitorcore.redact import Redactor, redact

(The ``render_md`` module's public function is named ``render_markdown``, so it has
no such clash and IS re-exported. The PDF ladder (``detect_engines`` / ``render_pdf``)
now lives in the vendored ``monitorcore.pdf`` module and is re-exported from there.)
"""

from __future__ import annotations

from monitorcore.pdf import detect_engines, render_pdf

from .cli import run_export
from .model import AgentExport, ExportModel, PhaseExport, collect_run
from .render_md import render_markdown

__all__: list[str] = [
    "AgentExport",
    "ExportModel",
    "PhaseExport",
    "collect_run",
    "render_markdown",
    "detect_engines",
    "render_pdf",
    "run_export",
]
