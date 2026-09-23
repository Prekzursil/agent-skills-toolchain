#!/usr/bin/env python3
"""Unit tests for the GitHub REST search adapter (keyless repo discovery, default ON).

Network-free: the ``adapters.HeaderCaller`` is the stdlib fake GitHub router
(``fake_github_backend.fake_caller``). Pins the query composition (``created:>``
/ ``pushed:>`` / ``stars:>=`` / ``language:`` / ``topic:``), argument validation,
the compact result mapping, the ``x-ratelimit-*`` passthrough, the truthful
403 / 422 / 429 errors, the 202 "still computing" semantics of the stats routes,
the Bearer-token handling (sent to the wire, never echoed), the
``ENABLE_GITHUB_SEARCH`` kill switch, and the hub-level wiring. One test uses a
real loopback socket to prove the default header-aware urllib caller.
"""

from __future__ import annotations

import json
import os
import sys
import threading
from datetime import date
from http.server import HTTPServer

import pytest

HUB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HUB_DIR)
sys.path.insert(0, TESTS_DIR)

import accounts  # noqa: E402
import adapters  # noqa: E402
import hub  # noqa: E402
import rotation  # noqa: E402

import fake_github_backend as fake  # noqa: E402

BASE = "https://api.github.com"
TODAY = date(2026, 9, 2)
TOKEN = "ghp_TESTSECRET_never_printed_0123456789"


def _adapter(base=BASE, caller=None, token=None, sleeper=None):
    return adapters.GitHubSearchAdapter(
        base,
        caller=caller or fake.fake_caller,
        token=token,
        today=lambda: TODAY,
        sleeper=sleeper or (lambda _s: None),
    )


def _payload(result: dict) -> dict:
    assert not result["isError"], result
    return json.loads(result["content"][0]["text"])


def _error_text(result: dict) -> str:
    assert result["isError"] is True, result
    return result["content"][0]["text"]


def _spy(captured: list):
    def caller(method, url, body, headers, timeout):
        captured.append(
            {"method": method, "url": url, "body": body, "headers": headers}
        )
        return fake.fake_caller(method, url, body, headers, timeout)

    return caller


def _query_of(url: str) -> dict:
    from urllib.parse import parse_qs, urlsplit

    parts = urlsplit(url)
    return parts.path, {k: v[0] for k, v in parse_qs(parts.query).items()}


@pytest.fixture(autouse=True)
def _reset_fake():
    fake.reset()
    yield
    fake.reset()


# --------------------------------------------------------------------------- #
# surface
# --------------------------------------------------------------------------- #
def test_tool_surface_and_honest_descriptions():
    ad = _adapter()
    assert ad.tool_names() == [
        "github_repo_search",
        "github_new_and_hot",
        "github_popular_and_alive",
        "github_topic_search",
        "github_repo_activity",
    ]
    defs = {d["name"]: d for d in ad.tool_defs()}
    # Honest limits in the descriptions: keyless rate limits + no star velocity.
    assert "10" in defs["github_repo_search"]["description"]
    assert "star velocity" in defs["github_new_and_hot"]["description"].lower()
    assert "202" in defs["github_repo_activity"]["description"]
    assert defs["github_repo_search"]["inputSchema"]["required"] == ["q"]
    assert defs["github_repo_activity"]["inputSchema"]["required"] == ["owner", "repo"]
    assert (
        defs["github_repo_search"]["inputSchema"]["properties"]["per_page"]["maximum"]
        == 50
    )
    # Never collides with the OSSInsight sibling or any provider tool.
    assert all(n.startswith("github_") for n in ad.tool_names())


def test_capabilities_report_authenticated_flag_and_public_api():
    report = _adapter().capabilities()
    assert report["provider"] == "github"
    assert report["keyless"] is True
    assert report["self_hosted"] is False  # a public API, not a daemon we run
    assert report["authenticated"] is False
    assert all(t["state"] == "native" for t in report["tools"])
    with_token = _adapter(token=TOKEN).capabilities()
    assert with_token["authenticated"] is True
    assert TOKEN not in json.dumps(with_token)


