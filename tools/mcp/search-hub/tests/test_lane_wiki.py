#!/usr/bin/env python3
"""Unit tests for ``lane_wiki``: the keyless grounding lane (Wikipedia + Wayback +
Hacker News; platform ``grounding``, default ON, one kill switch per source).

Network-free: the ``adapters.HeaderCaller`` is the stdlib fake router in
``fake_wiki_backend`` (one fake for all four upstream hosts). Pins the request
composition per tool, the HTML-stripped Wikipedia snippets, ``lang`` validation
and subdomain swapping, the 404 / 429 / non-JSON mappings, CDX header-row parsing
(including the EMPTY-body "no captures" answer), the ``.onion`` refusal with no
request spent, the per-source kill switches, ``lanes.build_lane`` wiring, and the
truthful transport errors. Two tests use a real loopback socket: one for the
default header-aware urllib caller, one for connection-refused / read-timeout.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import HTTPServer
from urllib.parse import parse_qs, urlsplit

import pytest

HUB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HUB_DIR)
sys.path.insert(0, TESTS_DIR)

import accounts  # noqa: E402
import adapters  # noqa: E402
import hub  # noqa: E402
import lane_wiki  # noqa: E402
import lanes  # noqa: E402
import rotation  # noqa: E402

import fake_wiki_backend as fake  # noqa: E402

NOW = datetime(2026, 9, 2, 7, 15, 0, tzinfo=timezone.utc)
FETCHED_AT = "2026-09-02T07:15:00Z"
ALL_TOOLS = [
    "wikipedia_search",
    "wikipedia_summary",
    "wayback_available",
    "wayback_snapshots",
    "hn_search",
]


def _adapter(caller=None, **overrides):
    kwargs = dict(
        wikipedia_url=lane_wiki.DEFAULT_WIKIPEDIA_URL,
        wayback_url=lane_wiki.DEFAULT_WAYBACK_URL,
        wayback_cdx_url=lane_wiki.DEFAULT_WAYBACK_CDX_URL,
        hn_url=lane_wiki.DEFAULT_HN_URL,
        caller=caller or fake.fake_caller,
        now=lambda: NOW,
    )
    kwargs.update(overrides)
    return lane_wiki.GroundingAdapter(**kwargs)


def _payload(result: dict) -> dict:
    assert result["isError"] is False, result
    return json.loads(result["content"][0]["text"])


def _error_text(result: dict) -> str:
    assert result["isError"] is True, result
    text = result["content"][0]["text"]
    assert text.startswith("[search-hub:grounding] ")
    return text


def _spy(captured: list, inner=None):
    inner = inner or fake.fake_caller

    def caller(method, url, body, headers, timeout):
        captured.append(
            {
                "method": method,
                "url": url,
                "body": body,
                "headers": headers,
                "timeout": timeout,
            }
        )
        return inner(method, url, body, headers, timeout)

    return caller


def _split(url: str) -> tuple[str, str, dict]:
    parts = urlsplit(url)
    return (
        parts.hostname or "",
        parts.path,
        {k: v[0] for k, v in parse_qs(parts.query, keep_blank_values=True).items()},
    )


def _dead(_m, _u, _b, _h, _t):
    return 0, None, "request failed: <urlopen error [Errno 111] Connection refused>", {}


@pytest.fixture(autouse=True)
def _reset_fake():
    fake.reset()
    yield
    fake.reset()


# --------------------------------------------------------------------------- #
# surface + import hygiene
# --------------------------------------------------------------------------- #
def test_tool_surface_and_honest_descriptions():
    ad = _adapter()
    assert ad.platform == "grounding"
    assert ad.tool_names() == ALL_TOOLS
    defs = {d["name"]: d for d in ad.tool_defs()}
    for name, d in defs.items():
        text = d["description"].lower()
        assert "keyless" in text, name
        assert "fabricated" in text, name
    assert "disambiguation" in defs["wikipedia_summary"]["description"].lower()
    assert ".onion" in defs["wayback_available"]["description"]
    assert defs["wikipedia_search"]["inputSchema"]["required"] == ["query"]
    assert (
        defs["wikipedia_search"]["inputSchema"]["properties"]["limit"]["maximum"] == 20
    )
    assert defs["wikipedia_summary"]["inputSchema"]["required"] == ["title"]
    assert defs["wayback_available"]["inputSchema"]["required"] == ["url"]
    assert (
        defs["wayback_snapshots"]["inputSchema"]["properties"]["limit"]["maximum"] == 50
    )
    assert defs["hn_search"]["inputSchema"]["properties"]["limit"]["maximum"] == 50
    assert defs["hn_search"]["inputSchema"]["properties"]["sort"]["enum"] == [
        "relevance",
        "date",
    ]
    assert lane_wiki.TOOL_SOURCES == {
        "wikipedia_search": "wikipedia",
        "wikipedia_summary": "wikipedia",
        "wayback_available": "wayback",
        "wayback_snapshots": "wayback",
        "hn_search": "hn",
    }


def test_module_is_stdlib_only_plus_hub_siblings():
    # Import-safe lane contract (lanes.py): stdlib + the hub's own modules, no
    # third-party import, no network at import time.
    imported = {
        v.__name__.split(".")[0]
        for v in vars(lane_wiki).values()
        if isinstance(v, type(sys))
    }
    allowed = set(sys.stdlib_module_names) | {"adapters", "onions"}
    assert imported <= allowed, imported - allowed


def test_capabilities_report_sources_states_and_public_api():
    report = _adapter().capabilities()
    assert report["provider"] == "grounding"
    assert report["keyless"] is True
    assert report["self_hosted"] is False  # public APIs, no daemon of ours
    assert report["probed"] is False
    assert report["sources"] == ["hn", "wayback", "wikipedia"]
    assert report["base_urls"] == {
        "wikipedia": "https://en.wikipedia.org",
        "wayback": "https://archive.org",
        "wayback_cdx": "https://web.archive.org",
        "hn": "https://hn.algolia.com",
    }
    assert report["kill_switches"] == {
        "wikipedia": "ENABLE_WIKIPEDIA",
        "wayback": "ENABLE_WAYBACK",
        "hn": "ENABLE_HN",
    }
    assert [t["tool"] for t in report["tools"]] == ALL_TOOLS
    assert all(t["state"] == "native" for t in report["tools"])
    assert all(t["realized_by"] == "native" for t in report["tools"])
    assert [t["source"] for t in report["tools"]] == [
        "wikipedia",
        "wikipedia",
        "wayback",
        "wayback",
        "hn",
    ]


def test_probe_hits_each_source_once_and_upgrades_to_probed():
    captured: list = []
    ad = _adapter(caller=_spy(captured))
    reachable, note = ad.probe()
    assert reachable, note
    hosts = sorted(_split(c["url"])[0] for c in captured)
    assert hosts == ["archive.org", "en.wikipedia.org", "hn.algolia.com"]
    assert all(c["timeout"] == adapters.PROBE_TIMEOUT for c in captured)
    assert "wikipedia" in note and "wayback" in note and "hn" in note
    probed = ad.capabilities(probe=True)
    assert probed["probed"] is True
    assert all(t["state"] == "probed" for t in probed["tools"])


def test_probe_marks_only_the_dead_source_absent():
    def caller(method, url, body, headers, timeout):
        if "hn.algolia.com" in url:
            return _dead(method, url, body, headers, timeout)
        return fake.fake_caller(method, url, body, headers, timeout)

    ad = _adapter(caller=caller)
    reachable, note = ad.probe()
    assert reachable is False
    assert "hn" in note and "Connection refused" in note
    states = {t["tool"]: t["state"] for t in ad.capabilities(probe=True)["tools"]}
    assert states["hn_search"] == "absent"
    assert states["wikipedia_search"] == "probed"
    assert states["wayback_snapshots"] == "probed"


# --------------------------------------------------------------------------- #
# wikipedia_search
# --------------------------------------------------------------------------- #
def test_wikipedia_search_composes_request_and_strips_html_snippets():
    captured: list = []
    result = _adapter(caller=_spy(captured)).handle_call(
        "wikipedia_search", {"query": "model context protocol", "limit": 2}
    )
    assert len(captured) == 1
    host, path, params = _split(captured[0]["url"])
    assert captured[0]["method"] == "GET" and captured[0]["body"] is None
    assert captured[0]["timeout"] == lane_wiki.GROUNDING_TIMEOUT == 15.0
    assert host == "en.wikipedia.org" and path == "/w/api.php"
    assert params == {
        "action": "query",
        "list": "search",
        "format": "json",
        "srsearch": "model context protocol",
        "srlimit": "2",
    }
    sent = captured[0]["headers"]
    assert sent["User-Agent"] == lane_wiki.USER_AGENT
    assert "search-hub" in sent["User-Agent"] and "github.com" in sent["User-Agent"]
    assert sent["Accept"] == "application/json"
    payload = _payload(result)
    assert payload["tool"] == "wikipedia_search"
    assert payload["source"] == "wikipedia"
    assert payload["lang"] == "en"
    assert payload["query"] == "model context protocol"
    assert payload["total_hits"] == 4054
    assert payload["suggestion"] == "model content protocol"
    assert payload["count"] == 2 and len(payload["results"]) == 2
    first, second = payload["results"]
    assert set(first) == {"title", "pageid", "snippet", "url"}
    assert first["title"] == "Model Context Protocol"
    assert first["pageid"] == 79706999
    assert first["url"] == "https://en.wikipedia.org/wiki/Model_Context_Protocol"
    # <span class="searchmatch"> markup gone, entities decoded, whitespace sane.
    assert first["snippet"] == (
        "The Model Context Protocol (MCP) is an open standard & open-source "
        "framework introduced by Anthropic"
    )
    assert "<" not in second["snippet"] and "&" not in second["snippet"]
    assert "Figma's Model Context Protocol" in second["snippet"]
    assert '"connecting"' in second["snippet"]
    assert second["url"] == "https://en.wikipedia.org/wiki/OpenAI_Codex_(AI_agent)"
    assert payload["fetched_at"] == FETCHED_AT


def test_wikipedia_search_default_limit_is_10():
    captured: list = []
    _adapter(caller=_spy(captured)).handle_call("wikipedia_search", {"query": "x"})
    assert _split(captured[0]["url"])[2]["srlimit"] == "10"


@pytest.mark.parametrize(
    "lang, host",
    [
        ("de", "de.wikipedia.org"),
        ("zh-yue", "zh-yue.wikipedia.org"),
        ("ceb", "ceb.wikipedia.org"),
    ],
)
def test_wikipedia_search_lang_swaps_only_the_subdomain(lang, host):
    captured: list = []
    payload = _payload(
        _adapter(caller=_spy(captured)).handle_call(
            "wikipedia_search", {"query": "Berlin", "lang": lang}
        )
    )
    assert _split(captured[0]["url"])[0] == host
    assert payload["lang"] == lang
    assert payload["results"][0]["url"].startswith(f"https://{host}/wiki/")


@pytest.mark.parametrize(
    "lang",
    [
        "EN",
        "e",
        "abcd",
        "en_US",
        "en.wikipedia.org",
        "../x",
        "de;rm -rf",
        "e n",
        "en-",
        "-en",
        "1a",
    ],
)
def test_wikipedia_lang_validation_refuses_without_request(lang):
    captured: list = []
    ad = _adapter(caller=_spy(captured))
    for tool, args in (
        ("wikipedia_search", {"query": "x", "lang": lang}),
        ("wikipedia_summary", {"title": "x", "lang": lang}),
    ):
        text = _error_text(ad.handle_call(tool, args))
        assert "'lang'" in text and "[a-z]{2,3}" in text
    assert captured == []


def test_wikipedia_lang_on_a_custom_host_is_refused_unless_default():
    # A loopback fake (or any non-*.wikipedia.org mirror) has no language
    # subdomain to swap: the default lang passes through, another is refused.
    captured: list = []
    ad = _adapter(caller=_spy(captured), wikipedia_url="http://127.0.0.1:9/")
    ok = _payload(ad.handle_call("wikipedia_search", {"query": "x", "lang": "en"}))
    assert ok["lang"] == "en"
    assert captured[0]["url"].startswith("http://127.0.0.1:9/w/api.php?")
    text = _error_text(ad.handle_call("wikipedia_search", {"query": "x", "lang": "de"}))
    assert "127.0.0.1" in text and "WIKIPEDIA_API_URL" in text and "de" in text
    assert len(captured) == 1  # the refusal spent no request


def test_wikipedia_host_for_is_pure_and_keeps_scheme_and_port():
    f = lane_wiki.wikipedia_host_for
    assert f("https://en.wikipedia.org", "de") == "https://de.wikipedia.org"
    assert f("https://en.wikipedia.org", "en") == "https://en.wikipedia.org"
    assert f("https://en.m.wikipedia.org", "fr") == "https://fr.m.wikipedia.org"
    assert (
        f("http://en.wikipedia.org:8080/", "zh-yue")
        == "http://zh-yue.wikipedia.org:8080"
    )
    assert f("http://127.0.0.1:9", "en") == "http://127.0.0.1:9"
    with pytest.raises(ValueError):
        f("http://127.0.0.1:9", "de")
    with pytest.raises(ValueError):
        f("https://en.wikipedia.org", "EN")


@pytest.mark.parametrize(
    "args, needle",
    [
        ({}, "'query' is required"),
        ({"query": "   "}, "'query' is required"),
        ({"query": "a\nb"}, "control characters"),
        ({"query": "x", "limit": 0}, "'limit' must be"),
        ({"query": "x", "limit": 21}, "'limit' must be"),
        ({"query": "x", "limit": "many"}, "'limit' must be"),
        ({"query": "x", "limit": True}, "'limit' must be"),
        ({"query": "q" * 301}, "300"),
    ],
)
def test_wikipedia_search_validates_arguments_before_any_request(args, needle):
    captured: list = []
    text = _error_text(
        _adapter(caller=_spy(captured)).handle_call("wikipedia_search", args)
    )
    assert needle in text
    assert captured == []


def test_wikipedia_search_api_error_object_is_a_truthful_error():
    # MediaWiki reports a bad request as HTTP 200 + {"error": {...}}: that must
    # never be shown as "0 results".
    text = _error_text(
        _adapter().handle_call("wikipedia_search", {"query": "apierror"})
    )
    assert "missingparam" in text and "srsearch" in text
    assert "results" not in text.lower().replace("no results are fabricated", "")


def test_wikipedia_search_zero_hits_is_an_honest_empty_success():
    payload = _payload(_adapter().handle_call("wikipedia_search", {"query": "nohits"}))
    assert payload["count"] == 0 and payload["results"] == []
    assert payload["total_hits"] == 0


def test_wikipedia_search_429_is_rate_limited_error_with_retry_after():
    text = _error_text(
        _adapter().handle_call("wikipedia_search", {"query": "ratelimited"})
    )
    assert "HTTP 429" in text and "rate limit" in text.lower()
    assert "retry-after 5" in text.lower()
    assert "fabricated" in text


# --------------------------------------------------------------------------- #
# wikipedia_summary
# --------------------------------------------------------------------------- #
def test_wikipedia_summary_standard_page_maps_fields():
    captured: list = []
    result = _adapter(caller=_spy(captured)).handle_call(
        "wikipedia_summary", {"title": "Model Context Protocol"}
    )
    host, path, params = _split(captured[0]["url"])
    assert host == "en.wikipedia.org"
    assert path == "/api/rest_v1/page/summary/Model_Context_Protocol"  # spaces -> _
    assert params == {}
    payload = _payload(result)
    assert payload["tool"] == "wikipedia_summary"
    assert payload["source"] == "wikipedia" and payload["lang"] == "en"
    assert payload["title"] == "Model Context Protocol"
    assert payload["pageid"] == 79706999
    assert payload["type"] == "standard"
    assert payload["disambiguation"] is False
    assert (
        payload["description"]
        == "Protocol for communicating between LLMs and applications"
    )
    assert payload["extract"].startswith("The Model Context Protocol (MCP)")
    assert payload["url"] == "https://en.wikipedia.org/wiki/Model_Context_Protocol"
    assert payload["thumbnail"] == {
        "source": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/fe/MCP.png",
        "width": 330,
        "height": 330,
    }
    assert payload["fetched_at"] == FETCHED_AT
    assert "note" not in payload


def test_wikipedia_summary_encodes_slashes_and_keeps_parentheses():
    captured: list = []
    ad = _adapter(caller=_spy(captured))
    ad.handle_call("wikipedia_summary", {"title": "AC/DC"})
    ad.handle_call("wikipedia_summary", {"title": "Mercury (planet)", "lang": "de"})
    assert captured[0]["url"].endswith("/api/rest_v1/page/summary/AC%2FDC")
    assert captured[1]["url"] == (
        "https://de.wikipedia.org/api/rest_v1/page/summary/Mercury_(planet)"
    )


def test_wikipedia_summary_disambiguation_is_flagged_truthfully():
    payload = _payload(
        _adapter().handle_call("wikipedia_summary", {"title": "Mercury"})
    )
    assert payload["type"] == "disambiguation"
    assert payload["disambiguation"] is True
    assert "disambiguation" in payload["note"].lower()
    assert "wikipedia_search" in payload["note"]  # the honest next step
    assert "thumbnail" not in payload  # none upstream -> none fabricated
    assert payload["extract"].startswith("Mercury most commonly refers to")


def test_wikipedia_summary_404_is_no_such_page_error():
    text = _error_text(
        _adapter().handle_call("wikipedia_summary", {"title": "Zzqx No Such Page"})
    )
    assert "HTTP 404" in text and "no such page" in text.lower()
    assert "Zzqx No Such Page" in text
    assert "wikipedia_search" in text  # points at the search tool, fabricates nothing
    assert "fabricated" in text


def test_wikipedia_summary_429_is_rate_limited_error():
    text = _error_text(
        _adapter().handle_call("wikipedia_summary", {"title": "Ratelimited_Page"})
    )
    assert (
        "HTTP 429" in text
        and "rate limit" in text.lower()
        and "retry-after 7" in text.lower()
    )


def test_wikipedia_summary_503_html_body_is_truthful_error_with_readable_detail():
    text = _error_text(
        _adapter().handle_call("wikipedia_summary", {"title": "Server_Error"})
    )
    assert "HTTP 503" in text
    assert "Temporarily Offline" in text  # the HTML page's text, tags stripped
    assert "<html>" not in text and "<p>" not in text


@pytest.mark.parametrize(
    "args, needle",
    [
        ({}, "'title' is required"),
        ({"title": ""}, "'title' is required"),
        ({"title": "a\x00b"}, "control characters"),
        ({"title": "t" * 256}, "255"),
    ],
)
def test_wikipedia_summary_validates_title_before_any_request(args, needle):
    captured: list = []
    text = _error_text(
        _adapter(caller=_spy(captured)).handle_call("wikipedia_summary", args)
    )
    assert needle in text
    assert captured == []


# --------------------------------------------------------------------------- #
# wayback_available
# --------------------------------------------------------------------------- #
def test_wayback_available_maps_closest_snapshot():
    captured: list = []
    result = _adapter(caller=_spy(captured)).handle_call(
        "wayback_available", {"url": "https://example.com/page"}
    )
    host, path, params = _split(captured[0]["url"])
    assert host == "archive.org" and path == "/wayback/available"
    assert params == {"url": "https://example.com/page"}
    assert captured[0]["headers"]["User-Agent"] == lane_wiki.USER_AGENT
    payload = _payload(result)
    assert payload == {
        "tool": "wayback_available",
        "source": "wayback",
        "url": "https://example.com/page",
        "requested_timestamp": None,
        "available": True,
        "snapshot_url": "http://web.archive.org/web/20260902040541/https://example.com/",
        "timestamp": "20260902040541",
        "status": "200",
        "fetched_at": FETCHED_AT,
    }


def test_wayback_available_sends_and_echoes_timestamp():
    captured: list = []
    payload = _payload(
        _adapter(caller=_spy(captured)).handle_call(
            "wayback_available", {"url": "example.com", "timestamp": "20200101"}
        )
    )
    assert _split(captured[0]["url"])[2] == {
        "url": "example.com",
        "timestamp": "20200101",
    }
    assert payload["requested_timestamp"] == "20200101"
    assert payload["timestamp"] == "20200101000000"
    assert payload["available"] is True


def test_wayback_available_no_capture_is_truthful_false_not_an_error():
    payload = _payload(
        _adapter().handle_call(
            "wayback_available", {"url": "https://never-archived.example/x"}
        )
    )
    assert payload["available"] is False
    assert payload["snapshot_url"] is None and payload["timestamp"] is None
    assert payload["status"] is None
    assert "no capture" in payload["note"].lower()


@pytest.mark.parametrize(
    "args, needle",
    [
        ({}, "'url' is required"),
        ({"url": "  "}, "'url' is required"),
        ({"url": "https://a.example/\n"}, "control characters"),
        ({"url": "example.com", "timestamp": "2020-01-01"}, "'timestamp'"),
        ({"url": "example.com", "timestamp": "202"}, "'timestamp'"),
        ({"url": "example.com", "timestamp": "202001012359591"}, "'timestamp'"),
    ],
)
def test_wayback_available_validates_before_any_request(args, needle):
    captured: list = []
    text = _error_text(
        _adapter(caller=_spy(captured)).handle_call("wayback_available", args)
    )
    assert needle in text
    assert captured == []


def test_wayback_available_503_html_is_truthful_error():
    text = _error_text(
        _adapter().handle_call("wayback_available", {"url": "https://boom.example/"})
    )
    assert "HTTP 503" in text and "Temporarily Offline" in text and "fabricated" in text


@pytest.mark.parametrize(
    "url",
    [
        "http://abcdefghijklmnop.onion/page",
        "https://juhanurmihxlp77nkq76byazcldy2hlmovfu2epvl5ankdibsot4csyd.ONION./",
        "abcdefghijklmnop.onion",
        "abcdefghijklmnop.onion/some/path",
        "abcdefghijklmnop.onion:8080/x",
        # A replay URL whose archived target is an onion service: the Wayback
        # Machine would render it, so it is refused too (the outer host is clearnet).
        "https://web.archive.org/web/20200101000000/http://abcdefghijklmnop.onion/",
    ],
)
@pytest.mark.parametrize("tool", ["wayback_available", "wayback_snapshots"])
def test_wayback_refuses_onion_urls_without_any_request(tool, url):
    captured: list = []
    text = _error_text(_adapter(caller=_spy(captured)).handle_call(tool, {"url": url}))
    assert ".onion" in text and "refused" in text.lower()
    assert "onions-lane-envelope" in text
    assert captured == []


@pytest.mark.parametrize("tool", ["wayback_available", "wayback_snapshots"])
def test_wayback_clearnet_host_with_an_onion_label_is_not_refused(tool):
    # "foo.onion.example" is an ordinary clearnet host, not an onion service.
    captured: list = []
    result = _adapter(caller=_spy(captured)).handle_call(
        tool, {"url": "https://foo.onion.example/page"}
    )
    assert not result.get("isError"), result
    assert len(captured) == 1


# --------------------------------------------------------------------------- #
# wayback_snapshots (CDX)
# --------------------------------------------------------------------------- #
def test_wayback_snapshots_composes_cdx_request_and_parses_header_row():
    captured: list = []
    result = _adapter(caller=_spy(captured)).handle_call(
        "wayback_snapshots", {"url": "example.com", "limit": 3}
    )
    host, path, params = _split(captured[0]["url"])
    assert host == "web.archive.org" and path == "/cdx/search/cdx"
    assert params == {
        "url": "example.com",
        "output": "json",
        "limit": "3",
        "fl": "timestamp,original,statuscode,mimetype",
        "filter": "statuscode:200",
    }
    payload = _payload(result)
    assert payload["tool"] == "wayback_snapshots" and payload["source"] == "wayback"
    assert payload["url"] == "example.com"
    assert payload["from_year"] is None and payload["to_year"] is None
    assert payload["limit"] == 3
    assert payload["count"] == 3
    # The header row is consumed, not returned as a "snapshot".
    assert payload["snapshots"][0] == {
        "timestamp": "20150315120000",
        "original": "http://example.com/",
        "statuscode": "200",
        "mimetype": "text/html",
        "snapshot_url": "https://web.archive.org/web/20150315120000/http://example.com/",
    }
    assert [s["timestamp"] for s in payload["snapshots"]] == [
        "20150315120000",
        "20200101231047",
        "20260902040541",
    ]
    assert payload["fetched_at"] == FETCHED_AT


def test_wayback_snapshots_year_window_is_sent_and_echoed():
    captured: list = []
    payload = _payload(
        _adapter(caller=_spy(captured)).handle_call(
            "wayback_snapshots",
            {"url": "example.com", "from_year": "2016", "to_year": "2021"},
        )
    )
    params = _split(captured[0]["url"])[2]
    assert params["from"] == "2016" and params["to"] == "2021"
    assert params["limit"] == "20"  # the default
    assert payload["from_year"] == "2016" and payload["to_year"] == "2021"
    assert [s["timestamp"] for s in payload["snapshots"]] == ["20200101231047"]


def test_wayback_snapshots_header_order_comes_from_the_server_not_assumed():
    def caller(method, url, body, headers, timeout):
        rows = [
            ["original", "timestamp", "mimetype", "statuscode"],
            ["https://x.example/", "20210101000000", "text/html", "200"],
        ]
        return 200, rows, json.dumps(rows), {}

    payload = _payload(
        _adapter(caller=caller).handle_call("wayback_snapshots", {"url": "x.example"})
    )
    assert payload["snapshots"] == [
        {
            "timestamp": "20210101000000",
            "original": "https://x.example/",
            "statuscode": "200",
            "mimetype": "text/html",
            "snapshot_url": "https://web.archive.org/web/20210101000000/https://x.example/",
        }
    ]


@pytest.mark.parametrize(
    "url", ["never-archived.example/x", "never-archived-plain.example/x"]
)
def test_wayback_snapshots_empty_answer_means_no_captures_not_an_error(url):
    # JSON mode says "no captures" with the body [] (measured live 2026-09-02);
    # the plain mode says it with an EMPTY body. Both are zero captures, no error.
    payload = _payload(_adapter().handle_call("wayback_snapshots", {"url": url}))
    assert payload["count"] == 0 and payload["snapshots"] == []
    assert "no captures" in payload["note"].lower()


def test_wayback_snapshots_json_empty_list_is_zero_captures():
    captured: list = []

    def empty_list(method, url, body, headers, timeout):
        captured.append(url)
        return 200, [], "[]", {"content-type": "application/json"}

    payload = _payload(
        _adapter(caller=empty_list).handle_call(
            "wayback_snapshots", {"url": "x.example"}
        )
    )
    assert len(captured) == 1
    assert payload["count"] == 0 and payload["snapshots"] == []
    assert lane_wiki.parse_cdx_rows([]) == []


def test_wayback_snapshots_offline_503_html_is_truthful_error():
    text = _error_text(
        _adapter().handle_call("wayback_snapshots", {"url": "offline.example"})
    )
    assert "HTTP 503" in text and "Temporarily Offline" in text
    assert "web.archive.org" in text and "fabricated" in text
    # The live page ships a <style> block: its CSS must not be relayed as words.
    assert "font-size" not in text and "{" not in text
    assert "Internet Archive services are temporarily offline" in text


def test_wayback_snapshots_unexpected_shapes_are_errors_not_empty_successes():
    def dict_body(method, url, body, headers, timeout):
        return 200, {"unexpected": True}, '{"unexpected": true}', {}

    def bad_header(method, url, body, headers, timeout):
        rows = [["foo", "bar"], ["1", "2"]]
        return 200, rows, json.dumps(rows), {}

    def html_200(method, url, body, headers, timeout):
        return 200, None, "<html>captcha</html>", {"content-type": "text/html"}

    for caller in (dict_body, bad_header, html_200):
        text = _error_text(
            _adapter(caller=caller).handle_call(
                "wayback_snapshots", {"url": "x.example"}
            )
        )
        assert "fabricated" in text
        assert "snapshots" not in text.lower().replace("wayback_snapshots", "")


@pytest.mark.parametrize(
    "args, needle",
    [
        ({}, "'url' is required"),
        ({"url": "x.example", "limit": 0}, "'limit' must be"),
        ({"url": "x.example", "limit": 51}, "'limit' must be"),
        ({"url": "x.example", "from_year": "20xx"}, "'from_year'"),
        ({"url": "x.example", "to_year": "abcd"}, "'to_year'"),
        ({"url": "x.example", "from_year": "202"}, "'from_year'"),
        ({"url": "x.example", "from_year": "2021", "to_year": "2019"}, "after"),
    ],
)
def test_wayback_snapshots_validates_before_any_request(args, needle):
    captured: list = []
    text = _error_text(
        _adapter(caller=_spy(captured)).handle_call("wayback_snapshots", args)
    )
    assert needle in text
    assert captured == []


# --------------------------------------------------------------------------- #
# hn_search
# --------------------------------------------------------------------------- #
def test_hn_search_relevance_route_and_compact_hits():
    captured: list = []
    result = _adapter(caller=_spy(captured)).handle_call(
        "hn_search", {"query": "model context protocol", "limit": 3}
    )
    host, path, params = _split(captured[0]["url"])
    assert host == "hn.algolia.com" and path == "/api/v1/search"
    assert params == {
        "query": "model context protocol",
        "tags": "story",
        "hitsPerPage": "3",
    }
    assert captured[0]["headers"]["User-Agent"] == lane_wiki.USER_AGENT
    payload = _payload(result)
    assert payload["tool"] == "hn_search" and payload["source"] == "hn"
    assert payload["query"] == "model context protocol"
    assert payload["tags"] == "story" and payload["sort"] == "relevance"
    assert payload["total_hits"] == 660 and payload["pages"] == 330
    assert payload["count"] == 3
    hit = payload["hits"][0]
    assert hit == {
        "title": "Model Context Protocol",
        "url": "https://www.anthropic.com/news/model-context-protocol",
        "points": 872,
        "num_comments": 258,
        "author": "benocodes",
        "created_at": "2024-11-25T16:14:22Z",
        "objectID": "42237424",
        "hn_url": "https://news.ycombinator.com/item?id=42237424",
    }
    assert payload["hits"][1]["url"] is None  # an Ask HN has no external URL
    assert payload["fetched_at"] == FETCHED_AT


def test_hn_search_date_sort_uses_search_by_date_route():
    captured: list = []
    payload = _payload(
        _adapter(caller=_spy(captured)).handle_call(
            "hn_search", {"query": "mcp", "sort": "date", "tags": "show_hn", "limit": 2}
        )
    )
    host, path, params = _split(captured[0]["url"])
    assert path == "/api/v1/search_by_date"
    assert params == {"query": "mcp", "tags": "show_hn", "hitsPerPage": "2"}
    assert payload["sort"] == "date" and payload["tags"] == "show_hn"
    assert [h["created_at"] for h in payload["hits"]] == [
        "2026-09-02T06:28:48Z",
        "2025-03-01T10:00:00Z",
    ]


def test_hn_search_default_limit_is_20():
    captured: list = []
    _adapter(caller=_spy(captured)).handle_call("hn_search", {"query": "x"})
    assert _split(captured[0]["url"])[2]["hitsPerPage"] == "20"


def test_hn_search_comment_hits_carry_story_context():
    payload = _payload(
        _adapter().handle_call("hn_search", {"query": "llvm", "tags": "comment"})
    )
    hit = payload["hits"][0]
    assert hit["title"] is None and hit["url"] is None and hit["points"] is None
    assert hit["author"] == "eslaught"
    assert hit["hn_url"] == "https://news.ycombinator.com/item?id=9999959"
    assert hit["story_title"] == "LLVM for Grad Students"
    assert hit["story_url"] == "http://adriansampson.net/blog/llvm.html"
    assert hit["comment_text"].startswith("The issue is not having")


@pytest.mark.parametrize(
    "tags",
    [
        "story",
        "comment",
        "ask_hn",
        "show_hn",
        "front_page",
        "poll",
        "pollopt",
        "author_pg",
        "story_42237424",
        "story,author_pg",
        "(story,poll)",
        "comment,story_42237424",
    ],
)
def test_hn_search_accepts_documented_tag_grammar(tags):
    captured: list = []
    _payload(
        _adapter(caller=_spy(captured)).handle_call(
            "hn_search", {"query": "x", "tags": tags}
        )
    )
    assert _split(captured[0]["url"])[2]["tags"] == tags


@pytest.mark.parametrize(
    "args, needle",
    [
        ({}, "'query' is required"),
        ({"query": ""}, "'query' is required"),
        ({"query": "a\rb"}, "control characters"),
        ({"query": "x", "tags": "bogus_tag"}, "'tags'"),
        ({"query": "x", "tags": "story;drop"}, "'tags'"),
        ({"query": "x", "tags": "(story"}, "'tags'"),
        ({"query": "x", "sort": "points"}, "'sort' must be"),
        ({"query": "x", "limit": 0}, "'limit' must be"),
        ({"query": "x", "limit": 51}, "'limit' must be"),
        ({"query": "q" * 513}, "512"),
    ],
)
def test_hn_search_validates_before_any_request(args, needle):
    # A bogus tag is validated locally because Algolia answers HTTP 200 with zero
    # hits for it (measured 2026-09-02), which would look like an honest "nothing".
    captured: list = []
    text = _error_text(_adapter(caller=_spy(captured)).handle_call("hn_search", args))
    assert needle in text
    assert captured == []


def test_hn_search_zero_hits_is_an_honest_empty_success():
    payload = _payload(_adapter().handle_call("hn_search", {"query": "nohits"}))
    assert (
        payload["count"] == 0 and payload["hits"] == [] and payload["total_hits"] == 0
    )


def test_hn_search_429_is_rate_limited_error():
    text = _error_text(_adapter().handle_call("hn_search", {"query": "ratelimited"}))
    assert (
        "HTTP 429" in text
        and "rate limit" in text.lower()
        and "Too many requests" in text
    )


# --------------------------------------------------------------------------- #
# cross-cutting honesty: source + fetched_at, transport errors, non-JSON
# --------------------------------------------------------------------------- #
HAPPY_CALLS = [
    ("wikipedia_search", {"query": "mcp"}),
    ("wikipedia_summary", {"title": "Mercury"}),
    ("wayback_available", {"url": "example.com"}),
    ("wayback_snapshots", {"url": "example.com"}),
    ("hn_search", {"query": "mcp"}),
]


@pytest.mark.parametrize("tool, args", HAPPY_CALLS)
def test_every_success_carries_source_and_fetched_at(tool, args):
    payload = _payload(_adapter().handle_call(tool, args))
    assert payload["tool"] == tool
    assert payload["source"] == lane_wiki.TOOL_SOURCES[tool]
    assert payload["fetched_at"] == FETCHED_AT


def test_fetched_at_defaults_to_now_utc_iso_z():
    ad = lane_wiki.GroundingAdapter(caller=fake.fake_caller)
    before = datetime.now(timezone.utc).replace(microsecond=0)
    stamp = _payload(ad.handle_call("hn_search", {"query": "mcp"}))["fetched_at"]
    parsed = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    assert before <= parsed <= datetime.now(timezone.utc)


@pytest.mark.parametrize("tool, args", HAPPY_CALLS)
def test_transport_failure_is_a_truthful_error(tool, args):
    text = _error_text(_adapter(caller=_dead).handle_call(tool, args))
    assert "not reachable" in text and "Connection refused" in text
    assert "fabricated" in text
    assert lane_wiki.TOOL_SOURCES[tool] in text.lower()


@pytest.mark.parametrize("tool, args", HAPPY_CALLS[:3] + HAPPY_CALLS[4:])
def test_non_json_200_is_an_error_not_an_empty_success(tool, args):
    def caller(method, url, body, headers, timeout):
        return 200, None, "<html>proxy login</html>", {"content-type": "text/html"}

    text = _error_text(_adapter(caller=caller).handle_call(tool, args))
    assert "HTTP 200" in text and "not JSON" in text and "fabricated" in text


@pytest.mark.parametrize("tool, args", HAPPY_CALLS)
def test_unexpected_500_relays_status_and_detail(tool, args):
    def caller(method, url, body, headers, timeout):
        return (
            500,
            {"message": "upstream exploded"},
            '{"message": "upstream exploded"}',
            {},
        )

    text = _error_text(_adapter(caller=caller).handle_call(tool, args))
    assert "HTTP 500" in text and "upstream exploded" in text and "fabricated" in text


def test_unknown_tool_is_rejected():
    assert "unknown grounding tool" in _error_text(_adapter().handle_call("nope", {}))


def test_strip_html_is_pure():
    f = lane_wiki.strip_html
    assert f('a <span class="x">b</span> &amp; c &#039;d&#039;') == "a b & c 'd'"
    assert f("  many\n\n  spaces\t here ") == "many spaces here"
    assert f("") == "" and f(None) == ""
    assert f("<b>bold</b><br>break") == "bold break"
    # <style>/<script> subtrees are dropped whole (the CDX 503 page ships CSS).
    assert f("<style>p{font-size:24px;}</style><h1>Offline</h1>") == "Offline"
    assert f("<script type='x'>var a=1;</script>text") == "text"
    assert f("<STYLE>x</STYLE>y</b>") == "y"
    # An HN comment body: entities decoded, <p> becomes a break.
    assert (
        f("Remote: Yes (Global &#x2F; EOR)<p>Next") == "Remote: Yes (Global / EOR) Next"
    )


# --------------------------------------------------------------------------- #
# build(environ): default ON, per-source kill switches, env URLs, registry
# --------------------------------------------------------------------------- #
def test_build_returns_one_grounding_adapter_with_all_five_tools():
    built = lane_wiki.build({})
    assert len(built) == 1
    ad = built[0]
    assert isinstance(ad, lane_wiki.GroundingAdapter)
    assert isinstance(ad, adapters.SelfHostedAdapter)
    assert ad.platform == "grounding"
    assert ad.tool_names() == ALL_TOOLS
    assert ad.sources == {
        "wikipedia": "https://en.wikipedia.org",
        "wayback": "https://archive.org",
        "hn": "https://hn.algolia.com",
    }
    assert ad.wayback_cdx_url == "https://web.archive.org"


@pytest.mark.parametrize(
    "env, expected",
    [
        (
            {"ENABLE_WIKIPEDIA": "0"},
            ["wayback_available", "wayback_snapshots", "hn_search"],
        ),
        (
            {"ENABLE_WAYBACK": "false"},
            ["wikipedia_search", "wikipedia_summary", "hn_search"],
        ),
        (
            {"ENABLE_HN": " OFF "},
            [
                "wikipedia_search",
                "wikipedia_summary",
                "wayback_available",
                "wayback_snapshots",
            ],
        ),
        (
            {"ENABLE_WIKIPEDIA": "no", "ENABLE_HN": "off"},
            ["wayback_available", "wayback_snapshots"],
        ),
    ],
)
def test_kill_switches_drop_one_source_each(env, expected):
    built = lane_wiki.build(env)
    assert len(built) == 1 and built[0].platform == "grounding"
    assert built[0].tool_names() == expected
    report = built[0].capabilities()
    assert sorted(report["sources"]) == sorted(
        {lane_wiki.TOOL_SOURCES[t] for t in expected}
    )


@pytest.mark.parametrize("flag", ["", "1", "true", "yes", "on"])
def test_truthy_or_empty_flags_keep_every_source(flag):
    env = {"ENABLE_WIKIPEDIA": flag, "ENABLE_WAYBACK": flag, "ENABLE_HN": flag}
    assert lane_wiki.build(env)[0].tool_names() == ALL_TOOLS


def test_all_three_killed_builds_nothing():
    env = {"ENABLE_WIKIPEDIA": "0", "ENABLE_WAYBACK": "0", "ENABLE_HN": "0"}
    assert lane_wiki.build(env) == []
    assert lanes.build_lane("lane_wiki", env) == []
    built, degraded = lanes.extra_adapters(env, modules=("lane_wiki",))
    assert built == [] and degraded == {}  # "not now", not degraded


def test_env_urls_are_read_and_trailing_slashes_stripped():
    ad = lane_wiki.build(
        {
            "WIKIPEDIA_API_URL": "http://127.0.0.1:9/",
            "WAYBACK_API_URL": "http://127.0.0.1:8/",
            "WAYBACK_CDX_URL": "http://127.0.0.1:7/",
            "HN_API_URL": "http://127.0.0.1:6/",
        }
    )[0]
    assert ad.sources == {
        "wikipedia": "http://127.0.0.1:9",
        "wayback": "http://127.0.0.1:8",
        "hn": "http://127.0.0.1:6",
    }
    assert ad.wayback_cdx_url == "http://127.0.0.1:7"
    blank = lane_wiki.build({"WIKIPEDIA_API_URL": "   ", "WAYBACK_CDX_URL": ""})[0]
    assert blank.sources["wikipedia"] == "https://en.wikipedia.org"
    assert blank.wayback_cdx_url == "https://web.archive.org"


def test_killed_wikipedia_refuses_its_tools_even_when_called_directly():
    ad = lane_wiki.build({"ENABLE_WIKIPEDIA": "0"})[0]
    text = _error_text(ad.handle_call("wikipedia_search", {"query": "x"}))
    assert "unknown grounding tool" in text


def test_lanes_build_lane_wires_the_module_by_name():
    built = lanes.build_lane("lane_wiki", {})
    assert [a.platform for a in built] == ["grounding"]
    assert built[0].tool_names() == ALL_TOOLS
    extra, degraded = lanes.extra_adapters({"ENABLE_HN": "0"}, modules=("lane_wiki",))
    assert degraded == {}
    assert [a.tool_names() for a in extra] == [ALL_TOOLS[:4]]


def _bare_hub(tmp_path, environ):
    store = accounts.AccountStore(str(tmp_path / "acc.json"), [], environ=environ)
    rot = rotation.Rotator.from_specs([], store, environ=environ)
    return hub.SearchHub(
        [], emit=lambda _line: None, store=store, rotator=rot, environ=environ
    )


def test_hub_exposes_the_lane_once_registered(tmp_path, monkeypatch):
    # The parent registers "lane_wiki" in lanes.LANE_MODULES after gating; this
    # proves the registration is all that is needed (no hub edit).
    monkeypatch.setattr(lanes, "LANE_MODULES", ("lane_wiki",))
    server = _bare_hub(tmp_path, {})
    names = {t["name"] for t in server.all_tools}
    assert set(ALL_TOOLS) <= names
    assert server._children == {}  # in-process, nothing spawned
    assert not any(k.startswith("lane:") for k in server.degraded)
    assert server.adapter_routes["hn_search"].platform == "grounding"
    killed = _bare_hub(
        tmp_path, {"ENABLE_WIKIPEDIA": "0", "ENABLE_WAYBACK": "0", "ENABLE_HN": "0"}
    )
    killed_names = {t["name"] for t in killed.all_tools}
    assert not (set(ALL_TOOLS) & killed_names)
    assert not any(k.startswith("lane:") for k in killed.degraded)


def test_print_plan_shows_one_grounding_bucket(monkeypatch, capsys):
    monkeypatch.setattr(lanes, "LANE_MODULES", ("lane_wiki",))
    monkeypatch.setattr(hub.os, "environ", {"ENABLE_HN": "0"})
    assert hub._cmd_print_plan() == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["per_provider"]["grounding"] == 4  # one bucket, HN killed
    assert not any(k.startswith("lane:") for k in plan["degraded"])


# --------------------------------------------------------------------------- #
# end-to-end over a real loopback socket (default header-aware urllib caller)
# --------------------------------------------------------------------------- #
def test_default_header_caller_against_real_socket():
    server = HTTPServer(("127.0.0.1", 0), fake._Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"
    try:
        ad = lane_wiki.build(
            {
                "WIKIPEDIA_API_URL": base,
                "WAYBACK_API_URL": base,
                "WAYBACK_CDX_URL": base,
                "HN_API_URL": base,
            }
        )[0]  # the real urllib caller
        reachable, note = ad.probe()
        assert reachable, note
        assert all(t["state"] == "probed" for t in ad.capabilities(probe=True)["tools"])
        wiki = _payload(
            ad.handle_call("wikipedia_search", {"query": "mcp", "limit": 1})
        )
        assert wiki["results"][0]["title"] == "Model Context Protocol"
        assert wiki["results"][0]["url"] == f"{base}/wiki/Model_Context_Protocol"
        assert fake.RECEIVED[-1]["user-agent"] == lane_wiki.USER_AGENT  # on the wire
        summary = _payload(ad.handle_call("wikipedia_summary", {"title": "Mercury"}))
        assert summary["disambiguation"] is True
        available = _payload(
            ad.handle_call("wayback_available", {"url": "example.com"})
        )
        assert available["available"] is True
        cdx = _payload(
            ad.handle_call("wayback_snapshots", {"url": "example.com", "limit": 2})
        )
        assert cdx["count"] == 2
        assert cdx["snapshots"][0]["snapshot_url"].startswith(
            f"{base}/web/20150315120000/"
        )
        empty = _payload(
            ad.handle_call("wayback_snapshots", {"url": "never-archived.example"})
        )
        assert empty["count"] == 0  # a real 3-byte "[]" 200 over the socket
        empty_plain = _payload(
            ad.handle_call("wayback_snapshots", {"url": "never-archived-plain.example"})
        )
        assert empty_plain["count"] == 0  # a real zero-byte 200 over the socket
        hn = _payload(
            ad.handle_call("hn_search", {"query": "mcp", "sort": "date", "limit": 1})
        )
        assert hn["hits"][0]["title"] == "Fresh MCP story"
        offline = ad.handle_call("wayback_snapshots", {"url": "offline.example"})
        assert offline["isError"] and "HTTP 503" in offline["content"][0]["text"]
        missing = ad.handle_call("wikipedia_summary", {"title": "Zzqx_No_Such_Page"})
        assert (
            missing["isError"]
            and "no such page" in missing["content"][0]["text"].lower()
        )
    finally:
        server.shutdown()
        server.server_close()


def test_connection_refused_and_read_timeout_are_truthful_errors():
    # Connection refused: a port nothing listens on (bound then released).
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    closed_port = probe.getsockname()[1]
    probe.close()
    refused = lane_wiki.build({"HN_API_URL": f"http://127.0.0.1:{closed_port}"})[0]
    text = _error_text(refused.handle_call("hn_search", {"query": "x"}))
    assert "not reachable" in text and "fabricated" in text
    # Read timeout: a listener that accepts the TCP connection but never answers.
    silent = socket.socket()
    silent.bind(("127.0.0.1", 0))
    silent.listen(1)
    silent_port = silent.getsockname()[1]
    try:
        slow = lane_wiki.build(
            {"WIKIPEDIA_API_URL": f"http://127.0.0.1:{silent_port}"}
        )[0]
        slow.timeout_s = 0.3
        started = time.monotonic()
        text = _error_text(slow.handle_call("wikipedia_search", {"query": "x"}))
        assert time.monotonic() - started < 5
        assert "not reachable" in text and "timed out" in text.lower()
        assert "fabricated" in text
    finally:
        silent.close()
