#!/usr/bin/env python3
"""Tests for per-key health, pick_active, the rotate-retry wrapper, the Tavily
ambiguous-429 usage probe, and numbered-backup seeding. All mocked -- the
``forward`` callback and usage ``getter`` are fakes, so no child spawns and no
network is touched."""

from __future__ import annotations

import json
import os
import sys

HUB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HUB_DIR)

import accounts  # noqa: E402
import providers  # noqa: E402
import rotation  # noqa: E402


class Clock:
    def __init__(self, t: float = 1000.0):
        self.t = t

    def __call__(self) -> float:
        return self.t


def _store(tmp_path, environ):
    pols = [
        accounts.AccountPolicy(
            platform=s.platform, mode="env", seed_env=(s.key_env,), label=s.label
        )
        for s in providers.default_providers()
    ]
    return accounts.AccountStore(str(tmp_path / "acc.json"), pols, environ=environ)


def _rotator(tmp_path, environ, clock=None, getter=None):
    store = _store(tmp_path, environ)
    rotation.seed_backup_keys(store, providers.default_providers(), environ)
    rot = rotation.Rotator.from_specs(
        providers.default_providers(),
        store,
        environ=environ,
        clock=clock or Clock(),
        getter=getter,
    )
    return rot, store


def _call(name: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": 7,
        "method": "tools/call",
        "params": {"name": name, "arguments": {}},
    }


def _clean() -> dict:
    return {
        "jsonrpc": "2.0",
        "id": 7,
        "result": {"content": [{"type": "text", "text": "ok"}]},
    }


def _iserror(text: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": 7,
        "result": {"isError": True, "content": [{"type": "text", "text": text}]},
    }


def _forward(responses: dict):
    calls: list[str] = []

    def forward(name: str, _request: dict) -> dict:
        calls.append(name)
        resp = responses[name]
        return resp() if callable(resp) else resp

    return forward, calls


# --------------------------------------------------------------------------- #
# roster + pick_active
# --------------------------------------------------------------------------- #
def test_usable_names_skip_unresolvable(tmp_path):
    # EXA_API_KEY present, EXA_API_KEY_2 registered but its env value is absent.
    rot, _ = _rotator(tmp_path, {"EXA_API_KEY": "k1", "EXA_API_KEY_2": "k2"})
    assert rot.usable_names("exa") == ["default", "key2"]
    # Drop the backup's env value: key2 becomes unusable (stale ${ref} -> "").
    rot.environ = {"EXA_API_KEY": "k1"}
    rot.store.environ = {"EXA_API_KEY": "k1"}
    assert rot.usable_names("exa") == ["default"]


def test_pick_active_skips_cooled(tmp_path):
    rot, _ = _rotator(tmp_path, {"EXA_API_KEY": "k1", "EXA_API_KEY_2": "k2"})
    assert rot.pick_active("exa") == "default"  # store's active, healthy
    rot.mark_exhausted("exa", "default", 100.0)
    assert rot.is_cooled("exa", "default")
    assert rot.pick_active("exa") == "key2"  # rotated past the cooled active
    rot.mark_exhausted("exa", "key2", 100.0)
    assert rot.pick_active("exa") is None  # all cooled


def test_pick_active_none_when_no_keys(tmp_path):
    rot, _ = _rotator(tmp_path, {})  # no EXA_API_KEY at all
    assert rot.pick_active("exa") is None


def test_clear_cooldown_uncools(tmp_path):
    rot, _ = _rotator(tmp_path, {"EXA_API_KEY": "k1"})
    rot.mark_exhausted("exa", "default", 100.0)
    assert rot.is_cooled("exa", "default")
    rot.clear_cooldown("exa", "default")
    assert not rot.is_cooled("exa", "default")


# --------------------------------------------------------------------------- #
# route_call: the reactive rotate-retry-once policy (SG-2)
# --------------------------------------------------------------------------- #
def test_route_call_happy_path_no_cooldown(tmp_path):
    rot, _ = _rotator(tmp_path, {"EXA_API_KEY": "k1"})
    forward, calls = _forward({"default": _clean()})
    resp = rot.route_call("exa", _call("web_search_exa"), forward)
    assert resp == _clean() and calls == ["default"]
    assert not rot.is_cooled("exa", "default")


def test_route_call_rotates_and_retries_once(tmp_path):
    rot, _ = _rotator(
        tmp_path, {"EXA_API_KEY": "exhaust-k1", "EXA_API_KEY_2": "good-k2"}
    )
    forward, calls = _forward(
        {
            "default": _iserror("HTTP 402 NO_MORE_CREDITS"),
            "key2": _clean(),
        }
    )
    resp = rot.route_call("exa", _call("web_search_exa"), forward)
    # Exhausted key cooled, call retried once on the backup, backup's reply wins.
    assert calls == ["default", "key2"]
    assert resp == _clean()
    assert rot.is_cooled("exa", "default") and not rot.is_cooled("exa", "key2")


def test_route_call_single_key_returns_native_error(tmp_path):
    rot, _ = _rotator(tmp_path, {"EXA_API_KEY": "k1"})
    native = _iserror("HTTP 402 NO_MORE_CREDITS")
    forward, calls = _forward({"default": native})
    resp = rot.route_call("exa", _call("web_search_exa"), forward)
    assert resp == native and calls == ["default"]  # no backup -> native error, once
    assert rot.is_cooled("exa", "default")


