#!/usr/bin/env python3
"""Stdlib fakes of the twelve keyed search vendors for the ``lane_keyed`` tests.

Every vendor behind ``lane_keyed`` is a paid external API; these fakes stand in so
the lane is exercised with NO network and NO real key. The synthetic keys the
fakes accept are ``X-Fake-Key-<vendor>`` (``VALID_KEYS``); DataForSEO takes HTTP
basic ``fake-login:X-Fake-Key-dataforseo``. Nothing here is, or resembles, a real
credential.

One fake, twelve vendors, keyed on the FIRST path segment: the tests point each
adapter's ``<VENDOR>_API_URL`` at ``http://<fake>/<vendor>`` so Brave's
``/res/v1/web/search`` arrives here as ``/brave/res/v1/web/search`` and the four
vendors that all use ``/search`` never collide. Per vendor the fake mirrors the
shapes the adapter relies on (vendor docs read 2026-09-02, URLs in the search-hub
README "Keyed search APIs"):

* the documented route (method + path) -- anything else is 404;
* the documented AUTH PLACEMENT: the key must arrive exactly where the vendor
  documents it (``X-Subscription-Token`` / ``Authorization: Bot`` / ``Bearer`` /
  ``X-API-Key`` / ``API-Key`` / ``X-API-KEY`` / ``apikey`` header, ``api_key``
  query parameter for Mojeek and SerpApi only, or HTTP basic). A key anywhere
  else is "no credential" (401);
  a WRONG key is rejected with the vendor's own error envelope, and that body
  ECHOES the presented key -- exactly what a careless adapter would leak, so the
  scrubbing tests have teeth;
* a happy-path body in the vendor's documented result shape plus the quota
  header/field the adapter relays as ``credits_hint`` (Brave ``x-ratelimit-*``,
  Serper ``credits``, DataForSEO ``cost``, Kagi ``meta.api_balance``,
  ScrapingBee ``spb-cost``).

Query-text triggers (any vendor): ``ratelimited`` -> 429 + ``retry-after: 17``;
``nocredit`` -> 402; ``boom`` -> 500; ``notjson`` -> 200 with an HTML body;
``weirdshape`` -> 200 with an unrecognised JSON object. Vendor-specific:
``empty`` (Brave web) -> a 200 with no ``web`` block; ``noresults`` (SerpApi) ->
SerpApi's 200-with-``error``-string "no results" envelope; ``badtask``
(DataForSEO) -> a 200 whose task failed (status 40501).

Every request is appended to ``RECEIVED`` as ``{vendor, method, path, query,
headers, body}`` (headers lower-cased, body JSON-parsed) so tests can prove the
key reached the wire at the right place without ever printing it. Used as an
importable ``fake_caller`` (the ``adapters.HeaderCaller`` 4-tuple shape) and as a
runnable loopback socket server (GET + POST) for the real-urllib test.
"""

from __future__ import annotations

import base64
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlsplit

DATAFORSEO_LOGIN = "fake-login"
DATAFORSEO_PASSWORD = "X-Fake-Key-dataforseo"

#: The only credentials the fakes accept (synthetic; never real keys).
VALID_KEYS: dict[str, str] = {
    "brave": "X-Fake-Key-brave",
    "kagi": "X-Fake-Key-kagi",
    "linkup": "X-Fake-Key-linkup",
    "mojeek": "X-Fake-Key-mojeek",
    "youcom": "X-Fake-Key-youcom",
    "perplexity": "X-Fake-Key-perplexity",
    "marginalia": "X-Fake-Key-marginalia",
    "serper": "X-Fake-Key-serper",
    "serpapi": "X-Fake-Key-serpapi",
    "dataforseo": f"{DATAFORSEO_LOGIN}:{DATAFORSEO_PASSWORD}",
    "zenserp": "X-Fake-Key-zenserp",
    "scrapingbee": "X-Fake-Key-scrapingbee",
}

