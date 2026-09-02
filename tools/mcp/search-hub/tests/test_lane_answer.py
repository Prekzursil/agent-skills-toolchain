#!/usr/bin/env python3
"""Tests for the opt-in ``answer`` lane: ``lane_answer.VaneAdapter`` + its deploy kit.

Network-free by default: the ``adapters.Caller`` is injected with the fake Vane
router (``fake_vane_backend.FakeVane``), so opt-in semantics, the provider
resolution (UUIDs drift -> resolved per call, cached 60 s), the ``/api/search``
mapping and every truthful degradation are pinned without Docker, SearXNG or an
LLM. Two tests stand the fake up over a real loopback socket to prove the default
stdlib ``urllib`` caller works end to end, including a real client-side timeout.

The deploy kit is checked at text level (plus a real YAML parse when pyyaml is
installed) and the run script's ``--print`` mode is executed for real -- it is
the one mode that does not need Docker, which this VM does not have.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
from http.server import HTTPServer

import pytest

HUB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
DEPLOY_DIR = os.path.join(HUB_DIR, "deploy")
sys.path.insert(0, HUB_DIR)
sys.path.insert(0, TESTS_DIR)

import adapters  # noqa: E402
import fake_vane_backend as fake  # noqa: E402
import lane_answer  # noqa: E402
import lanes  # noqa: E402
import onions  # noqa: E402

BASE = "http://127.0.0.1:3000"
TOOL = "selfhosted_answer"
COMPOSE = os.path.join(DEPLOY_DIR, "docker-compose.answer-engines.yml")
RUN_SH = os.path.join(DEPLOY_DIR, "run-answer-engines.sh")
RUN_PS1 = os.path.join(DEPLOY_DIR, "run-answer-engines.ps1")
STOP_SH = os.path.join(DEPLOY_DIR, "stop-answer-engines.sh")
STOP_PS1 = os.path.join(DEPLOY_DIR, "stop-answer-engines.ps1")
ENV_EXAMPLE = os.path.join(DEPLOY_DIR, "env.minimal.example")
DEPLOY_README = os.path.join(DEPLOY_DIR, "README.md")
HUB_README = os.path.join(HUB_DIR, "README.md")

VANE_IMAGE = "itzcrazykns1337/vane:slim-v1.12.2"
LDR_IMAGE = "localdeepresearch/local-deep-research:1.10.7"
OLLAMA_IMAGE = "ollama/ollama:0.33.2"


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _adapter(base=BASE, backend: fake.FakeVane | None = None, **kw):
    backend = backend if backend is not None else fake.FakeVane()
    return lane_answer.VaneAdapter(base, caller=backend.caller, **kw), backend


def _payload(result: dict) -> dict:
    assert result["isError"] is False, result
    return json.loads(result["content"][0]["text"])


def _error_text(result: dict) -> str:
    assert result["isError"] is True, result
    text = result["content"][0]["text"]
    assert text.startswith("[search-hub:answer] ")
    return text


class _Clock:
    """An injectable monotonic clock the cache tests can advance by hand."""

    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


# --------------------------------------------------------------------------- #
# opt-in / off semantics -- default OFF means 0 RAM idle
# --------------------------------------------------------------------------- #
def test_build_returns_nothing_unless_opted_in():
    assert lane_answer.build({}) == []
    assert lane_answer.build({"ENABLE_VANE": ""}) == []
    assert lane_answer.build({"ENABLE_VANE": "0"}) == []
    assert lane_answer.build({"ENABLE_VANE": "false"}) == []
    assert lane_answer.build({"VANE_URL": "   "}) == []  # blank URL is not a URL


def test_enable_flag_wires_the_adapter_at_the_default_url():
    built = lane_answer.build({"ENABLE_VANE": "1"})
    assert len(built) == 1
    ad = built[0]
    assert isinstance(ad, lane_answer.VaneAdapter)
    assert isinstance(ad, adapters.SelfHostedAdapter)
    assert ad.base_url == lane_answer.DEFAULT_VANE_URL == "http://127.0.0.1:3000"
    assert ad.platform == "answer"
    assert ad.timeout_s == lane_answer.DEFAULT_TIMEOUT_S == 120.0


def test_non_empty_vane_url_alone_wires_it_endpoint_agnostic():
    # G-4: one-line repoint to an OVH box, trailing slash tolerated.
    built = lane_answer.build({"VANE_URL": "https://vane.example.ovh/"})
    assert len(built) == 1 and built[0].base_url == "https://vane.example.ovh"


def test_explicit_falsey_flag_is_a_kill_switch_even_with_a_url():
    assert lane_answer.build({"ENABLE_VANE": "0", "VANE_URL": BASE}) == []
    assert lane_answer.build({"ENABLE_VANE": "off", "VANE_URL": BASE}) == []


def test_timeout_env_is_honoured_and_bad_values_fall_back():
    assert lane_answer.resolve_timeout({}) == 120.0
    assert lane_answer.resolve_timeout({"VANE_TIMEOUT_S": "15"}) == 15.0
    assert lane_answer.resolve_timeout({"VANE_TIMEOUT_S": " 2.5 "}) == 2.5
    assert lane_answer.resolve_timeout({"VANE_TIMEOUT_S": "nope"}) == 120.0
    assert lane_answer.resolve_timeout({"VANE_TIMEOUT_S": "0"}) == 120.0
    assert lane_answer.resolve_timeout({"VANE_TIMEOUT_S": "-3"}) == 120.0
    assert lane_answer.resolve_timeout({"VANE_TIMEOUT_S": "99999"}) == 3600.0  # cap
    built = lane_answer.build({"ENABLE_VANE": "1", "VANE_TIMEOUT_S": "15"})
    assert built[0].timeout_s == 15.0


def test_build_does_no_network_and_is_stdlib_only():
    calls = []

    def spy(*args):
        calls.append(args)
        return fake.fake_caller(*args)

    # build() itself must not probe: wiring is free, the daemon may be off.
    built = lane_answer.build({"ENABLE_VANE": "1"})
    assert built and calls == []
    # Import-time dependencies: stdlib + the hub's own modules only (lanes.py rule).
    source = _read(os.path.join(HUB_DIR, "lane_answer.py"))
    imported = re.findall(r"^(?:from|import)\s+([A-Za-z_][\w.]*)", source, re.M)
    allowed = set(sys.stdlib_module_names) | {"adapters", "onions", "__future__"}
    assert {name.split(".")[0] for name in imported} <= allowed


# --------------------------------------------------------------------------- #
# lanes.py wiring -- the registry sees [] when off, one adapter when on
# --------------------------------------------------------------------------- #
def test_lanes_build_lane_wires_lane_answer():
    assert lanes.build_lane("lane_answer", {}) == []
    built = lanes.build_lane("lane_answer", {"ENABLE_VANE": "1"})
    assert [a.platform for a in built] == ["answer"]
    adapters_on, degraded = lanes.extra_adapters(
        {"VANE_URL": BASE}, modules=("lane_answer",)
    )
    assert [a.platform for a in adapters_on] == ["answer"] and degraded == {}
    adapters_off, degraded_off = lanes.extra_adapters({}, modules=("lane_answer",))
    assert adapters_off == [] and degraded_off == {}  # off is not degraded


# --------------------------------------------------------------------------- #
# surface
# --------------------------------------------------------------------------- #
def test_tool_surface_is_the_single_answer_tool():
    ad, _ = _adapter()
    assert ad.tool_names() == [TOOL]
    assert not ad.owns("selfhosted_search")  # never collides with the TrailSearch pair
    schema = ad.tool_defs()[0]["inputSchema"]
    assert schema["required"] == ["query"]
    props = schema["properties"]
    assert set(props) == {
        "query",
        "focus",
        "optimization",
        "history",
        "chat_provider",
        "chat_model",
        "embedding_provider",
        "embedding_model",
    }
    assert props["focus"]["default"] == "webSearch"
    assert props["optimization"]["default"] == "balanced"
    assert props["optimization"]["enum"] == ["speed", "balanced", "quality"]
    assert props["history"]["type"] == "array"
    description = ad.tool_defs()[0]["description"]
    assert "Vane" in description and "never" in description.lower()
    assert "onion" in description.lower()  # the pass-through-only promise is stated


def test_capabilities_unprobed_is_native_and_does_no_network():
    calls = []

    def spy(*args):
        calls.append(args)
        return fake.fake_caller(*args)

    ad = lane_answer.VaneAdapter(BASE, caller=spy)
    report = ad.capabilities(probe=False)
    assert calls == []
    assert report["provider"] == "answer" and report["keyless"] is True
    assert report["self_hosted"] is True and report["base_url"] == BASE
    assert report["engine"] == "vane"
    assert report["timeout_s"] == 120.0
    assert report["providers_cache_ttl_s"] == 60
    assert "ENABLE_VANE" in report["opt_in"] and "VANE_URL" in report["opt_in"]
    (tool,) = report["tools"]
    assert tool["tool"] == TOOL and tool["state"] == "native"
    assert tool["backend_path"] == "/api/search"


def test_probe_is_get_api_providers_and_upgrades_to_probed():
    ad, backend = _adapter()
    reachable, note = ad.probe()
    assert reachable is True
    assert backend.calls == [("GET", "/api/providers", None)]
    assert "2 providers" in note and "3 chat" in note and "2 embedding" in note
    report = ad.capabilities(probe=True)
    assert report["probed"] is True
    assert report["tools"][0]["state"] == "probed"
    # A probed report names the providers so an operator sees the drifting ids.
    assert [p["name"] for p in report["providers"]] == ["Ollama", "OpenAI compatible"]
    assert report["providers"][0]["chat_models"] == ["llama3.2:3b", "qwen2.5:7b"]
    assert report["providers"][0]["embedding_models"] == ["nomic-embed-text"]


def test_probe_reachable_but_no_providers_says_so():
    ad, _ = _adapter(backend=fake.FakeVane(providers=[]))
    reachable, note = ad.probe()
    assert reachable is True  # the daemon answers ...
    assert "0 providers" in note and "no LLM" in note  # ... but it cannot answer yet


def test_probe_down_or_erroring_is_absent():
    def dead(_m, _u, _b, _h, _t):
        return 0, None, "connection refused"

    report = lane_answer.VaneAdapter(BASE, caller=dead).capabilities(probe=True)
    assert report["tools"][0]["state"] == "absent"
    assert "refused" in report["tools"][0]["note"]
    ad, _ = _adapter(backend=fake.FakeVane(providers_status=500))
    reachable, note = ad.probe()
    assert reachable is False and "HTTP 500" in note
    assert ad.capabilities(probe=True)["tools"][0]["state"] == "absent"


def test_no_base_url_is_absent_and_a_truthful_error():
    ad = lane_answer.VaneAdapter("", caller=fake.fake_caller)
    assert ad.capabilities()["tools"][0]["state"] == "absent"
    text = _error_text(ad.handle_call(TOOL, {"query": "x"}))
    assert "VANE_URL" in text and "fabricated" in text


# --------------------------------------------------------------------------- #
# provider resolution -- ids drift, so resolve per call and REPORT the pick
# --------------------------------------------------------------------------- #
def test_omitted_providers_pick_the_first_chat_and_embedding_and_report_them():
    ad, backend = _adapter()
    payload = _payload(ad.handle_call(TOOL, {"query": "what is vane"}))
    used = payload["providers_used"]
    assert used["chat"] == {
        "provider_id": "11111111-1111-4111-8111-111111111111",
        "provider": "Ollama",
        "model_key": "llama3.2:3b",
        "model_name": "Llama 3.2 3B",
        "selected_by": "first-available",
    }
    assert used["embedding"] == {
        "provider_id": "11111111-1111-4111-8111-111111111111",
        "provider": "Ollama",
        "model_key": "nomic-embed-text",
        "model_name": "Nomic Embed Text",
        "selected_by": "first-available",
    }
    # The request Vane received carried exactly those ids/keys.
    method, path, body = backend.calls[-1]
    assert (method, path) == ("POST", "/api/search")
    assert body["chatModel"] == {
        "providerId": "11111111-1111-4111-8111-111111111111",
        "key": "llama3.2:3b",
    }
    assert body["embeddingModel"] == {
        "providerId": "11111111-1111-4111-8111-111111111111",
        "key": "nomic-embed-text",
    }


def test_first_available_skips_a_provider_without_that_model_kind():
    providers = [
        {"id": "aaaa", "name": "ChatOnly", "chatModels": [{"name": "C", "key": "c"}]},
        {
            "id": "bbbb",
            "name": "Embeds",
            "chatModels": [],
            "embeddingModels": [{"name": "E", "key": "e"}],
        },
    ]
    ad, backend = _adapter(backend=fake.FakeVane(providers=providers))
    used = _payload(ad.handle_call(TOOL, {"query": "q"}))["providers_used"]
    assert (used["chat"]["provider"], used["chat"]["model_key"]) == ("ChatOnly", "c")
    assert (used["embedding"]["provider"], used["embedding"]["model_key"]) == (
        "Embeds",
        "e",
    )


def test_explicit_ids_are_honoured_verbatim():
    ad, backend = _adapter()
    payload = _payload(
        ad.handle_call(
            TOOL,
            {
                "query": "q",
                "chat_provider": "22222222-2222-4222-8222-222222222222",
                "chat_model": "gpt-4o-mini",
                "embedding_provider": "11111111-1111-4111-8111-111111111111",
                "embedding_model": "nomic-embed-text",
            },
        )
    )
    used = payload["providers_used"]
    assert used["chat"]["provider"] == "OpenAI compatible"
    assert used["chat"]["model_key"] == "gpt-4o-mini"
    assert used["chat"]["selected_by"] == "caller"
    assert used["embedding"]["provider"] == "Ollama"
    assert used["embedding"]["selected_by"] == "caller"
    body = backend.calls[-1][2]
    assert body["chatModel"]["providerId"] == "22222222-2222-4222-8222-222222222222"
    assert body["chatModel"]["key"] == "gpt-4o-mini"


def test_provider_and_model_names_resolve_case_insensitively():
    # Names are stable across installs while UUIDs drift -- accept both.
    ad, backend = _adapter()
    payload = _payload(
        ad.handle_call(
            TOOL,
            {"query": "q", "chat_provider": "ollama", "chat_model": "qwen 2.5 7b"},
        )
    )
    chat = payload["providers_used"]["chat"]
    assert chat["provider_id"] == "11111111-1111-4111-8111-111111111111"
    assert chat["model_key"] == "qwen2.5:7b" and chat["selected_by"] == "caller"
    body = backend.calls[-1][2]
    assert body["chatModel"]["key"] == "qwen2.5:7b"  # the KEY is sent, not the name


def test_explicit_provider_given_model_omitted_takes_its_first_model():
    ad, _ = _adapter()
    payload = _payload(
        ad.handle_call(TOOL, {"query": "q", "chat_provider": "OpenAI compatible"})
    )
    chat = payload["providers_used"]["chat"]
    assert chat["model_key"] == "gpt-4o-mini" and chat["selected_by"] == "caller"
    # Embedding was not constrained -> first available, reported as such.
    assert payload["providers_used"]["embedding"]["selected_by"] == "first-available"


def test_unknown_provider_or_model_is_a_truthful_error_listing_what_exists():
    ad, backend = _adapter()
    text = _error_text(ad.handle_call(TOOL, {"query": "q", "chat_provider": "Nope"}))
    assert "chat provider 'Nope'" in text
    assert "Ollama" in text and "OpenAI compatible" in text  # what IS configured
    text = _error_text(
        ad.handle_call(TOOL, {"query": "q", "embedding_model": "does-not-exist"})
    )
    assert "embedding model 'does-not-exist'" in text and "nomic-embed-text" in text
    # No /api/search request was spent on either bad resolution.
    assert all(path != "/api/search" for _m, path, _b in backend.calls)


def test_no_providers_configured_is_a_truthful_error_not_an_answer():
    ad, backend = _adapter(backend=fake.FakeVane(providers=[]))
    text = _error_text(ad.handle_call(TOOL, {"query": "q"}))
    assert "no providers" in text.lower() and "fabricated" in text
    assert "OLLAMA_BASE_URL" in text  # the remedy is named
    assert all(path != "/api/search" for _m, path, _b in backend.calls)


def test_providers_without_an_embedding_model_is_a_truthful_error():
    providers = [
        {"id": "x", "name": "ChatOnly", "chatModels": [{"name": "C", "key": "c"}]}
    ]
    ad, _ = _adapter(backend=fake.FakeVane(providers=providers))
    text = _error_text(ad.handle_call(TOOL, {"query": "q"}))
    assert "no embedding model" in text.lower() and "ChatOnly" in text


def test_providers_endpoint_failing_is_a_truthful_error():
    ad, _ = _adapter(backend=fake.FakeVane(providers_status=500))
    text = _error_text(ad.handle_call(TOOL, {"query": "q"}))
    assert "/api/providers" in text and "HTTP 500" in text and "fabricated" in text


# --------------------------------------------------------------------------- #
# the 60 s provider cache
# --------------------------------------------------------------------------- #
def test_provider_list_is_cached_for_60s_then_refetched():
    clock = _Clock(now=1000.0)
    ad, backend = _adapter(clock=clock)

    def provider_fetches() -> int:
        return sum(1 for _m, path, _b in backend.calls if path == "/api/providers")

    _payload(ad.handle_call(TOOL, {"query": "one"}))
    _payload(ad.handle_call(TOOL, {"query": "two"}))
    assert provider_fetches() == 1
    clock.now += 59.0
    payload = _payload(ad.handle_call(TOOL, {"query": "three"}))
    assert provider_fetches() == 1 and payload["providers_cached"] is True
    clock.now += 2.0  # past the TTL
    payload = _payload(ad.handle_call(TOOL, {"query": "four"}))
    assert provider_fetches() == 2 and payload["providers_cached"] is False
    assert lane_answer.PROVIDERS_CACHE_TTL_S == 60


def test_cache_is_dropped_when_a_refetch_fails_and_probe_warms_it():
    clock = _Clock()
    ad, backend = _adapter(clock=clock)
    assert ad.probe()[0] is True  # warms the cache: one GET
    _payload(ad.handle_call(TOOL, {"query": "q"}))
    assert [p for _m, p, _b in backend.calls] == ["/api/providers", "/api/search"]
    clock.now += 61.0
    backend.providers_status = 503
    text = _error_text(ad.handle_call(TOOL, {"query": "q"}))
    assert "HTTP 503" in text
    backend.providers_status = 200
    backend.providers = []  # the install changed under us -> the new truth is used
    text = _error_text(ad.handle_call(TOOL, {"query": "q"}))
    assert "no providers" in text.lower()


# --------------------------------------------------------------------------- #
# /api/search happy path -- the mapping
# --------------------------------------------------------------------------- #
def test_search_request_is_non_streaming_and_maps_the_response():
    ad, backend = _adapter()
    result = ad.handle_call(TOOL, {"query": "what is vane"})
    method, path, body = backend.calls[-1]
    assert (method, path) == ("POST", "/api/search")
    assert body["stream"] is False
    assert body["query"] == "what is vane"
    assert body["sources"] == ["web"]  # focus default webSearch -> Vane 'web'
    assert body["optimizationMode"] == "balanced"
    assert body["history"] == []
    assert set(body) == {
        "chatModel",
        "embeddingModel",
        "optimizationMode",
        "sources",
        "query",
        "history",
        "stream",
    }
    payload = _payload(result)
    assert payload["tool"] == TOOL and payload["engine"] == "vane"
    assert payload["query"] == "what is vane"
    assert payload["answer"].startswith("Answer about what is vane")
    assert payload["sources"] == [
        {
            "title": "result for what is vane",
            "url": "https://example.test/answer/1",
            "snippet": "snippet about what is vane",
        },
        {
            "title": "second result",
            "url": "https://example.test/2",
            "snippet": "second snippet about what is vane",
        },
    ]
    assert payload["focus"] == "webSearch" and payload["sources_used"] == ["web"]
    assert payload["optimization"] == "balanced"
    assert isinstance(payload["latency_ms"], int) and payload["latency_ms"] >= 0
    assert payload["providers_cached"] is False
    assert payload["base_url"] == BASE


def test_focus_vocabulary_maps_to_vane_sources():
    ad, backend = _adapter()

    def sources_for(focus) -> list[str]:
        _payload(ad.handle_call(TOOL, {"query": "q", "focus": focus}))
        return backend.calls[-1][2]["sources"]

    assert sources_for("webSearch") == ["web"]
    assert sources_for("academicSearch") == ["academic"]
    assert sources_for("redditSearch") == ["discussions"]
    assert sources_for("discussions") == ["discussions"]
    assert sources_for("web,academic") == ["web", "academic"]
    assert sources_for(["academic", "web", "web"]) == ["academic", "web"]
    assert sources_for("all") == ["web", "academic", "discussions"]
    assert sources_for("") == ["web"]  # empty means the default
    text = _error_text(ad.handle_call(TOOL, {"query": "q", "focus": "youtubeSearch"}))
    assert "youtubeSearch" in text and "web|academic|discussions" in text


def test_optimization_is_validated_before_any_request():
    ad, backend = _adapter()
    text = _error_text(ad.handle_call(TOOL, {"query": "q", "optimization": "turbo"}))
    assert "optimization" in text and "speed|balanced|quality" in text
    assert backend.calls == []  # nothing spent on a bad argument
    _payload(ad.handle_call(TOOL, {"query": "q", "optimization": "Quality"}))
    assert backend.calls[-1][2]["optimizationMode"] == "quality"


def test_query_is_required_and_must_be_text():
    ad, backend = _adapter()
    for args in ({}, {"query": ""}, {"query": "   "}, {"query": 7}, {"query": None}):
        text = _error_text(ad.handle_call(TOOL, args))
        assert "'query'" in text
    assert backend.calls == []


def test_history_pairs_and_role_dicts_pass_through_in_vane_shape():
    ad, backend = _adapter()
    history = [
        ["human", "Hi, how are you?"],
        ["assistant", "Well, thanks."],
        {"role": "user", "content": "and now?"},
        {"role": "ai", "content": "still fine"},
    ]
    payload = _payload(ad.handle_call(TOOL, {"query": "q", "history": history}))
    assert backend.calls[-1][2]["history"] == [
        ["human", "Hi, how are you?"],
        ["assistant", "Well, thanks."],
        ["human", "and now?"],
        ["assistant", "still fine"],
    ]
    assert payload["history_turns"] == 4


def test_malformed_history_is_a_truthful_error_before_any_request():
    ad, backend = _adapter()
    for bad in ("not a list", [["human"]], [{"content": "no role"}], [42], [[1, 2]]):
        text = _error_text(ad.handle_call(TOOL, {"query": "q", "history": bad}))
        assert "'history'" in text
    assert backend.calls == []


def test_unknown_tool_is_rejected():
    ad, _ = _adapter()
    assert "unknown answer tool" in _error_text(ad.handle_call("nope", {}))


# --------------------------------------------------------------------------- #
# truthful degradation of /api/search -- never a fabricated answer
# --------------------------------------------------------------------------- #
def test_backend_500_surfaces_status_and_vane_message():
    ad, _ = _adapter()
    text = _error_text(ad.handle_call(TOOL, {"query": "boom please"}))
    assert "HTTP 500" in text and "/api/search" in text
    assert "Search error" in text  # Vane's own message is relayed
    assert "fabricated" in text
    assert "https://" not in text  # no fake sources leak into the envelope


def test_backend_4xx_is_relayed():
    ad, _ = _adapter(backend=fake.FakeVane(search_status=400))
    text = _error_text(ad.handle_call(TOOL, {"query": "q"}))
    assert "HTTP 400" in text and "forced 400" in text


def test_connection_refused_on_search_is_truthful():
    backend = fake.FakeVane()

    def flaky(method, url, body, headers, timeout):
        if url.endswith("/api/search"):
            return 0, None, "request failed: [Errno 111] Connection refused"
        return backend.caller(method, url, body, headers, timeout)

    ad = lane_answer.VaneAdapter(BASE, caller=flaky)
    text = _error_text(ad.handle_call(TOOL, {"query": "q"}))
    assert "not reachable" in text and "Connection refused" in text
    assert "fabricated" in text


def test_timeout_is_named_with_the_configured_seconds_and_env():
    backend = fake.FakeVane()
    seen = {}

    def slow(method, url, body, headers, timeout):
        if url.endswith("/api/search"):
            seen["timeout"] = timeout
            return 0, None, "request failed: The read operation timed out"
        return backend.caller(method, url, body, headers, timeout)

    ad = lane_answer.VaneAdapter(BASE, caller=slow, timeout_s=7.5)
    text = _error_text(ad.handle_call(TOOL, {"query": "q"}))
    assert seen["timeout"] == 7.5  # the LLM timeout, not the 30 s adapter default
    assert "timed out" in text and "7.5" in text and "VANE_TIMEOUT_S" in text
    assert "fabricated" in text


def test_non_json_2xx_body_is_a_truthful_error():
    backend = fake.FakeVane()

    def html(method, url, body, headers, timeout):
        if url.endswith("/api/search"):
            return 200, None, "<html>proxy page</html>"
        return backend.caller(method, url, body, headers, timeout)

    ad = lane_answer.VaneAdapter(BASE, caller=html)
    text = _error_text(ad.handle_call(TOOL, {"query": "q"}))
    assert "not JSON" in text and "fabricated" in text


def test_empty_message_is_reported_not_padded():
    backend = fake.FakeVane()

    def empty(method, url, body, headers, timeout):
        if url.endswith("/api/search"):
            return 200, {"message": "", "sources": []}, '{"message":"","sources":[]}'
        return backend.caller(method, url, body, headers, timeout)

    ad = lane_answer.VaneAdapter(BASE, caller=empty)
    payload = _payload(ad.handle_call(TOOL, {"query": "q"}))
    assert payload["answer"] == "" and payload["sources"] == []
    assert "empty" in payload["note"].lower()


# --------------------------------------------------------------------------- #
# .onion sources: strings only, never fetched
# --------------------------------------------------------------------------- #
def test_onion_source_urls_pass_through_as_strings_and_are_never_fetched():
    ad, backend = _adapter()
    payload = _payload(ad.handle_call(TOOL, {"query": "onion index hit"}))
    onion = [s for s in payload["sources"] if s["url"].endswith(".onion/")]
    assert len(onion) == 1 and onion[0]["title"] == "onion index hit"
    assert payload["onion_sources"] == 1
    assert "never fetched" in payload["note"]
    # Every request went to the Vane base URL: nothing was fetched from a source.
    assert {path for _m, path, _b in backend.calls} == {"/api/providers", "/api/search"}
    assert onions.is_onion_url(onion[0]["url"])  # the hub's own onion detector agrees


def test_odd_source_shapes_are_kept_truthfully():
    backend = fake.FakeVane()
    weird = {
        "message": "m",
        "sources": [
            {"pageContent": "old perplexica shape", "metadata": {"url": "https://a"}},
            {"metadata": {"title": "no url"}},
            "not a dict",
            {"content": "no metadata at all"},
        ],
    }

    def odd(method, url, body, headers, timeout):
        if url.endswith("/api/search"):
            return 200, weird, json.dumps(weird)
        return backend.caller(method, url, body, headers, timeout)

    ad = lane_answer.VaneAdapter(BASE, caller=odd)
    payload = _payload(ad.handle_call(TOOL, {"query": "q"}))
    assert payload["sources"] == [
        {"title": None, "url": "https://a", "snippet": "old perplexica shape"},
        {"title": "no url", "url": None, "snippet": None},
        {"title": None, "url": None, "snippet": "no metadata at all"},
    ]


# --------------------------------------------------------------------------- #
# end-to-end over a real loopback socket (default stdlib urllib caller)
# --------------------------------------------------------------------------- #
def _serve(backend: fake.FakeVane):
    server = HTTPServer(("127.0.0.1", 0), backend.handler())
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


def test_default_urllib_caller_against_real_socket():
    backend = fake.FakeVane()
    server, base = _serve(backend)
    try:
        ad = lane_answer.VaneAdapter(base)  # the real caller
        reachable, note = ad.probe()
        assert reachable, note
        payload = _payload(ad.handle_call(TOOL, {"query": "socket"}))
        assert payload["answer"].startswith("Answer about socket")
        assert payload["providers_used"]["chat"]["model_key"] == "llama3.2:3b"
        assert payload["sources"][0]["url"] == "https://example.test/answer/1"
    finally:
        server.shutdown()
        server.server_close()


def test_real_client_timeout_is_a_truthful_error():
    backend = fake.FakeVane()
    server, base = _serve(backend)
    try:
        ad = lane_answer.VaneAdapter(base, timeout_s=0.2)  # fake sleeps 0.6 s
        text = _error_text(ad.handle_call(TOOL, {"query": "please sleep"}))
        assert "timed out" in text and "0.2" in text and "fabricated" in text
    finally:
        server.shutdown()
        server.server_close()


# --------------------------------------------------------------------------- #
# deploy kit: compose (profiles, pins, mem_limit, SearXNG repoint), scripts, docs
# --------------------------------------------------------------------------- #
def _compose_defaults(text: str) -> dict[str, str]:
    """Every ``${VAR:-default}`` in the compose file -> ``{VAR: default}``."""
    found: dict[str, str] = {}
    for var, default in re.findall(r"\$\{([A-Z0-9_]+):-([^}]*)\}", text):
        found.setdefault(var, default)
    return found


def test_compose_pins_images_and_starts_nothing_by_default():
    text = _read(COMPOSE)
    defaults = _compose_defaults(text)
    assert defaults["VANE_IMAGE"] == VANE_IMAGE
    assert defaults["LDR_IMAGE"] == LDR_IMAGE
    assert defaults["OLLAMA_IMAGE"] == OLLAMA_IMAGE
    assert ":latest" not in text.replace("slim-latest", "")  # no floating tag anywhere
    assert "slim-latest" not in re.sub(r"#.*", "", text)  # only mentioned in comments
    # The bundled all-in-one Vane image (SearXNG + uwsgi workers=%k) is NOT used.
    assert re.search(r"image:\s*\$\{VANE_IMAGE:-itzcrazykns1337/vane:slim-", text)
    assert defaults["VANE_SEARXNG_API_URL"] == "http://host.docker.internal:8890"
    assert defaults["VANE_PORT"] == "3000" and defaults["LDR_PORT"] == "5000"
    assert defaults["VANE_MEM_LIMIT"] == "768m"
    assert defaults["LDR_MEM_LIMIT"] == "2g"
    assert defaults["OLLAMA_MEM_LIMIT"] == "16g"
    assert "OLLAMA_KEEP_ALIVE" in text and '"0"' in text
    assert "host.docker.internal:host-gateway" in text
    assert "2026-09-02" in text  # the verification date travels with the pins


def test_compose_parses_and_every_service_is_profiled_capped_and_local_only():
    yaml = pytest.importorskip("yaml")
    data = yaml.safe_load(_read(COMPOSE))
    services = data["services"]
    assert set(services) == {"vane", "ldr", "ollama-evict"}
    assert services["vane"]["profiles"] == ["vane"]
    assert services["ldr"]["profiles"] == ["ldr"]
    assert services["ollama-evict"]["profiles"] == ["ollama"]
    for name, svc in services.items():
        assert svc.get("profiles"), f"{name} would start by default"
        assert "mem_limit" in svc, f"{name} has no memory cap"
        assert svc["restart"] == "${ANSWER_ENGINES_RESTART:-no}", name
        for port in svc.get("ports", []):
            assert str(port).startswith("127.0.0.1:"), (
                f"{name} publishes beyond loopback"
            )
    vane = services["vane"]
    assert vane["environment"]["SEARXNG_API_URL"].startswith("${VANE_SEARXNG_API_URL:-")
    assert any(v.endswith(":/home/vane/data") for v in vane["volumes"])  # config volume
    assert vane["ports"] == ["127.0.0.1:${VANE_PORT:-3000}:3000"]
    ldr = services["ldr"]
    assert ldr["ports"] == ["127.0.0.1:${LDR_PORT:-5000}:5000"]
    assert ldr["environment"]["LDR_WEB_PORT"] == "5000"
    assert ldr["environment"]["LDR_DATA_DIR"] == "/data"
    assert "LDR_LLM_OLLAMA_URL" in ldr["environment"]
    ollama = services["ollama-evict"]
    assert ollama["environment"]["OLLAMA_KEEP_ALIVE"] == "0"
    assert set(data["volumes"]) >= {
        "answer_engines_vane_data",
        "answer_engines_ldr_data",
    }


def test_run_script_print_mode_resolves_env_without_touching_docker(tmp_path):
    if shutil.which("bash") is None:
        pytest.skip("bash not available")
    # A docker shim that records any invocation: --print must never reach it.
    shim_dir = tmp_path / "bin"
    shim_dir.mkdir()
    marker = tmp_path / "docker-was-called"
    shim = shim_dir / "docker"
    shim.write_text(f'#!/usr/bin/env bash\necho "$@" >> "{marker}"\nexit 99\n')
    shim.chmod(0o755)
    env = {
        "PATH": f"{shim_dir}:{os.environ.get('PATH', '')}",
        "HOME": str(tmp_path),
        "VANE_PORT": "3100",
        "LDR_PORT": "5100",
        "VANE_SEARXNG_API_URL": "http://host.docker.internal:8891",
    }
    proc = subprocess.run(
        ["bash", RUN_SH, "up", "--vane", "--ldr", "--print"],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(tmp_path),  # the script must not depend on the cwd
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    assert not marker.exists(), "--print invoked docker"
    assert f"VANE_IMAGE={VANE_IMAGE}" in out
    assert f"LDR_IMAGE={LDR_IMAGE}" in out
    assert f"OLLAMA_IMAGE={OLLAMA_IMAGE}" in out
    assert "VANE_PORT=3100" in out and "LDR_PORT=5100" in out
    assert "VANE_SEARXNG_API_URL=http://host.docker.internal:8891" in out
    assert "VANE_MEM_LIMIT=768m" in out and "LDR_MEM_LIMIT=2g" in out
    assert "OLLAMA_KEEP_ALIVE=0" in out
    assert "--profile vane --profile ldr" in out
    assert "docker compose -f" in out and "up -d" in out
    # The hub flags an operator sets afterwards, ports substituted.
    assert "VANE_URL=http://127.0.0.1:3100" in out
    assert "ENABLE_VANE=1" in out
    # LDR: the flag is named, the container's REST port is shown, and the two are
    # NOT conflated -- providers.py runs ldr-mcp over STDIO on the host for
    # ENABLE_LDR=1 and reads LDR_URL only for a resident MCP gateway.
    assert "ENABLE_LDR=1" in out and "http://127.0.0.1:5100" in out
    assert "LDR_URL" in out and "STDIO" in out
    assert "LDR_URL=http://127.0.0.1:5100" not in out
    # `print` as an action and no profile at all both work and stay Docker-free.
    proc = subprocess.run(
        ["bash", RUN_SH, "print"], capture_output=True, text=True, env=env, timeout=30
    )
    assert proc.returncode == 0, proc.stderr
    assert "profiles" in proc.stdout and not marker.exists()


def test_run_script_up_without_a_profile_refuses_and_names_the_flags(tmp_path):
    if shutil.which("bash") is None:
        pytest.skip("bash not available")
    shim_dir = tmp_path / "bin"
    shim_dir.mkdir()
    marker = tmp_path / "docker-was-called"
    shim = shim_dir / "docker"
    shim.write_text(f'#!/usr/bin/env bash\necho "$@" >> "{marker}"\nexit 99\n')
    shim.chmod(0o755)
    env = {"PATH": f"{shim_dir}:{os.environ.get('PATH', '')}", "HOME": str(tmp_path)}
    proc = subprocess.run(
        ["bash", RUN_SH, "up"], capture_output=True, text=True, env=env, timeout=30
    )
    assert proc.returncode == 2
    assert "--vane" in proc.stderr and "--ldr" in proc.stderr
    assert not marker.exists()  # nothing starts by default, not even by accident


def test_script_defaults_match_the_compose_defaults():
    compose_defaults = _compose_defaults(_read(COMPOSE))
    sh = _read(RUN_SH)
    ps1 = _read(RUN_PS1)
    for var in (
        "VANE_IMAGE",
        "VANE_PORT",
        "VANE_SEARXNG_API_URL",
        "VANE_OLLAMA_BASE_URL",
        "VANE_MEM_LIMIT",
        "LDR_IMAGE",
        "LDR_PORT",
        "LDR_OLLAMA_URL",
        "LDR_SEARXNG_URL",
        "LDR_MEM_LIMIT",
        "OLLAMA_IMAGE",
        "OLLAMA_MEM_LIMIT",
    ):
        default = compose_defaults[var]
        # bash: VAR="${VAR:-default}"  --  powershell: 'default'
        assert re.search(rf"{var}=\"\$\{{{var}:-{re.escape(default)}\}}\"", sh), var
        assert f"'{default}'" in ps1, (var, default)
    # The stop scripts exist and delegate to a `down` of every profile.
    stop_sh = _read(STOP_SH)
    assert "run-answer-engines.sh" in stop_sh and "down" in stop_sh
    stop_ps1 = _read(STOP_PS1)
    assert "run-answer-engines.ps1" in stop_ps1 and "down" in stop_ps1
    assert os.access(RUN_SH, os.X_OK) and os.access(STOP_SH, os.X_OK)
    for text in (sh, ps1):
        assert "--vane" in text or "-Vane" in text
        assert "--ldr" in text or "-Ldr" in text
        assert "--print" in text or "-Print" in text
        assert "OLLAMA_KEEP_ALIVE" in text


def test_env_example_and_deploy_readme_document_the_answer_engines():
    env_text = _read(ENV_EXAMPLE)
    for var in (
        "ENABLE_VANE",
        "VANE_URL",
        "VANE_TIMEOUT_S",
        "VANE_PORT",
        "VANE_IMAGE",
        "VANE_SEARXNG_API_URL",
        "VANE_MEM_LIMIT",
        "LDR_PORT",
        "LDR_IMAGE",
        "LDR_MEM_LIMIT",
        "ENABLE_LDR",
        "LDR_URL",
        "OLLAMA_KEEP_ALIVE",
    ):
        assert var in env_text, var
    assert VANE_IMAGE in env_text and LDR_IMAGE in env_text
    # The original TrailSearch block is intact (append-only edit).
    assert "SELFHOSTED_SEARCH_PORT=8794" in env_text
    assert "TRAILSEARCH_REF=e0e2dc1160fc60d0ea925e164194e34040e750f6" in env_text
    readme = _read(DEPLOY_README)
    assert "## Answer engines" in readme
    assert "--vane" in readme and "--ldr" in readme and "--print" in readme
    assert (
        "ENABLE_LDR=1" in readme and "LDR_URL" in readme
    )  # the providers agent's flags
    assert "VANE_URL=https://" in readme  # the OVH repoint
    assert "OLLAMA_KEEP_ALIVE=0" in readme
    assert "workers=%k" in readme  # why the bundled image is avoided
    assert VANE_IMAGE in readme and LDR_IMAGE in readme
    assert "not been run" in readme  # honest: no Docker on the authoring VM
    # The TrailSearch sections above it are untouched.
    assert "# Deploy: the keyless self-hosted search backend" in readme
    assert "## Minimal profile (recommended on the 31.6 GB box)" in readme


def test_hub_readme_section_sits_immediately_before_tools():
    readme = _read(HUB_README)
    heading = (
        "## Answer engines (opt-in, on-demand): Vane adapter + local-deep-research"
    )
    assert readme.count(heading) == 1
    start = readme.index(heading)
    tools_at = readme.index("\n## Tools\n")
    assert start < tools_at
    section = readme[start:tools_at]
    assert "## " not in section[len(heading) :]  # nothing else in between
    assert section.rstrip().endswith("---")  # the section separator convention
    for needle in (
        "selfhosted_answer",
        "ENABLE_VANE",
        "VANE_URL",
        "VANE_TIMEOUT_S",
        "/api/providers",
        "/api/search",
        "providers_used",
        "latency_ms",
        '"engine": "vane"',
        "ENABLE_LDR",
        "LDR_URL",
        "deploy/README.md",
        "onion",
    ):
        assert needle in section, needle
    # The sections around it are untouched.
    assert "## `read_url` — in-process fetch negotiating Cloudflare" in readme
    assert "## Tools\n" in readme and "## Multi-key setup (plug-and-play)" in readme
