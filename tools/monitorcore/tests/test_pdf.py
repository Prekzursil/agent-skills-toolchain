"""Unit tests for ``monitorcore.pdf`` - the feature-detected PDF ladder.

No real PDF engine is required or invoked: subprocess-based rungs are exercised with an
injected fake ``runner`` and monkeypatched binary discovery, and import-based rungs
(playwright / xhtml2pdf / fpdf2) with fake modules dropped into ``sys.modules``. The
module MUST never import a PDF library at import time; that invariant is proven by
reloading it with the optional deps poisoned to ``None``.

Covered: the import-safety invariant, ``detect_engines`` (all-present + none-present +
``html``-terminal), ``_has_module`` (present / absent / poisoned), binary discovery
(``which`` hit / ``ProgramFiles`` hit / miss), the chromium version probe, the Edge/Chrome
headless print-to-pdf ladder (``--headless=new`` first, descent to ``old``, then the
``chrome-headless-shell`` fallback), every rung body via a fake engine, and the guaranteed
HTML terminal fallback on forced-unavailable / runner-raises / unknown-engine.
"""

import importlib
import os
import sys
import types

import pytest

import monitorcore.pdf as pdf

HTML = "<html><body><h1>run</h1></body></html>"
MD = "# run\n\nhello\n"


# --------------------------------------------------------------------------- helpers


class FakeRunner:
    """Records every argv it is handed. Optionally writes the ``--print-to-pdf`` /
    ``-o`` output so a rung reports success; returns a fabricated ``--version`` string."""

    def __init__(
        self,
        *,
        make_output=False,
        version="Microsoft Edge 141.0.3179.54",
        raise_on_render=False,
        only_on=None,
    ):
        self.calls = []
        self.make_output = make_output
        self.version = version
        self.raise_on_render = raise_on_render
        self.only_on = only_on  # substring an argv item must contain to "succeed"

    def __call__(self, argv, **kwargs):
        self.calls.append(list(argv))
        joined = " ".join(argv)
        if "--version" in argv:
            return types.SimpleNamespace(stdout=self.version, stderr="", returncode=0)
        if self.raise_on_render:
            raise OSError("boom")
        out = _output_path(argv)
        if out is not None and self.make_output:
            if self.only_on is None or self.only_on in joined:
                with open(out, "wb") as f:
                    f.write(b"%PDF-1.7 fake")
        return types.SimpleNamespace(stdout="", stderr="", returncode=0)


def _output_path(argv):
    for a in argv:
        if a.startswith("--print-to-pdf="):
            return a.split("=", 1)[1]
    if "-o" in argv:
        return argv[argv.index("-o") + 1]
    return None


@pytest.fixture
def out_pdf(tmp_path):
    return str(tmp_path / "export.pdf")


# ------------------------------------------------------------------ import-safety


def test_no_toplevel_pdf_import(monkeypatch):
    # Poison the optional PDF deps: if the module imported any at top level, reload raises.
    for name in ("xhtml2pdf", "fpdf", "playwright", "reportlab"):
        monkeypatch.setitem(sys.modules, name, None)
    reloaded = importlib.reload(pdf)
    assert "html" in reloaded.detect_engines()
    # Restore a clean module object for the remaining tests in this process.
    importlib.reload(reloaded)


# -------------------------------------------------------------------- _has_module


def test_has_module_present():
    assert pdf._has_module("os") is True


def test_has_module_absent():
    assert pdf._has_module("nonexistent_module_zzz_123") is False


def test_has_module_poisoned_none(monkeypatch):
    # A ``sys.modules[name] = None`` sentinel makes ``find_spec`` raise ValueError.
    monkeypatch.setitem(sys.modules, "xhtml2pdf", None)
    assert pdf._has_module("xhtml2pdf") is False


# ------------------------------------------------------------------ detect_engines


def test_detect_engines_ends_with_html():
    engines = pdf.detect_engines()
    assert engines[-1] == "html"
    assert "html" in engines