def test_probe_hits_rate_limit_route_and_reports_headroom():
    captured: list = []
    ad = _adapter(caller=_spy(captured))
    reachable, note = ad.probe()
    assert reachable, note
    assert captured[0]["url"] == BASE + "/rate_limit"
    assert "search 10/10" in note and "core 59/60" in note
    probed = ad.capabilities(probe=True)
    assert all(t["state"] == "probed" for t in probed["tools"])


# --------------------------------------------------------------------------- #
# github_repo_search
# --------------------------------------------------------------------------- #
def test_repo_search_builds_query_and_maps_compact_items():
    captured: list = []
    ad = _adapter(caller=_spy(captured))
    result = ad.handle_call(
        "github_repo_search", {"q": "vector database", "sort": "stars"}
    )
    path, params = _query_of(captured[0]["url"])
    assert captured[0]["method"] == "GET" and captured[0]["body"] is None
    assert path == "/search/repositories"
    assert params == {
        "q": "vector database",
        "sort": "stars",
        "order": "desc",
        "per_page": "20",
        "page": "1",
    }
    sent = captured[0]["headers"]
    assert sent["Accept"] == "application/vnd.github+json"
    assert sent["X-GitHub-Api-Version"] == "2022-11-28"
    assert "User-Agent" in sent and "Authorization" not in sent
    payload = _payload(result)
    assert payload["tool"] == "github_repo_search"
    assert payload["total_count"] == 2 and payload["incomplete_results"] is False
    assert payload["authenticated"] is False
    assert payload["rate_limit"] == {
        "limit": 10,
        "remaining": 9,
        "reset_epoch": fake.RESET_EPOCH,
        "resource": "search",
    }
    item = payload["items"][0]
    assert set(item) == {
        "full_name",
        "html_url",
        "description",
        "stargazers_count",
        "forks_count",
        "language",
        "created_at",
        "pushed_at",
        "topics",
        "license",
    }
    assert item["full_name"] == "acme/hot-new-thing"
    assert item["license"] == "MIT"  # spdx id, not the nested object
    assert item["topics"] == ["mcp", "search"]


def test_repo_search_best_match_omits_sort_and_order():
    captured: list = []
    _adapter(caller=_spy(captured)).handle_call(
        "github_repo_search", {"q": "mcp server", "per_page": 5, "page": 2}
    )
    _path, params = _query_of(captured[0]["url"])
    assert params == {"q": "mcp server", "per_page": "5", "page": "2"}


@pytest.mark.parametrize(
    "args, needle",
    [
        ({}, "'q' is required"),
        ({"q": "   "}, "'q' is required"),
        ({"q": "x", "sort": "bogus"}, "'sort' must be"),
        ({"q": "x", "order": "sideways"}, "'order' must be"),
        ({"q": "x", "per_page": 0}, "'per_page' must be"),
        ({"q": "x", "per_page": 51}, "'per_page' must be"),
        ({"q": "x", "per_page": "many"}, "'per_page' must be"),
        ({"q": "x", "page": 0}, "'page' must be"),
        ({"q": "x", "per_page": 50, "page": 21}, "first 1000"),
        ({"q": "a" * 257}, "256"),
        ({"q": "line\nbreak"}, "control characters"),
    ],
)
def test_repo_search_validates_arguments_before_any_request(args, needle):
    captured: list = []
    result = _adapter(caller=_spy(captured)).handle_call("github_repo_search", args)
    assert needle in _error_text(result)
    assert captured == []  # rejected locally, no request spent


