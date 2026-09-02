#!/usr/bin/env python3
"""Unit tests for the self-hosted, key-free search adapters.

Pure and network-free by default: the ``adapters.Caller`` is injected with the
fake TrailSearch router (``fake_trailsearch_backend.fake_caller``), so the
capability lattice, request translation, and truthful degradation are all pinned
without Docker, SearXNG, or a live socket. One test DOES stand up the fake over a
real loopback socket to prove the default stdlib ``urllib`` caller works
end-to-end.
"""

from __future__ import annotations

import json
import os
import sys
import threading
from http.server import HTTPServer

HUB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HUB_DIR)
sys.path.insert(0, TESTS_DIR)

import adapters  # noqa: E402
import fake_trailsearch_backend as fake  # noqa: E402

BASE = "http://127.0.0.1:8794"


def _adapter(base=BASE, caller=None):
    return adapters.TrailSearchAdapter(base, caller=caller or fake.fake_caller)


def _payload(result: dict) -> dict:
    assert not result["isError"], result
    return json.loads(result["content"][0]["text"])


# --------------------------------------------------------------------------- #
# surface
# --------------------------------------------------------------------------- #
def test_lattice_vocabulary_is_the_five_states():
    assert adapters.LATTICE == ("native", "probed", "declared", "emulated", "absent")


def test_tool_surface_is_keyless_selfhosted_pair():
    ad = _adapter()
    names = ad.tool_names()
    assert names == ["selfhosted_search", "selfhosted_extract"]
    # Names never collide with the keyed tavily_* provider.
    assert not any(n.startswith("tavily_") for n in names)
    defs = {d["name"]: d for d in ad.tool_defs()}
    assert defs["selfhosted_search"]["inputSchema"]["required"] == ["query"]
    assert defs["selfhosted_extract"]["inputSchema"]["required"] == ["urls"]


def test_default_adapters_reads_env_url_then_falls_back():
    assert (
        adapters.resolve_base_url({"TRAILSEARCH_URL": "http://host:9"})
        == "http://host:9"
    )
    assert (
        adapters.resolve_base_url({"SELFHOSTED_SEARCH_URL": "http://alt:10"})
        == "http://alt:10"
    )
    assert adapters.resolve_base_url({}) == adapters.DEFAULT_TRAILSEARCH_URL
    built = adapters.default_adapters({}, caller=fake.fake_caller)
    assert len(built) == 1 and built[0].platform == "selfhosted"


# --------------------------------------------------------------------------- #
# capability lattice
# --------------------------------------------------------------------------- #
def test_capabilities_declared_native_without_probe_does_no_network():
    calls = []

    def spy(*args):
        calls.append(args)
        return fake.fake_caller(*args)

    ad = _adapter(caller=spy)
    report = ad.capabilities(probe=False)
    assert calls == []  # RAM-cheap: tools/list must not touch the network
    assert report["keyless"] and report["self_hosted"] and report["base_url"] == BASE
    states = {t["tool"]: t for t in report["tools"]}
    # /tavily/* IS the Tavily contract -> native (declared confidence, unprobed).
    assert states["selfhosted_search"]["state"] == "native"
    assert states["selfhosted_search"]["realized_by"] == "native"


def test_capabilities_probed_when_backend_healthy():
    ad = _adapter()
    report = ad.capabilities(probe=True)
    assert report["probed"] is True
    assert all(t["state"] == "probed" for t in report["tools"])
    assert all(t["realized_by"] == "native" for t in report["tools"])


def test_capabilities_absent_when_unreachable():
    def dead(_m, _u, _b, _h, _t):
        return 0, None, "connection refused"

    report = _adapter(caller=dead).capabilities(probe=True)
    assert all(t["state"] == "absent" for t in report["tools"])
    assert "refused" in report["tools"][0]["note"]


def test_capabilities_absent_when_no_base_url():
    ad = _adapter(base="")
    report = ad.capabilities(probe=False)
    assert report["base_url"] is None
    assert all(t["state"] == "absent" for t in report["tools"])


