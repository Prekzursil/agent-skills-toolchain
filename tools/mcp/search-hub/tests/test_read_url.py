#!/usr/bin/env python3
"""Unit tests for the in-process ``read_url`` adapter (v0: Cloudflare markdown
negotiation + a stdlib tag-stripping fallback).

Runs against a REAL loopback fake origin (``fake_page_backend``) so the default
stdlib ``urllib`` fetch path, the content negotiation, the manual redirect loop
and the size cap are all exercised with NO network. Safety refusals (.onion,
non-http schemes, private/loopback targets, redirect caps, credentials in URLs)
are pinned with a fetch spy proving that NO request was made.

The fake origin lives on 127.0.0.1, which the adapter refuses by default, so the
tests that must reach it pass ``READ_URL_ALLOW_PRIVATE=1`` in the adapter's own
``environ`` -- the documented test/dev escape hatch, never ``os.environ``.
"""

from __future__ import annotations

import json
import os
import socket
import sys

import pytest

HUB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HUB_DIR)
sys.path.insert(0, TESTS_DIR)

import accounts  # noqa: E402
import adapters  # noqa: E402
import hub  # noqa: E402
import rotation  # noqa: E402

import fake_page_backend as fake  # noqa: E402

ALLOW = {"READ_URL_ALLOW_PRIVATE": "1"}


@pytest.fixture(scope="module")
def origin():
    server, base = fake.start_server()
    try:
        yield base
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture(autouse=True)
def _reset_fake():
    fake.reset()
    yield
    fake.reset()


def _spy_fetch(calls: list):
    def fetch(url, headers, timeout, max_bytes):
        calls.append(url)
        return adapters._urllib_fetch(url, headers, timeout, max_bytes)

    return fetch


def _adapter(environ=None, fetch=None, resolver=None):
    return adapters.ReadUrlAdapter(
        environ=ALLOW if environ is None else environ, fetch=fetch, resolver=resolver
    )


def _payload(result: dict) -> dict:
    assert not result["isError"], result
    return json.loads(result["content"][0]["text"])


def _error_text(result: dict) -> str:
    assert result["isError"] is True, result
    return result["content"][0]["text"]


# --------------------------------------------------------------------------- #
# surface
# --------------------------------------------------------------------------- #
def test_tool_surface_is_one_honest_tool():
    ad = _adapter()
    assert ad.tool_names() == ["read_url"]
    d = ad.tool_defs()[0]
    assert d["inputSchema"]["required"] == ["url"]
    assert set(d["inputSchema"]["properties"]) == {"url", "max_bytes", "timeout_s"}
    desc = d["description"].lower()
    assert "not readability" in desc  # the fallback is honest about being tag-stripping
    assert "cloudflare" in desc and ".onion" in desc
    report = ad.capabilities()
    assert report["provider"] == "read_url" and report["self_hosted"] is False
    assert report["keyless"] is True
    assert [t["state"] for t in report["tools"]] == ["native"]
    assert report["private_targets_allowed"] is True
    assert _adapter(environ={}).capabilities()["private_targets_allowed"] is False


# --------------------------------------------------------------------------- #
# (a) Cloudflare markdown path
# --------------------------------------------------------------------------- #
def test_cloudflare_markdown_negotiated_is_high_quality_with_tokens(origin):
    payload = _payload(_adapter().handle_call("read_url", {"url": origin + "/cf"}))
    assert payload["extractor"] == "cloudflare-markdown"
    assert payload["quality"] == "high"
    assert payload["content_type"] == "text/markdown"
    assert payload["tokens"] == {"markdown": 123, "original": 4567}
    assert payload["title"] == "Markdown for Agents"  # from the YAML frontmatter
    assert payload["markdown"].startswith("---\ntitle:")
    assert "# Markdown for Agents" in payload["markdown"]
    assert "text" not in payload  # one body key per extractor path
    assert payload["status"] == 200 and payload["truncated"] is False
    assert payload["url"] == payload["final_url"] == origin + "/cf"
    assert payload["redirects"] == 0
    sent = fake.RECEIVED[0]["headers"]
    # The negotiation header, exactly as Cloudflare documents it.
    assert sent["accept"].startswith("text/markdown, text/html;q=0.9")
    assert "search-hub" in sent["user-agent"]
    assert "cookie" not in sent and "authorization" not in sent


