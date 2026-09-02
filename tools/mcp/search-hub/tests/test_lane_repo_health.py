#!/usr/bin/env python3
"""Unit tests for the repo-health lane (bestofjs v2 + deps.dev + OpenSSF Scorecard).

Network-free: every ``adapters.Caller`` is the stdlib fake router in
``fake_repo_health_backend`` (one loopback test drives the real urllib caller
against that router on a socket). Pins the trending sort per period + tag filter
+ limit clamp, the exact / case-insensitive / substring project lookup, the TTL
dataset cache with an injected clock, the frozen-v1-host trap, deps.dev URL
encoding (``github.com%2Fowner%2Frepo``, ``%40types%2Fnode``) and system
validation, the 404 mappings (deps.dev "not found", Scorecard "not scanned --
never a zero"), the ``ENABLE_REPO_HEALTH`` kill switch, ``lanes.build_lane``
wiring, the hub surface, and the truthful connection-refused error.
"""

from __future__ import annotations

import json
import os
import sys
import threading
from http.server import HTTPServer
from urllib.parse import urlsplit

import pytest

HUB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HUB_DIR)
sys.path.insert(0, TESTS_DIR)

import accounts  # noqa: E402
import hub  # noqa: E402
import lanes  # noqa: E402
import rotation  # noqa: E402

import fake_repo_health_backend as fake  # noqa: E402
import lane_repo_health as lane  # noqa: E402

BESTOFJS = "https://bestofjs-static-api-v2.vercel.app"
DEPSDEV = "https://api.deps.dev"
SCORECARD = "https://api.securityscorecards.dev"
T0 = 1_788_336_000.0  # 2026-09-02T08:00:00Z
T0_ISO = "2026-09-02T08:00:00Z"
ALL_TOOLS = [
    "bestofjs_trending",
    "bestofjs_project",
    "depsdev_project",
    "depsdev_package",
    "scorecard_project",
]


class Clock:
    """An injectable clock: ``clock()`` -> epoch seconds; ``advance(s)`` moves it."""

    def __init__(self, start: float = T0) -> None:
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def _spy(captured: list):
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
        return fake.fake_caller(method, url, body, headers, timeout)

    return caller


def _bestofjs(base=BESTOFJS, caller=None, ttl_s=None, clock=None):
    kwargs = {"caller": caller or fake.fake_caller, "clock": clock or Clock()}
    if ttl_s is not None:
        kwargs["ttl_s"] = ttl_s
    return lane.BestOfJSAdapter(base, **kwargs)


def _depsdev(base=DEPSDEV, caller=None, clock=None):
    return lane.DepsDevAdapter(
        base, caller=caller or fake.fake_caller, clock=clock or Clock()
    )


def _scorecard(base=SCORECARD, caller=None, clock=None):
    return lane.ScorecardAdapter(
        base, caller=caller or fake.fake_caller, clock=clock or Clock()
    )


def _payload(result: dict) -> dict:
    assert not result["isError"], result
    return json.loads(result["content"][0]["text"])


def _error_text(result: dict) -> str:
    assert result["isError"] is True, result
    text = result["content"][0]["text"]
    assert text.startswith("[search-hub:repohealth] ")
    return text


def _dead(_m, _u, _b, _h, _t):
    return 0, None, "request failed: [Errno 111] Connection refused"


@pytest.fixture(autouse=True)
def _reset_fake():
    fake.reset()
    yield
    fake.reset()


# --------------------------------------------------------------------------- #
# surface, defaults, the frozen-v1 trap
# --------------------------------------------------------------------------- #
def test_build_returns_three_adapters_with_the_five_tools_in_order():
    built = lane.build({})
    assert [type(a).__name__ for a in built] == [
        "BestOfJSAdapter",
        "DepsDevAdapter",
        "ScorecardAdapter",
    ]
    assert all(a.platform == "repohealth" for a in built)
    assert [n for a in built for n in a.tool_names()] == ALL_TOOLS
    assert [a.service for a in built] == ["bestofjs", "depsdev", "scorecard"]
    # Import-safe and lazy: building the lane made no request at all.
    assert fake.RECEIVED == []


def test_default_bases_are_the_live_hosts_and_never_the_frozen_v1():
    built = {a.service: a for a in lane.build({})}
    assert built["bestofjs"].base_url == lane.DEFAULT_BESTOFJS_API_URL == BESTOFJS
    assert built["depsdev"].base_url == lane.DEFAULT_DEPSDEV_API_URL == DEPSDEV
    assert built["scorecard"].base_url == lane.DEFAULT_SCORECARD_API_URL == SCORECARD
    # The lens trap: the v1 host is frozen at 2024-08-10 (2,005 projects, live
    # probe 2026-09-02). The default MUST be the v2 host.
    assert urlsplit(BESTOFJS).hostname == "bestofjs-static-api-v2.vercel.app"
    assert urlsplit(BESTOFJS).hostname != lane.FROZEN_BESTOFJS_V1_HOST
    assert lane.FROZEN_BESTOFJS_V1_HOST == "bestofjs-static-api.vercel.app"
    assert "v2" in built["bestofjs"].tool_defs()[0]["description"]


@pytest.mark.parametrize(
    "url",
    [
        "https://bestofjs-static-api.vercel.app",
        "https://BestOfJS-Static-API.vercel.app/",
        "http://bestofjs-static-api.vercel.app/projects.json",
    ],
)
def test_build_refuses_the_frozen_v1_host(url):
    with pytest.raises(ValueError) as info:
        lane.build({"BESTOFJS_API_URL": url})
    text = str(info.value)
    assert "2024-08-10" in text and "v2" in text and "BESTOFJS_API_URL" in text
    # Through the registry the refusal is a truthful degraded entry, not a crash.
    built, degraded = lanes.extra_adapters(
        {"BESTOFJS_API_URL": url}, modules=("lane_repo_health",)
    )
    assert built == []
    assert degraded["lane:lane_repo_health"].startswith("ValueError")
    assert "2024-08-10" in degraded["lane:lane_repo_health"]