# --------------------------------------------------------------------------- #
# github_new_and_hot / github_popular_and_alive (query composition)
# --------------------------------------------------------------------------- #
def test_new_and_hot_composes_created_window_and_qualifiers():
    captured: list = []
    ad = _adapter(caller=_spy(captured))
    result = ad.handle_call(
        "github_new_and_hot",
        {
            "keyword": "agent framework",
            "days": 30,
            "language": "Python",
            "topic": "MCP",
            "min_stars": 50,
            "per_page": 10,
        },
    )
    _path, params = _query_of(captured[0]["url"])
    # 2026-09-02 minus 30 days = 2026-08-03; topics are lower-cased by GitHub.
    assert params["q"] == (
        "agent framework created:>2026-08-03 language:Python topic:mcp stars:>=50"
    )
    assert params["sort"] == "stars" and params["order"] == "desc"
    assert params["per_page"] == "10"
    payload = _payload(result)
    assert payload["tool"] == "github_new_and_hot"
    assert payload["window"] == {"qualifier": "created:>2026-08-03", "days": 30}
    assert payload["q"] == params["q"]
    assert payload["rate_limit"]["resource"] == "search"


def test_new_and_hot_defaults_work_with_empty_keyword():
    captured: list = []
    _adapter(caller=_spy(captured)).handle_call("github_new_and_hot", {})
    _path, params = _query_of(captured[0]["url"])
    assert params["q"] == "created:>2026-08-03"  # min_stars=0 adds no qualifier
    assert params["sort"] == "stars"


def test_new_and_hot_quotes_language_with_spaces():
    captured: list = []
    _adapter(caller=_spy(captured)).handle_call(
        "github_new_and_hot", {"language": "Jupyter Notebook", "days": 7}
    )
    _path, params = _query_of(captured[0]["url"])
    assert params["q"] == 'created:>2026-08-26 language:"Jupyter Notebook"'


def test_popular_and_alive_composes_pushed_and_stars():
    captured: list = []
    ad = _adapter(caller=_spy(captured))
    result = ad.handle_call(
        "github_popular_and_alive", {"keyword": "vector database", "pushed_days": 14}
    )
    _path, params = _query_of(captured[0]["url"])
    assert params["q"] == "vector database pushed:>2026-08-19 stars:>=100"
    assert params["sort"] == "stars"
    payload = _payload(result)
    assert payload["window"] == {"qualifier": "pushed:>2026-08-19", "days": 14}
    assert payload["items"][0]["pushed_at"] == "2026-09-01T12:00:00Z"


@pytest.mark.parametrize(
    "tool, args, needle",
    [
        ("github_new_and_hot", {"days": 0}, "'days' must be"),
        ("github_new_and_hot", {"days": 4000}, "'days' must be"),
        ("github_new_and_hot", {"min_stars": -1}, "'min_stars' must be"),
        ("github_new_and_hot", {"language": "C++; DROP"}, "'language' must match"),
        ("github_new_and_hot", {"topic": "not valid!"}, "'topic' must match"),
        ("github_popular_and_alive", {"pushed_days": -3}, "'pushed_days' must be"),
        ("github_popular_and_alive", {"min_stars": "lots"}, "'min_stars' must be"),
    ],
)
def test_composed_tools_validate_qualifiers(tool, args, needle):
    captured: list = []
    result = _adapter(caller=_spy(captured)).handle_call(tool, args)
    assert needle in _error_text(result)
    assert captured == []


# --------------------------------------------------------------------------- #
# github_topic_search
# --------------------------------------------------------------------------- #
def test_topic_search_hits_topics_route_with_compact_items():
    captured: list = []
    result = _adapter(caller=_spy(captured)).handle_call(
        "github_topic_search", {"q": "mcp", "per_page": 5}
    )
    path, params = _query_of(captured[0]["url"])
    assert path == "/search/topics"
    assert params == {"q": "mcp", "per_page": "5", "page": "1"}
    payload = _payload(result)
    assert payload["total_count"] == 1
    topic = payload["items"][0]
    assert topic["name"] == "mcp" and topic["curated"] is True
    assert set(topic) == {
        "name",
        "display_name",
        "short_description",
        "created_by",
        "released",
        "created_at",
        "updated_at",
        "featured",
        "curated",
    }
    assert payload["rate_limit"]["limit"] == 10


def test_topic_search_requires_q():
    assert "'q' is required" in _error_text(
        _adapter().handle_call("github_topic_search", {})
    )