#: The documented route(s) per vendor; anything else is a 404.
ROUTES: dict[str, tuple[tuple[str, str], ...]] = {
    "brave": (("GET", "/res/v1/web/search"), ("GET", "/res/v1/llm/context")),
    "kagi": (
        ("POST", "/api/v1/search"),  # v1 OpenAPI: JSON body, HTTP bearer
        ("GET", "/api/v0/enrich/web"),  # v0 help pages: ?q=, "Bot" scheme
        ("GET", "/api/v0/enrich/news"),
    ),
    "linkup": (("POST", "/v1/search"),),
    "mojeek": (("GET", "/search"),),
    "youcom": (("POST", "/v1/search"),),
    "perplexity": (("POST", "/search"),),
    "marginalia": (("GET", "/search"),),
    "serper": (("POST", "/search"),),
    "serpapi": (("GET", "/search.json"),),
    "dataforseo": (("POST", "/v3/serp/google/organic/live/advanced"),),
    "zenserp": (("GET", "/api/v2/search"),),
    "scrapingbee": (("GET", "/api/v1/google"),),
}

RAW_HTML = "<html><body><h1>upstream returned HTML, not JSON</h1></body></html>"

# Every request (pure caller and socket alike), oldest first.
RECEIVED: list[dict] = []
_LOCK = threading.Lock()


def reset() -> None:
    with _LOCK:
        RECEIVED.clear()


# --------------------------------------------------------------------------- #
# auth placement (the documented location per vendor)
# --------------------------------------------------------------------------- #
def presented_key(
    vendor: str, headers: dict[str, str], params: dict[str, str], sub: str = ""
):
    """The credential found at ``vendor``'s DOCUMENTED location, else ``None``."""
    auth = headers.get("authorization", "")
    if vendor == "brave":
        return headers.get("x-subscription-token")
    if vendor == "kagi":
        # v1 /search declares an HTTP *bearer* scheme; the v0 Enrich pages document
        # "Bot". Each route accepts ONLY its own scheme so a mix-up is a 401 here.
        if sub == "/api/v1/search":
            return auth[7:] if auth.startswith("Bearer ") else None
        return auth[4:] if auth.startswith("Bot ") else None
    if vendor in ("linkup", "perplexity", "scrapingbee"):
        # ScrapingBee: the ``?api_key=`` query form is deprecated upstream, so the
        # fake accepts ONLY the documented Bearer header.
        return auth[7:] if auth.startswith("Bearer ") else None
    if vendor in ("mojeek", "serpapi"):
        return params.get("api_key")
    if vendor in ("youcom", "serper"):
        return headers.get("x-api-key")
    if vendor == "marginalia":
        return headers.get("api-key")
    if vendor == "zenserp":
        return headers.get("apikey")
    if vendor == "dataforseo":
        if not auth.startswith("Basic "):
            return None
        try:
            return base64.b64decode(auth[6:]).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return None
    return None


def _query_text(vendor: str, params: dict[str, str], body) -> str:
    obj = body if isinstance(body, dict) else {}
    if vendor == "kagi":  # v0 enrich: ?q= ; v1 search: JSON {"query": ...}
        return params.get("q") or str(obj.get("query", ""))
    if vendor in ("brave", "mojeek", "serpapi", "zenserp"):
        return params.get("q", "")
    if vendor in ("serper", "linkup"):
        return str(obj.get("q", ""))
    if vendor in ("youcom", "perplexity"):
        return str(obj.get("query", ""))
    if vendor == "marginalia":
        return params.get("query", "")
    if vendor == "scrapingbee":
        return params.get("search", "")
    if vendor == "dataforseo":
        first = body[0] if isinstance(body, list) and body else {}
        return str(first.get("keyword", "")) if isinstance(first, dict) else ""
    return ""


