#!/usr/bin/env python3
"""Integration tests for the search-hub runtime.

They drive the REAL ``SearchHub`` against a lightweight fake search backend,
asserting the load-bearing promises: ``tools/list`` (provider tools + account
tools + search_usage) is served with ZERO children spawned; a ``tools/call`` is
routed to the active key's lazily-spawned child; a hard-exhaustion reply rotates
to the backup key and retries once; a manual switch changes the active key and
clears its cooldown; keyless SearXNG still serves search after every keyed
account cools; and search_usage reports per-key usage via the injected getter --
all with NO live keys and NO network.
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

import accounts  # noqa: E402
import adapters  # noqa: E402
import hub  # noqa: E402
import providers  # noqa: E402
import rotation  # noqa: E402

import fake_trailsearch_backend as fake_ts  # noqa: E402

PY = sys.executable
FAKE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "fake_search_backend.py"
)


class Capture:
    """Thread-safe emit sink: collects outbound JSON-RPC messages."""

    def __init__(self) -> None:
        self._q: "queue.Queue[dict]" = queue.Queue()

    def __call__(self, line: str) -> None:
        self._q.put(json.loads(line))

    def wait(self, n: int, timeout: float = 30.0) -> list[dict]:
        got: list[dict] = []
        end = time.monotonic() + timeout
        while len(got) < n and (rem := end - time.monotonic()) > 0:
            try:
                got.append(self._q.get(timeout=rem))
            except queue.Empty:
                break
        return got


def _fake_spec() -> providers.ProviderSpec:
    return providers.ProviderSpec(
        platform="exa",
        label="Exa",
        prefix="ex",
        key_env="EXA_API_KEY",
        cmd=(PY, FAKE, "exa", "web_search_exa", "EXA_API_KEY"),
        cache="exa.json",
        usage_url="https://api.firecrawl.dev/v2/team/credit-usage",
        usage_kind="firecrawl",  # test double: exercises the usage getter path
        exhaust_patterns=("NO_MORE_CREDITS", "402", "insufficient credits"),
        rate_patterns=("429", "rate limit"),
    ).compiled()


def _fake_searxng_spec() -> providers.ProviderSpec:
    return providers.ProviderSpec(
        platform="searxng",
        label="SearXNG",
        prefix="sx",
        key_env="",
        cmd=(
            PY,
            FAKE,
            "searxng",
            "searxng_web_search",
            "SEARCH_HUB_TEST_KEYLESS_SENTINEL",
        ),
        cache="searxng.json",
        keyless=True,
        max_backup_keys=0,
    ).compiled()


def _getter(_url, _key, _timeout):
    return 200, {"data": {"remainingCredits": 123}}, ""


@pytest.fixture
def hub_env(tmp_path):
    # default key value contains "exhaust" -> the fake returns 402; key2 is good.
    environ = {"EXA_API_KEY": "exhaust-me", "EXA_API_KEY_2": "good-one"}
    specs = [_fake_spec(), _fake_searxng_spec()]
    keyed = [s for s in specs if not s.keyless]
    old = hub.CACHE_DIR
    hub.CACHE_DIR = str(tmp_path)
    for spec in specs:
        ok, _n, msg = hub.refresh_provider(spec)
        assert ok, msg
    store = accounts.AccountStore(
        str(tmp_path / "acc.json"),
        [hub._account_policy(s) for s in keyed],
        environ=environ,
    )
    rotation.seed_backup_keys(store, keyed, environ)
    rot = rotation.Rotator.from_specs(keyed, store, environ=environ, getter=_getter)
    cap = Capture()
    self_hosted = [
        adapters.TrailSearchAdapter("http://127.0.0.1:8794", caller=fake_ts.fake_caller)
    ]
    server = hub.SearchHub(
        specs,
        emit=cap,
        store=store,
        rotator=rot,
        environ=environ,
        self_hosted=self_hosted,
    )
    try:
        yield server, cap, rot
    finally:
        hub.CACHE_DIR = old
        for child in server._children.values():
            child._terminate()


def _call(mid, name, arguments=None):
    return {
        "jsonrpc": "2.0",
        "id": mid,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments or {}},
    }


def test_tools_list_served_without_spawning(hub_env):
    server, cap, _rot = hub_env
    server.dispatch({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    server.dispatch({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    msgs = cap.wait(2)
    listing = [m for m in msgs if m.get("id") == 2][0]
    names = {t["name"] for t in listing["result"]["tools"]}
    assert "web_search_exa" in names
    assert {"ex_account_list", "ex_account_switch", "ex_account_cycle"} <= names
    assert "search_usage" in names
    # The RAM promise: nothing spawned to answer tools/list.
    assert server._children == {}


def test_initialize_identifies_hub(hub_env):
    server, cap, _rot = hub_env
    server.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-06-18"},
        }
    )
    init = cap.wait(1)[0]
    assert init["result"]["serverInfo"]["name"] == "search-hub"
    assert init["result"]["protocolVersion"] == "2025-06-18"
    assert server._children == {}


def test_call_exhausts_active_and_rotates_to_backup(hub_env):
    server, cap, rot = hub_env
    server.dispatch(_call(10, "web_search_exa"))
    reply = cap.wait(1)[0]
    assert reply["id"] == 10
    payload = json.loads(reply["result"]["content"][0]["text"])
    # default ("exhaust-me") 402'd -> cooled + retried on key2 ("good-one").
    assert payload["backend"] == "exa"
    assert payload["received_name"] == "web_search_exa"
    assert payload["key_value"] == "good-one"
    assert rot.is_cooled("exa", "default")
    assert ("exa", "default") in server._children
    assert ("exa", "key2") in server._children


def test_keyless_searxng_serves_when_all_keyed_keys_cool(hub_env, monkeypatch):
    server, cap, rot = hub_env
    for name in rot.key_names("exa"):
        rot.mark_exhausted("exa", name, 100.0)
    assert rot.pick_active("exa") is None

    def reject_rotator(*_args, **_kwargs):
        raise AssertionError("keyless provider entered rotator")

    monkeypatch.setattr(rot, "route_call", reject_rotator)
    server.dispatch(_call(50, "searxng_web_search", {"query": "fallback"}))
    reply = cap.wait(1)[0]
    payload = json.loads(reply["result"]["content"][0]["text"])
    assert reply["id"] == 50
    assert payload == {
        "backend": "searxng",
        "received_name": "searxng_web_search",
        "key_value": "",
        "arguments": {"query": "fallback"},
    }
    names = {tool["name"] for tool in server.all_tools}
    assert "searxng_web_search" in names
    assert not any(name.startswith("sx_account_") for name in names)


def test_account_switch_changes_active_and_clears_cooldown(hub_env):
    server, cap, rot = hub_env
    rot.mark_exhausted("exa", "key2", 100.0)  # pretend key2 was cooled earlier
    server.dispatch(_call(20, "ex_account_switch", {"name": "key2"}))
    reply = cap.wait(1)[0]
    payload = json.loads(reply["result"]["content"][0]["text"])
    assert payload["ok"] and payload["active"] == "key2"
    # A deliberate switch un-cools the chosen key (manual op wins).
    assert not rot.is_cooled("exa", "key2")
    # Account management never spawns a search child.
    assert server._children == {}


def test_search_usage_reports_per_key(hub_env):
    server, cap, _rot = hub_env
    server.dispatch(_call(30, "search_usage", {"provider": "exa"}))
    reply = cap.wait(1)[0]
    report = json.loads(reply["result"]["content"][0]["text"])
    prov = report["providers"][0]
    assert prov["provider"] == "exa"
    key_names = {k["label"] or k["provider"] for k in prov["keys"]}
    assert len(prov["keys"]) == 2  # default + seeded key2
    # remaining flows from the injected getter (123) for every key.
    assert all(k["remaining"] == 123 for k in prov["keys"])
    assert all("health" in k for k in prov["keys"])
    assert server._children == {}  # usage never spawns a child
    assert key_names  # labels present


def test_unknown_tool_errors(hub_env):
    server, cap, _rot = hub_env
    server.dispatch(_call(40, "does_not_exist"))
    reply = cap.wait(1)[0]
    assert reply["id"] == 40 and reply["error"]["code"] == -32602
    assert server._children == {}


def test_selfhosted_tools_listed_without_spawning(hub_env):
    server, cap, _rot = hub_env
    server.dispatch({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
    listing = cap.wait(1)[0]
    names = {t["name"] for t in listing["result"]["tools"]}
    assert {"selfhosted_search", "selfhosted_extract"} <= names
    # Keyless self-hosted tools never collide with the keyed tavily_* provider.
    assert not any(n.startswith("tavily_") for n in names)
    assert server._children == {}  # HTTP lane spawns no child


def test_selfhosted_search_routes_over_http_in_process(hub_env):
    server, cap, _rot = hub_env
    server.dispatch(_call(60, "selfhosted_search", {"query": "keyless"}))
    reply = cap.wait(1)[0]
    assert reply["id"] == 60
    payload = json.loads(reply["result"]["content"][0]["text"])
    assert payload["query"] == "keyless"
    assert payload["results"][0]["url"] == "https://example.test/1"
    assert server._children == {}  # never spawns a subprocess


def test_selfhosted_backend_down_degrades_truthfully(hub_env):
    server, cap, _rot = hub_env

    def dead(_m, _u, _b, _h, _t):
        return 0, None, "connection refused"

    server.adapters[0]._caller = dead
    server.dispatch(_call(61, "selfhosted_search", {"query": "x"}))
    reply = cap.wait(1)[0]
    result = reply["result"]
    assert result["isError"] is True
    assert "not reachable" in result["content"][0]["text"]


def test_search_usage_includes_selfhosted_capability_lattice(hub_env):
    server, cap, _rot = hub_env
    server.dispatch(
        _call(62, "search_usage", {"provider": "selfhosted", "probe": True})
    )
    reply = cap.wait(1)[0]
    report = json.loads(reply["result"]["content"][0]["text"])
    assert report["providers"] == []  # narrowed to the self-hosted lane
    sh = report["self_hosted"][0]
    assert sh["provider"] == "selfhosted" and sh["keyless"] is True
    states = {t["state"] for t in sh["tools"]}
    assert states <= set(adapters.LATTICE)
    assert states == {"probed"}  # fake backend answers /docs healthy
    assert server._children == {}
