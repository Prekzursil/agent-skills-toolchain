"""``monitorcore.export`` — the generic export pipeline + the read-only out-guard mechanism.

Covers the mask-count banner parse, the 8.3/junction-expanding guard resolver + containment
check, and the ``export_report`` md/html/pdf branches (PDF via an injected fake ``render_pdf``
so no real engine is needed and the routing is asserted deterministically). Byte fidelity of
the rendered artifacts is proven by the golden harness; here we hold the pipeline branches to
the tools/monitorcore 100% gate.
"""

from __future__ import annotations

import os

import pytest

from monitorcore import export as mcx
from monitorcore.export import (
    export_report,
    extract_masked,
    resolve_for_guard,
    under_root,
)
from monitorcore.report_doc import ReportDoc, Section
from monitorcore.timeline import TimelineEvent as TE


def _free_drive() -> str | None:
    for letter in "ZYXWVUT":
        if not os.path.exists(f"{letter}:\\"):
            return letter
    return None


def _doc() -> ReportDoc:
    card = Section(
        title="a",
        anchor="agent-a",
        card=True,
        badge="done",
        task="t",
        output="o",
        timeline=(TE(kind="text", seq=0, text="sk-FAKE0000000000000000000000"),),
    )
    return ReportDoc(
        title="Run",
        generated_at="2026-07-12T00:00:00+00:00",
        subtitle="wf_x",
        meta=(("wf_id", "wf_x"),),
        rollup=(
            ("running", 0),
            ("done", 1),
            ("error", 0),
            ("idle", 0),
            ("total", 1),
            ("tokens", 0),
        ),
        blocks=(Section(title="P", anchor="phase-1", index=1, children=(card,)),),
    )


# ───────────────────────── extract_masked ─────────────────────────
def test_extract_masked_md_html_and_off():
    assert extract_masked("> **redaction: strict** - 7 masked\nrest") == 7
    assert (
        extract_masked(
            '<div class="banner audit">redaction: strict &mdash; 3 masked</div>'
        )
        == 3
    )
    assert (
        extract_masked("> **redaction: off** - secrets NOT masked (`--no-redact`)")
        is None
    )
    assert extract_masked('<div class="banner audit">redaction: off</div>') is None
    # first (banner) match wins over later transcript content
    assert extract_masked("redaction: strict - 2 masked\n... 99 masked ...") == 2


# ───────────────────────── resolve_for_guard / under_root ─────────────────────────
def test_resolve_for_guard_existing_and_tail(tmp_path):
    assert resolve_for_guard(str(tmp_path)) == os.path.normcase(
        os.path.realpath(str(tmp_path))
    )
    tail = resolve_for_guard(str(tmp_path / "no" / "such"))
    assert tail.startswith(os.path.normcase(os.path.realpath(str(tmp_path))))
    assert tail.endswith(os.path.normcase(os.path.join("no", "such")))


def test_resolve_for_guard_free_drive_terminates():
    letter = _free_drive()
    if letter is None:  # pragma: no cover - virtually every host has a free letter
        pytest.skip("no free drive letter available")
    resolved = resolve_for_guard(f"{letter}:\\nope\\deep")
    assert resolved and resolved == os.path.normcase(resolved)


def test_resolve_for_guard_ascends_to_root(monkeypatch):
    # Force the ascent to reach a filesystem root (parent == head) on ANY platform.
    # With nothing existing, the loop climbs to the root and takes the `break` guard --
    # otherwise unreachable on POSIX via real paths, where "/" always exists (so the
    # free-drive test above only exercises the break on Windows).
    monkeypatch.setattr(mcx.os.path, "exists", lambda _p: False)
    resolved = resolve_for_guard(os.path.join(os.sep, "nope", "deep"))
    assert resolved == os.path.normcase(resolved)


def test_under_root_containment(tmp_path):
    root = tmp_path / "ro"
    root.mkdir()
    assert under_root(str(root / "sub" / "x"), str(root)) is True  # under
    assert under_root(os.path.realpath(str(root)), str(root)) is True  # equal
    assert under_root(str(tmp_path / "elsewhere"), str(root)) is False  # sibling


# ───────────────────────── export_report ─────────────────────────
def test_export_report_md(tmp_path):
    out = tmp_path / "sub"  # created on demand
    result = export_report(_doc(), str(out), "base", fmt="md")
    assert result.engine == ""
    assert result.path.endswith("base.md")
    assert os.path.isfile(result.path)
    assert result.masked and result.masked > 0  # the FAKE secret was masked


def test_export_report_html(tmp_path):
    result = export_report(_doc(), str(tmp_path), "base", fmt="html")
    assert result.path.endswith("base.html")
    assert "redaction" in open(result.path, encoding="utf-8").read()


def test_export_report_no_redact_masked_none(tmp_path):
    result = export_report(_doc(), str(tmp_path), "base", fmt="md", redact=False)
    assert result.masked is None


def test_export_report_pdf_routing(tmp_path, monkeypatch):
    captured = {}

    def fake_render_pdf(html, md, out_path, *, engine=None, runner=None):
        captured["html"] = html
        captured["md"] = md
        captured["engine_arg"] = engine
        with open(out_path, "wb") as fh:
            fh.write(b"%PDF-1.4 fake")
        return "typst", out_path

    monkeypatch.setattr(mcx, "render_pdf", fake_render_pdf)
    result = export_report(_doc(), str(tmp_path), "base", fmt="pdf", pdf_engine="typst")
    assert result.engine == "typst"
    assert result.path.endswith("base.pdf")
    assert captured["engine_arg"] == "typst"
    assert captured["md"].startswith("---")  # md channel fed to the ladder
    assert "redaction" in captured["html"]  # html channel fed to the ladder
    assert result.masked and result.masked > 0