def test_emulated_backend_kind_reports_emulated_unprobed():
    class Emulated(adapters.TrailSearchAdapter):
        kind = "emulated"  # e.g. a fastCRW/Orio backend needing shape translation

    report = Emulated(BASE, caller=fake.fake_caller).capabilities(probe=False)
    assert all(t["state"] == "emulated" for t in report["tools"])


# --------------------------------------------------------------------------- #
# request translation
# --------------------------------------------------------------------------- #
def test_search_request_body_is_tavily_shaped_and_whitelisted():
    captured = {}

    def spy(method, url, body, _h, _t):
        captured["method"] = method
        captured["url"] = url
        captured["body"] = json.loads(body.decode()) if body else None
        return fake.fake_caller(method, url, body, _h, _t)

    ad = _adapter(caller=spy)
    result = ad.handle_call(
        "selfhosted_search",
        {"query": "rust async", "max_results": 3, "topic": "code", "bogus": "drop-me"},
    )
    assert captured["method"] == "POST"
    assert captured["url"] == BASE + "/tavily/search"
    assert captured["body"] == {
        "query": "rust async",
        "max_results": 3,
        "topic": "code",
    }
    payload = _payload(result)
    assert payload["results"][0]["url"] == "https://example.test/1"
    assert payload["query"] == "rust async"


def test_extract_request_targets_extract_route():
    captured = {}

    def spy(method, url, body, _h, _t):
        captured["url"] = url
        captured["body"] = json.loads(body.decode()) if body else None
        return fake.fake_caller(method, url, body, _h, _t)

    ad = _adapter(caller=spy)
    result = ad.handle_call(
        "selfhosted_extract", {"urls": ["https://a.test", "https://b.test"]}
    )
    assert captured["url"] == BASE + "/tavily/extract"
    assert captured["body"] == {"urls": ["https://a.test", "https://b.test"]}
    payload = _payload(result)
    assert [r["url"] for r in payload["results"]] == [
        "https://a.test",
        "https://b.test",
    ]


# --------------------------------------------------------------------------- #
# truthful degradation -- never fabricate a result
# --------------------------------------------------------------------------- #
def test_call_when_backend_down_returns_truthful_error_not_fake_hits():
    def dead(_m, _u, _b, _h, _t):
        return 0, None, "connection refused"

    result = _adapter(caller=dead).handle_call("selfhosted_search", {"query": "x"})
    assert result["isError"] is True
    text = result["content"][0]["text"]
    assert "not reachable" in text and "fabricated" in text
    # No results key, no fake data leaked into the error envelope.
    assert "https://" not in text


def test_call_when_backend_errors_surfaces_status():
    result = _adapter().handle_call("selfhosted_search", {"query": "boom please"})
    assert result["isError"] is True
    assert "HTTP 500" in result["content"][0]["text"]


def test_call_without_base_url_is_absent_error():
    result = _adapter(base="").handle_call("selfhosted_search", {"query": "x"})
    assert result["isError"] is True
    assert "no self-hosted backend configured" in result["content"][0]["text"]


def test_unknown_tool_is_rejected():
    result = _adapter().handle_call("nope", {})
    assert result["isError"] is True
    assert "unknown self-hosted tool" in result["content"][0]["text"]


# --------------------------------------------------------------------------- #
# end-to-end over a real loopback socket (default stdlib urllib caller)
# --------------------------------------------------------------------------- #
def test_default_urllib_caller_against_real_socket():
    server = HTTPServer(("127.0.0.1", 0), fake._Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        ad = adapters.TrailSearchAdapter(f"http://127.0.0.1:{port}")  # real caller
        reachable, note = ad.probe()
        assert reachable, note
        result = ad.handle_call("selfhosted_search", {"query": "socket"})
        payload = _payload(result)
        assert payload["results"][0]["content"] == "content about socket"
    finally:
        server.shutdown()
        server.server_close()