# --------------------------------------------------------------------------- #
# (b) stdlib HTML fallback
# --------------------------------------------------------------------------- #
def test_html_fallback_strips_boilerplate_keeps_title_and_paragraphs(origin):
    payload = _payload(_adapter().handle_call("read_url", {"url": origin + "/html"}))
    assert payload["extractor"] == "stdlib-text"
    assert payload["quality"] == "low"
    assert payload["content_type"] == "text/html"
    assert "tokens" not in payload and "markdown" not in payload
    assert (
        payload["title"] == "Example Page \u2014 Read Me"
    )  # entity decoded, ws collapsed
    text = payload["text"]
    assert (
        "SKIP-" not in text
    )  # script/style/noscript/svg/template/nav/footer/aside/header
    assert "First heading" in text
    assert "Tom & Jerry went to the market \u2014 it was busy, very busy." in text
    assert "Second paragraph with an inline link and inline code." in text
    assert "alpha\nbeta" in text  # list items keep line breaks
    assert "First heading\n\nTom & Jerry" in text  # paragraph breaks kept
    assert "  " not in text.replace("\n", "")  # whitespace collapsed
    assert "low" in payload["note"] and "trafilatura" in payload["note"].lower()


def test_plain_text_passes_through_with_collapsed_blank_lines(origin):
    payload = _payload(_adapter().handle_call("read_url", {"url": origin + "/plain"}))
    assert payload["extractor"] == "stdlib-text" and payload["quality"] == "low"
    assert payload["text"] == "just plain\n\ntext"
    assert payload["title"] is None


def test_declared_charset_is_honoured(origin):
    payload = _payload(_adapter().handle_call("read_url", {"url": origin + "/latin1"}))
    assert payload["title"] == "Caf\u00e9" and "na\u00efve" in payload["text"]


# --------------------------------------------------------------------------- #
# (c) .onion refused, (d) non-http schemes refused -- before ANY request
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "url",
    [
        "http://expyuzz4wqqyqhjn.onion/",
        "https://something.ONION./page",
        "http://user@abc.onion:8080/x",
    ],
)
def test_onion_urls_refused_without_any_request(url):
    calls: list = []
    text = _error_text(
        _adapter(fetch=_spy_fetch(calls)).handle_call("read_url", {"url": url})
    )
    assert ".onion" in text and "envelope" in text.lower()
    assert calls == []


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://ftp.example.test/pub/x",
        "javascript:alert(1)",
        "data:text/html,hi",
        "gopher://x",
        "//no-scheme.example/x",
        "example.com/no-scheme",
    ],
)
def test_non_http_schemes_refused_without_any_request(url):
    calls: list = []
    text = _error_text(
        _adapter(fetch=_spy_fetch(calls)).handle_call("read_url", {"url": url})
    )
    assert "http" in text and "https" in text
    assert calls == []


def test_credentials_in_url_are_refused_never_sent():
    calls: list = []
    text = _error_text(
        _adapter(fetch=_spy_fetch(calls)).handle_call(
            "read_url", {"url": "http://alice:secret@127.0.0.1:9/x"}
        )
    )
    assert "credentials" in text.lower() and "secret" not in text
    assert calls == []


# --------------------------------------------------------------------------- #
# (e) redirects: followed up to 5 hops, re-checked each hop, loops refused
# --------------------------------------------------------------------------- #
def test_redirect_loop_is_refused_after_the_hop_cap(origin):
    calls: list = []
    text = _error_text(
        _adapter(fetch=_spy_fetch(calls)).handle_call(
            "read_url", {"url": origin + "/loop"}
        )
    )
    assert "too many redirects" in text and "5" in text
    assert (
        len(calls) == adapters.READ_URL_MAX_REDIRECTS + 1
    )  # initial + 5 hops, then stop


def test_five_redirects_are_followed_six_are_not(origin):
    ad = _adapter()
    payload = _payload(ad.handle_call("read_url", {"url": origin + "/hop/5"}))
    assert payload["redirects"] == 5
    assert (
        payload["final_url"] == origin + "/hop/0"
        and payload["url"] == origin + "/hop/5"
    )
    assert payload["title"] == "Example Page \u2014 Read Me"
    assert "too many redirects" in _error_text(
        ad.handle_call("read_url", {"url": origin + "/hop/6"})
    )