def test_tool_definitions_are_honest_and_schemas_pin_arguments():
    defs = {d["name"]: d for a in lane.build({}) for d in a.tool_defs()}
    assert set(defs) == set(ALL_TOOLS)
    trending = defs["bestofjs_trending"]["inputSchema"]["properties"]
    assert trending["period"]["enum"] == list(lane.PERIODS)
    assert trending["period"]["default"] == "weekly"
    assert trending["limit"]["maximum"] == 50 and trending["limit"]["minimum"] == 1
    assert defs["bestofjs_project"]["inputSchema"]["required"] == ["query"]
    assert defs["depsdev_project"]["inputSchema"]["required"] == ["owner", "repo"]
    package = defs["depsdev_package"]["inputSchema"]
    assert package["required"] == ["system", "name"]
    assert package["properties"]["system"]["enum"] == list(lane.DEPSDEV_SYSTEMS)
    assert defs["scorecard_project"]["inputSchema"]["required"] == ["owner", "repo"]
    # Honest limits and traps live in the descriptions themselves.
    assert "curated" in defs["bestofjs_trending"]["description"].lower()
    assert "cache" in defs["bestofjs_trending"]["description"].lower()
    assert "no search" in defs["depsdev_package"]["description"].lower()
    assert "404" in defs["depsdev_project"]["description"]
    assert "not scanned" in defs["scorecard_project"]["description"].lower()
    assert "never a zero" in defs["scorecard_project"]["description"].lower()
    for d in defs.values():
        assert "fabricat" in d["description"].lower()


def test_capabilities_report_public_api_not_self_hosted():
    for ad in lane.build({}):
        report = ad.capabilities()
        assert report["provider"] == "repohealth"
        assert report["keyless"] is True and report["self_hosted"] is False
        assert report["service"] == ad.service
        assert report["url_env"] in {
            "BESTOFJS_API_URL",
            "DEPSDEV_API_URL",
            "SCORECARD_API_URL",
        }
        assert all(t["state"] == "native" for t in report["tools"])
    bj = _bestofjs().capabilities()
    assert bj["dataset"] == {
        "cached": False,
        "fetched_at": None,
        "dataset_date": None,
        "projects": None,
        "ttl_s": lane.DEFAULT_BESTOFJS_TTL_S,
    }


# --------------------------------------------------------------------------- #
# bestofjs_trending
# --------------------------------------------------------------------------- #
EXPECTED_ORDER = {
    "daily": [
        "mattpocock/skills",
        "honojs/hono",
        "facebook/react",
        "vitest-dev/vitest",
        "expressjs/express",
        "remix-run/react-router",
        "vuejs/pinia",
        "vuejs/core",
        "sourcey/sourcey",
    ],
    # React Router ties Vue.js at 41 and wins on stars (55k > 54k); Sourcey has
    # no weekly figure yet and is excluded, not scored 0.
    "weekly": [
        "mattpocock/skills",
        "honojs/hono",
        "facebook/react",
        "vitest-dev/vitest",
        "expressjs/express",
        "remix-run/react-router",
        "vuejs/core",
        "vuejs/pinia",
    ],
    "monthly": [
        "honojs/hono",
        "facebook/react",
        "vitest-dev/vitest",
        "expressjs/express",
        "vuejs/core",
        "remix-run/react-router",
        "vuejs/pinia",
    ],
    "quarterly": [
        "honojs/hono",
        "facebook/react",
        "vitest-dev/vitest",
        "expressjs/express",
        "vuejs/core",
        "remix-run/react-router",
        "vuejs/pinia",
    ],
    "yearly": [
        "honojs/hono",
        "facebook/react",
        "vitest-dev/vitest",
        "expressjs/express",
        "vuejs/core",
        "remix-run/react-router",
        "vuejs/pinia",
    ],
}


@pytest.mark.parametrize("period", list(lane.PERIODS))
def test_trending_sorts_by_the_chosen_period_delta(period):
    payload = _payload(
        _bestofjs().handle_call("bestofjs_trending", {"period": period, "limit": 50})
    )
    assert payload["tool"] == "bestofjs_trending" and payload["period"] == period
    assert [i["full_name"] for i in payload["items"]] == EXPECTED_ORDER[period]
    deltas = [i["delta"] for i in payload["items"]]
    assert deltas == sorted(deltas, reverse=True)
    assert all(i["delta"] == i["trends"][period] for i in payload["items"])
    assert [i["rank"] for i in payload["items"]] == list(
        range(1, len(payload["items"]) + 1)
    )
    assert payload["total_ranked"] == len(EXPECTED_ORDER[period])
    assert payload["excluded_without_trend"] == 9 - len(EXPECTED_ORDER[period])
    assert payload["count"] == len(payload["items"])
    assert payload["tag"] is None


def test_trending_defaults_to_weekly_and_limit_20():
    payload = _payload(_bestofjs().handle_call("bestofjs_trending", {}))
    assert payload["period"] == "weekly" and payload["limit"] == 20
    assert [i["full_name"] for i in payload["items"]] == EXPECTED_ORDER["weekly"]


def test_trending_item_shape_and_derived_urls():
    payload = _payload(
        _bestofjs().handle_call("bestofjs_trending", {"period": "weekly", "limit": 50})
    )
    vue = next(i for i in payload["items"] if i["full_name"] == "vuejs/core")
    assert set(vue) == {
        "rank",
        "delta",
        "name",
        "full_name",
        "description",
        "stars",
        "trends",
        "tags",
        "status",
        "created_at",
        "pushed_at",
        "added_at",
        "contributor_count",
        "npm",
        "downloads",
        "url",
        "repo_url",
        "bestofjs_url",
    }
    assert vue["name"] == "Vue.js" and vue["stars"] == 54286
    assert vue["repo_url"] == "https://github.com/vuejs/core"
    assert vue["bestofjs_url"] == "https://bestofjs.org/projects/vuejs"
    assert vue["url"] == "https://vuejs.org/" and vue["npm"] == "vue"
    assert vue["trends"]["yearly"] == 2831 and vue["status"] == "featured"
    react = next(i for i in payload["items"] if i["full_name"] == "facebook/react")
    assert react["url"] is None  # no homepage in the dataset -> null, not invented


