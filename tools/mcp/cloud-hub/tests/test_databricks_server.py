#!/usr/bin/env python3
"""Unit tests for the built Databricks FastMCP wrapper (``databricks-mcp/server.py``).

They avoid a live Databricks workspace entirely: the module lazy-imports
``databricks-sdk`` inside each tool, so ``tools/list`` enumerates offline, and a
fake ``WorkspaceClient`` (injected by monkeypatching ``_client``) exercises the
routing, serialization, guardrail, and raw-passthrough logic. The module is
loaded by explicit path as ``dbx_server`` so it never collides with the other
built wrappers' ``server.py`` modules."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys

HUB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HUB_DIR)

_SERVER_PATH = os.path.join(HUB_DIR, "databricks-mcp", "server.py")
_spec = importlib.util.spec_from_file_location("dbx_server", _SERVER_PATH)
dbx_server = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dbx_server)


class _Obj:
    """A stand-in for an SDK dataclass exposing ``as_dict()``."""

    def __init__(self, data: dict) -> None:
        self._data = data

    def as_dict(self) -> dict:
        return self._data


# --------------------------------------------------------------------------- #
# Offline enumeration (no databricks-sdk, no credentials)
# --------------------------------------------------------------------------- #
def test_enumerates_full_dbx_surface_offline():
    tools = asyncio.run(dbx_server.mcp.list_tools())
    names = {t.name for t in tools}
    assert len(names) == 65
    assert all(n.startswith("dbx_") for n in names)
    # Load-bearing tools from the research spec are all present.
    for name in (
        "dbx_cluster_create",
        "dbx_exec",
        "dbx_run_on_cluster",
        "dbx_sql_exec",
        "dbx_serving_query",
        "dbx_api_raw",
        "dbx_current_user",
    ):
        assert name in names


def test_sdk_absent_returns_clear_hint(monkeypatch):
    monkeypatch.setattr(
        dbx_server,
        "_client",
        lambda: (None, "databricks-sdk not available; `pip install databricks-sdk`"),
    )
    out = json.loads(dbx_server.dbx_cluster_list())
    assert out["ok"] is False
    assert "databricks-sdk" in out["error"]


# --------------------------------------------------------------------------- #
# Routing + serialization against a fake WorkspaceClient
# --------------------------------------------------------------------------- #
def test_list_and_get_route_and_dump(monkeypatch):
    class FakeClusters:
        def list(self):
            return iter([_Obj({"cluster_id": "c-1"}), _Obj({"cluster_id": "c-2"})])

        def get(self, cluster_id):
            return _Obj({"cluster_id": cluster_id, "state": "RUNNING"})

    class FakeW:
        clusters = FakeClusters()

    monkeypatch.setattr(dbx_server, "_client", lambda: (FakeW(), None))
    lst = json.loads(dbx_server.dbx_cluster_list())
    assert lst["ok"] and lst["data"] == [{"cluster_id": "c-1"}, {"cluster_id": "c-2"}]
    got = json.loads(dbx_server.dbx_cluster_get("c-9"))
    assert got["data"] == {"cluster_id": "c-9", "state": "RUNNING"}


def test_destructive_tool_is_guarded(monkeypatch):
    calls = {"delete": 0}

    class FakeClusters:
        def delete(self, cluster_id):
            calls["delete"] += 1

    class FakeW:
        clusters = FakeClusters()

    monkeypatch.setattr(dbx_server, "_client", lambda: (FakeW(), None))
    # Without confirm: a dry-run preview, and the SDK is NOT touched.
    dry = json.loads(dbx_server.dbx_cluster_terminate("c-1"))
    assert dry["ok"] is False and dry["dry_run"] is True
    assert calls["delete"] == 0
    # With confirm=True: the terminate actually runs.
    ok = json.loads(dbx_server.dbx_cluster_terminate("c-1", confirm=True))
    assert ok["ok"] is True and ok["data"]["terminated"] == "c-1"
    assert calls["delete"] == 1


def test_dbfs_delete_is_guarded(monkeypatch):
    calls = {"delete": 0}

    class FakeDbfs:
        def delete(self, path, recursive=False):
            calls["delete"] += 1

    class FakeW:
        dbfs = FakeDbfs()

    monkeypatch.setattr(dbx_server, "_client", lambda: (FakeW(), None))
    dry = json.loads(dbx_server.dbx_dbfs_delete("dbfs:/tmp/data", recursive=True))
    assert dry["ok"] is False and dry["dry_run"] is True
    assert calls["delete"] == 0

    ok = json.loads(
        dbx_server.dbx_dbfs_delete("dbfs:/tmp/data", recursive=True, confirm=True)
    )
    assert ok["ok"] is True and ok["data"] == {
        "deleted": "dbfs:/tmp/data",
        "recursive": True,
    }
    assert calls["delete"] == 1


def test_volume_rm_is_guarded(monkeypatch):
    calls = {"delete": 0}

    class FakeFiles:
        def delete(self, path):
            calls["delete"] += 1

    class FakeW:
        files = FakeFiles()

    monkeypatch.setattr(dbx_server, "_client", lambda: (FakeW(), None))
    dry = json.loads(dbx_server.dbx_volume_rm("/Volumes/catalog/schema/volume/file"))
    assert dry["ok"] is False and dry["dry_run"] is True
    assert calls["delete"] == 0

    ok = json.loads(
        dbx_server.dbx_volume_rm("/Volumes/catalog/schema/volume/file", confirm=True)
    )
    assert ok["ok"] is True and ok["data"] == {
        "deleted": "/Volumes/catalog/schema/volume/file",
        "is_directory": False,
    }
    assert calls["delete"] == 1


def test_serving_delete_is_guarded(monkeypatch):
    calls = {"delete": 0}

    class FakeServingEndpoints:
        def delete(self, name):
            calls["delete"] += 1

    class FakeW:
        serving_endpoints = FakeServingEndpoints()

    monkeypatch.setattr(dbx_server, "_client", lambda: (FakeW(), None))
    dry = json.loads(dbx_server.dbx_serving_delete("endpoint-1"))
    assert dry["ok"] is False and dry["dry_run"] is True
    assert calls["delete"] == 0

    ok = json.loads(dbx_server.dbx_serving_delete("endpoint-1", confirm=True))
    assert ok["ok"] is True and ok["data"]["deleted_endpoint"] == "endpoint-1"
    assert calls["delete"] == 1


def test_secret_scope_delete_is_guarded(monkeypatch):
    calls = {"delete_scope": 0}

    class FakeSecrets:
        def delete_scope(self, scope):
            calls["delete_scope"] += 1

    class FakeW:
        secrets = FakeSecrets()

    monkeypatch.setattr(dbx_server, "_client", lambda: (FakeW(), None))
    dry = json.loads(dbx_server.dbx_secret_scope_delete("scope-1"))
    assert dry["ok"] is False and dry["dry_run"] is True
    assert calls["delete_scope"] == 0

    ok = json.loads(dbx_server.dbx_secret_scope_delete("scope-1", confirm=True))
    assert ok["ok"] is True and ok["data"]["deleted_scope"] == "scope-1"
    assert calls["delete_scope"] == 1


def test_repo_delete_is_guarded(monkeypatch):
    calls = {"delete": 0}

    class FakeRepos:
        def delete(self, repo_id):
            calls["delete"] += 1

    class FakeW:
        repos = FakeRepos()

    monkeypatch.setattr(dbx_server, "_client", lambda: (FakeW(), None))
    dry = json.loads(dbx_server.dbx_repo_delete(123))
    assert dry["ok"] is False and dry["dry_run"] is True
    assert calls["delete"] == 0

    ok = json.loads(dbx_server.dbx_repo_delete(123, confirm=True))
    assert ok["ok"] is True and ok["data"]["deleted_repo"] == 123
    assert calls["delete"] == 1


def test_exec_guard_blocks_code_execution(monkeypatch):
    class FakeW:
        pass  # exec must never reach the SDK without confirm

    monkeypatch.setattr(dbx_server, "_client", lambda: (FakeW(), None))
    dry = json.loads(dbx_server.dbx_exec("c-1", "ctx-1", "print(1)"))
    assert dry["ok"] is False and dry["dry_run"] is True


def test_api_raw_passthrough(monkeypatch):
    seen: dict = {}

    class FakeApiClient:
        def do(self, method, path, body=None, query=None):
            seen.update(method=method, path=path, body=body, query=query)
            return {"echo": True}

    class FakeW:
        api_client = FakeApiClient()

    monkeypatch.setattr(dbx_server, "_client", lambda: (FakeW(), None))
    out = json.loads(
        dbx_server.dbx_api_raw("get", "/api/2.1/clusters/list", "", '{"limit": 5}')
    )
    assert out["ok"] and out["data"] == {"echo": True}
    assert seen["method"] == "GET" and seen["path"] == "/api/2.1/clusters/list"
    assert seen["query"] == {"limit": 5} and seen["body"] is None


def test_job_create_uses_raw_rest_body(monkeypatch):
    seen: dict = {}

    class FakeApiClient:
        def do(self, method, path, body=None, query=None):
            seen.update(method=method, path=path, body=body)
            return {"job_id": 42}

    class FakeW:
        api_client = FakeApiClient()

    monkeypatch.setattr(dbx_server, "_client", lambda: (FakeW(), None))
    out = json.loads(dbx_server.dbx_job_create('{"name": "nightly", "tasks": []}'))
    assert out["ok"] and out["data"] == {"job_id": 42}
    assert seen["method"] == "POST" and seen["path"] == "/api/2.1/jobs/create"
    assert seen["body"] == {"name": "nightly", "tasks": []}


def test_secret_get_decodes_value(monkeypatch):
    import base64

    class _Val:
        value = base64.b64encode(b"s3cr3t").decode("ascii")

    class FakeSecrets:
        def get_secret(self, scope, key):
            return _Val()

    class FakeW:
        secrets = FakeSecrets()

    monkeypatch.setattr(dbx_server, "_client", lambda: (FakeW(), None))
    out = json.loads(dbx_server.dbx_secret_get("scope", "key"))
    assert out["ok"] and out["data"]["value"] == "s3cr3t"