def test_detect_engines_all_available(monkeypatch):
    monkeypatch.setattr(pdf.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(pdf, "_has_module", lambda name: True)
    monkeypatch.setattr(pdf, "_edge_binary", lambda: "msedge.exe")
    monkeypatch.setattr(pdf, "_chrome_binary", lambda: "chrome.exe")
    assert pdf.detect_engines() == [
        "typst",
        "playwright",
        "edge",
        "chrome",
        "pandoc",
        "xhtml2pdf",
        "fpdf2",
        "html",
    ]


def test_detect_engines_none_available(monkeypatch):
    monkeypatch.setattr(pdf.shutil, "which", lambda name: None)
    monkeypatch.setattr(pdf, "_has_module", lambda name: False)
    monkeypatch.setattr(pdf, "_edge_binary", lambda: None)
    monkeypatch.setattr(pdf, "_chrome_binary", lambda: None)
    assert pdf.detect_engines() == ["html"]


# ------------------------------------------------------------- binary discovery


def test_edge_binary_from_which(monkeypatch):
    monkeypatch.setattr(pdf.shutil, "which", lambda name: "C:/edge/msedge.exe")
    assert pdf._edge_binary() == "C:/edge/msedge.exe"


def test_edge_binary_from_program_files(monkeypatch):
    monkeypatch.setattr(pdf.shutil, "which", lambda name: None)
    monkeypatch.setitem(os.environ, "ProgramFiles(x86)", r"C:\PF86")
    monkeypatch.setattr(pdf.os.path, "isfile", lambda p: p.endswith("msedge.exe"))
    assert pdf._edge_binary().endswith("msedge.exe")


def test_edge_binary_missing(monkeypatch):
    monkeypatch.setattr(pdf.shutil, "which", lambda name: None)
    monkeypatch.setattr(pdf.os.path, "isfile", lambda p: False)
    assert pdf._edge_binary() is None


def test_chrome_binary_from_which(monkeypatch):
    monkeypatch.setattr(pdf.shutil, "which", lambda name: "C:/chrome/chrome.exe")
    assert pdf._chrome_binary() == "C:/chrome/chrome.exe"


def test_chrome_binary_from_program_files(monkeypatch):
    monkeypatch.setattr(pdf.shutil, "which", lambda name: None)
    monkeypatch.setitem(os.environ, "ProgramFiles", r"C:\PF")
    monkeypatch.setattr(pdf.os.path, "isfile", lambda p: p.endswith("chrome.exe"))
    assert pdf._chrome_binary().endswith("chrome.exe")


def test_chrome_binary_missing(monkeypatch):
    monkeypatch.setattr(pdf.shutil, "which", lambda name: None)
    monkeypatch.setattr(pdf.os.path, "isfile", lambda p: False)
    assert pdf._chrome_binary() is None


# ----------------------------------------------------------- chromium version probe


def test_chromium_major_parsed():
    runner = FakeRunner(version="Microsoft Edge 141.0.3179.54")
    assert pdf._chromium_major("msedge", runner) == 141


def test_chromium_major_no_digits():
    runner = FakeRunner(version="edge (dev build)")
    assert pdf._chromium_major("msedge", runner) == 0


def test_chromium_major_runner_raises():
    def boom(argv, **kwargs):
        raise OSError("no such binary")

    assert pdf._chromium_major("msedge", boom) == 0


# ------------------------------------------------------------------- html terminal


def test_render_pdf_html_terminal(out_pdf):
    engine, path = pdf.render_pdf(HTML, MD, out_pdf, engine="html")
    assert engine == "html"
    assert path.endswith(".html")
    with open(path, encoding="utf-8") as f:
        assert f.read() == HTML


def test_render_pdf_auto_no_engines(monkeypatch, out_pdf):
    monkeypatch.setattr(pdf, "detect_engines", lambda: ["html"])
    engine, path = pdf.render_pdf(HTML, MD, out_pdf)
    assert engine == "html"
    assert os.path.exists(path)


def test_render_pdf_unknown_engine(out_pdf):
    engine, path = pdf.render_pdf(HTML, MD, out_pdf, engine="bogus")
    assert engine == "html"


# --------------------------------------------------------------- edge / chrome rungs


def test_render_pdf_edge_argv_headless_new(monkeypatch, out_pdf):
    monkeypatch.setattr(pdf, "_edge_binary", lambda: "msedge.exe")
    runner = FakeRunner(make_output=True)
    engine, path = pdf.render_pdf(HTML, MD, out_pdf, engine="edge", runner=runner)
    assert engine == "edge"
    assert path == out_pdf
    render_calls = [c for c in runner.calls if "--version" not in c]
    first = render_calls[0]
    assert "--headless=new" in first
    assert any(a.startswith("--print-to-pdf=") for a in first)
    assert any(a.startswith("file:///") for a in first)


def test_render_pdf_edge_descends_new_then_old(monkeypatch, out_pdf):
    monkeypatch.setattr(pdf, "_edge_binary", lambda: "msedge.exe")
    monkeypatch.setattr(pdf.shutil, "which", lambda name: None)  # no headless-shell
    runner = FakeRunner(make_output=False)  # never produces a PDF -> all attempts fail
    engine, path = pdf.render_pdf(HTML, MD, out_pdf, engine="edge", runner=runner)
    assert engine == "html"
    modes = [
        m
        for c in runner.calls
        if "--version" not in c
        for m in c
        if m.startswith("--headless=")
    ]
    assert modes == ["--headless=new", "--headless=old"]


def test_render_pdf_edge_runner_raises_descends(monkeypatch, out_pdf):
    monkeypatch.setattr(pdf, "_edge_binary", lambda: "msedge.exe")
    monkeypatch.setattr(pdf.shutil, "which", lambda name: None)
    runner = FakeRunner(raise_on_render=True)
    engine, path = pdf.render_pdf(HTML, MD, out_pdf, engine="edge", runner=runner)
    assert engine == "html"


def test_render_pdf_edge_unavailable_descends(monkeypatch, out_pdf):
    monkeypatch.setattr(pdf, "_edge_binary", lambda: None)
    runner = FakeRunner(make_output=True)
    engine, path = pdf.render_pdf(HTML, MD, out_pdf, engine="edge", runner=runner)
    assert engine == "html"


def test_render_pdf_auto_selects_edge(monkeypatch, out_pdf):
    monkeypatch.setattr(pdf, "detect_engines", lambda: ["edge", "html"])
    monkeypatch.setattr(pdf, "_edge_binary", lambda: "msedge.exe")
    monkeypatch.setattr(pdf.shutil, "which", lambda name: None)
    runner = FakeRunner(make_output=True)
    engine, path = pdf.render_pdf(HTML, MD, out_pdf, runner=runner)
    assert engine == "edge"


def test_render_pdf_chrome_headless_shell_fallback(monkeypatch, out_pdf):
    monkeypatch.setattr(pdf, "_edge_binary", lambda: "msedge.exe")
    # headless-shell exists; only the shell attempt is allowed to produce output.
    monkeypatch.setattr(
        pdf.shutil,
        "which",
        lambda name: (
            "chrome-headless-shell.exe" if name == "chrome-headless-shell" else None
        ),
    )
    runner = FakeRunner(make_output=True, only_on="chrome-headless-shell")
    engine, path = pdf.render_pdf(HTML, MD, out_pdf, engine="edge", runner=runner)
    assert engine == "edge"
    # The shell binary was the one that finally produced the PDF.
    shell_calls = [c for c in runner.calls if "chrome-headless-shell.exe" in c[0]]
    assert shell_calls


def test_render_pdf_chrome_engine(monkeypatch, out_pdf):
    monkeypatch.setattr(pdf, "_chrome_binary", lambda: "chrome.exe")
    monkeypatch.setattr(pdf.shutil, "which", lambda name: None)
    runner = FakeRunner(make_output=True)
    engine, path = pdf.render_pdf(HTML, MD, out_pdf, engine="chrome", runner=runner)
    assert engine == "chrome"
    assert runner.calls[-1][0] == "chrome.exe"


# ------------------------------------------------------------------- pandoc / typst


def test_render_pdf_typst_argv(monkeypatch, out_pdf):
    monkeypatch.setattr(pdf.shutil, "which", lambda name: f"/usr/bin/{name}")
    runner = FakeRunner(make_output=True)
    engine, path = pdf.render_pdf(HTML, MD, out_pdf, engine="typst", runner=runner)
    assert engine == "typst"
    call = runner.calls[-1]
    assert call[0] == "pandoc"
    assert "--pdf-engine=typst" in call


def test_render_pdf_typst_unavailable_descends(monkeypatch, out_pdf):
    monkeypatch.setattr(pdf.shutil, "which", lambda name: None)
    runner = FakeRunner(make_output=True)
    engine, path = pdf.render_pdf(HTML, MD, out_pdf, engine="typst", runner=runner)
    assert engine == "html"


def test_render_pdf_pandoc(monkeypatch, out_pdf):
    monkeypatch.setattr(
        pdf.shutil,
        "which",
        lambda name: "/usr/bin/pandoc" if name == "pandoc" else None,
    )
    runner = FakeRunner(make_output=True)
    engine, path = pdf.render_pdf(HTML, MD, out_pdf, engine="pandoc", runner=runner)
    assert engine == "pandoc"
    call = runner.calls[-1]
    assert call[0] == "pandoc"
    assert "--pdf-engine=typst" not in call


def test_render_pdf_pandoc_unavailable_descends(monkeypatch, out_pdf):
    monkeypatch.setattr(pdf.shutil, "which", lambda name: None)
    runner = FakeRunner(make_output=True)
    engine, path = pdf.render_pdf(HTML, MD, out_pdf, engine="pandoc", runner=runner)
    assert engine == "html"


def test_render_pdf_pandoc_no_output_descends(monkeypatch, out_pdf):
    monkeypatch.setattr(
        pdf.shutil,
        "which",
        lambda name: "/usr/bin/pandoc" if name == "pandoc" else None,
    )
    runner = FakeRunner(make_output=False)  # pandoc "runs" but writes nothing
    engine, path = pdf.render_pdf(HTML, MD, out_pdf, engine="pandoc", runner=runner)
    assert engine == "html"


# ------------------------------------------------- import-based rungs (fake modules)


def _install_fake_playwright(monkeypatch, *, write=True):
    mod = types.ModuleType("playwright")
    sync_mod = types.ModuleType("playwright.sync_api")

    class _Page:
        def set_content(self, html):
            self._html = html

        def pdf(self, *, path, print_background=False):
            if write:
                with open(path, "wb") as f:
                    f.write(b"%PDF fake")

    class _Browser:
        def new_page(self):
            return _Page()

        def close(self):
            pass

    class _Chromium:
        def launch(self):
            return _Browser()

    class _PW:
        def __enter__(self):
            return types.SimpleNamespace(chromium=_Chromium())

        def __exit__(self, *exc):
            return False

    sync_mod.sync_playwright = lambda: _PW()
    mod.sync_api = sync_mod
    monkeypatch.setitem(sys.modules, "playwright", mod)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", sync_mod)


def test_render_pdf_playwright(monkeypatch, out_pdf):
    _install_fake_playwright(monkeypatch, write=True)
    monkeypatch.setattr(pdf, "_has_module", lambda name: name == "playwright")
    engine, path = pdf.render_pdf(HTML, MD, out_pdf, engine="playwright")
    assert engine == "playwright"
    assert path == out_pdf


def test_render_pdf_playwright_unavailable_descends(monkeypatch, out_pdf):
    monkeypatch.setattr(pdf, "_has_module", lambda name: False)
    engine, path = pdf.render_pdf(HTML, MD, out_pdf, engine="playwright")
    assert engine == "html"


def test_render_pdf_playwright_no_output_descends(monkeypatch, out_pdf):
    _install_fake_playwright(monkeypatch, write=False)
    monkeypatch.setattr(pdf, "_has_module", lambda name: name == "playwright")
    engine, path = pdf.render_pdf(HTML, MD, out_pdf, engine="playwright")
    assert engine == "html"


def _install_fake_xhtml2pdf(monkeypatch, *, err=0):
    mod = types.ModuleType("xhtml2pdf")
    pisa = types.ModuleType("xhtml2pdf.pisa")

    def create_pdf(src, dest=None, **kwargs):
        if err == 0 and dest is not None:
            dest.write(b"%PDF fake")
        return types.SimpleNamespace(err=err)

    pisa.CreatePDF = create_pdf
    mod.pisa = pisa
    monkeypatch.setitem(sys.modules, "xhtml2pdf", mod)
    monkeypatch.setitem(sys.modules, "xhtml2pdf.pisa", pisa)


def test_render_pdf_xhtml2pdf(monkeypatch, out_pdf):
    _install_fake_xhtml2pdf(monkeypatch, err=0)
    monkeypatch.setattr(pdf, "_has_module", lambda name: name == "xhtml2pdf")
    engine, path = pdf.render_pdf(HTML, MD, out_pdf, engine="xhtml2pdf")
    assert engine == "xhtml2pdf"
    assert path == out_pdf


def test_render_pdf_xhtml2pdf_error_descends(monkeypatch, out_pdf):
    _install_fake_xhtml2pdf(monkeypatch, err=1)
    monkeypatch.setattr(pdf, "_has_module", lambda name: name == "xhtml2pdf")
    engine, path = pdf.render_pdf(HTML, MD, out_pdf, engine="xhtml2pdf")
    assert engine == "html"


def test_render_pdf_xhtml2pdf_unavailable_descends(monkeypatch, out_pdf):
    monkeypatch.setattr(pdf, "_has_module", lambda name: False)
    engine, path = pdf.render_pdf(HTML, MD, out_pdf, engine="xhtml2pdf")
    assert engine == "html"


def _install_fake_fpdf(monkeypatch, *, write=True):
    mod = types.ModuleType("fpdf")

    class FPDF:
        def add_page(self):
            pass

        def set_font(self, *a, **k):
            pass

        def set_auto_page_break(self, *a, **k):
            pass

        def multi_cell(self, *a, **k):
            pass

        def output(self, path):
            if write:
                with open(path, "wb") as f:
                    f.write(b"%PDF fake")

    mod.FPDF = FPDF
    monkeypatch.setitem(sys.modules, "fpdf", mod)


def test_render_pdf_fpdf2(monkeypatch, out_pdf):
    _install_fake_fpdf(monkeypatch, write=True)
    monkeypatch.setattr(pdf, "_has_module", lambda name: name == "fpdf")
    engine, path = pdf.render_pdf(HTML, MD, out_pdf, engine="fpdf2")
    assert engine == "fpdf2"
    assert path == out_pdf


def test_render_pdf_fpdf2_no_output_descends(monkeypatch, out_pdf):
    _install_fake_fpdf(monkeypatch, write=False)
    monkeypatch.setattr(pdf, "_has_module", lambda name: name == "fpdf")
    engine, path = pdf.render_pdf(HTML, MD, out_pdf, engine="fpdf2")
    assert engine == "html"


def test_render_pdf_fpdf2_unavailable_descends(monkeypatch, out_pdf):
    monkeypatch.setattr(pdf, "_has_module", lambda name: False)
    engine, path = pdf.render_pdf(HTML, MD, out_pdf, engine="fpdf2")
    assert engine == "html"


# ---------------------------------------------------- defensive branches (100% lane)


def test_has_module_import_error(monkeypatch):
    # ``find_spec`` may raise ``ImportError`` for a broken parent package.
    def boom(name):
        raise ImportError("broken parent")

    monkeypatch.setattr(pdf.importlib.util, "find_spec", boom)
    assert pdf._has_module("whatever.sub") is False


def test_program_files_binary_env_absent(monkeypatch):
    # Neither ProgramFiles env var set -> the ``if base:`` guard skips both iterations.
    monkeypatch.delenv("ProgramFiles(x86)", raising=False)
    monkeypatch.delenv("ProgramFiles", raising=False)
    assert pdf._program_files_binary("Vendor/App/app.exe") is None


def test_ok_oserror(monkeypatch):
    # ``getsize`` raising (e.g. race delete) must be swallowed -> not "ok".
    monkeypatch.setattr(pdf.os.path, "exists", lambda p: True)

    def boom(p):
        raise OSError("gone")

    monkeypatch.setattr(pdf.os.path, "getsize", boom)
    assert pdf._ok("phantom.pdf") is False


def test_safe_remove_oserror(monkeypatch):
    # ``_safe_remove`` never propagates an ``OSError``.
    def boom(p):
        raise OSError("locked")

    monkeypatch.setattr(pdf.os, "remove", boom)
    pdf._safe_remove("locked.tmp")  # must not raise


def test_render_pdf_edge_major_below_141(monkeypatch, out_pdf):
    # major < 141 -> the chrome-headless-shell branch is skipped entirely.
    monkeypatch.setattr(pdf, "_edge_binary", lambda: "msedge.exe")
    runner = FakeRunner(make_output=True, version="Microsoft Edge 120.0.0.0")
    engine, path = pdf.render_pdf(HTML, MD, out_pdf, engine="edge", runner=runner)
    assert engine == "edge"
    # No headless-shell was consulted; only the two headless modes were attempted.
    modes = [
        m
        for c in runner.calls
        if "--version" not in c
        for m in c
        if m.startswith("--headless=")
    ]
    assert modes[0] == "--headless=new"


def test_render_pdf_pandoc_runner_raises_descends(monkeypatch, out_pdf):
    monkeypatch.setattr(
        pdf.shutil,
        "which",
        lambda name: "/usr/bin/pandoc" if name == "pandoc" else None,
    )
    runner = FakeRunner(raise_on_render=True)
    engine, path = pdf.render_pdf(HTML, MD, out_pdf, engine="pandoc", runner=runner)
    assert engine == "html"


def test_render_pdf_playwright_raises_descends(monkeypatch, out_pdf):
    mod = types.ModuleType("playwright")
    sync_mod = types.ModuleType("playwright.sync_api")

    def boom():
        raise RuntimeError("playwright launch failed")

    sync_mod.sync_playwright = boom
    mod.sync_api = sync_mod
    monkeypatch.setitem(sys.modules, "playwright", mod)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", sync_mod)
    monkeypatch.setattr(pdf, "_has_module", lambda name: name == "playwright")
    engine, path = pdf.render_pdf(HTML, MD, out_pdf, engine="playwright")
    assert engine == "html"


def test_render_pdf_xhtml2pdf_raises_descends(monkeypatch, out_pdf):
    mod = types.ModuleType("xhtml2pdf")
    pisa = types.ModuleType("xhtml2pdf.pisa")

    def boom(*a, **k):
        raise RuntimeError("pisa exploded")

    pisa.CreatePDF = boom
    mod.pisa = pisa
    monkeypatch.setitem(sys.modules, "xhtml2pdf", mod)
    monkeypatch.setitem(sys.modules, "xhtml2pdf.pisa", pisa)
    monkeypatch.setattr(pdf, "_has_module", lambda name: name == "xhtml2pdf")
    engine, path = pdf.render_pdf(HTML, MD, out_pdf, engine="xhtml2pdf")
    assert engine == "html"


def test_render_pdf_fpdf2_raises_descends(monkeypatch, out_pdf):
    mod = types.ModuleType("fpdf")

    class FPDF:
        def __init__(self):
            raise RuntimeError("fpdf init failed")

    mod.FPDF = FPDF
    monkeypatch.setitem(sys.modules, "fpdf", mod)
    monkeypatch.setattr(pdf, "_has_module", lambda name: name == "fpdf")
    engine, path = pdf.render_pdf(HTML, MD, out_pdf, engine="fpdf2")
    assert engine == "html"


def test_render_pdf_rung_raises_descends_to_html(monkeypatch, out_pdf):
    # A rung raising unexpectedly is caught by ``render_pdf`` itself -> HTML terminal.
    def boom(*a, **k):
        raise RuntimeError("rung explode")

    monkeypatch.setitem(pdf._RUNGS, "edge", boom)
    monkeypatch.setattr(pdf, "_edge_binary", lambda: "msedge.exe")
    engine, path = pdf.render_pdf(HTML, MD, out_pdf, engine="edge")
    assert engine == "html"
    assert path.endswith(".html")