def test_trending_limit_is_applied_after_the_sort():
    payload = _payload(
        _bestofjs().handle_call("bestofjs_trending", {"period": "weekly", "limit": 2})
    )
    assert [i["full_name"] for i in payload["items"]] == [
        "mattpocock/skills",
        "honojs/hono",
    ]
    assert payload["count"] == 2 and payload["limit"] == 2
    assert payload["total_ranked"] == 8  # the whole ranking is still counted


def test_trending_tag_filter_accepts_code_or_display_name():
    ad = _bestofjs()
    by_code = _payload(
        ad.handle_call("bestofjs_trending", {"period": "weekly", "tag": "framework"})
    )
    assert [i["full_name"] for i in by_code["items"]] == [
        "honojs/hono",
        "facebook/react",
        "vuejs/core",
    ]
    assert by_code["tag"] == "framework" and by_code["tag_name"] == "Framework"
    by_name = _payload(
        ad.handle_call(
            "bestofjs_trending", {"period": "weekly", "tag": " node.js FRAMEWORK "}
        )
    )
    assert [i["full_name"] for i in by_name["items"]] == [
        "honojs/hono",
        "expressjs/express",
    ]
    assert by_name["tag"] == "nodejs-framework"
    # A tag filter counts exclusions within the tag, not across the dataset.
    ai_monthly = _payload(
        ad.handle_call("bestofjs_trending", {"period": "monthly", "tag": "ai"})
    )
    assert ai_monthly["items"] == [] and ai_monthly["excluded_without_trend"] == 2
    assert ai_monthly["total_ranked"] == 0


def test_trending_unknown_tag_is_an_error_with_candidates_not_an_empty_list():
    text = _error_text(_bestofjs().handle_call("bestofjs_trending", {"tag": "reac"}))
    assert "unknown tag 'reac'" in text
    assert "react" in text  # the substring candidate is offered
    text2 = _error_text(_bestofjs().handle_call("bestofjs_trending", {"tag": "zzz"}))
    assert "unknown tag 'zzz'" in text2 and "no similar tag" in text2


@pytest.mark.parametrize(
    "args, needle",
    [
        ({"period": "hourly"}, "'period' must be one of"),
        ({"period": 7}, "'period' must be one of"),
        ({"limit": 0}, "'limit' must be an integer between 1 and 50"),
        ({"limit": 51}, "'limit' must be an integer between 1 and 50"),
        ({"limit": "many"}, "'limit' must be an integer between 1 and 50"),
        ({"limit": True}, "'limit' must be an integer between 1 and 50"),
        ({"tag": "bad\ntag"}, "control characters"),
    ],
)
def test_trending_validates_arguments_before_fetching_the_dataset(args, needle):
    captured: list = []
    result = _bestofjs(caller=_spy(captured)).handle_call("bestofjs_trending", args)
    assert needle in _error_text(result)
    assert captured == []  # a bad argument never costs the 1.4 MB download


def test_trending_accepts_digit_strings_and_integral_floats_for_limit():
    ad = _bestofjs()
    assert _payload(ad.handle_call("bestofjs_trending", {"limit": "3"}))["count"] == 3
    assert _payload(ad.handle_call("bestofjs_trending", {"limit": 4.0}))["count"] == 4


# --------------------------------------------------------------------------- #
# bestofjs_project
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "query, matched_on",
    [
        ("Vue.js", "name"),
        ("vue.JS", "name"),
        ("vuejs/core", "full_name"),
        ("VUEJS/CORE", "full_name"),
        ("  vuejs/core  ", "full_name"),
        ("vuejs", "slug"),
        ("https://github.com/vuejs/core", "full_name"),
        ("https://github.com/vuejs/core/", "full_name"),
        ("https://github.com/vuejs/core.git", "full_name"),
        ("http://github.com/vuejs/core/tree/main/packages", "full_name"),
        ("github.com/vuejs/core", "full_name"),
    ],
)
def test_project_exact_match_is_case_insensitive_and_url_tolerant(query, matched_on):
    payload = _payload(_bestofjs().handle_call("bestofjs_project", {"query": query}))
    assert payload["tool"] == "bestofjs_project"
    assert payload["query"] == query
    assert payload["match"]["full_name"] == "vuejs/core"
    assert payload["matched_on"] == matched_on
    assert payload["candidates"] == [] and payload["candidates_total"] == 0
    assert payload["same_repo_entries"] == []
    assert set(payload["match"]) >= {
        "name",
        "full_name",
        "stars",
        "trends",
        "tags",
        "repo_url",
        "bestofjs_url",
    }
    assert "rank" not in payload["match"] and "delta" not in payload["match"]


def test_project_exact_match_lists_the_other_entries_sharing_the_repo():
    # bestofjs curates monorepo packages as separate projects with ONE full_name
    # (live 2026-09-02: 7 such repos, e.g. TanStack Start + TanStack Router both
    # on TanStack/router). The first exact hit is the match; the siblings are
    # listed under same_repo_entries, never silently dropped.
    projects = [
        fake._project(
            "TanStack Router",
            "TanStack/router",
            "tanstack-router",
            15024,
            {"weekly": 40},
            ["react"],
            npm="@tanstack/react-router",
        ),
        fake._project(
            "TanStack Start",
            "TanStack/router",
            "tanstack-start",
            15024,
            {"weekly": 40},
            ["react"],
            npm="@tanstack/react-start",
        ),
    ]

    def caller(method, url, body, headers, timeout):
        doc = {"date": fake.DATASET_DATE, "tags": fake.TAGS, "projects": projects}
        return 200, doc, json.dumps(doc)

    ad = _bestofjs(caller=caller)
    by_repo = _payload(ad.handle_call("bestofjs_project", {"query": "tanstack/ROUTER"}))
    assert by_repo["matched_on"] == "full_name"
    assert by_repo["match"]["name"] == "TanStack Router"  # first in dataset order
    assert [e["name"] for e in by_repo["same_repo_entries"]] == ["TanStack Start"]
    assert by_repo["same_repo_entries"][0]["npm"] == "@tanstack/react-start"
    assert by_repo["candidates"] == [] and by_repo["candidates_total"] == 0
    assert "1 other curated entry share" in by_repo["note"]
    by_name = _payload(ad.handle_call("bestofjs_project", {"query": "tanstack start"}))
    assert by_name["matched_on"] == "name"
    assert by_name["match"]["bestofjs_url"].endswith("/tanstack-start")
    assert [e["name"] for e in by_name["same_repo_entries"]] == ["TanStack Router"]
    # Both entries rank in trending -- the dataset's truth, not a dedupe.
    weekly = _payload(ad.handle_call("bestofjs_trending", {}))
    assert [i["name"] for i in weekly["items"]] == ["TanStack Router", "TanStack Start"]


