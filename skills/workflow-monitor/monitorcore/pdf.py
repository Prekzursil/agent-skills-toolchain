"""Feature-detected PDF ladder for the shared export path (stdlib-only at import time).

``render_pdf`` turns a rendered HTML+Markdown pair into a PDF using the best available
engine, walking DOWN a fixed ladder on any failure and ALWAYS ending by writing the
self-contained interactive HTML next to ``out_path`` (the ``html`` rung never fails, so
the user always gets a usable artifact). It never raises to the caller.

Ladder order (``detect_engines`` lists the available rungs, ``html`` always last):

    typst  -> pandoc MD -> PDF with ``--pdf-engine=typst``
    playwright -> HTML -> ``page.pdf``
    edge   -> Edge headless ``--print-to-pdf`` (``--headless=new`` first, ``old`` fallback,
              then the ``chrome-headless-shell`` binary on Edge/Chrome 141+)
    chrome -> Chrome headless ``--print-to-pdf`` (same headless ladder)
    pandoc -> pandoc MD -> PDF (default engine)
    xhtml2pdf -> HTML -> ``pisa.CreatePDF``
    fpdf2  -> redacted plaintext -> ``FPDF.multi_cell``
    html   -> write the self-contained HTML (terminal; never fails)

CRITICAL invariant: NO PDF library is imported at module top level. Every third-party
lib/binary is discovered with ``shutil.which`` / ``importlib.util.find_spec`` and only
imported or spawned inside its own rung's ``try/except``. ``runner`` (default
``subprocess.run``) is injectable so the subprocess rungs are fully testable without a
real engine.
"""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import tempfile

from monitorcore.textsafe import strip_ansi

__all__ = ["detect_engines", "render_pdf"]

# Canonical ladder order. ``html`` is the terminal rung and is always reachable.
ALL_ENGINES = [
    "typst",
    "playwright",
    "edge",
    "chrome",
    "pandoc",
    "xhtml2pdf",
    "fpdf2",
    "html",
]

# Edge/Chrome 141 (Oct 2025) broke the legacy headless path; ``--headless=new`` must be
# attempted first, with ``--headless=old`` kept as a fallback, and the standalone
# ``chrome-headless-shell`` binary as a last resort on 141+ builds.
_EDGE_141 = 141


# --------------------------------------------------------------------- detection


def _has_module(name: str) -> bool:
    """True if ``name`` is importable, without importing it. Fail-safe on a poisoned
    ``sys.modules[name] = None`` sentinel (``find_spec`` raises ``ValueError`` then)."""
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _program_files_binary(rel: str) -> str | None:
    """Return the first existing ``<ProgramFiles*>/<rel>`` path, or ``None``."""
    for env in ("ProgramFiles(x86)", "ProgramFiles"):
        base = os.environ.get(env)
        if base:
            cand = os.path.join(base, *rel.split("/"))
            if os.path.isfile(cand):
                return cand
    return None


def _edge_binary() -> str | None:
    """Locate the Microsoft Edge binary (PATH first, then the standard install dir)."""
    found = shutil.which("msedge")
    if found:
        return found
    return _program_files_binary("Microsoft/Edge/Application/msedge.exe")


def _chrome_binary() -> str | None:
    """Locate the Google Chrome binary (PATH first, then the standard install dir)."""
    found = shutil.which("chrome")
    if found:
        return found
    return _program_files_binary("Google/Chrome/Application/chrome.exe")


def detect_engines() -> list[str]:
    """Return the available ladder rungs in priority order; ``html`` is always last."""
    engines: list[str] = []
    have_pandoc = shutil.which("pandoc") is not None
    if shutil.which("typst") is not None and have_pandoc:
        engines.append("typst")
    if _has_module("playwright"):
        engines.append("playwright")
    if _edge_binary() is not None:
        engines.append("edge")
    if _chrome_binary() is not None:
        engines.append("chrome")
    if have_pandoc:
        engines.append("pandoc")
    if _has_module("xhtml2pdf"):
        engines.append("xhtml2pdf")
    if _has_module("fpdf"):
        engines.append("fpdf2")
    engines.append("html")
    return engines


# ----------------------------------------------------------------------- helpers


def _ok(path: str) -> bool:
    """True if ``path`` exists and is non-empty (a real PDF was produced)."""
    try:
        return os.path.exists(path) and os.path.getsize(path) > 0
    except OSError:
        return False


def _safe_remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def _write_temp(text: str, suffix: str) -> str:
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    return path


# --------------------------------------------------------------- chromium rungs


def _chromium_major(binary: str, runner) -> int:
    """Best-effort major version of a chromium binary via ``--version`` (0 on failure)."""
    try:
        proc = runner([binary, "--version"], capture_output=True, text=True, timeout=15)
        text = (
            f"{getattr(proc, 'stdout', '') or ''} {getattr(proc, 'stderr', '') or ''}"
        )
        match = re.search(r"(\d+)\.\d+", text)
        return int(match.group(1)) if match else 0
    except Exception:
        return 0