# --------------------------------------------------------------------------- #
# github_repo_activity (stats routes + 202 semantics)
# --------------------------------------------------------------------------- #
def test_repo_activity_returns_commit_series_and_participation():
    captured: list = []
    ad = _adapter(caller=_spy(captured))
    payload = _payload(
        ad.handle_call("github_repo_activity", {"owner": "acme", "repo": "x"})
    )
    assert [c["url"] for c in captured] == [
        BASE + "/repos/acme/x/stats/commit_activity",
        BASE + "/repos/acme/x/stats/participation",
    ]
    assert payload["repo"] == "acme/x"
    ca = payload["commit_activity"]
    assert ca["status"] == 200 and ca["computing"] is False
    assert ca["weeks"] == 52 and ca["total_commits"] == 153  # 10 * (1+2+3+4+5) + 1 + 2
    assert ca["recent_4_weeks_commits"] == sum(w["total"] for w in ca["series"][-4:])
    assert len(ca["series"]) == 52 and set(ca["series"][0]) == {"days", "total", "week"}
    pa = payload["participation"]
    assert pa["status"] == 200 and pa["computing"] is False
    assert pa["all_total"] == 153 and pa["owner_total"] == 52
    assert len(pa["all"]) == 52 and len(pa["owner"]) == 52
    assert payload["rate_limit"]["resource"] == "core"
    assert payload["authenticated"] is False


def test_repo_activity_202_is_reported_as_computing_after_exactly_one_retry():
    captured: list = []
    pauses: list = []
    ad = _adapter(caller=_spy(captured), sleeper=pauses.append)
    ad.stats_retry_pause_s = 0.25
    result = ad.handle_call("github_repo_activity", {"owner": "computing", "repo": "x"})
    payload = _payload(result)  # 202 is NOT an error: it is a truthful "not yet"
    # One retry per endpoint (2 GETs each), one short pause per retry -- never a busy loop.
    assert len(captured) == 4
    assert pauses == [0.25, 0.25]
    assert payload["commit_activity"] == {
        "status": 202,
        "computing": True,
        "note": payload["commit_activity"]["note"],
    }
    assert "computing" in payload["commit_activity"]["note"]
    assert payload["participation"]["computing"] is True
    assert payload["rate_limit"]["resource"] == "core"


def test_repo_activity_202_then_200_after_the_single_retry():
    captured: list = []
    ad = _adapter(caller=_spy(captured))
    payload = _payload(
        ad.handle_call("github_repo_activity", {"owner": "slow", "repo": "x"})
    )
    assert len(captured) == 4  # each endpoint: 202 then 200
    assert payload["commit_activity"]["computing"] is False
    assert payload["commit_activity"]["total_commits"] == 153
    assert payload["participation"]["computing"] is False


def test_repo_activity_204_is_no_content_not_an_error():
    payload = _payload(
        _adapter().handle_call("github_repo_activity", {"owner": "empty", "repo": "x"})
    )
    assert payload["commit_activity"]["status"] == 204
    assert payload["commit_activity"]["computing"] is False
    assert "204" in payload["commit_activity"]["note"]


def test_repo_activity_404_is_truthful_error():
    text = _error_text(
        _adapter().handle_call(
            "github_repo_activity", {"owner": "missing", "repo": "x"}
        )
    )
    assert "HTTP 404" in text and "missing/x" in text


def test_repo_activity_validates_segments():
    ad = _adapter()
    assert "'repo' is required" in _error_text(
        ad.handle_call("github_repo_activity", {"owner": "a"})
    )
    assert "must match" in _error_text(
        ad.handle_call("github_repo_activity", {"owner": "a/../b", "repo": "x"})
    )


# --------------------------------------------------------------------------- #
# truthful degradation -- 403 / 422 / 429 / down, never a fabricated success
# --------------------------------------------------------------------------- #
def test_rate_limited_403_is_truthful_error_carrying_the_headers():
    text = _error_text(
        _adapter().handle_call("github_repo_search", {"q": "ratelimited"})
    )
    assert "rate limit" in text.lower()
    assert "HTTP 403" in text and "unauthenticated" in text
    assert "remaining=0/10" in text
    assert str(fake.RESET_EPOCH) in text
    assert "retry-after 60" in text.lower()
    assert "GITHUB_TOKEN" in text  # the honest remedy, by env name only
    assert "fabricated" in text
    assert "items" not in text  # no fake empty success leaked into the error