def test_redirect_to_onion_or_file_is_refused_at_the_hop(origin):
    calls: list = []
    ad = _adapter(fetch=_spy_fetch(calls))
    text = _error_text(ad.handle_call("read_url", {"url": origin + "/to-onion"}))
    assert ".onion" in text and len(calls) == 1  # the onion hop was never fetched
    calls.clear()
    text = _error_text(ad.handle_call("read_url", {"url": origin + "/to-file"}))
    assert "file" in text and len(calls) == 1


def test_redirect_without_location_is_an_error(origin):
    text = _error_text(
        _adapter().handle_call("read_url", {"url": origin + "/nolocation"})
    )
    assert "302" in text and "Location" in text


# --------------------------------------------------------------------------- #
# (f) private / loopback / link-local targets refused unless the escape hatch is set
# --------------------------------------------------------------------------- #
def test_loopback_refused_by_default_and_allowed_with_the_flag(origin):
    calls: list = []
    strict = _adapter(environ={}, fetch=_spy_fetch(calls))
    text = _error_text(strict.handle_call("read_url", {"url": origin + "/html"}))
    assert "private" in text.lower() and "READ_URL_ALLOW_PRIVATE" in text
    assert calls == []
    allowed = _adapter(environ=ALLOW, fetch=_spy_fetch(calls))
    payload = _payload(allowed.handle_call("read_url", {"url": origin + "/html"}))
    assert payload["status"] == 200 and len(calls) == 1


@pytest.mark.parametrize(
    "url, resolved",
    [
        ("http://intranet.test/", ["10.0.0.5"]),  # RFC1918 via DNS
        ("http://corp.test/", ["172.16.4.4"]),
        ("http://home.test/", ["192.168.1.1"]),
        ("http://meta.test/", ["169.254.169.254"]),  # cloud metadata, link-local
        ("http://six.test/", ["fd12::1"]),  # fc00::/7
        ("http://mapped.test/", ["::ffff:127.0.0.1"]),  # IPv4-mapped loopback
        ("http://mixed.test/", ["93.184.216.34", "10.0.0.1"]),  # ANY private answer
        ("http://169.254.169.254/latest/meta-data/", None),  # literal, no DNS
        ("http://[::1]:80/", None),
        ("http://0.0.0.0/", None),
    ],
)
def test_private_targets_refused_without_fetch(url, resolved):
    calls: list = []
    ad = _adapter(
        environ={},
        fetch=_spy_fetch(calls),
        resolver=(lambda _h: resolved) if resolved else None,
    )
    text = _error_text(ad.handle_call("read_url", {"url": url}))
    assert "private" in text.lower() or "loopback" in text.lower()
    assert calls == []


def test_redirect_into_private_space_is_refused_at_the_hop(origin):
    calls: list = []
    # The fake origin is loopback too, so the injected resolver pretends hop 1 is
    # public and lets only the redirect target resolve into RFC1918 space.
    resolved = {"127.0.0.1": ["93.184.216.34"], "intranet.test": ["10.0.0.5"]}
    ad = _adapter(environ={}, fetch=_spy_fetch(calls), resolver=lambda h: resolved[h])
    text = _error_text(ad.handle_call("read_url", {"url": origin + "/to-private"}))
    assert "private" in text.lower() and len(calls) == 1


def test_unresolvable_host_is_truthful_error():
    calls: list = []

    def failing(_host):
        raise socket.gaierror("Name or service not known")

    text = _error_text(
        _adapter(environ={}, fetch=_spy_fetch(calls), resolver=failing).handle_call(
            "read_url", {"url": "http://does-not-resolve.invalid/"}
        )
    )
    assert "resolve" in text.lower() and calls == []


# --------------------------------------------------------------------------- #
# (g) size cap
# --------------------------------------------------------------------------- #
def test_size_cap_marks_truncated(origin):
    payload = _payload(
        _adapter().handle_call("read_url", {"url": origin + "/big", "max_bytes": 1000})
    )
    assert payload["truncated"] is True
    assert len(payload["text"].encode("utf-8")) <= 1000
    assert payload["bytes"] <= 1000  # the fetch stops reading at the cap
    full = _payload(_adapter().handle_call("read_url", {"url": origin + "/big"}))
    assert full["truncated"] is False and full["bytes"] == len(fake.BIG_BODY)