def _render_chromium(binary: str | None, html: str, out_path: str, runner) -> bool:
    """Drive an Edge/Chrome binary to ``--print-to-pdf``; True once a PDF is written."""
    if not binary:
        return False
    html_path = _write_temp(html, ".html")
    user_data = tempfile.mkdtemp(prefix="wfmon-pdf-")
    try:
        major = _chromium_major(binary, runner)
        attempts: list[list[str]] = [
            [binary, "--headless=new"],
            [binary, "--headless=old"],
        ]
        if major >= _EDGE_141:
            shell = shutil.which("chrome-headless-shell")
            if shell:
                attempts.append([shell])
        file_uri = "file:///" + html_path.replace("\\", "/")
        common = [
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--user-data-dir={user_data}",
            f"--print-to-pdf={out_path}",
            file_uri,
        ]
        for prefix in attempts:
            try:
                runner(prefix + common, capture_output=True, timeout=120)
            except Exception:
                continue
            if _ok(out_path):
                return True
        return False
    finally:
        _safe_remove(html_path)
        shutil.rmtree(user_data, ignore_errors=True)


# ------------------------------------------------------------- pandoc-based rungs


def _pandoc_convert(md: str, out_path: str, runner, pdf_engine: str | None) -> bool:
    """Convert Markdown to PDF via pandoc (optionally forcing ``--pdf-engine``)."""
    md_path = _write_temp(md, ".md")
    try:
        argv = ["pandoc", md_path, "-o", out_path]
        if pdf_engine:
            argv.append(f"--pdf-engine={pdf_engine}")
        try:
            runner(argv, capture_output=True, timeout=120)
        except Exception:
            return False
        return _ok(out_path)
    finally:
        _safe_remove(md_path)


# -------------------------------------------------------------------- rung table


def _typst_rung(html: str, md: str, out_path: str, runner) -> tuple[bool, str]:
    if not (shutil.which("typst") and shutil.which("pandoc")):
        return False, ""
    return _pandoc_convert(md, out_path, runner, "typst"), out_path


def _playwright_rung(html: str, md: str, out_path: str, runner) -> tuple[bool, str]:
    if not _has_module("playwright"):
        return False, ""
    try:
        from playwright.sync_api import sync_playwright  # pyright: ignore[reportMissingImports]

        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page()
            page.set_content(html)
            page.pdf(path=out_path, print_background=True)
            browser.close()
    except Exception:
        return False, ""
    return _ok(out_path), out_path


def _edge_rung(html: str, md: str, out_path: str, runner) -> tuple[bool, str]:
    return _render_chromium(_edge_binary(), html, out_path, runner), out_path


def _chrome_rung(html: str, md: str, out_path: str, runner) -> tuple[bool, str]:
    return _render_chromium(_chrome_binary(), html, out_path, runner), out_path


def _pandoc_rung(html: str, md: str, out_path: str, runner) -> tuple[bool, str]:
    if not shutil.which("pandoc"):
        return False, ""
    return _pandoc_convert(md, out_path, runner, None), out_path


def _xhtml2pdf_rung(html: str, md: str, out_path: str, runner) -> tuple[bool, str]:
    if not _has_module("xhtml2pdf"):
        return False, ""
    try:
        from xhtml2pdf import pisa  # pyright: ignore[reportMissingImports]

        with open(out_path, "wb") as dest:
            result = pisa.CreatePDF(html, dest=dest)
        if getattr(result, "err", 1):
            return False, ""
    except Exception:
        return False, ""
    return _ok(out_path), out_path


def _fpdf2_rung(html: str, md: str, out_path: str, runner) -> tuple[bool, str]:
    if not _has_module("fpdf"):
        return False, ""
    try:
        from fpdf import FPDF  # pyright: ignore[reportMissingModuleSource]

        doc = FPDF()
        doc.set_auto_page_break(True, margin=15)
        doc.add_page()
        doc.set_font("Helvetica", size=10)
        # ``md`` is already redacted by the renderer; strip ANSI for a clean plaintext.
        text = strip_ansi(md).encode("latin-1", "replace").decode("latin-1")
        doc.multi_cell(0, 5, text)
        doc.output(out_path)
    except Exception:
        return False, ""
    return _ok(out_path), out_path


def _html_rung(html: str, md: str, out_path: str, runner) -> tuple[bool, str]:
    """Terminal rung: write the self-contained HTML next to ``out_path``. Never fails."""
    html_path = os.path.splitext(out_path)[0] + ".html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    return True, html_path


_RUNGS = {
    "typst": _typst_rung,
    "playwright": _playwright_rung,
    "edge": _edge_rung,
    "chrome": _chrome_rung,
    "pandoc": _pandoc_rung,
    "xhtml2pdf": _xhtml2pdf_rung,
    "fpdf2": _fpdf2_rung,
    "html": _html_rung,
}


# ------------------------------------------------------------------- public API


def _engine_candidates(engine: str | None) -> list[str]:
    """Non-``html`` rungs to attempt, in order. Empty => go straight to the HTML terminal.

    ``engine=None`` auto-selects every detected non-``html`` rung; a forced, known rung is
    tried alone (then degrades to HTML); ``html`` or an unknown name yields no candidates.
    """
    if engine is None:
        return [e for e in detect_engines() if e != "html"]
    if engine != "html" and engine in _RUNGS:
        return [engine]
    return []


def render_pdf(
    html: str,
    md: str,
    out_path: str,
    *,
    engine: str | None = None,
    runner=subprocess.run,
) -> tuple[str, str]:
    """Render ``html``/``md`` to a PDF, returning ``(engine_used, written_path)``.

    Tries the selected/auto engine, descending the ladder on any failure, and always
    ends on the HTML terminal rung (which never fails). Never raises to the caller.
    """
    for name in _engine_candidates(engine):
        try:
            ok, path = _RUNGS[name](html, md, out_path, runner)
        except Exception:
            ok, path = False, ""
        if ok:
            return name, path
    _, html_path = _html_rung(html, md, out_path, runner)
    return "html", html_path