def test_429_is_reported_as_rate_limit():
    def caller(method, url, body, headers, timeout):
        return (
            429,
            {"message": "You have exceeded a secondary rate limit."},
            "{}",
            {
                "retry-after": "30",
                "x-ratelimit-remaining": "5",
                "x-ratelimit-limit": "10",
            },
        )

    text = _error_text(
        _adapter(caller=caller).handle_call("github_repo_search", {"q": "x"})
    )
    assert (
        "HTTP 429" in text
        and "rate limit" in text.lower()
        and "retry-after 30" in text.lower()
    )


def test_forbidden_403_with_headroom_is_not_called_a_rate_limit():
    text = _error_text(_adapter().handle_call("github_repo_search", {"q": "forbidden"}))
    assert "HTTP 403" in text and "forbidden" in text.lower()
    assert "not a rate limit" in text.lower()
    assert "Resource not accessible" in text


def test_422_validation_is_truthful_error_relaying_github_message():
    text = _error_text(_adapter().handle_call("github_repo_search", {"q": "toolong"}))
    assert "HTTP 422" in text and "Validation Failed" in text
    assert "longer than 256 characters" in text
    assert "field q" in text


def test_401_bad_credentials_names_env_var_not_value():
    def caller(method, url, body, headers, timeout):
        return 401, {"message": "Bad credentials"}, "{}", {}

    text = _error_text(
        _adapter(caller=caller, token=TOKEN).handle_call(
            "github_repo_search", {"q": "x"}
        )
    )
    assert "HTTP 401" in text and "GITHUB_TOKEN" in text
    assert TOKEN not in text


def test_backend_down_is_truthful_error():
    def dead(_m, _u, _b, _h, _t):
        return 0, None, "request failed: connection refused", {}

    text = _error_text(
        _adapter(caller=dead).handle_call("github_repo_search", {"q": "x"})
    )
    assert "not reachable" in text and "fabricated" in text


def test_non_json_200_is_an_error_not_an_empty_success():
    def caller(method, url, body, headers, timeout):
        return 200, None, "<html>proxy login</html>", {}

    text = _error_text(
        _adapter(caller=caller).handle_call("github_repo_search", {"q": "x"})
    )
    assert "HTTP 200" in text and "not JSON" in text


def test_unknown_tool_is_rejected():
    assert "unknown GitHub tool" in _error_text(_adapter().handle_call("nope", {}))


# --------------------------------------------------------------------------- #
# token handling: sent as Bearer, never echoed anywhere
# --------------------------------------------------------------------------- #
def test_token_is_sent_as_bearer_and_never_appears_in_output():
    ad = _adapter(token=TOKEN)
    ok = ad.handle_call("github_repo_search", {"q": "mcp"})
    assert fake.RECEIVED[-1]["authorization"] == f"Bearer {TOKEN}"
    payload = _payload(ok)
    assert payload["authenticated"] is True
    assert payload["rate_limit"]["limit"] == 30  # the fake raised the limit for auth
    assert TOKEN not in json.dumps(ok)
    err = ad.handle_call("github_repo_search", {"q": "ratelimited"})
    assert err["isError"] and TOKEN not in json.dumps(err)
    assert (
        "authenticated" in err["content"][0]["text"]
    )  # says WHICH pool, not the token
    assert TOKEN not in json.dumps(ad.capabilities(probe=True))
    assert TOKEN not in repr(ad.tool_defs())


def test_blank_token_means_unauthenticated():
    ad = _adapter(token="   ")
    ad.handle_call("github_repo_search", {"q": "mcp"})
    assert "authorization" not in fake.RECEIVED[-1]
    assert ad.capabilities()["authenticated"] is False


