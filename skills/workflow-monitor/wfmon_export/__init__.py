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

Two callables are deliberately NOT re-exported at package level because each would
SHADOW a submodule attribute of the same name, breaking
``from wfmon_export import <name> as <module>``:

* ``redact`` (function) would shadow the ``wfmon_export.redact`` submodule.
* ``render_html`` (function) would shadow the ``wfmon_export.render_html`` submodule
  (which ``tests/test_render_html.py`` imports as a module).

Import those two directly from their submodules instead::

    from wfmon_export.render_html import render_html
    from wfmon_export.redact import Redactor, redact

(The ``render_md`` module's public function is named ``render_markdown``, so it has
no such clash and IS re-exported; likewise ``detect_engines`` / ``render_pdf`` do not
collide with the ``pdf`` submodule name.)
"""

from __future__ import annotations

from .cli import run_export
from .model import AgentExport, ExportModel, PhaseExport, collect_run
from .pdf import detect_engines, render_pdf
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