# --------------------------------------------------------------------------- #
# vendor error envelopes (each ECHOES the presented key, on purpose)
# --------------------------------------------------------------------------- #
def _rejected(vendor: str, presented: str) -> tuple[int, dict, dict]:
    if vendor == "brave":
        return (
            401,
            {
                "type": "ErrorResponse",
                "error": {
                    "id": "fake-brave-error",
                    "status": 401,
                    "code": "SUBSCRIPTION_TOKEN_INVALID",
                    "detail": f"Invalid token {presented}",
                    "meta": {"token": presented},
                },
                "time": 1_788_000_000,
            },
            {},
        )
    if vendor == "kagi":
        # v1 errorEnvelope: meta + empty data + error[{code, url, message, location}]
        return (
            401,
            {
                "meta": {"trace": "fake-trace", "node": "fake", "ms": 1},
                "data": [],
                "error": [
                    {
                        "code": "unauthorized",
                        "url": "https://kagi.com/api/docs",
                        "message": f"Invalid API key: {presented}",
                        "location": "header",
                    }
                ],
            },
            {},
        )
    if vendor == "linkup":
        return (
            401,
            {
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": f"Invalid API key {presented}",
                    "details": [],
                }
            },
            {},
        )
    if vendor == "youcom":
        return 401, {"detail": f"Invalid API key: {presented}"}, {}
    if vendor == "perplexity":
        return (
            401,
            {
                "error": {
                    "message": f"Invalid API key {presented}",
                    "type": "invalid_api_key",
                    "code": 401,
                }
            },
            {},
        )
    if vendor == "serper":
        return 403, {"message": f"Unauthorized. Invalid API key: {presented}"}, {}
    if vendor == "serpapi":
        return (
            401,
            {
                "error": (
                    f"Invalid API key ({presented}). Your API key should be here: "
                    "https://serpapi.com/manage-api-key"
                )
            },
            {},
        )
    if vendor == "dataforseo":
        return (
            401,
            {
                "version": "0.1.20260901",
                "status_code": 40100,
                "status_message": (
                    "You are not authorized to access this resource. "
                    f"(credentials {presented})"
                ),
                "time": "0 sec.",
                "cost": 0,
                "tasks_count": 0,
                "tasks_error": 0,
                "tasks": None,
            },
            {},
        )
    if vendor == "zenserp":
        return (
            403,
            {"errors": [{"message": f"Not authenticated: apikey {presented}"}]},
            {},
        )
    return 401, {"message": f"{vendor}: invalid key {presented}"}, {}


# --------------------------------------------------------------------------- #
# happy-path bodies (documented result shapes)
# --------------------------------------------------------------------------- #
def _brave_web(q: str, params: dict[str, str]) -> tuple[dict, dict]:
    headers = {
        "x-ratelimit-limit": "1, 2000",
        "x-ratelimit-remaining": "0, 1999",
        "x-ratelimit-reset": "1, 1419704",
    }
    query = {
        "original": q,
        "show_strict_warning": False,
        "is_navigational": False,
        "more_results_available": True,
        "country": params.get("country", "us"),
    }
    if "empty" in q:
        return {"type": "search", "query": query}, headers
    body = {
        "type": "search",
        "query": query,
        "web": {
            "type": "search",
            "results": [
                {
                    "title": "Brave hit <strong>one</strong>",
                    "url": "https://example.com/one",
                    "is_source_local": False,
                    "is_source_both": False,
                    "description": "First <strong>brave</strong> result &amp; more",
                    "page_age": "2026-08-30T10:00:00",
                    "language": "en",
                    "family_friendly": True,
                    "type": "search_result",
                    "subtype": "generic",
                    "age": "3 days ago",
                    "extra_snippets": ["extra one", "extra two"],
                },
                {
                    "title": "Brave hit two",
                    "url": "https://example.org/two",
                    "description": "Second result",
                    "type": "search_result",
                    "subtype": "generic",
                },
            ],
            "family_friendly": True,
        },
    }
    return body, headers


def _brave_llm(q: str) -> tuple[dict, dict]:
    headers = {"x-ratelimit-remaining": "0, 1998"}
    body = {
        "type": "llm_context",
        "grounding": {
            "generic": [
                {
                    "url": "https://example.com/ctx",
                    "title": f"Context for {q}",
                    "snippets": ["grounding snippet A", "grounding snippet B"],
                },
                {
                    "url": "https://example.org/ctx2",
                    "title": "Second context",
                    "snippets": ["only snippet"],
                },
            ],
            # The docs' "local response": ``poi`` is ONE object, ``map`` a list.
            "poi": {
                "name": "Fake Business",
                "url": "https://business.example/",
                "title": "Title of business.example",
                "snippets": ["Business details"],
            },
            "map": [],
        },
        "sources": {
            "https://example.com/ctx": {"title": "Context", "hostname": "example.com"}
        },
    }
    return body, headers