def test_project_substring_candidates_are_top5_by_stars():
    payload = _payload(_bestofjs().handle_call("bestofjs_project", {"query": "s"}))
    assert payload["match"] is None and payload["matched_on"] is None
    # 7 of 9 fixtures contain an "s" in name/full_name/slug; the 5 starriest win.
    assert payload["candidates_total"] == 7
    assert [c["full_name"] for c in payload["candidates"]] == [
        "expressjs/express",
        "vuejs/core",
        "honojs/hono",
        "vitest-dev/vitest",
        "vuejs/pinia",
    ]
    assert "candidates" in payload["note"]


def test_project_substring_match_when_no_exact_hit():
    payload = _payload(_bestofjs().handle_call("bestofjs_project", {"query": "reac"}))
    assert payload["match"] is None
    assert [c["full_name"] for c in payload["candidates"]] == [
        "facebook/react",
        "remix-run/react-router",
    ]
    # "react" exact-matches the name "React" case-insensitively (and the slug):
    # an exact hit always beats the substring candidates it would also produce.
    exact = _payload(_bestofjs().handle_call("bestofjs_project", {"query": "react"}))
    assert exact["match"]["full_name"] == "facebook/react"
    assert exact["matched_on"] == "name" and exact["candidates"] == []


def test_project_miss_is_a_truthful_empty_result_not_an_error():
    payload = _payload(
        _bestofjs().handle_call("bestofjs_project", {"query": "no-such-thing-zz"})
    )
    assert payload["match"] is None and payload["candidates"] == []
    assert payload["candidates_total"] == 0
    assert "curated" in payload["note"] and "not" in payload["note"]


def test_project_requires_query_before_any_fetch():
    captured: list = []
    ad = _bestofjs(caller=_spy(captured))
    assert "'query' is required" in _error_text(ad.handle_call("bestofjs_project", {}))
    assert "'query' is required" in _error_text(
        ad.handle_call("bestofjs_project", {"query": "   "})
    )
    assert captured == []


# --------------------------------------------------------------------------- #
# the dataset cache: TTL, staleness fields, failure modes, probe
# --------------------------------------------------------------------------- #
def _fetches() -> int:
    return sum(1 for p in fake.RECEIVED if p.endswith("/projects.json"))


def test_dataset_is_fetched_lazily_once_and_served_from_cache_within_ttl():
    clock = Clock()
    captured: list = []
    ad = _bestofjs(caller=_spy(captured), clock=clock)  # default TTL 6 h
    assert captured == []  # nothing at construction
    first = _payload(ad.handle_call("bestofjs_trending", {}))
    assert captured[0]["url"] == BESTOFJS + "/projects.json"
    assert captured[0]["method"] == "GET" and captured[0]["body"] is None
    assert captured[0]["headers"]["Accept"] == "application/json"
    assert "User-Agent" in captured[0]["headers"]
    assert captured[0]["timeout"] > 0
    assert first["cache"] == {"hit": False, "age_s": 0, "ttl_s": 21600}
    assert first["dataset_fetched_at"] == T0_ISO
    assert first["dataset_date"] == fake.DATASET_DATE
    assert first["dataset_projects"] == 9
    assert first["dataset_source"] == BESTOFJS + "/projects.json"
    assert first["fetched_at"] == T0_ISO
    clock.advance(3600)
    second = _payload(ad.handle_call("bestofjs_project", {"query": "hono"}))
    assert _fetches() == 1  # served from cache: no second download
    assert second["cache"] == {"hit": True, "age_s": 3600, "ttl_s": 21600}
    assert second["dataset_fetched_at"] == T0_ISO  # when the DATA was fetched
    assert second["fetched_at"] == "2026-09-02T09:00:00Z"  # when THIS call ran
    clock.advance(21600 - 3600 - 1)  # one second before expiry -> still a hit
    third = _payload(ad.handle_call("bestofjs_trending", {}))
    assert _fetches() == 1 and third["cache"]["hit"] is True
    assert third["cache"]["age_s"] == 21599


def test_dataset_is_refetched_after_the_ttl_expires():
    clock = Clock()
    ad = _bestofjs(clock=clock, ttl_s=600)
    _payload(ad.handle_call("bestofjs_trending", {}))
    clock.advance(600)  # exactly the TTL -> stale
    payload = _payload(ad.handle_call("bestofjs_trending", {}))
    assert _fetches() == 2
    assert payload["cache"] == {"hit": False, "age_s": 0, "ttl_s": 600}
    assert payload["dataset_fetched_at"] == "2026-09-02T08:10:00Z"
    cap = ad.capabilities()
    assert cap["dataset"]["cached"] is True and cap["dataset"]["projects"] == 9
    assert cap["dataset"]["fetched_at"] == "2026-09-02T08:10:00Z"
    assert cap["dataset"]["dataset_date"] == fake.DATASET_DATE


def test_ttl_zero_refetches_on_every_call():
    ad = _bestofjs(ttl_s=0)
    for _ in range(3):
        payload = _payload(ad.handle_call("bestofjs_trending", {}))
        assert payload["cache"]["hit"] is False
    assert _fetches() == 3


