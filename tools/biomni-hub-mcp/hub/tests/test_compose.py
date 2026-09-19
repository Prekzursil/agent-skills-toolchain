"""End-to-end COMPOSITION smoke test for the reconciled hub.

Proves the hub composes offline:
  1. BOTH real adapters load through ``backends.load_backend`` (no
     ``AdapterUnavailable`` / isinstance failure) -- the headline blocker is gone.
  2. All 10 canonical tools dispatch through ``server.py`` against a MOCK backend
     and return a valid ``ToolEnvelope``.
  3. The 3 previously-misrouted tools (start_new_task / upload_file /
     wait_for_next_update) now pass their args to the backend in the RIGHT order.
  4. The A3 feature tools register on the SDK FastMCP (R8) and one runs
     end-to-end through the sync->async bridge (R6).
"""

from __future__ import annotations

import asyncio
import json

import pytest

import backends
import server
from backends import BiomniBackend
from schema import CANONICAL_TOOL_NAMES, BackendDescriptor, ToolEnvelope

A3_TOOLS = {
    "biomni_run_history", "biomni_fetch_artifact", "biomni_cost",
    "biomni_tool_catalog", "biomni_inject_mcp",
}


class RecordingBackend(BiomniBackend):
    """A canonical BiomniBackend that records the exact positional args it
    receives for every tool and returns a valid ToolEnvelope."""

    def __init__(self, name: str = "online") -> None:
        self.name = name
        self.calls: dict[str, tuple[tuple, dict]] = {}

    def _rec(self, tool: str, *args, **kwargs) -> ToolEnvelope:
        self.calls[tool] = (args, kwargs)
        return ToolEnvelope.success(self.name, tool, data={"args": list(args)})

    def describe(self) -> BackendDescriptor:
        return BackendDescriptor(
            name=self.name, available=True, is_default=False,
            status="ready", cost="mock",
        )

    def create_project(self, name, description="") -> ToolEnvelope:
        return self._rec("create_project", name, description)

    def list_projects(self) -> ToolEnvelope:
        return self._rec("list_projects")

    def list_workspaces(self) -> ToolEnvelope:
        return self._rec("list_workspaces")

    def switch_workspace(self, workspace_id) -> ToolEnvelope:
        return self._rec("switch_workspace", workspace_id)

    def upload_file(self, local_path, project_id="", destination="") -> ToolEnvelope:
        return self._rec("upload_file", local_path, project_id, destination)

    def start_new_task(
        self, project_id, prompt, model_profile="standard"
    ) -> ToolEnvelope:
        return self._rec("start_new_task", project_id, prompt, model_profile)

    def send_message(self, task_id, content) -> ToolEnvelope:
        return self._rec("send_message", task_id, content)

    def wait_for_next_update(self, task_id, timeout_seconds=60.0, *, since=None):
        return self._rec("wait_for_next_update", task_id, timeout_seconds, since=since)

    def list_tasks(self, project_id="") -> ToolEnvelope:
        return self._rec("list_tasks", project_id)

    def list_result_files(self, task_id="") -> ToolEnvelope:
        return self._rec("list_result_files", task_id)


@pytest.fixture
def mock():
    backends.reset_cache()
    fb = RecordingBackend("online")
    backends.register_backend("online", fb)
    yield fb
    backends.reset_cache()


# ===== 1. the blocker is gone: both adapters load through the real gate ======
def test_both_real_adapters_load_and_are_biomnibackends():
    backends.reset_cache()
    try:
        for name in ("online", "databricks"):
            adapter = backends.load_backend(name)
            assert isinstance(adapter, BiomniBackend), f"{name} is not a BiomniBackend"
            assert adapter.name == name
    finally:
        backends.reset_cache()


# ===== 2. all 10 canonical tools dispatch to a valid ToolEnvelope ============
def test_all_ten_canonical_tools_dispatch_valid_envelope(mock):
    calls = [
        lambda: server.create_project("P", "d"),
        lambda: server.list_projects(),
        lambda: server.list_workspaces(),
        lambda: server.switch_workspace("ws1"),
        lambda: server.upload_file("/tmp/x.csv", "p1", "dest.csv"),
        lambda: server.start_new_task("p1", "analyze X", "standard"),
        lambda: server.send_message("t1", "hi"),
        lambda: server.wait_for_next_update("t1", 10.0),
        lambda: server.list_tasks("p1"),
        lambda: server.list_result_files("t1"),
    ]
    seen = set()
    for call in calls:
        env = ToolEnvelope(**json.loads(call()))  # must be a valid ToolEnvelope
        assert env.ok is True
        assert env.backend == "online"
        assert env.tool in CANONICAL_TOOL_NAMES
        seen.add(env.tool)
    assert seen == set(CANONICAL_TOOL_NAMES)  # every canonical tool exercised


# ===== 3. the 3 previously-misrouted tools now pass args in the RIGHT order ==
def test_start_new_task_arg_order(mock):
    json.loads(server.start_new_task("proj1", "do the analysis", "fast"))
    assert mock.calls["start_new_task"][0] == ("proj1", "do the analysis", "fast")


def test_upload_file_arg_order(mock):
    json.loads(server.upload_file("/data/in.csv", "proj1", "renamed.csv"))
    assert mock.calls["upload_file"][0] == ("/data/in.csv", "proj1", "renamed.csv")


def test_wait_for_next_update_arg_order(mock):
    json.loads(server.wait_for_next_update("task1", 30.0, since=5))
    args, kwargs = mock.calls["wait_for_next_update"]
    assert args == ("task1", 30.0)  # timeout binds to timeout_seconds, NOT since
    assert kwargs == {"since": 5}  # resume cursor preserved, keyword-only


# ===== 4. A3 feature tools register (R8) + run end-to-end via the bridge (R6) =
def test_register_features_wires_a3_onto_sdk_fastmcp():
    from mcp.server.fastmcp import FastMCP

    fresh = FastMCP("compose-probe")
    names = server.register_features(fresh)  # R8 wiring path
    backends.reset_cache()
    assert set(names) == A3_TOOLS
    registered = {t.name for t in asyncio.run(fresh.list_tools())}
    assert A3_TOOLS <= registered


def test_a3_tool_runs_end_to_end_through_bridge(tmp_path):
    from mcp.server.fastmcp import FastMCP

    from features import bridge_adapter, register_all
    from features.backend import BackendRegistry
    from features.context import HubContext
    from features.store import RunStore

    store = RunStore(str(tmp_path / "hub.sqlite3"))
    reg = BackendRegistry(default="online")
    reg.register("online", bridge_adapter(RecordingBackend("online")))
    ctx = HubContext(data_dir=str(tmp_path), store=store, backends=reg)

    mcp = FastMCP("compose-test")
    register_all(mcp, ctx)
    _content, structured = asyncio.run(mcp.call_tool("biomni_run_history", {}))
    assert structured["count"] == 0  # empty ledger, but the tool executed cleanly
    assert "online" in structured["backends_known"]


def test_bridge_maps_sync_adapter_to_async_client():
    from features import bridge_adapter
    from features.backend import CAP_LIST_RESULTS

    client = bridge_adapter(RecordingBackend("online"))
    assert client.name == "online"
    assert CAP_LIST_RESULTS in client.capabilities()
    # list_results unwraps the sync ToolEnvelope into a plain list (async)
    rows = asyncio.run(client.list_results("sess_1"))
    assert isinstance(rows, list)