def _kagi(q: str, sub: str, params: dict[str, str], body_in) -> tuple[dict, dict]:
    if sub == "/api/v1/search":
        # v1 (OpenAPI at kagi.com/api/docs): ``data`` is an object of sections,
        # every item ``{url, title, snippet?, time?, image?, props?}``.
        obj = body_in if isinstance(body_in, dict) else {}
        limit = int(obj.get("limit") or 10)
        search = [
            {
                "url": "https://example.com/kagi-one",
                "title": f"Kagi <b>{q}</b> one",
                "snippet": "Kagi snippet <b>one</b>",
                "time": "2026-08-01T00:00:00Z",
                "props": {"language": "en", "group_id": "example.com"},
            },
            {
                "url": "https://example.org/kagi-two",
                "title": "Kagi two",
                "snippet": "Kagi snippet two",
                "props": {"language": "en", "group_id": "example.org"},
            },
        ][:limit]
        return {
            "meta": {"trace": "fake-kagi-trace", "node": "fake", "ms": 152},
            "data": {
                "search": search,
                "news": [
                    {
                        "url": "https://news.example/kagi",
                        "title": "Kagi news",
                        "snippet": "news snippet",
                        "time": "2026-09-01T00:00:00Z",
                    }
                ],
                "adjacent_question": [
                    {
                        "url": "https://example.net/adjacent",
                        "title": "Kagi adjacent",
                        "snippet": "adjacent snippet",
                        "props": {"question": "what is an mcp server?"},
                    }
                ],
                "related_search": [
                    {"title": "related a", "url": "https://kagi.com/search?q=a"},
                    {"title": "related b", "url": "https://kagi.com/search?q=b"},
                ],
            },
        }, {}
    # v0 Enrich (help.kagi.com/kagi/api/enrich.html): ``data`` is a LIST of
    # ``{t: 0, rank, url, title, snippet, published}``; ``t: 1`` = related list.
    items = [
        {
            "t": 0,
            "rank": 0,
            "url": "https://example.com/kagi-one",
            "title": f"Kagi <b>{q}</b> one",
            "snippet": "Kagi snippet <b>one</b>",
            "published": "2026-08-01T00:00:00Z",
        },
        {
            "t": 0,
            "rank": 1,
            "url": "https://example.org/kagi-two",
            "title": "Kagi two",
            "snippet": "Kagi snippet two",
        },
    ]
    body = {
        "meta": {"id": "fake-kagi", "node": "fake", "ms": 152, "api_balance": 4.87},
        "data": items,
    }
    return body, {}


def _linkup(body_in) -> tuple[dict, dict]:
    obj = body_in if isinstance(body_in, dict) else {}
    if obj.get("outputType") == "sourcedAnswer":
        return {
            "answer": f"Fake answer about {obj.get('q', '')}.",
            "sources": [
                {
                    "name": "Source one",
                    "url": "https://example.com/src1",
                    "snippet": "supporting snippet one",
                },
                {
                    "name": "Source two",
                    "url": "https://example.org/src2",
                    "snippet": "supporting snippet two",
                },
            ],
        }, {}
    return {
        "results": [
            {
                "type": "text",
                "name": "Linkup result one",
                "url": "https://example.com/l1",
                "content": "linkup content one",
            },
            {
                "type": "text",
                "name": "Linkup result two",
                "url": "https://example.org/l2",
                "content": "linkup content two",
            },
        ]
    }, {}


def _mojeek(q: str, params: dict[str, str]) -> tuple[dict, dict]:
    count = int(params.get("t", "10") or 10)
    results = [
        {
            "url": "https://example.com/mj1",
            "title": "Mojeek one",
            "desc": "mojeek description one",
            "mdate": "2026-07-02",
            "cdate": "2025-01-01",
        },
        {
            "url": "https://example.org/mj2",
            "title": "Mojeek two",
            "desc": "mojeek description two",
        },
    ][:count]
    return {
        "response": {
            "status": "OK",
            "head": {
                "query": q,
                "results": len(results),
                "timer": 0.06,
                "totalresults": 1234,
                "start": 1,
                "return": len(results),
            },
            "results": results,
        }
    }, {}


