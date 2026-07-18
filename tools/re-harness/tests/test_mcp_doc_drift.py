"""Hermetic unit tests for mcp_doc_drift (documented-but-missing MCP audit).

Every test injects the `claude mcp list` output as a string (the injectable
seam) and passes explicit doc paths -- NO live network, NO subprocess. A single
@pytest.mark.live smoke test exercises the real CLI and is excluded from the
fast suite via `-m "not live"`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import mcp_doc_drift as m  # noqa: E402

SAMPLE_LIST = """Checking MCP server health…

claude.ai Boltz API: https://mcp.boltz.bio/mcp - ✔ Connected
codex: codex mcp-server - ✔ Connected
basic-memory: basic-memory mcp - ✔ Connected
cloud-hub: C:\\Python314\\python.exe hub.py - ✔ Connected
angr: http://127.0.0.1:8760/sse (SSE) - ✘ Failed to connect

MCP config diagnostics ⚠
Location: C:\\Users\\x\\.mcp.json
 └ [Warning] [cloud-hub] mcpServers.cloud-hub: Missing environment variables
"""


def test_normalize_folds_handles_and_display_names():
    assert m.normalize("claude_ai_Boltz_API") == m.normalize("claude.ai Boltz API")
    assert m.normalize("basic-memory") == "basic_memory"
    assert m.normalize("  Codex  ") == "codex"


def test_extract_handles_captures_hyphenated_server_names():
    text = "call mcp__basic-memory__search and mcp__codex__codex and mcp__claude_ai_Boltz_API__x"
    assert m.extract_handles(text) == {"basic-memory", "codex", "claude_ai_Boltz_API"}


def test_extract_handles_ignores_non_handles():
    assert m.extract_handles("this mentions mcp servers but no handles") == set()


def test_extract_prose_matches_known_aliases_only():
    assert m.extract_prose("run the codex mcp-server and basic-memory mcp") == {
        "codex",
        "basic-memory",
    }
    assert m.extract_prose("no known server names here") == set()


def test_parse_mcp_list_reads_status_and_skips_diagnostics():
    mounted = m.parse_mcp_list(SAMPLE_LIST)
    assert mounted["codex"]["connected"] is True
    assert mounted["basic_memory"]["connected"] is True
    assert mounted["angr"]["connected"] is False
    assert mounted["claude_ai_boltz_api"]["raw"] == "claude.ai Boltz API"
    # Diagnostic / header lines must not become "servers".
    assert "location" not in mounted
    assert "checking_mcp_server_health" not in mounted


def test_audit_flags_missing_handle_server_high():
    mounted = m.parse_mcp_list(SAMPLE_LIST)
    rep = m.audit({"codex", "ghost-server"}, set(), mounted)
    kinds = {(f["server"], f["kind"], f["severity"]) for f in rep["findings"]}
    assert ("ghost-server", "documented-but-missing", "HIGH") in kinds
    assert rep["counts"]["HIGH"] == 1


def test_audit_flags_mounted_but_failed_server():
    mounted = m.parse_mcp_list(SAMPLE_LIST)
    rep = m.audit({"angr"}, set(), mounted)
    assert rep["findings"][0]["kind"] == "documented-but-failed"
    assert rep["counts"]["HIGH"] == 1


def test_audit_clean_when_all_documented_are_connected():
    mounted = m.parse_mcp_list(SAMPLE_LIST)
    rep = m.audit({"codex", "basic-memory"}, set(), mounted)
    assert rep["findings"] == []
    assert rep["counts"] == {"HIGH": 0, "MEDIUM": 0}


def test_audit_prose_only_is_medium_and_deduped_against_handles():
    mounted = m.parse_mcp_list(SAMPLE_LIST)
    # "agent-mail" is prose-only and NOT mounted -> MEDIUM. "codex" prose is also
    # a handle so it must NOT double-report.
    rep = m.audit({"codex"}, {"codex", "agent-mail"}, mounted)
    servers = [(f["server"], f["severity"]) for f in rep["findings"]]
    assert ("agent-mail", "MEDIUM") in servers
    assert all(s != "codex" for s, _ in servers)
    assert rep["counts"] == {"HIGH": 0, "MEDIUM": 1}


def test_audit_optional_servers_never_flagged():
    mounted = m.parse_mcp_list(SAMPLE_LIST)
    rep = m.audit({"angr"}, set(), mounted, optional=frozenset({"angr"}))
    assert rep["findings"] == []


def test_build_report_no_docs_returns_error(tmp_path):
    rep = m.build_report(doc_paths=[tmp_path / "nope.md"], list_output=SAMPLE_LIST)
    assert rep["error"] == "no-docs"


def test_build_report_end_to_end_with_injected_list(tmp_path):
    doc = tmp_path / "CLAUDE.md"
    doc.write_text(
        "we use mcp__codex__codex and mcp__basic-memory__search and mcp__ghost__x",
        encoding="utf-8",
    )
    rep = m.build_report(doc_paths=[doc], list_output=SAMPLE_LIST)
    missing = {f["server"] for f in rep["findings"]}
    assert missing == {"ghost"}
    assert rep["read_paths"] == [str(doc)]


def test_main_returns_1_on_drift(tmp_path, monkeypatch, capsys):
    doc = tmp_path / "CLAUDE.md"
    doc.write_text("mcp__ghost__x", encoding="utf-8")
    monkeypatch.setattr(m, "run_claude_mcp_list", lambda *a, **k: SAMPLE_LIST)
    rc = m.main(["--docs", str(doc)])
    assert rc == 1
    assert "FAILED:docdrift" in capsys.readouterr().out


def test_main_returns_0_when_clean(tmp_path, monkeypatch, capsys):
    doc = tmp_path / "CLAUDE.md"
    doc.write_text("mcp__codex__codex", encoding="utf-8")
    monkeypatch.setattr(m, "run_claude_mcp_list", lambda *a, **k: SAMPLE_LIST)
    rc = m.main(["--docs", str(doc)])
    assert rc == 0
    assert "SUCCESS:docdrift" in capsys.readouterr().out


def test_main_fails_closed_when_cli_unavailable(tmp_path, monkeypatch, capsys):
    doc = tmp_path / "CLAUDE.md"
    doc.write_text("mcp__codex__codex", encoding="utf-8")

    def _boom(*a, **k):
        raise RuntimeError("claude not found")

    monkeypatch.setattr(m, "run_claude_mcp_list", _boom)
    rc = m.main(["--docs", str(doc)])
    assert rc == 2
    assert "FAILED:docdrift" in capsys.readouterr().out


def test_main_fails_closed_when_no_docs(monkeypatch, capsys):
    monkeypatch.setattr(m, "run_claude_mcp_list", lambda *a, **k: SAMPLE_LIST)
    rc = m.main(["--docs"])  # empty explicit list -> no docs read
    assert rc == 2
    assert "no CLAUDE.md" in capsys.readouterr().out


@pytest.mark.live
def test_live_claude_mcp_list_smoke():
    """Real CLI call. Excluded from the fast suite via `-m 'not live'`."""
    out = m.run_claude_mcp_list()
    assert isinstance(out, str)