def test_dataset_http_failure_is_a_truthful_error_and_leaves_no_cache():
    ad = _bestofjs(base=BESTOFJS + "/broken")
    text = _error_text(ad.handle_call("bestofjs_trending", {}))
    assert "HTTP 503" in text and "/projects.json" in text and "fabricated" in text
    assert "service unavailable" in text
    assert ad.capabilities()["dataset"]["cached"] is False
    # Every call retries (nothing bad is cached) and keeps failing truthfully.
    assert _error_text(ad.handle_call("bestofjs_project", {"query": "x"}))
    assert _fetches() == 2


def test_dataset_wrong_shape_or_non_json_is_an_error_not_an_empty_ranking():
    bad = _error_text(
        _bestofjs(base=BESTOFJS + "/badshape").handle_call("bestofjs_trending", {})
    )
    assert "not the expected" in bad and "projects" in bad
    nonjson = _error_text(
        _bestofjs(base=BESTOFJS + "/nonjson").handle_call("bestofjs_trending", {})
    )
    assert "not the expected" in nonjson and "maintenance" in nonjson


def test_dataset_failure_keeps_a_good_cache_intact_for_other_callers():
    # A refetch that fails after expiry must not wipe the previous dataset, but
    # the failing call itself is reported truthfully (no stale data served as fresh).
    clock = Clock()
    calls: list[str] = []

    def flaky(method, url, body, headers, timeout):
        calls.append(url)
        if len(calls) == 2:
            return 502, None, "bad gateway"
        return fake.fake_caller(method, url, body, headers, timeout)

    ad = _bestofjs(caller=flaky, clock=clock, ttl_s=100)
    assert _payload(ad.handle_call("bestofjs_trending", {}))["cache"]["hit"] is False
    clock.advance(100)
    text = _error_text(ad.handle_call("bestofjs_trending", {}))
    assert "HTTP 502" in text
    assert ad.capabilities()["dataset"]["cached"] is True  # the old copy survives
    ok = _payload(ad.handle_call("bestofjs_trending", {}))  # third call refetches
    assert ok["cache"]["hit"] is False and len(calls) == 3


def test_probe_downloads_the_dataset_and_warms_the_cache():
    ad = _bestofjs()
    reachable, note = ad.probe()
    assert reachable, note
    assert "9 projects" in note and fake.DATASET_DATE in note
    assert _fetches() == 1
    payload = _payload(ad.handle_call("bestofjs_trending", {}))
    assert payload["cache"]["hit"] is True and _fetches() == 1  # warmed, not repeated
    probed = ad.capabilities(probe=True)
    assert all(t["state"] == "probed" for t in probed["tools"])
    assert _fetches() == 1  # the probe reused the warm cache too
    down = _bestofjs(caller=_dead)
    assert down.probe() == (False, down.probe()[1])
    assert "Connection refused" in down.probe()[1]


# --------------------------------------------------------------------------- #
# depsdev_project
# --------------------------------------------------------------------------- #
def test_depsdev_project_encodes_the_slashes_and_maps_the_record():
    captured: list = []
    result = _depsdev(caller=_spy(captured)).handle_call(
        "depsdev_project", {"owner": "pallets", "repo": "flask"}
    )
    assert captured[0]["url"] == DEPSDEV + "/v3/projects/github.com%2Fpallets%2Fflask"
    assert captured[0]["method"] == "GET" and captured[0]["body"] is None
    assert captured[0]["headers"]["Accept"] == "application/json"
    payload = _payload(result)
    assert payload["tool"] == "depsdev_project"
    assert payload["project"] == "github.com/pallets/flask"
    assert payload["stars"] == 72165 and payload["forks"] == 16952
    assert payload["open_issues"] == 4
    assert payload["license"] == "BSD-3-Clause"
    assert payload["homepage"] == "https://flask.palletsprojects.com"
    assert payload["description"].startswith("The Python micro framework")
    sc = payload["scorecard"]
    assert sc["overall_score"] == 7.1 and sc["date"] == "2026-08-17T00:00:00Z"
    assert sc["scorecard_version"] == fake.SCORECARD_VERSION
    assert sc["commit"] == fake.SCORECARD_COMMIT
    assert sc["checks_count"] == 3
    assert sc["checks"][0] == {
        "name": "Maintained",
        "score": 10,
        "reason": "18 commit(s) and 20 issue activity found in the last 90 days",
    }
    assert all(set(c) == {"name", "score", "reason"} for c in sc["checks"])
    assert payload["oss_fuzz"]["lineCount"] == 6234
    assert payload["source"] == captured[0]["url"]
    assert payload["fetched_at"] == T0_ISO
    assert "starsCount" not in json.dumps(payload)  # renamed, not duplicated


def test_depsdev_project_without_scorecard_reports_null_not_zero():
    payload = _payload(
        _depsdev().handle_call(
            "depsdev_project", {"owner": "acme", "repo": "no-scorecard"}
        )
    )
    assert payload["scorecard"] is None and payload["oss_fuzz"] is None
    assert payload["stars"] == 12 and payload["license"] == "MIT"
    assert "scorecard_project" in payload["note"]  # points at the live API tool
    assert '"overall_score": 0' not in json.dumps(payload)


def test_depsdev_project_404_is_a_truthful_error_with_the_upstream_text():
    text = _error_text(
        _depsdev().handle_call(
            "depsdev_project", {"owner": "nobody", "repo": "nothing"}
        )
    )
    assert "HTTP 404" in text and "project not found" in text
    assert "github.com/nobody/nothing" in text
    assert "no project record" in text and "fabricated" in text
    assert '"stars"' not in text  # no fake zeros


def test_depsdev_project_500_is_a_truthful_error():
    text = _error_text(
        _depsdev().handle_call("depsdev_project", {"owner": "acme", "repo": "boom"})
    )
    assert "HTTP 500" in text and "internal error" in text and "fabricated" in text


@pytest.mark.parametrize(
    "args, needle",
    [
        ({}, "'owner' is required"),
        ({"owner": "pallets"}, "'repo' is required"),
        ({"owner": "pallets", "repo": ""}, "'repo' is required"),
        ({"owner": "a/../b", "repo": "x"}, "'owner' must match"),
        ({"owner": "pallets", "repo": "fl ask"}, "'repo' must match"),
        ({"owner": "pallets", "repo": "flask?x=1"}, "'repo' must match"),
    ],
)
def test_depsdev_project_validates_segments_before_any_request(args, needle):
    captured: list = []
    result = _depsdev(caller=_spy(captured)).handle_call("depsdev_project", args)
    assert needle in _error_text(result)
    assert captured == []