def _youcom(q: str) -> tuple[dict, dict]:
    return {
        "results": {
            "web": [
                {
                    "url": "https://example.com/y1",
                    "title": "You.com web one",
                    "description": "you web description one",
                    "snippets": ["you snippet a", "you snippet b"],
                    "page_age": "2026-08-01T00:00:00",
                },
                {
                    "url": "https://example.org/y2",
                    "title": "You.com web two",
                    "description": "you web description two",
                },
            ],
            "news": [
                {
                    "url": "https://news.example.com/n1",
                    "title": "You.com news one",
                    "description": "news description",
                    "page_age": "2026-09-01T12:00:00",
                }
            ],
        },
        "metadata": {"query": q, "latency": 0.4, "search_uuid": "fake-uuid"},
    }, {}


def _perplexity(q: str, body_in) -> tuple[dict, dict]:
    obj = body_in if isinstance(body_in, dict) else {}
    limit = int(obj.get("max_results") or 10)
    results = [
        {
            "title": "Perplexity one",
            "url": "https://example.com/p1",
            "snippet": f"perplexity snippet about {q}",
            "date": "2026-08-15",
            "last_updated": "2026-08-20",
        },
        {
            "title": "Perplexity two",
            "url": "https://example.org/p2",
            "snippet": "perplexity snippet two",
        },
    ][:limit]
    return {"id": "fake-pplx-request", "results": results}, {}


def _marginalia(q: str) -> tuple[dict, dict]:
    return {
        "license": "CC-BY-SA 4.0",
        "results": [
            {
                "url": "https://example.com/mg1",
                "title": f"Marginalia {q}",
                "description": "small-web description one",
                "quality": 0.7,
            },
            {
                "url": "https://example.org/mg2",
                "title": "Marginalia two",
                "description": "small-web description two",
            },
        ],
    }, {}


def _serper(q: str, body_in) -> tuple[dict, dict]:
    obj = body_in if isinstance(body_in, dict) else {}
    num = int(obj.get("num") or 10)
    return {
        "searchParameters": {"q": q, "type": "search", "num": num, "engine": "google"},
        "organic": [
            {
                "title": "Serper one",
                "link": "https://example.com/s1",
                "snippet": "serper snippet one",
                "date": "Aug 30, 2026",
                "position": 1,
            },
            {
                "title": "Serper two",
                "link": "https://example.org/s2",
                "snippet": "serper snippet two",
                "position": 2,
            },
        ],
        "relatedSearches": [{"query": f"{q} more"}],
        "credits": 2 if num > 10 else 1,
    }, {}


def _serpapi(q: str) -> tuple[dict, dict]:
    meta = {
        "id": "fake-serpapi-id",
        "status": "Success",
        "created_at": "2026-09-02 07:15:00 UTC",
        "total_time_taken": 1.23,
    }
    if "noresults" in q:
        return {
            "search_metadata": meta,
            "search_parameters": {"engine": "google", "q": q},
            "error": "Google hasn't returned any results for this query.",
        }, {}
    return {
        "search_metadata": meta,
        "search_parameters": {
            "engine": "google",
            "q": q,
            "google_domain": "google.com",
        },
        "search_information": {"total_results": 12345, "query_displayed": q},
        "organic_results": [
            {
                "position": 1,
                "title": "SerpApi one",
                "link": "https://example.com/sa1",
                "displayed_link": "example.com › sa1",
                "snippet": "serpapi snippet one",
                "date": "Aug 30, 2026",
            },
            {
                "position": 2,
                "title": "SerpApi two",
                "link": "https://example.org/sa2",
                "snippet": "serpapi snippet two",
            },
        ],
    }, {}


