#!/usr/bin/env python3
"""``wfmon_export.cli`` tests: ``build_parser`` / ``run_export`` / ``main`` +
``_resolve_for_guard`` out-guard against the frozen ``wf_export00-fixture``.

All fixture-reading tests point at the ISOLATED export fixture root
``fixtures/export/projects`` (never the live ``~/.claude`` tree). Every write goes
to a ``tmp_path`` (or a monkeypatched tempdir) so the suite never pollutes the real
export directory. The read-only out-guard is proven for a plain sub-directory, an
existing-directory alias, and a NON-EXISTENT 8.3 short-name (``PREKZU~1``) path.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest

import workflow_run as wr
from wfmon_export import cli

# ── isolated export fixture root (mirrors test_model.py's EXPORT_PROJECTS) ──
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORT_PROJECTS = os.path.join(HERE, "fixtures", "export", "projects")
WF_ID = "wf_export00-fixture"


# ───────────────────────── small host helpers ─────────────────────────
def _free_drive() -> str | None:
    """A drive letter that is NOT mounted (for the guard's root-terminate branch)."""
    for letter in "ZYXWVUT":
        if not os.path.exists(f"{letter}:\\"):
            return letter
    return None


def _short_home() -> str | None:
    """The 8.3 short-name home (e.g. ``C:\\Users\\PREKZU~1``) if the host tempdir is
    expressed that way, else ``None``."""
    import tempfile

    tmp = tempfile.gettempdir()
    marker = os.sep + "AppData" + os.sep
    idx = tmp.lower().find(marker.lower())
    return tmp[:idx] if idx != -1 else None


# ═════════════════════════ build_parser ═════════════════════════
def test_build_parser_defaults():
    ns = cli.build_parser().parse_args([WF_ID])
    assert ns.wf_id == WF_ID
    assert ns.scope == "run"
    assert ns.agents is None
    assert ns.fmt == "md"
    assert ns.pdf_engine is None
    assert ns.tools == "full"
    assert ns.thinking is True
    assert ns.redact is True
    assert ns.out is None
    assert ns.projects == wr.DEFAULT_PROJECTS


def test_build_parser_full_surface_and_label_split():
    ns = cli.build_parser().parse_args(
        [
            WF_ID,
            "--scope",
            "subset",
            "--agents",
            "a, b ,c",
            "--format",
            "html",
            "--pdf-engine",
            "edge",
            "--tools",
            "summary",
            "--no-thinking",
            "--no-redact",
            "--out",
            "D:/x",
            "--projects",
            "P",
        ]
    )
    assert ns.scope == "subset"
    assert ns.agents == ["a", "b", "c"]  # comma split + strip, empties dropped
    assert ns.fmt == "html"
    assert ns.pdf_engine == "edge"
    assert ns.tools == "summary"
    assert ns.thinking is False
    assert ns.redact is False
    assert ns.out == "D:/x"
    assert ns.projects == "P"


def test_build_parser_bad_choice_exits_2():
    with pytest.raises(SystemExit) as ei:
        cli.build_parser().parse_args([WF_ID, "--scope", "bogus"])
    assert ei.value.code == 2


def test_split_labels_helper():
    assert cli._split_labels("a, b ,c") == ["a", "b", "c"]
    assert cli._split_labels("solo") == ["solo"]
    assert cli._split_labels("") == []
    assert cli._split_labels("  ,  ") == []


# ═════════════════════════ _extract_masked (banner parse) ═════════════════════════
def test_extract_masked_md_html_and_off():
    # md audit banner
    assert cli._extract_masked("> **redaction: strict** - 7 masked\nrest") == 7
    # html audit banner
    assert (
        cli._extract_masked(
            '<div class="banner audit">redaction: strict &mdash; 3 masked</div>'
        )
        == 3
    )
    # off banners carry no "<digits> masked" run -> None
    assert (
        cli._extract_masked("> **redaction: off** - secrets NOT masked (`--no-redact`)")
        is None
    )
    assert cli._extract_masked('<div class="banner audit">redaction: off</div>') is None
    # the FIRST (banner) match wins over later transcript content
    assert cli._extract_masked("redaction: strict - 2 masked\n... 99 masked ...") == 2


# ═════════════════════════ _resolve_for_guard ═════════════════════════
def test_resolve_for_guard_normcases_and_expands(tmp_path):
    # an existing dir resolves to its canonical (realpath) normcased form
    p = str(tmp_path)
    resolved = cli._resolve_for_guard(p)
    assert resolved == os.path.normcase(os.path.realpath(p))


def test_resolve_for_guard_nonexistent_tail(tmp_path):
    # nearest existing ancestor is realpath'd, the non-existent tail rejoined
    p = str(tmp_path / "no" / "such" / "dir")
    resolved = cli._resolve_for_guard(p)
    assert resolved.startswith(os.path.normcase(os.path.realpath(str(tmp_path))))
    assert resolved.endswith(os.path.normcase(os.path.join("no", "such", "dir")))


def test_resolve_for_guard_free_drive_terminates():
    letter = _free_drive()
    if letter is None:  # pragma: no cover - virtually every host has a free letter
        pytest.skip("no free drive letter available")
    # walks up to a NON-existent filesystem root and stops (no infinite loop)
    resolved = cli._resolve_for_guard(f"{letter}:\\nope\\deep\\sub")
    assert resolved
    assert resolved == os.path.normcase(resolved)


# ═════════════════════════ run_export: happy paths ═════════════════════════
def test_run_export_md_writes_and_returns_abs_path(tmp_path):
    path = cli.run_export(WF_ID, projects=EXPORT_PROJECTS, out=str(tmp_path))
    assert os.path.isabs(path)
    assert os.path.isfile(path)
    assert os.path.basename(path) == WF_ID + ".md"
    text = Path(path).read_text(encoding="utf-8")
    assert text.startswith("---")  # YAML front-matter
    assert "redaction: strict" in text
    assert "[REDACTED:" in text  # secretcheck secrets masked in the render path


def test_run_export_html_writes(tmp_path):
    path = cli.run_export(
        WF_ID, projects=EXPORT_PROJECTS, fmt="html", out=str(tmp_path)
    )
    assert os.path.basename(path) == WF_ID + ".html"
    text = Path(path).read_text(encoding="utf-8")
    assert "redaction" in text


def test_run_export_scope_agent_filename_and_targeting(tmp_path):
    path = cli.run_export(
        WF_ID,
        projects=EXPORT_PROJECTS,
        scope="agent",
        agents=["kitchensink"],
        out=str(tmp_path),
    )
    # scope != run appends the scope token to the basename
    assert os.path.basename(path) == WF_ID + ".agent.md"
    text = Path(path).read_text(encoding="utf-8")
    assert '<a id="agent-kitchensink"></a>' in text
    assert '<a id="agent-secretcheck"></a>' not in text


def test_run_export_default_out_created_on_demand(tmp_path, monkeypatch):
    monkeypatch.setattr(cli.tempfile, "gettempdir", lambda: str(tmp_path))
    path = cli.run_export(WF_ID, projects=EXPORT_PROJECTS)
    expected_dir = os.path.join(str(tmp_path), "wfmon-exports")
    assert os.path.isdir(expected_dir)  # created on demand
    assert os.path.dirname(path) == expected_dir
    assert os.path.isfile(path)


def test_run_export_no_redact_mutates_banner_and_frontmatter(tmp_path):
    path = cli.run_export(
        WF_ID, projects=EXPORT_PROJECTS, redact=False, out=str(tmp_path)
    )
    text = Path(path).read_text(encoding="utf-8")
    assert "redaction: off" in text
    # provenance mutated on both model + provenance -> front-matter reads "off"
    assert 'redaction_mode: "off"' in text
    # raw (unmasked) secret token surfaces when redaction is off
    assert "[REDACTED:" not in text


def test_run_export_tools_none_drops_tool_blocks(tmp_path):
    path = cli.run_export(
        WF_ID, projects=EXPORT_PROJECTS, tools="none", out=str(tmp_path)
    )
    text = Path(path).read_text(encoding="utf-8")
    assert "\U0001f527" not in text  # no 🔧 tool-detail blocks


def test_run_export_no_thinking_flows_to_renderer(tmp_path):
    with_t = cli.run_export(WF_ID, projects=EXPORT_PROJECTS, out=str(tmp_path / "t"))
    no_t = cli.run_export(
        WF_ID, projects=EXPORT_PROJECTS, thinking=False, out=str(tmp_path / "n")
    )
    assert "*thinking:*" in Path(with_t).read_text(encoding="utf-8")
    assert "*thinking:*" not in Path(no_t).read_text(encoding="utf-8")


def test_run_export_pdf_degrades_to_html(tmp_path):
    # forcing the html rung always degrades: writes .html, returns that path
    path = cli.run_export(
        WF_ID,
        projects=EXPORT_PROJECTS,
        fmt="pdf",
        pdf_engine="html",
        out=str(tmp_path),
    )
    assert path.endswith(".html")
    assert os.path.isfile(path)


def test_run_export_pdf_success_via_injected_engine(tmp_path, monkeypatch):
    captured = {}

    def fake_render_pdf(html, md, out_path, *, engine=None, runner=None):
        captured["html"] = html
        captured["md"] = md
        with open(out_path, "wb") as f:
            f.write(b"%PDF-1.4 fake")
        return "edge", out_path

    monkeypatch.setattr(cli, "render_pdf", fake_render_pdf)
    path = cli.run_export(WF_ID, projects=EXPORT_PROJECTS, fmt="pdf", out=str(tmp_path))
    assert path.endswith(".pdf")
    assert os.path.isfile(path)
    # both renderers fed the ladder
    assert "redaction" in captured["html"]
    assert captured["md"].startswith("---")


# ═════════════════════════ run_export: out-guard refusals ═════════════════════════
def test_out_guard_refuses_subdir(tmp_path, monkeypatch):
    root = tmp_path / "ro"
    root.mkdir()
    monkeypatch.setattr(cli, "_claude_projects_root", lambda: str(root))
    with pytest.raises(ValueError):
        cli.run_export(
            WF_ID, projects=EXPORT_PROJECTS, out=str(root / "exports" / "run")
        )


def test_out_guard_refuses_existing_alias(tmp_path, monkeypatch):
    # writing INTO the guarded root itself (same dir, canonical spelling) is refused
    root = tmp_path / "ro"
    root.mkdir()
    monkeypatch.setattr(cli, "_claude_projects_root", lambda: str(root))
    with pytest.raises(ValueError):
        cli.run_export(WF_ID, projects=EXPORT_PROJECTS, out=os.path.realpath(str(root)))


def test_out_guard_refuses_nonexistent_shortname(monkeypatch):
    short_home = _short_home()
    if not (short_home and "~" in short_home):
        pytest.skip("host tempdir does not expose an 8.3 short-name home")
    long_home = os.path.realpath(short_home)  # PREKZU~1 -> Prekzursil
    root = os.path.join(long_home, ".claude", "projects")  # guard root = LONG form
    monkeypatch.setattr(cli, "_claude_projects_root", lambda: root)
    # --out expressed via the 8.3 SHORT home + a NON-EXISTENT tail must still be caught
    out = os.path.join(short_home, ".claude", "projects", "does", "not", "exist")
    with pytest.raises(ValueError):
        cli.run_export(WF_ID, projects=EXPORT_PROJECTS, out=out)


def test_out_guard_allows_sibling_directory(tmp_path, monkeypatch):
    root = tmp_path / "ro"
    root.mkdir()
    monkeypatch.setattr(cli, "_claude_projects_root", lambda: str(root))
    path = cli.run_export(
        WF_ID, projects=EXPORT_PROJECTS, out=str(tmp_path / "elsewhere")
    )
    assert os.path.isfile(path)


# ═════════════════════════ main: invocation + exit codes ═════════════════════════
def test_main_bare_form_exit0(tmp_path, capsys):
    code = cli.main([WF_ID, "--projects", EXPORT_PROJECTS, "--out", str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 0
    lines = out.splitlines()
    assert os.path.isfile(lines[0])  # first line = abs written path
    assert lines[0].endswith(".md")
    masked_line = next(ln for ln in lines if ln.endswith("masked"))
    assert int(masked_line.split()[0]) > 0


def test_main_export_token_form_exit0(tmp_path):
    # wfmon.cmd forwards the whole tail incl the leading 'export' token
    code = cli.main(
        ["export", WF_ID, "--projects", EXPORT_PROJECTS, "--out", str(tmp_path)]
    )
    assert code == 0
    assert os.path.isfile(tmp_path / (WF_ID + ".md"))


def test_main_argv_none_reads_sys_argv(tmp_path, monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["wfmon", WF_ID, "--projects", EXPORT_PROJECTS, "--out", str(tmp_path)],
    )
    assert cli.main() == 0


def test_main_no_redact_prints_off(tmp_path, capsys):
    code = cli.main(
        [WF_ID, "--no-redact", "--projects", EXPORT_PROJECTS, "--out", str(tmp_path)]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "redaction: off" in out


def test_main_pdf_success_prints_engine_exit0(tmp_path, monkeypatch, capsys):
    def fake_render_pdf(html, md, out_path, *, engine=None, runner=None):
        with open(out_path, "wb") as f:
            f.write(b"%PDF-1.4 fake")
        return "edge", out_path

    monkeypatch.setattr(cli, "render_pdf", fake_render_pdf)
    code = cli.main(
        [
            WF_ID,
            "--format",
            "pdf",
            "--projects",
            EXPORT_PROJECTS,
            "--out",
            str(tmp_path),
        ]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "engine: edge" in out
    assert out.splitlines()[0].endswith(".pdf")


def test_main_pdf_html_degrade_exit1(tmp_path, capsys):
    code = cli.main(
        [
            WF_ID,
            "--format",
            "pdf",
            "--pdf-engine",
            "html",
            "--projects",
            EXPORT_PROJECTS,
            "--out",
            str(tmp_path),
        ]
    )
    out = capsys.readouterr().out
    assert code == 1  # degraded to HTML (no true PDF produced)
    assert "engine: html" in out


def test_main_unknown_wf_id_exit2(tmp_path):
    code = cli.main(
        ["wf_totally-absent-zzz", "--projects", EXPORT_PROJECTS, "--out", str(tmp_path)]
    )
    assert code == 2


def test_main_unknown_label_exit2(tmp_path):
    code = cli.main(
        [
            WF_ID,
            "--scope",
            "agent",
            "--agents",
            "ghost",
            "--projects",
            EXPORT_PROJECTS,
            "--out",
            str(tmp_path),
        ]
    )
    assert code == 2


def test_main_subset_without_agents_exit2(tmp_path):
    code = cli.main(
        [
            WF_ID,
            "--scope",
            "subset",
            "--projects",
            EXPORT_PROJECTS,
            "--out",
            str(tmp_path),
        ]
    )
    assert code == 2


def test_main_out_guard_exit2(tmp_path, monkeypatch):
    root = tmp_path / "ro"
    root.mkdir()
    monkeypatch.setattr(cli, "_claude_projects_root", lambda: str(root))
    code = cli.main([WF_ID, "--projects", EXPORT_PROJECTS, "--out", str(root / "x")])
    assert code == 2


def test_main_bad_arg_argparse_exit2(tmp_path):
    with pytest.raises(SystemExit) as ei:
        cli.main(
            [
                WF_ID,
                "--format",
                "xml",
                "--projects",
                EXPORT_PROJECTS,
                "--out",
                str(tmp_path),
            ]
        )
    assert ei.value.code == 2


def test_main_write_error_returns_1(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    # pre-create a DIRECTORY where the .md file must go -> open('w') raises OSError
    (out / (WF_ID + ".md")).mkdir()
    code = cli.main([WF_ID, "--projects", EXPORT_PROJECTS, "--out", str(out)])
    assert code == 1


# ═════════════════════════ packaging: __main__ + re-exports ═════════════════════════
def test_dunder_main_module_exposes_main():
    mod = importlib.import_module("wfmon_export.__main__")
    assert mod.main is cli.main


def test_package_reexports_cli_and_renderers():
    import wfmon_export

    # The PDF ladder now lives in the vendored monitorcore package; wfmon_export
    # re-exports it from there (extracted out of the skill in WU3).
    from monitorcore.pdf import detect_engines as de_fn
    from monitorcore.pdf import render_pdf as rp_fn
    from wfmon_export.render_md import render_markdown as rm_fn

    assert wfmon_export.run_export is cli.run_export
    assert wfmon_export.render_markdown is rm_fn
    assert wfmon_export.detect_engines is de_fn
    assert wfmon_export.render_pdf is rp_fn
    for name in ("run_export", "render_markdown", "detect_engines", "render_pdf"):
        assert name in wfmon_export.__all__


def test_render_html_submodule_not_shadowed():
    # render_html is intentionally NOT re-exported at package level (it would shadow
    # the render_html SUBMODULE that test_render_html.py imports as a module).
    import wfmon_export

    assert "render_html" not in wfmon_export.__all__
    from wfmon_export import render_html as rh

    assert hasattr(rh, "render_html")  # rh resolves to the MODULE, not the function