# --------------------------------------------------------------------------- #
# depsdev_package
# --------------------------------------------------------------------------- #
def test_depsdev_package_summarizes_versions():
    captured: list = []
    payload = _payload(
        _depsdev(caller=_spy(captured)).handle_call(
            "depsdev_package", {"system": "npm", "name": "express"}
        )
    )
    assert captured[0]["url"] == DEPSDEV + "/v3/systems/npm/packages/express"
    assert payload["tool"] == "depsdev_package"
    assert payload["system"] == "npm" and payload["name"] == "express"
    assert payload["package_key"] == {"system": "NPM", "name": "express"}
    assert payload["versions_count"] == 5
    assert payload["default_version"] == {
        "version": "5.2.1",
        "published_at": "2025-12-01T20:49:43Z",
        "is_default": True,
        "is_deprecated": False,
    }
    # The newest publishedAt is a pre-release: reported as latest, NOT as default.
    assert payload["latest_published"]["version"] == "5.3.0-beta.1"
    assert payload["latest_published"]["is_default"] is False
    assert payload["deprecated_count"] == 1
    recent = payload["recent_versions"]
    assert [v["version"] for v in recent] == [
        "5.3.0-beta.1",
        "5.2.1",
        "5.1.0",
        "4.18.0",
        "4.17.1",
    ]
    assert recent[3]["is_deprecated"] is True
    assert recent[3]["deprecated_reason"] == "upgrade to 4.18.2"
    assert "deprecated_reason" not in recent[0]  # only carried when set
    assert "pre-release" in payload["note"]
    assert payload["source"] == captured[0]["url"]


def test_depsdev_package_encodes_scoped_names_and_lowercases_the_system():
    captured: list = []
    payload = _payload(
        _depsdev(caller=_spy(captured)).handle_call(
            "depsdev_package", {"system": " NPM ", "name": "@types/node"}
        )
    )
    assert captured[0]["url"] == DEPSDEV + "/v3/systems/npm/packages/%40types%2Fnode"
    assert payload["system"] == "npm" and payload["name"] == "@types/node"
    assert payload["package_key"]["name"] == "@types/node"
    assert payload["versions_count"] == 2
    assert payload["default_version"]["version"] == "24.1.0"


def test_depsdev_package_encodes_go_and_maven_names_the_same_way():
    captured: list = []
    ad = _depsdev(caller=_spy(captured))
    ad.handle_call(
        "depsdev_package", {"system": "go", "name": "github.com/gin-gonic/gin"}
    )
    ad.handle_call(
        "depsdev_package", {"system": "maven", "name": "com.google.guava:guava"}
    )
    assert [c["url"] for c in captured] == [
        DEPSDEV + "/v3/systems/go/packages/github.com%2Fgin-gonic%2Fgin",
        DEPSDEV + "/v3/systems/maven/packages/com.google.guava%3Aguava",
    ]


def test_depsdev_package_relays_normalized_keys():
    payload = _payload(
        _depsdev().handle_call("depsdev_package", {"system": "pypi", "name": "Flask"})
    )
    assert payload["name"] == "Flask"  # what was asked
    assert payload["package_key"] == {"system": "PYPI", "name": "flask"}  # upstream


def test_depsdev_package_recent_versions_are_capped_at_ten():
    versions = [
        fake._version("big", f"1.0.{i}", f"2026-01-{i + 1:02d}T00:00:00Z")
        for i in range(25)
    ]
    versions[-1]["isDefault"] = True

    def caller(method, url, body, headers, timeout):
        doc = {"packageKey": {"system": "NPM", "name": "big"}, "versions": versions}
        return 200, doc, json.dumps(doc)

    payload = _payload(
        _depsdev(caller=caller).handle_call(
            "depsdev_package", {"system": "npm", "name": "big"}
        )
    )
    assert payload["versions_count"] == 25
    assert len(payload["recent_versions"]) == 10
    assert payload["recent_versions"][0]["version"] == "1.0.24"
    assert payload["latest_published"]["version"] == "1.0.24"


@pytest.mark.parametrize(
    "args, needle",
    [
        ({}, "'system' must be one of npm|pypi|cargo|go|maven|nuget|rubygems"),
        ({"system": "bogus", "name": "x"}, "'system' must be one of"),
        ({"system": "npm"}, "'name' is required"),
        ({"system": "npm", "name": "  "}, "'name' is required"),
        ({"system": "npm", "name": "bad\x00name"}, "control characters"),
    ],
)
def test_depsdev_package_validates_before_any_request(args, needle):
    captured: list = []
    result = _depsdev(caller=_spy(captured)).handle_call("depsdev_package", args)
    assert needle in _error_text(result)
    assert captured == []


def test_depsdev_package_404_is_a_truthful_error():
    text = _error_text(
        _depsdev().handle_call(
            "depsdev_package", {"system": "cargo", "name": "nope-zz"}
        )
    )
    assert "HTTP 404" in text and "package not found" in text
    assert "'nope-zz'" in text and "cargo" in text and "fabricated" in text


def test_depsdev_package_500_is_a_truthful_error():
    text = _error_text(
        _depsdev().handle_call("depsdev_package", {"system": "npm", "name": "boom"})
    )
    assert "HTTP 500" in text and "fabricated" in text


def test_depsdev_has_no_search_endpoint_and_none_is_invented():
    names = [n for a in lane.build({}) for n in a.tool_names()]
    assert not any("search" in n for n in names)
    # The fake mirrors the live API: /v3/search is a 404 page, never called by us.
    assert fake.route("GET", "/v3/search?q=flask")[0] == 404