def _dataforseo(q: str, body_in) -> tuple[dict, dict]:
    first = body_in[0] if isinstance(body_in, list) and body_in else {}
    first = first if isinstance(first, dict) else {}
    if "badtask" in q:
        task = {
            "id": "fake-task",
            "status_code": 40501,
            "status_message": "Invalid Field: 'location_code'.",
            "time": "0 sec.",
            "cost": 0,
            "result_count": 0,
            "path": ["v3", "serp", "google", "organic", "live", "advanced"],
            "data": first,
            "result": None,
        }
        return {
            "version": "0.1.20260901",
            "status_code": 20000,
            "status_message": "Ok.",
            "time": "0.1 sec.",
            "cost": 0,
            "tasks_count": 1,
            "tasks_error": 1,
            "tasks": [task],
        }, {}
    items = [
        {
            "type": "organic",
            "rank_group": 1,
            "rank_absolute": 1,
            "title": "DataForSEO one",
            "url": "https://example.com/d1",
            "description": "dataforseo description one",
            "timestamp": "2026-08-30 10:00:00 +00:00",
        },
        {
            "type": "people_also_ask",
            "rank_group": 1,
            "rank_absolute": 2,
            "items": [{"type": "people_also_ask_element", "title": "Why?"}],
        },
        {
            "type": "organic",
            "rank_group": 2,
            "rank_absolute": 3,
            "title": "DataForSEO two",
            "url": "https://example.org/d2",
            "description": "dataforseo description two",
        },
    ]
    return {
        "version": "0.1.20260901",
        "status_code": 20000,
        "status_message": "Ok.",
        "time": "1.2 sec.",
        "cost": 0.002,
        "tasks_count": 1,
        "tasks_error": 0,
        "tasks": [
            {
                "id": "fake-task",
                "status_code": 20000,
                "status_message": "Ok.",
                "time": "1.1 sec.",
                "cost": 0.002,
                "result_count": 1,
                "path": ["v3", "serp", "google", "organic", "live", "advanced"],
                "data": {"api": "serp", "function": "live", "se": "google", **first},
                "result": [
                    {
                        "keyword": q,
                        "type": "organic",
                        "se_domain": "google.com",
                        "location_code": first.get("location_code", 2840),
                        "language_code": first.get("language_code", "en"),
                        "check_url": "https://www.google.com/search?q=fake",
                        "datetime": "2026-09-02 07:15:00 +00:00",
                        "item_types": ["organic", "people_also_ask"],
                        "se_results_count": 987654,
                        "items_count": len(items),
                        "items": items,
                    }
                ],
            }
        ],
    }, {}


def _zenserp(q: str) -> tuple[dict, dict]:
    return {
        "query": {"q": q, "url": "https://www.google.com/search?q=fake"},
        "organic": [
            {
                "position": 1,
                "title": "ZenSerp one",
                "url": "https://example.com/z1",
                "destination": "example.com › z1",
                "description": "zenserp description one",
                "isAmp": False,
            },
            {
                "questions": [
                    {"question": "What is it?", "url": "https://example.net/q"}
                ]
            },
            {
                "position": 2,
                "title": "ZenSerp two",
                "url": "https://example.org/z2",
                "destination": "example.org › z2",
                "description": "zenserp description two",
                "date": "Aug 30, 2026",
            },
        ],
    }, {}


def _scrapingbee(q: str, params: dict[str, str]) -> tuple[dict, dict]:
    # Vendor default is a LIGHT request (10 credits); only an explicit
    # ``light_request=false`` buys the 15-credit regular one.
    light = params.get("light_request", "true").lower() != "false"
    headers = {"spb-cost": "10" if light else "15", "spb-initial-status-code": "200"}
    return {
        "meta_data": {
            "url": "https://www.google.com/search?q=fake",
            "number_of_results": 1234567,
            "number_of_organic_results": 2,
            "number_of_page": int(params.get("page", "1") or 1),
            "location": params.get("country_code", "us"),
        },
        "organic_results": [
            {
                "url": "https://example.com/b1",
                "displayed_url": "https://example.com › b1",
                "description": "scrapingbee description one",
                "position": 1,
                "title": "ScrapingBee one",
                "domain": "example.com",
                "date": "Aug 30, 2026",
            },
            {
                "url": "https://example.org/b2",
                "displayed_url": "https://example.org › b2",
                "description": "scrapingbee description two",
                "position": 2,
                "title": "ScrapingBee two",
                "domain": "example.org",
            },
        ],
        "related_queries": [{"title": f"{q} more", "url": "https://www.google.com/x"}],
        "questions": [],
    }, headers


def _happy(vendor: str, sub: str, q: str, params: dict[str, str], body):
    if vendor == "brave":
        return _brave_llm(q) if sub == "/res/v1/llm/context" else _brave_web(q, params)
    if vendor == "kagi":
        return _kagi(q, sub, params, body)
    if vendor == "linkup":
        return _linkup(body)
    if vendor == "mojeek":
        return _mojeek(q, params)
    if vendor == "youcom":
        return _youcom(q)
    if vendor == "perplexity":
        return _perplexity(q, body)
    if vendor == "marginalia":
        return _marginalia(q)
    if vendor == "serper":
        return _serper(q, body)
    if vendor == "serpapi":
        return _serpapi(q)
    if vendor == "dataforseo":
        return _dataforseo(q, body)
    if vendor == "zenserp":
        return _zenserp(q)
    return _scrapingbee(q, params)


