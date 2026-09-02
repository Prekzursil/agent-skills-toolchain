"""Unit tests for scholarly_access.server — the MCP tool wrappers delegate to
logic.*; logic is mocked. Also covers _load_env_file and main()."""

from __future__ import annotations

from scholarly_access import server
from scholarly_access import logic


def test_paper_resolve(monkeypatch):
    monkeypatch.setattr(logic, "resolve", lambda i: {"ok": i})
    assert server.paper_resolve("X") == {"ok": "X"}


def test_paper_fetch_metadata(monkeypatch):
    monkeypatch.setattr(logic, "fetch_metadata", lambda i: {"m": i})
    assert server.paper_fetch_metadata("X") == {"m": "X"}


def test_paper_find_oa_pdf(monkeypatch):
    monkeypatch.setattr(logic, "find_oa_pdf", lambda **k: {"oa": k})
    assert server.paper_find_oa_pdf(identifier="X")["oa"]["identifier"] == "X"


def test_paper_access_status(monkeypatch):
    monkeypatch.setattr(logic, "access_status", lambda **k: {"a": k})
    assert server.paper_access_status(doi="10.1/x")["a"]["doi"] == "10.1/x"


def test_paper_citation_graph(monkeypatch):
    monkeypatch.setattr(logic, "citation_graph", lambda **k: {"c": k})
    assert server.paper_citation_graph(doi="10.1/x", limit=5)["c"]["limit"] == 5


def test_paper_download_ok(monkeypatch):
    monkeypatch.setattr(
        logic, "download_oa_pdf", lambda url, **k: {"ok": True, "url": url}
    )
    out = server.paper_download_oa_pdf("https://arxiv.org/pdf/x")
    assert out["ok"] is True


def test_paper_download_refused(monkeypatch):
    def boom(url, **k):
        raise PermissionError("nope")

    monkeypatch.setattr(logic, "download_oa_pdf", boom)
    out = server.paper_download_oa_pdf("https://sci-hub.se/x")
    assert out["refused"] is True and out["ok"] is False


def test_paper_summarize(monkeypatch):
    monkeypatch.setattr(logic, "summarize", lambda **k: {"s": k})
    assert server.paper_summarize(doi="10.1/x")["s"]["doi"] == "10.1/x"


def test_paper_batch_resolve(monkeypatch):
    monkeypatch.setattr(logic, "batch_resolve", lambda ids: {"n": len(ids)})
    assert server.paper_batch_resolve(["a", "b"]) == {"n": 2}


def test_paper_citations_for_doi(monkeypatch):
    monkeypatch.setattr(logic, "citations_for_doi", lambda d, limit: {"c": (d, limit)})
    assert server.paper_citations_for_doi("10.1/x") == {"c": ("10.1/x", 100)}
    assert server.paper_citations_for_doi("10.1/x", limit=5) == {"c": ("10.1/x", 5)}


def test_paper_references_for_doi(monkeypatch):
    monkeypatch.setattr(logic, "references_for_doi", lambda d, limit: {"r": (d, limit)})
    assert server.paper_references_for_doi("10.1/x", limit=7) == {"r": ("10.1/x", 7)}


def test_paper_europepmc_fulltext(monkeypatch):
    monkeypatch.setattr(
        logic, "europepmc_fulltext", lambda p, max_chars: {"f": (p, max_chars)}
    )
    assert server.paper_europepmc_fulltext("PMC1") == {"f": ("PMC1", 60_000)}
    assert server.paper_europepmc_fulltext("PMC1", max_chars=5000) == {
        "f": ("PMC1", 5000)
    }


def test_paper_europepmc_fulltext_refused(monkeypatch):
    def boom(p, max_chars):
        raise PermissionError("nope")

    monkeypatch.setattr(logic, "europepmc_fulltext", boom)
    out = server.paper_europepmc_fulltext("PMC1")
    assert out["refused"] is True and out["ok"] is False
    assert out["reason"] == "nope" and out["policy"] == server.policy.POLICY_BANNER


def test_paper_europepmc_annotations(monkeypatch):
    monkeypatch.setattr(
        logic, "europepmc_annotations", lambda a, type, limit: {"a": (a, type, limit)}
    )
    assert server.paper_europepmc_annotations("PMC1") == {"a": ("PMC1", "", 200)}
    assert server.paper_europepmc_annotations("1", type="Diseases", limit=3) == {
        "a": ("1", "Diseases", 3)
    }


# --------------------------------------------------------------------------- tool surface
EXPECTED_TOOLS = [
    "paper_resolve",
    "paper_fetch_metadata",
    "paper_find_oa_pdf",
    "paper_access_status",
    "paper_citation_graph",
    "paper_download_oa_pdf",
    "paper_summarize",
    "paper_batch_resolve",
    "paper_citations_for_doi",
    "paper_references_for_doi",
    "paper_europepmc_fulltext",
    "paper_europepmc_annotations",
]


def test_tool_surface_is_pinned():
    import asyncio

    tools = asyncio.run(server.mcp.list_tools())
    assert [t.name for t in tools] == EXPECTED_TOOLS
    assert len(tools) == 12
    for t in tools:
        first = (t.description or "").strip().splitlines()[0]
        assert first, f"{t.name} has no one-line description"
        assert "Spec: paper." in (t.description or ""), t.name


def test_no_shadow_library_tools_or_params():
    import asyncio

    tools = asyncio.run(server.mcp.list_tools())
    for t in tools:
        blob = (t.name + " " + str(t.inputSchema)).lower()
        for bad in ("scihub", "sci-hub", "libgen", "scidownl", "use_scihub"):
            assert bad not in blob, (t.name, bad)


# --------------------------------------------------------------------------- _load_env_file
def test_load_env_file_reads(monkeypatch, tmp_path):
    envf = tmp_path / "env"
    envf.write_text('# comment\n\nFOO_TESTVAR="bar"\nBADLINE\n', encoding="utf-8")
    monkeypatch.setenv("SCHOLARLY_ENV_FILE", str(envf))
    monkeypatch.delenv("FOO_TESTVAR", raising=False)
    server._load_env_file()
    import os

    assert os.environ["FOO_TESTVAR"] == "bar"


def test_load_env_file_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("SCHOLARLY_ENV_FILE", str(tmp_path / "does-not-exist"))
    server._load_env_file()  # no error


def test_load_env_file_oserror(monkeypatch, tmp_path):
    # point at a directory -> open() raises OSError -> swallowed
    monkeypatch.setenv("SCHOLARLY_ENV_FILE", str(tmp_path))
    server._load_env_file()  # no error


# --------------------------------------------------------------------------- main
def test_main(monkeypatch):
    calls = []
    monkeypatch.setattr(server, "_load_env_file", lambda: calls.append("env"))
    monkeypatch.setattr(server.mcp, "run", lambda: calls.append("run"))
    server.main()
    assert calls == ["env", "run"]