# --------------------------------------------------------------------------- #
# scorecard_project
# --------------------------------------------------------------------------- #
def test_scorecard_project_maps_score_date_and_checks():
    captured: list = []
    payload = _payload(
        _scorecard(caller=_spy(captured)).handle_call(
            "scorecard_project", {"owner": "pallets", "repo": "flask"}
        )
    )
    # Scorecard's documented path form keeps the slashes (unlike deps.dev).
    assert captured[0]["url"] == SCORECARD + "/projects/github.com/pallets/flask"
    assert payload["tool"] == "scorecard_project"
    assert payload["repo"] == "github.com/pallets/flask"
    assert payload["score"] == 7.1 and payload["date"] == "2026-08-24"
    assert payload["commit"] == fake.SCORECARD_COMMIT
    assert payload["scorecard_version"] == fake.SCORECARD_VERSION
    assert payload["checks_count"] == 3
    assert payload["checks"] == [
        {
            "name": "Code-Review",
            "score": 0,
            "reason": "Found 2/25 approved changesets -- score normalized to 0",
        },
        {
            "name": "Maintained",
            "score": 10,
            "reason": "18 commit(s) and 20 issue activity found in the last 90 days",
        },
        {
            "name": "Vulnerabilities",
            "score": -1,  # inconclusive, relayed verbatim -- never rewritten to 0
            "reason": "internal error: check could not run (inconclusive)",
        },
    ]
    assert "-1" in payload["note"]
    assert payload["source"] == captured[0]["url"]
    assert payload["fetched_at"] == T0_ISO


def test_scorecard_404_means_not_scanned_and_is_never_a_zero_score():
    result = _scorecard().handle_call(
        "scorecard_project", {"owner": "unscanned", "repo": "repo"}
    )
    text = _error_text(result)
    assert "not scanned" in text.lower() and "HTTP 404" in text
    assert "github.com/unscanned/repo" in text
    assert "not a zero" in text.lower() and "fabricated" in text
    assert "scorecard --repo=github.com/unscanned/repo" in text  # the local remedy
    assert '"score"' not in json.dumps(result)


def test_scorecard_500_is_a_truthful_error():
    text = _error_text(
        _scorecard().handle_call("scorecard_project", {"owner": "acme", "repo": "boom"})
    )
    assert "HTTP 500" in text and "fabricated" in text


def test_scorecard_validates_segments_before_any_request():
    captured: list = []
    ad = _scorecard(caller=_spy(captured))
    assert "'owner' is required" in _error_text(
        ad.handle_call("scorecard_project", {"repo": "x"})
    )
    assert "'repo' must match" in _error_text(
        ad.handle_call("scorecard_project", {"owner": "a", "repo": "b/c"})
    )
    assert captured == []


def test_scorecard_probe_hits_the_api_root():
    captured: list = []
    ad = _scorecard(caller=_spy(captured))
    reachable, note = ad.probe()
    assert reachable and note == "HTTP 200"
    assert captured[0]["url"] == SCORECARD + "/"
    dd_captured: list = []
    dd = _depsdev(caller=_spy(dd_captured))
    assert dd.probe()[0] is True
    assert dd_captured[0]["url"] == DEPSDEV + "/v3/systems/npm/packages/left-pad"


# --------------------------------------------------------------------------- #
# truthful degradation shared by all three
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "make, tool, args",
    [
        (_bestofjs, "bestofjs_trending", {}),
        (_bestofjs, "bestofjs_project", {"query": "x"}),
        (_depsdev, "depsdev_project", {"owner": "a", "repo": "b"}),
        (_depsdev, "depsdev_package", {"system": "npm", "name": "x"}),
        (_scorecard, "scorecard_project", {"owner": "a", "repo": "b"}),
    ],
)
def test_connection_refused_is_a_truthful_error(make, tool, args):
    text = _error_text(make(caller=_dead).handle_call(tool, args))
    assert "not reachable" in text and "Connection refused" in text
    assert "fabricated" in text


@pytest.mark.parametrize(
    "make, tool, args",
    [
        (_depsdev, "depsdev_project", {"owner": "a", "repo": "b"}),
        (_scorecard, "scorecard_project", {"owner": "a", "repo": "b"}),
    ],
)
def test_non_json_200_is_an_error_not_an_empty_success(make, tool, args):
    def caller(method, url, body, headers, timeout):
        return 200, None, "<html>captive portal</html>", None

    def caller3(method, url, body, headers, timeout):
        return caller(method, url, body, headers, timeout)[:3]

    text = _error_text(make(caller=caller3).handle_call(tool, args))
    assert "HTTP 200" in text and "not the expected JSON" in text


def test_unknown_tool_and_missing_base_url_are_truthful():
    ad = _depsdev()
    assert "unknown repo-health tool" in _error_text(ad.handle_call("nope", {}))
    bare = lane.DepsDevAdapter("", caller=fake.fake_caller)
    text = _error_text(bare.handle_call("depsdev_project", {"owner": "a", "repo": "b"}))
    assert "DEPSDEV_API_URL" in text and DEPSDEV in text
    assert bare.capabilities()["tools"][0]["state"] == "absent"


def test_every_success_carries_fetched_at_from_the_injected_clock():
    clock = Clock(T0 + 90)
    calls = [
        (_bestofjs(clock=clock), "bestofjs_trending", {}),
        (_bestofjs(clock=clock), "bestofjs_project", {"query": "hono"}),
        (
            _depsdev(clock=clock),
            "depsdev_project",
            {"owner": "pallets", "repo": "flask"},
        ),
        (
            _depsdev(clock=clock),
            "depsdev_package",
            {"system": "npm", "name": "express"},
        ),
        (
            _scorecard(clock=clock),
            "scorecard_project",
            {"owner": "pallets", "repo": "flask"},
        ),
    ]
    for ad, tool, args in calls:
        assert (
            _payload(ad.handle_call(tool, args))["fetched_at"] == "2026-09-02T08:01:30Z"
        )


def test_default_clock_is_wall_time_utc():
    ad = lane.DepsDevAdapter(DEPSDEV, caller=fake.fake_caller)
    stamp = _payload(
        ad.handle_call("depsdev_project", {"owner": "pallets", "repo": "flask"})
    )["fetched_at"]
    assert stamp.endswith("Z") and stamp.startswith("20") and len(stamp) == 20