# --------------------------------------------------------------------------- #
# the router
# --------------------------------------------------------------------------- #
def route(
    method: str, path: str, headers: dict[str, str], body: bytes | None = None
) -> tuple[int, object, dict]:
    """Pure router: ``(status, json-payload | raw-text-str | None, headers)``."""
    lowered = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
    split = urlsplit(path)
    params = {k: v[0] for k, v in parse_qs(split.query, keep_blank_values=True).items()}
    parts = split.path.split("/")
    vendor = parts[1] if len(parts) > 1 else ""
    sub = "/" + "/".join(parts[2:])
    parsed_body = None
    if body:
        try:
            parsed_body = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            parsed_body = None
    with _LOCK:
        RECEIVED.append(
            {
                "vendor": vendor,
                "method": method,
                "path": sub,
                "query": params,
                "headers": lowered,
                "body": parsed_body,
                "raw_path": path,
            }
        )
    if vendor not in VALID_KEYS:
        return 404, {"message": f"unknown fake vendor {vendor!r}"}, {}
    if (method, sub) not in ROUTES[vendor]:
        return 404, {"message": f"no route {method} {sub} for {vendor}"}, {}
    presented = presented_key(vendor, lowered, params, sub)
    if presented is None:
        return (
            401,
            {"message": f"{vendor}: no credential at the documented location"},
            {},
        )
    if presented != VALID_KEYS[vendor]:
        return _rejected(vendor, presented)
    q = _query_text(vendor, params, parsed_body)
    if "ratelimited" in q:
        return (
            429,
            {"message": f"{vendor}: rate limit exceeded for this key"},
            {"retry-after": "17", "x-ratelimit-remaining": "0"},
        )
    if "nocredit" in q:
        return (
            402,
            {"message": f"{vendor}: insufficient credit; add a payment method"},
            {},
        )
    if "boom" in q:
        return 500, {"message": "simulated upstream failure"}, {}
    if "notjson" in q:
        return 200, RAW_HTML, {"content-type": "text/html"}
    if "weirdshape" in q:
        return 200, {"unexpected": True}, {}
    payload, resp_headers = _happy(vendor, sub, q, params, parsed_body)
    return 200, payload, resp_headers


def fake_caller(
    method: str, url: str, body: bytes | None, headers: dict, timeout: float
) -> tuple[int, dict | list | None, str, dict[str, str]]:
    """A stdlib-only ``adapters.HeaderCaller`` that never touches the network."""
    split = urlsplit(url)
    path = split.path + (f"?{split.query}" if split.query else "")
    status, payload, resp_headers = route(method, path, headers, body)
    if isinstance(payload, str):  # a non-JSON body
        return status, None, payload, resp_headers
    raw = json.dumps(payload) if payload is not None else ""
    return status, payload, raw, resp_headers


class _Handler(BaseHTTPRequestHandler):
    def _serve(self, method: str) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        status, payload, resp_headers = route(
            method, self.path, dict(self.headers), body
        )
        if isinstance(payload, str):
            raw = payload.encode("utf-8")
            ctype = "text/html; charset=utf-8"
        else:
            raw = json.dumps(payload).encode("utf-8") if payload is not None else b""
            ctype = "application/json; charset=utf-8"
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        for key, value in resp_headers.items():
            if key.lower() != "content-type":
                self.send_header(key, value)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        if raw:
            self.wfile.write(raw)

    def do_GET(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler API)
        self._serve("GET")

    def do_POST(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler API)
        self._serve("POST")

    def log_message(self, *_args) -> None:  # keep the test output quiet
        return


def make_server(port: int = 0) -> HTTPServer:
    return HTTPServer(("127.0.0.1", port), _Handler)


def main(argv: list[str]) -> int:
    port = int(argv[0]) if argv else 0
    server = make_server(port)
    print(f"fake-keyed listening on http://127.0.0.1:{server.server_address[1]}")
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
