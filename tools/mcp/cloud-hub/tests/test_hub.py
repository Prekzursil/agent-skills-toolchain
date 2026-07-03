#!/usr/bin/env python3
"""Integration tests for the multiplexing runtime.

They drive the REAL ``HubServer`` against lightweight fake backends, asserting
the load-bearing promises: the merged ``tools/list`` is served with ZERO
backends spawned; a ``tools/call`` lazily spawns ONLY the owning backend; a
collision-renamed name is rewritten back to its original before forwarding; and
a broken backend degrades to a clear per-tool error without crashing the hub.
"""
from __future__ import annotations

import json
import os
import queue
import sys
import time

import pytest

HUB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HUB_DIR)

import hub  # noqa: E402
from backends import BackendSpec  # noqa: E402
from registry import build_plan  # noqa: E402

PY = sys.executable
FAKE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fake_backend.py")
BROKEN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "broken_backend.py")


class Capture:
    """Thread-safe emit sink: collects outbound JSON-RPC messages."""

    def __init__(self) -> None:
        self._q: "queue.Queue[dict]" = queue.Queue()

    def __call__(self, line: str) -> None:
        self._q.put(json.loads(line))

    def wait(self, n: int, timeout: float = 30.0) -> list[dict]:
        got: list[dict] = []
        end = time.monotonic() + timeout
        while len(got) < n:
            remaining = end - time.monotonic()
            if remaining <= 0:
                break
            try:
                got.append(self._q.get(timeout=remaining))
            except queue.Empty:
                break
        return got


def _fake(bid: str, prefix: str, tools: list[str], cache: str) -> BackendSpec:
    return BackendSpec(id=bid, label=f"fake-{bid}", prefix=prefix,
                       cmd=(PY, FAKE, bid, ",".join(tools)), cache=cache)


@pytest.fixture
def hub_env(tmp_path):
    cache_dir = str(tmp_path)
    specs = [
        _fake("alpha", "al", ["shared_tool", "alpha_only"], "alpha.json"),
        _fake("beta", "be", ["shared_tool", "beta_only"], "beta.json"),
        BackendSpec(id="broken", label="broken-backend", prefix="bk",
                    cmd=(PY, BROKEN), cache="broken.json"),
    ]
    old = hub.CACHE_DIR
    hub.CACHE_DIR = cache_dir
    for spec in specs[:2]:
        ok, _n, msg = hub.refresh_backend(spec)
        assert ok, msg
    # The broken backend cannot enumerate; hand-write a cache so its tool is
    # LISTED but calls to it must fail gracefully.
    with open(os.path.join(cache_dir, "broken.json"), "w", encoding="utf-8") as fh:
        json.dump({"initialize": {}, "tools": {"tools": [
            {"name": "broken_tool", "description": "x",
             "inputSchema": {"type": "object"}}]}}, fh)
    plan = build_plan(specs, cache_dir)
    cap = Capture()
    server = hub.HubServer(specs, plan, emit=cap)
    try:
        yield server, plan, cap
    finally:
        hub.CACHE_DIR = old
        for backend in server.backends.values():
            backend._terminate()


def test_tools_list_served_without_spawning(hub_env):
    server, _plan, cap = hub_env
    server.dispatch({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    server.dispatch({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    msgs = cap.wait(2)
    listing = [m for m in msgs if m.get("id") == 2][0]
    names = {t["name"] for t in listing["result"]["tools"]}
    assert names == {"al_shared_tool", "alpha_only", "be_shared_tool",
                     "beta_only", "broken_tool"}
    # The RAM promise: nothing was spawned to answer tools/list.
    for backend in server.backends.values():
        assert backend.proc is None


def test_initialize_echoes_version_and_identifies_hub(hub_env):
    server, _plan, cap = hub_env
    server.dispatch({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                     "params": {"protocolVersion": "2025-06-18"}})
    server.dispatch({"jsonrpc": "2.0", "id": 2, "method": "ping"})
    msgs = cap.wait(2)
    init = [m for m in msgs if m.get("id") == 1][0]
    assert init["result"]["serverInfo"]["name"] == "cloud-hub"
    assert init["result"]["protocolVersion"] == "2025-06-18"
    for backend in server.backends.values():
        assert backend.proc is None


def test_call_spawns_only_the_owning_backend(hub_env):
    server, _plan, cap = hub_env
    server.dispatch({"jsonrpc": "2.0", "id": 10, "method": "tools/call",
                     "params": {"name": "alpha_only", "arguments": {"x": 1}}})
    reply = cap.wait(1)[0]
    assert reply["id"] == 10
    payload = json.loads(reply["result"]["content"][0]["text"])
    assert payload["backend"] == "alpha"
    assert payload["received_name"] == "alpha_only"
    assert payload["arguments"] == {"x": 1}
    assert server.backends["alpha"].proc is not None
    assert server.backends["beta"].proc is None
    assert server.backends["broken"].proc is None


def test_collision_name_rewritten_to_original_on_forward(hub_env):
    server, _plan, cap = hub_env
    server.dispatch({"jsonrpc": "2.0", "id": 20, "method": "tools/call",
                     "params": {"name": "be_shared_tool", "arguments": {}}})
    reply = cap.wait(1)[0]
    assert reply["id"] == 20
    payload = json.loads(reply["result"]["content"][0]["text"])
    assert payload["backend"] == "beta"
    # The hub advertised 'be_shared_tool' but forwarded the ORIGINAL name.
    assert payload["received_name"] == "shared_tool"
    assert server.backends["beta"].proc is not None
    assert server.backends["alpha"].proc is None


def test_broken_backend_degrades_without_crashing(hub_env):
    server, _plan, cap = hub_env
    server.dispatch({"jsonrpc": "2.0", "id": 30, "method": "tools/call",
                     "params": {"name": "broken_tool", "arguments": {}}})
    reply = cap.wait(1)[0]
    assert reply["id"] == 30
    assert reply["result"]["isError"] is True
    assert "unavailable" in reply["result"]["content"][0]["text"]
    # The hub is still alive: a healthy call afterwards still succeeds.
    server.dispatch({"jsonrpc": "2.0", "id": 31, "method": "tools/call",
                     "params": {"name": "alpha_only", "arguments": {}}})
    reply2 = cap.wait(1)[0]
    assert json.loads(reply2["result"]["content"][0]["text"])["backend"] == "alpha"


def test_unknown_tool_returns_error(hub_env):
    server, _plan, cap = hub_env
    server.dispatch({"jsonrpc": "2.0", "id": 40, "method": "tools/call",
                     "params": {"name": "does_not_exist"}})
    reply = cap.wait(1)[0]
    assert reply["id"] == 40
    assert reply["error"]["code"] == -32602
    for backend in server.backends.values():
        assert backend.proc is None
