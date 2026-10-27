"""Unit tests for mcp_server.server — the FastMCP wrappers delegate to
mcp_server.logic (mocked here) exactly like the scholarly-access template.
Also covers main()."""

from __future__ import annotations

import pytest

from mcp_server import logic, server


def test_register_task(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        logic, "register_task", lambda t, i, c, **k: {"t": t, "i": i, "c": c, "k": k}
    )
    out = server.register_task("generic-logfile", "t1", {"path": "/x"}, remediate=True)
    assert out["t"] == "generic-logfile"
    assert out["i"] == "t1"
    assert out["c"] == {"path": "/x"}
    assert out["k"]["remediate"] is True


def test_list_tasks(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(logic, "list_tasks", lambda r: {"reg": r})
    assert server.list_tasks("my.toml") == {"reg": "my.toml"}


def test_status(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(logic, "status", lambda r, **k: {"reg": r, "k": k})
    out = server.status("my.toml", task_id="t2", history="h.db", stall_after_s=99.0)
    assert out["reg"] == "my.toml"
    assert out["k"] == {"task_id": "t2", "history": "h.db", "stall_after_s": 99.0}


def test_attach_watch(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(logic, "attach_watch", lambda i, **k: {"i": i, "k": k})
    out = server.attach_watch("t1", remediate=True)
    assert out["i"] == "t1"
    assert out["k"]["remediate"] is True


def test_set_notify(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(logic, "set_notify", lambda i, ch, **k: {"i": i, "ch": ch})
    out = server.set_notify("t1", ["terminal", "stall"])
    assert out["i"] == "t1" and out["ch"] == ["terminal", "stall"]


def test_main(monkeypatch: pytest.MonkeyPatch):
    calls: list[str] = []
    monkeypatch.setattr(server.mcp, "run", lambda: calls.append("run"))
    server.main()
    assert calls == ["run"]
