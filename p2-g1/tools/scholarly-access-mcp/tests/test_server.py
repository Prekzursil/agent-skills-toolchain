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
