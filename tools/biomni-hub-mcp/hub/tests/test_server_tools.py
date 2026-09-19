"""Server tests: the 10 canonical tools + catalog register and dispatch."""

from __future__ import annotations

import asyncio
import json

import pytest

import backends
import server
from schema import CANONICAL_TOOL_NAMES, CATALOG_TOOL_NAME


def _tool_names() -> set[str]:
    return {t.name for t in asyncio.run(server.mcp.list_tools())}


@pytest.fixture(autouse=True)
def _clean_cache():
    backends.reset_cache()
    yield
    backends.reset_cache()


def test_all_canonical_tools_plus_catalog_register():
    names = _tool_names()
    for expected in CANONICAL_TOOL_NAMES:
        assert expected in names, f"missing tool {expected}"
    assert CATALOG_TOOL_NAME in names
    # Exactly the 10 canonical tools + the one catalog tool, nothing extra.
    assert names == set(CANONICAL_TOOL_NAMES) | {CATALOG_TOOL_NAME}
    assert len(names) == 11


def test_dispatch_routes_to_registered_backend():
    from fake_backend import FakeBackend

    fb = FakeBackend("online")
    backends.register_backend("online", fb)

    out = json.loads(server.create_project("My Project", "desc"))
    assert out["ok"] is True
    assert out["backend"] == "online"
    assert out["tool"] == "create_project"
    assert fb.calls[-1][0] == "create_project"


def test_backend_arg_selects_backend():
    from fake_backend import FakeBackend

    online = FakeBackend("online")
    dbx = FakeBackend("databricks")
    backends.register_backend("online", online)
    backends.register_backend("databricks", dbx)

    out = json.loads(server.list_projects(backend="databricks"))
    assert out["backend"] == "databricks"
    assert dbx.calls[-1][0] == "list_projects"
    assert not online.calls


def test_start_new_task_carries_display_protocol():
    from fake_backend import FakeBackend

    backends.register_backend("online", FakeBackend("online"))
    out = json.loads(server.start_new_task("p1", "analyze X"))
    assert out["data"]["task_id"] == "task_1"
    assert out["display_instruction"]
    assert out["biomni_url"].startswith("https://")


def test_list_result_files_returns_name_and_size():
    from fake_backend import FakeBackend

    backends.register_backend("online", FakeBackend("online"))
    out = json.loads(server.list_result_files("task_1"))
    files = out["data"]
    assert files[0]["name"] == "out.csv"
    assert files[0]["size"] == 42


def test_unavailable_backend_returns_error_envelope_not_crash(monkeypatch):
    # If the selected adapter genuinely cannot load (e.g. databricks-sdk missing),
    # the server returns a clean terminal error envelope, never a crash.
    def _boom(_name):
        raise backends.AdapterUnavailable("adapter unavailable: forced for test")

    monkeypatch.setattr(backends, "load_backend", _boom)
    out = json.loads(server.list_projects())
    assert out["ok"] is False
    assert out["backend"] == "online"
    assert "unavailable" in out["error"].lower()


def test_adapter_exception_is_wrapped():
    from fake_backend import ExplodingBackend

    backends.register_backend("online", ExplodingBackend())
    out = json.loads(server.list_projects())
    assert out["ok"] is False
    assert "kaboom" in out["error"]


def test_catalog_lists_both_backends_default_flagged():
    from fake_backend import FakeBackend

    backends.register_backend("online", FakeBackend("online"))
    # databricks intentionally NOT registered -> shows unavailable.
    cat = json.loads(server.biomni_backends())
    assert cat["default"] == "online"
    rows = {r["name"]: r for r in cat["backends"]}
    assert set(rows) == {"online", "databricks"}
    assert rows["online"]["available"] is True
    assert rows["online"]["is_default"] is True
    assert rows["databricks"]["available"] is False
    assert rows["databricks"]["is_default"] is False