# --------------------------------------------------------------------------- #
# wiring: kill switch, env plumbing, lanes registry, hub surface
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("flag", ["0", "false", "no", "off", " OFF "])
def test_kill_switch_builds_nothing(flag):
    assert lane.build({"ENABLE_REPO_HEALTH": flag}) == []
    built, degraded = lanes.extra_adapters(
        {"ENABLE_REPO_HEALTH": flag}, modules=("lane_repo_health",)
    )
    assert built == [] and degraded == {}  # off is not degraded


@pytest.mark.parametrize("flag", ["", "1", "true", "yes", "on"])
def test_truthy_or_empty_flag_keeps_the_lane_wired(flag):
    assert len(lane.build({"ENABLE_REPO_HEALTH": flag})) == 3


def test_env_plumbing_reads_base_urls_and_ttl():
    built = {
        a.service: a
        for a in lane.build(
            {
                "BESTOFJS_API_URL": "http://127.0.0.1:9/",
                "BESTOFJS_TTL_S": " 120 ",
                "DEPSDEV_API_URL": "http://127.0.0.1:8/",
                "SCORECARD_API_URL": "http://127.0.0.1:7",
            }
        )
    }
    assert built["bestofjs"].base_url == "http://127.0.0.1:9"  # trailing slash gone
    assert built["bestofjs"].ttl_s == 120
    assert built["depsdev"].base_url == "http://127.0.0.1:8"
    assert built["scorecard"].base_url == "http://127.0.0.1:7"
    default = {a.service: a for a in lane.build({"BESTOFJS_TTL_S": ""})}
    assert default["bestofjs"].ttl_s == 21600 == lane.DEFAULT_BESTOFJS_TTL_S


@pytest.mark.parametrize("ttl", ["abc", "-5", "1.5", "6h"])
def test_invalid_ttl_is_a_truthful_build_error(ttl):
    with pytest.raises(ValueError) as info:
        lane.build({"BESTOFJS_TTL_S": ttl})
    assert "BESTOFJS_TTL_S" in str(info.value) and repr(ttl) in str(info.value)


def test_lanes_build_lane_wires_the_module():
    built = lanes.build_lane("lane_repo_health", {})
    assert [n for a in built for n in a.tool_names()] == ALL_TOOLS
    extra, degraded = lanes.extra_adapters({}, modules=("lane_repo_health",))
    assert [n for a in extra for n in a.tool_names()] == ALL_TOOLS
    assert degraded == {}


def _bare_hub(tmp_path, environ, self_hosted):
    store = accounts.AccountStore(str(tmp_path / "acc.json"), [], environ=environ)
    rot = rotation.Rotator.from_specs([], store, environ=environ)
    return hub.SearchHub(
        [],
        emit=lambda _line: None,
        store=store,
        rotator=rot,
        environ=environ,
        self_hosted=self_hosted,
    )


def test_hub_surface_lists_routes_and_reports_the_lattice(tmp_path):
    clock = Clock()
    self_hosted = [
        _bestofjs(clock=clock),
        _depsdev(clock=clock),
        _scorecard(clock=clock),
    ]
    server = _bare_hub(tmp_path, {}, self_hosted)
    names = [t["name"] for t in server.all_tools]
    assert names[: len(ALL_TOOLS)] == ALL_TOOLS
    assert server._children == {}  # in-process, nothing spawned
    assert set(server.adapter_routes) == set(ALL_TOOLS)
    # A tools/call through the hub's route table reaches the adapter.
    result = server.adapter_routes["bestofjs_trending"].handle_call(
        "bestofjs_trending", {"limit": 1}
    )
    assert _payload(result)["items"][0]["full_name"] == "mattpocock/skills"
    # search_usage {"provider": "repohealth"} yields one lattice entry per service.
    sent: list = []
    server._tool_result = lambda mid, payload, is_error=False: sent.append(payload)
    server._handle_usage({"params": {"arguments": {"provider": "repohealth"}}}, 1)
    report = sent[0]["self_hosted"]
    assert [r["service"] for r in report] == ["bestofjs", "depsdev", "scorecard"]
    assert all(r["provider"] == "repohealth" for r in report)


# --------------------------------------------------------------------------- #
# end-to-end over a real loopback socket (default urllib caller)
# --------------------------------------------------------------------------- #
def test_default_caller_against_real_socket():
    server = HTTPServer(("127.0.0.1", 0), fake._Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"
    try:
        bj = lane.BestOfJSAdapter(base)  # real caller, real clock
        payload = _payload(bj.handle_call("bestofjs_trending", {"limit": 3}))
        assert [i["full_name"] for i in payload["items"]] == [
            "mattpocock/skills",
            "honojs/hono",
            "facebook/react",
        ]
        assert payload["dataset_projects"] == 9
        dd = lane.DepsDevAdapter(base)
        project = _payload(
            dd.handle_call("depsdev_project", {"owner": "pallets", "repo": "flask"})
        )
        assert (
            project["stars"] == 72165 and project["scorecard"]["overall_score"] == 7.1
        )
        assert fake.RECEIVED[-1] == "/v3/projects/github.com%2Fpallets%2Fflask"
        # A text/plain 404 body travels through urllib into the truthful error.
        missing = dd.handle_call("depsdev_project", {"owner": "x", "repo": "y"})
        assert "project not found" in _error_text(missing)
        sc = lane.ScorecardAdapter(base)
        scored = _payload(
            sc.handle_call("scorecard_project", {"owner": "pallets", "repo": "flask"})
        )
        assert scored["score"] == 7.1 and scored["checks"][2]["score"] == -1
        unscanned = sc.handle_call(
            "scorecard_project", {"owner": "unscanned", "repo": "repo"}
        )
        assert "not scanned" in _error_text(unscanned).lower()
        assert sc.probe() == (True, "HTTP 200")
        refused = lane.ScorecardAdapter("http://127.0.0.1:9")  # nothing listens
        assert "not reachable" in _error_text(
            refused.handle_call("scorecard_project", {"owner": "a", "repo": "b"})
        )
    finally:
        server.shutdown()
        server.server_close()
