#!/usr/bin/env python3
"""Golden-output regression harness (PR-B1 WU4).

Proves the refactored generic ``monitorcore`` renderers, fed the wfmon
``ExportModel → ReportDoc`` mapping, reproduce PR-A's Markdown + HTML **byte-for-byte**
for the frozen ``wf_export00-fixture`` at a pinned ``generated_at``. The committed golden
bytes (``tools/monitorcore/tests/golden/wf_export00.*``) were captured from the PRE-refactor
wfmon renderers, so this comparison is non-circular: any drift in the render refactor (or the
mapper) fails here.

PDF is NEVER byte-compared (it embeds a nondeterministic ``/CreationDate`` + xref, and on CI
degrades to the HTML rung); instead the PDF path is asserted by **routing** — the exact
``(html, md)`` pair the mapper feeds the ladder is captured and asserted equal to the golden
HTML/MD, and the reported engine is the one the (faked) ladder returned.
"""

from __future__ import annotations

import os

import pytest

from monitorcore import export as mcx
from monitorcore.render_html import render_html
from monitorcore.render_md import render_md
from wfmon_export.model import collect_run, export_model

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORT_PROJECTS = os.path.join(HERE, "fixtures", "export", "projects")
REPO = os.path.dirname(os.path.dirname(HERE))
GOLDEN = os.path.join(REPO, "tools", "monitorcore", "tests", "golden")
WF_ID = "wf_export00-fixture"
PINNED = "2026-07-12T00:00:00+00:00"

# (golden-name, render kwargs, redact-mutates-model)
_COMBOS = [
    ("full", dict(tools="full", thinking=True, redact=True), True),
    ("summary", dict(tools="summary", thinking=True, redact=True), True),
    ("none", dict(tools="none", thinking=True, redact=True), True),
    ("noredact", dict(tools="full", thinking=True, redact=False), False),
    ("nothink", dict(tools="full", thinking=False, redact=True), True),
]


def _doc(*, scope="run", agents=None, redact=True):
    model = collect_run(
        WF_ID,
        projects=EXPORT_PROJECTS,
        scope=scope,
        agents=agents,
        generated_at=PINNED,  # inject the pinned instant -> deterministic output
    )
    if not redact:
        # mirror the cli --no-redact model mutation (provenance redaction_mode -> off)
        model.redaction_mode = "off"
        model.provenance["redaction_mode"] = "off"
    return export_model(model)


def _golden(name: str, ext: str) -> str:
    with open(os.path.join(GOLDEN, f"wf_export00.{name}.{ext}"), encoding="utf-8") as f:
        return f.read()


@pytest.mark.parametrize("name,kwargs,redact", _COMBOS)
def test_golden_md_byte_identical(name, kwargs, redact):
    doc = _doc(redact=redact)
    assert render_md(doc, **kwargs) == _golden(name, "md")


@pytest.mark.parametrize("name,kwargs,redact", _COMBOS)
def test_golden_html_byte_identical(name, kwargs, redact):
    doc = _doc(redact=redact)
    assert render_html(doc, **kwargs) == _golden(name, "html")


def test_golden_agent_scope_md_html_byte_identical():
    doc = _doc(scope="agent", agents=["kitchensink"])
    assert render_md(doc, tools="full", thinking=True, redact=True) == _golden(
        "agent", "md"
    )
    assert render_html(doc, tools="full", thinking=True, redact=True) == _golden(
        "agent", "html"
    )


def test_pdf_routing_feeds_golden_channels(tmp_path, monkeypatch):
    """PDF is asserted by ROUTING: the (html, md) fed to the ladder is byte-identical to
    the golden channels, and the reported engine is the one the ladder returned."""
    captured: dict[str, str] = {}

    def fake_render_pdf(html, md, out_path, *, engine=None, runner=None):
        captured["html"] = html
        captured["md"] = md
        with open(out_path, "wb") as fh:
            fh.write(b"%PDF-1.4 fake")
        return "typst", out_path

    monkeypatch.setattr(mcx, "render_pdf", fake_render_pdf)
    doc = _doc()
    result = mcx.export_report(
        doc, str(tmp_path), WF_ID, fmt="pdf", tools="full", thinking=True, redact=True
    )
    assert result.engine == "typst"
    assert result.path.endswith(".pdf")
    # the exact channels fed to the ladder reduce to the MD/HTML golden
    assert captured["html"] == _golden("full", "html")
    assert captured["md"] == _golden("full", "md")