# --------------------------------------------------------------------------- #
# truthful errors: non-2xx, binary, unreachable, bad arguments
# --------------------------------------------------------------------------- #
def test_non_2xx_is_truthful_error(origin):
    text = _error_text(_adapter().handle_call("read_url", {"url": origin + "/404"}))
    assert "HTTP 404" in text and "/404" in text


def test_binary_content_type_is_refused_truthfully(origin):
    text = _error_text(_adapter().handle_call("read_url", {"url": origin + "/binary"}))
    assert "application/pdf" in text and "text" in text.lower()


def test_unreachable_origin_is_truthful_error():
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()  # nothing listens here now
    text = _error_text(
        _adapter().handle_call(
            "read_url", {"url": f"http://127.0.0.1:{port}/", "timeout_s": 2}
        )
    )
    assert "request failed" in text and "fabricated" in text


@pytest.mark.parametrize(
    "args, needle",
    [
        ({}, "'url' is required"),
        ({"url": 42}, "'url' is required"),
        ({"url": "http://example.test/", "max_bytes": 10}, "'max_bytes' must be"),
        ({"url": "http://example.test/", "max_bytes": "big"}, "'max_bytes' must be"),
        ({"url": "http://example.test/", "timeout_s": 0}, "'timeout_s' must be"),
        ({"url": "http://example.test/", "timeout_s": 999}, "'timeout_s' must be"),
    ],
)
def test_argument_validation_happens_before_any_request(args, needle):
    calls: list = []
    text = _error_text(_adapter(fetch=_spy_fetch(calls)).handle_call("read_url", args))
    assert needle in text and calls == []


def test_unknown_tool_is_rejected():
    assert "unknown" in _error_text(_adapter().handle_call("nope", {}))


# --------------------------------------------------------------------------- #
# (h) wiring: default ON, ENABLE_READ_URL=0 kill switch, hub-level listing
# --------------------------------------------------------------------------- #
def test_wired_by_default_and_kill_switch():
    assert "read_url" in [a.platform for a in adapters.wired_adapters({})]
    for flag in ("0", "false", "no", "off"):
        platforms = [
            a.platform for a in adapters.wired_adapters({"ENABLE_READ_URL": flag})
        ]
        assert "read_url" not in platforms and "selfhosted" in platforms
    for flag in ("", "1", "true"):
        assert "read_url" in [
            a.platform for a in adapters.wired_adapters({"ENABLE_READ_URL": flag})
        ]
    # The lane-gated builder keeps its historical contract.
    assert [a.platform for a in adapters.default_adapters({})] == ["selfhosted"]


def _bare_hub(tmp_path, environ):
    store = accounts.AccountStore(str(tmp_path / "acc.json"), [], environ=environ)
    rot = rotation.Rotator.from_specs([], store, environ=environ)
    return hub.SearchHub(
        [], emit=lambda _line: None, store=store, rotator=rot, environ=environ
    )


def test_hub_lists_read_url_by_default_and_hides_it_when_killed(tmp_path):
    names = {t["name"] for t in _bare_hub(tmp_path, {}).all_tools}
    assert "read_url" in names
    killed = {
        t["name"] for t in _bare_hub(tmp_path, {"ENABLE_READ_URL": "0"}).all_tools
    }
    assert "read_url" not in killed and "selfhosted_search" in killed


def test_hub_routes_read_url_in_process(tmp_path, origin):
    captured: list = []
    store = accounts.AccountStore(str(tmp_path / "acc.json"), [], environ=ALLOW)
    rot = rotation.Rotator.from_specs([], store, environ=ALLOW)
    server = hub.SearchHub(
        [],
        emit=lambda line: captured.append(json.loads(line)),
        store=store,
        rotator=rot,
        environ=ALLOW,
    )
    server.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {"name": "read_url", "arguments": {"url": origin + "/cf"}},
        }
    )
    reply = captured[0]
    assert reply["id"] == 7 and reply["result"]["isError"] is False
    payload = json.loads(reply["result"]["content"][0]["text"])
    assert payload["extractor"] == "cloudflare-markdown"
    assert server._children == {}  # never spawns a subprocess