# --------------------------------------------------------------------------- #
# wiring: default ON, ENABLE_GITHUB_SEARCH=0 kill switch, env plumbing
# --------------------------------------------------------------------------- #
def test_wired_by_default_and_default_adapters_unchanged():
    wired = adapters.wired_adapters({})
    assert "github" in [a.platform for a in wired]
    # The lane-gated builder keeps its historical contract (TrailSearch only).
    assert [a.platform for a in adapters.default_adapters({})] == ["selfhosted"]
    gh = [a for a in wired if a.platform == "github"][0]
    assert gh.base_url == adapters.DEFAULT_GITHUB_API_URL == "https://api.github.com"
    assert gh.capabilities()["authenticated"] is False


@pytest.mark.parametrize("flag", ["0", "false", "no", "off", " OFF "])
def test_kill_switch_unwires_github(flag):
    platforms = [
        a.platform for a in adapters.wired_adapters({"ENABLE_GITHUB_SEARCH": flag})
    ]
    assert "github" not in platforms
    assert "selfhosted" in platforms  # the rest of the lane is untouched


@pytest.mark.parametrize("flag", ["", "1", "true", "yes", "on"])
def test_truthy_or_empty_flag_keeps_github_wired(flag):
    platforms = [
        a.platform for a in adapters.wired_adapters({"ENABLE_GITHUB_SEARCH": flag})
    ]
    assert "github" in platforms


def test_env_plumbing_reads_api_url_and_token_envs():
    gh = [
        a
        for a in adapters.wired_adapters(
            {"GITHUB_API_URL": "http://127.0.0.1:9/", "GITHUB_TOKEN": TOKEN}
        )
        if a.platform == "github"
    ][0]
    assert gh.base_url == "http://127.0.0.1:9"  # trailing slash stripped
    assert gh.capabilities()["authenticated"] is True
    gh2 = [
        a
        for a in adapters.wired_adapters({"GH_TOKEN": TOKEN})
        if a.platform == "github"
    ][0]
    assert gh2.capabilities()["authenticated"] is True  # GH_TOKEN fallback
    assert TOKEN not in json.dumps(gh2.capabilities())


def _bare_hub(tmp_path, environ):
    store = accounts.AccountStore(str(tmp_path / "acc.json"), [], environ=environ)
    rot = rotation.Rotator.from_specs([], store, environ=environ)
    return hub.SearchHub(
        [], emit=lambda _line: None, store=store, rotator=rot, environ=environ
    )


def test_hub_lists_github_tools_by_default_and_hides_them_when_killed(tmp_path):
    server = _bare_hub(tmp_path, {})
    names = {t["name"] for t in server.all_tools}
    assert {"github_repo_search", "github_new_and_hot", "github_repo_activity"} <= names
    assert server._children == {}  # in-process, nothing spawned
    killed = _bare_hub(tmp_path, {"ENABLE_GITHUB_SEARCH": "0"})
    killed_names = {t["name"] for t in killed.all_tools}
    assert not any(n.startswith("github_") for n in killed_names)
    assert "selfhosted_search" in killed_names


# --------------------------------------------------------------------------- #
# end-to-end over a real loopback socket (default header-aware urllib caller)
# --------------------------------------------------------------------------- #
def test_default_header_caller_against_real_socket_with_token():
    server = HTTPServer(("127.0.0.1", 0), fake._Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        ad = adapters.GitHubSearchAdapter(
            f"http://127.0.0.1:{port}", token=TOKEN, today=lambda: TODAY
        )  # real caller
        reachable, note = ad.probe()
        assert reachable, note
        assert "search 30/30" in note  # authenticated pool reported by the fake
        payload = _payload(ad.handle_call("github_new_and_hot", {"keyword": "socket"}))
        assert payload["items"][0]["full_name"] == "acme/hot-new-thing"
        # Real headers came back through urllib and the token reached the wire.
        assert payload["rate_limit"]["limit"] == 30 and payload["authenticated"] is True
        assert fake.RECEIVED[-1]["authorization"] == f"Bearer {TOKEN}"
        assert TOKEN not in json.dumps(payload)
        err = ad.handle_call("github_repo_search", {"q": "ratelimited"})
        assert err["isError"] and "remaining=0/30" in err["content"][0]["text"]
    finally:
        server.shutdown()
        server.server_close()