def test_route_call_all_cooled_returns_exhausted_reply(tmp_path):
    rot, _ = _rotator(tmp_path, {"EXA_API_KEY": "k1", "EXA_API_KEY_2": "k2"})
    rot.mark_exhausted("exa", "default", 100.0)
    rot.mark_exhausted("exa", "key2", 100.0)
    forward, calls = _forward({})
    resp = rot.route_call("exa", _call("web_search_exa"), forward)
    assert calls == []  # never forwarded -- nothing to route to
    assert (
        resp["result"]["isError"] and "cooling" in resp["result"]["content"][0]["text"]
    )


def test_route_call_no_key_configured_reply(tmp_path):
    rot, _ = _rotator(tmp_path, {})
    forward, calls = _forward({})
    resp = rot.route_call("exa", _call("web_search_exa"), forward)
    assert calls == [] and resp["result"]["isError"]
    assert "no usable Exa API key" in resp["result"]["content"][0]["text"]


def test_route_call_rate_limit_does_not_cool(tmp_path):
    # Firecrawl 429 -> RATE_LIMITED: return native, DO NOT cool, DO NOT rotate.
    rot, _ = _rotator(
        tmp_path, {"FIRECRAWL_API_KEY": "k1", "FIRECRAWL_API_KEY_2": "k2"}
    )
    native = _iserror("HTTP 429 rate limit, Retry-After: 30")
    forward, calls = _forward({"default": native})
    resp = rot.route_call("firecrawl", _call("firecrawl_search"), forward)
    assert resp == native and calls == ["default"]
    assert not rot.is_cooled("firecrawl", "default")


# --------------------------------------------------------------------------- #
# Tavily ambiguous 429 -> probe /usage to decide
# --------------------------------------------------------------------------- #
def _usage_getter(remaining_body):
    def get(_url, _key, _timeout):
        return 200, remaining_body, ""

    return get


def test_tavily_ambiguous_429_exhausted_when_no_headroom(tmp_path):
    getter = _usage_getter({"account": {"plan_limit": 100, "plan_usage": 100}})
    rot, _ = _rotator(
        tmp_path, {"TAVILY_API_KEY": "k1", "TAVILY_API_KEY_2": "k2"}, getter=getter
    )
    forward, calls = _forward(
        {"default": _iserror("HTTP 429 rate limit"), "key2": _clean()}
    )
    resp = rot.route_call("tavily", _call("tavily_search"), forward)
    # /usage says 0 remaining -> treat the 429 as exhaustion -> rotate.
    assert calls == ["default", "key2"] and resp == _clean()
    assert rot.is_cooled("tavily", "default")


def test_tavily_ambiguous_429_rate_when_headroom(tmp_path):
    getter = _usage_getter({"account": {"plan_limit": 100, "plan_usage": 10}})
    rot, _ = _rotator(
        tmp_path, {"TAVILY_API_KEY": "k1", "TAVILY_API_KEY_2": "k2"}, getter=getter
    )
    native = _iserror("HTTP 429 rate limit")
    forward, calls = _forward({"default": native})
    resp = rot.route_call("tavily", _call("tavily_search"), forward)
    # 90 remaining -> a genuine rate limit -> no rotate, no cool, native returned.
    assert calls == ["default"] and resp == native
    assert not rot.is_cooled("tavily", "default")


# --------------------------------------------------------------------------- #
# cooldown duration + numbered-backup seeding
# --------------------------------------------------------------------------- #
def test_exhaust_cooldown_override_and_default(tmp_path):
    rot, _ = _rotator(
        tmp_path, {"EXA_API_KEY": "k1", "SEARCH_HUB_EXHAUST_COOLDOWN_S": "5"}
    )
    assert rot.exhaust_cooldown_s() == 5.0
    rot2, _ = _rotator(tmp_path, {"EXA_API_KEY": "k1"}, clock=Clock(1_700_000_000.0))
    assert rot2.exhaust_cooldown_s() > 0  # seconds until next month reset


def test_seconds_until_month_reset_positive():
    assert rotation.seconds_until_month_reset(1_700_000_000.0) > 0


def test_seed_backup_keys_refs_only_and_idempotent(tmp_path):
    environ = {"EXA_API_KEY": "k1", "EXA_API_KEY_2": "k2", "EXA_API_KEY_3": "k3"}
    store = _store(tmp_path, environ)
    added = rotation.seed_backup_keys(store, providers.default_providers(), environ)
    names = {(a["platform"], a["name"]) for a in added}
    assert ("exa", "key2") in names and ("exa", "key3") in names
    assert store.env_for("exa", "key2") == {"EXA_API_KEY": "k2"}
    # Idempotent: a second pass adds nothing.
    assert (
        rotation.seed_backup_keys(store, providers.default_providers(), environ) == []
    )
    # Refs only on disk -- never a literal secret.
    disk = json.loads((tmp_path / "acc.json").read_text(encoding="utf-8"))
    stored = {a["name"]: a["env"]["EXA_API_KEY"] for a in disk["exa"]["accounts"]}
    assert stored["default"] == "${EXA_API_KEY}"
    assert stored["key2"] == "${EXA_API_KEY_2}"
    assert "k2" not in (tmp_path / "acc.json").read_text(encoding="utf-8")


def test_health_snapshot_shape(tmp_path):
    rot, _ = _rotator(tmp_path, {"EXA_API_KEY": "k1", "EXA_API_KEY_2": "k2"})
    rot.mark_exhausted("exa", "default", 100.0, reason="hard-exhaustion")
    snap = {h["name"]: h for h in rot.health_snapshot("exa")}
    assert snap["default"]["cooled"] and snap["default"]["cooldown_remaining_s"] > 0
    assert not snap["key2"]["cooled"] and snap["key2"]["usable"]
