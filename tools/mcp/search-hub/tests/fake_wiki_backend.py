#!/usr/bin/env python3
"""Stdlib fake of the three grounding backends for the search-hub ``lane_wiki`` tests.

Wikipedia (``en.wikipedia.org``), the Wayback Machine (``archive.org`` for the
availability API, ``web.archive.org`` for the CDX API) and Hacker News' Algolia
search (``hn.algolia.com``) are external public APIs; this ONE fake stands in for
all four hosts so the adapter is exercised with NO network. The four route
families never collide on path, so a single loopback server can serve every
``*_URL`` the lane reads. The canned shapes mirror what the live endpoints
answered on 2026-09-02 (probe receipts in the search-hub README):

* ``GET /w/api.php?action=query&list=search&srsearch=..&srlimit=N``
  -> MediaWiki ``{batchcomplete, continue, query:{searchinfo:{totalhits,
  suggestion}, search:[{ns,title,pageid,size,wordcount,snippet,timestamp}]}}``;
  the snippet carries ``<span class="searchmatch">`` markup and HTML entities
  exactly as the live API does. ``srsearch`` containing ``ratelimited`` -> 429 +
  ``retry-after``; ``apierror`` -> HTTP 200 with a MediaWiki ``error`` object
  (how the API reports a bad request); ``nohits`` -> zero results.
  ``GET /w/api.php?action=query&meta=siteinfo`` -> the probe route (200).
* ``GET /api/rest_v1/page/summary/{title}`` -> the REST summary
  (``type: standard``); title ``Mercury`` -> ``type: disambiguation``;
  ``Zzqx_No_Such_Page`` -> 404 ``{"status":404,"type":"Internal error"}`` (the
  live 404 body, verbatim); ``Ratelimited_Page`` -> 429; ``Server_Error`` -> 503
  with a text/html body (no JSON).
* ``GET /wayback/available?url=..[&timestamp=..]`` -> ``{url,
  archived_snapshots:{closest:{status,available,url,timestamp}}}``; the request
  ``timestamp`` is echoed back like the live API does; a ``url`` containing
  ``never-archived`` -> ``archived_snapshots: {}`` (HTTP 200: the truthful "no
  capture"); ``boom`` -> 503 text/html.
* ``GET /cdx/search/cdx?url=..&output=json&..`` -> a JSON array of arrays whose
  FIRST row is the header (``fl`` order), rows filtered by ``from``/``to`` (year
  prefix) and capped by ``limit``; ``never-archived`` -> HTTP 200 with the body
  ``[]`` (how JSON mode says "no captures", measured live 2026-09-02: 3 bytes);
  ``never-archived-plain`` -> HTTP 200 with an EMPTY body (how the plain,
  non-JSON mode says it); ``offline`` -> the 503 "Internet Archive: Temporarily
  Offline" text/html page observed live on 2026-09-02.
* ``GET /api/v1/search`` and ``/api/v1/search_by_date`` -> Algolia
  ``{hits, nbHits, page, nbPages, hitsPerPage, query, params}`` with the query
  string echoed in ``params`` (as the live API does); ``tags=comment`` ->
  comment-shaped hits (``story_title``/``story_url``/``comment_text``, no
  title/url/points); ``query`` containing ``ratelimited`` -> 429; ``nohits`` ->
  zero hits.

Every received request's headers are appended to ``RECEIVED`` (lower-cased keys;
call ``reset()`` first) so tests can prove the descriptive ``User-Agent`` reached
the wire. Used as an importable ``fake_caller`` (pure, returns the 4-tuple
``adapters.HeaderCaller`` shape) and as a runnable loopback socket server.
"""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, unquote

RECEIVED: list[dict[str, str]] = []
_LOCK = threading.Lock()

# The live 503 page (2026-09-02, 11.8 KB) minus its base64 logos: the <style>
# block is kept because its CSS must NOT leak into the relayed error text.
OFFLINE_HTML = (
    '<html><head><meta charset="UTF-8"><title>Internet Archive: Temporarily '
    "Offline</title><style>p{font-size:24px;}img{margin-bottom:2rem;}</style>"
    '</head><body style="padding:30px 0;"><h1 style="margin-top:0">Temporarily '
    "Offline</h1><p>Internet Archive services are temporarily offline.</p>"
    "<p>We apologize for the inconvenience.</p></body></html>"
)

WIKI_SEARCH_HITS = [
    {
        "ns": 0,
        "title": "Model Context Protocol",
        "pageid": 79706999,
        "size": 17254,
        "wordcount": 1566,
        "snippet": (
            'The <span class="searchmatch">Model</span> <span class="searchmatch">'
            'Context</span> <span class="searchmatch">Protocol</span> (MCP) is an '
            "open standard &amp; open-source framework introduced by Anthropic"
        ),
        "timestamp": "2026-08-25T15:33:43Z",
    },
    {
        "ns": 0,
        "title": "OpenAI Codex (AI agent)",
        "pageid": 82664001,
        "size": 24663,
        "wordcount": 2154,
        "snippet": (
            "integration that let users move between Figma and Codex through "
            'Figma&#039;s <span class="searchmatch">Model</span> <span class='
            '"searchmatch">Context</span> <span class="searchmatch">Protocol'
            "</span> server, &quot;connecting&quot; design and code"
        ),
        "timestamp": "2026-08-29T05:13:45Z",
    },
    {
        "ns": 0,
        "title": "Anthropic",
        "pageid": 72248594,
        "size": 90000,
        "wordcount": 8000,
        "snippet": "Anthropic PBC is an American artificial intelligence company",
        "timestamp": "2026-08-30T00:00:00Z",
    },
]

WIKI_SUMMARIES = {
    "Model_Context_Protocol": {
        "type": "standard",
        "title": "Model Context Protocol",
        "displaytitle": '<span class="mw-page-title-main">Model Context Protocol</span>',
        "namespace": {"id": 0, "text": ""},
        "wikibase_item": "Q131396478",
        "titles": {
            "canonical": "Model_Context_Protocol",
            "normalized": "Model Context Protocol",
            "display": "Model Context Protocol",
        },
        "pageid": 79706999,
        "thumbnail": {
            "source": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/fe/MCP.png",
            "width": 330,
            "height": 330,
        },
        "originalimage": {
            "source": "https://upload.wikimedia.org/wikipedia/commons/f/fe/MCP.svg",
            "width": 512,
            "height": 512,
        },
        "lang": "en",
        "dir": "ltr",
        "revision": "1308765432",
        "tid": "00000000-0000-0000-0000-000000000000",
        "timestamp": "2026-08-25T15:33:43Z",
        "description": "Protocol for communicating between LLMs and applications",
        "description_source": "local",
        "content_urls": {
            "desktop": {
                "page": "https://en.wikipedia.org/wiki/Model_Context_Protocol",
                "revisions": "https://en.wikipedia.org/wiki/Model_Context_Protocol?action=history",
                "edit": "https://en.wikipedia.org/wiki/Model_Context_Protocol?action=edit",
                "talk": "https://en.wikipedia.org/wiki/Talk:Model_Context_Protocol",
            },
            "mobile": {
                "page": "https://en.m.wikipedia.org/wiki/Model_Context_Protocol",
                "revisions": "https://en.m.wikipedia.org/wiki/Special:History/Model_Context_Protocol",
                "edit": "https://en.m.wikipedia.org/wiki/Model_Context_Protocol?action=edit",
                "talk": "https://en.m.wikipedia.org/wiki/Talk:Model_Context_Protocol",
            },
        },
        "extract": (
            "The Model Context Protocol (MCP) is an open standard and open-source "
            "framework introduced by Anthropic in November 2024 to standardize the "
            "way artificial intelligence systems integrate with external tools."
        ),
        "extract_html": (
            "<p>The <b>Model Context Protocol</b> (<b>MCP</b>) is an open standard "
            "and open-source framework introduced by Anthropic in November 2024.</p>"
        ),
    },
    "Mercury": {
        "type": "disambiguation",
        "title": "Mercury",
        "displaytitle": '<span class="mw-page-title-main">Mercury</span>',
        "namespace": {"id": 0, "text": ""},
        "titles": {
            "canonical": "Mercury",
            "normalized": "Mercury",
            "display": "Mercury",
        },
        "pageid": 19007,
        "lang": "en",
        "dir": "ltr",
        "revision": "1300000000",
        "tid": "11111111-1111-1111-1111-111111111111",
        "timestamp": "2026-07-01T00:00:00Z",
        "description": "Topics referred to by the same term",
        "description_source": "local",
        "content_urls": {
            "desktop": {"page": "https://en.wikipedia.org/wiki/Mercury"},
            "mobile": {"page": "https://en.m.wikipedia.org/wiki/Mercury"},
        },
        "extract": (
            "Mercury most commonly refers to:Mercury (planet), the closest planet "
            "to the Sun\nMercury (element), a chemical element\nMercury (mythology), "
            "a Roman deity"
        ),
        "extract_html": "<p>Mercury most commonly refers to:</p>",
    },
}

CDX_HEADER = ["timestamp", "original", "statuscode", "mimetype"]
CDX_ROWS = [
    ["20150315120000", "http://example.com/", "200", "text/html"],
    ["20200101231047", "https://example.com/", "200", "text/html"],
    ["20260902040541", "https://example.com/", "200", "text/html"],
]

HN_STORY_HITS = [
    {
        "_highlightResult": {},
        "_tags": ["story", "author_benocodes", "story_42237424"],
        "author": "benocodes",
        "children": [42237600, 42237601],
        "created_at": "2024-11-25T16:14:22Z",
        "created_at_i": 1732551262,
        "num_comments": 258,
        "objectID": "42237424",
        "points": 872,
        "story_id": 42237424,
        "title": "Model Context Protocol",
        "updated_at": "2026-08-01T00:00:00Z",
        "url": "https://www.anthropic.com/news/model-context-protocol",
    },
    {
        "_highlightResult": {},
        "_tags": ["story", "author_someone", "story_43000000"],
        "author": "someone",
        "children": [],
        "created_at": "2025-03-01T10:00:00Z",
        "created_at_i": 1740823200,
        "num_comments": 12,
        "objectID": "43000000",
        "points": 40,
        "story_id": 43000000,
        "title": "Ask HN: Which MCP servers do you actually use?",
        "updated_at": "2025-03-02T00:00:00Z",
        "url": None,
    },
    {
        "_highlightResult": {},
        "_tags": ["story", "author_third", "story_44000000"],
        "author": "third",
        "children": [],
        "created_at": "2026-09-02T06:28:48Z",
        "created_at_i": 1788676128,
        "num_comments": 3,
        "objectID": "44000000",
        "points": 5,
        "story_id": 44000000,
        "title": "Fresh MCP story",
        "updated_at": "2026-09-02T06:30:00Z",
        "url": "https://example.com/fresh",
    },
]

HN_COMMENT_HIT = {
    "_highlightResult": {},
    "_tags": ["comment", "author_eslaught", "story_9998140"],
    "author": "eslaught",
    "children": [],
    "comment_text": "The issue is not having the type info available.",
    "created_at": "2015-07-31T00:00:00Z",
    "created_at_i": 1438300800,
    "objectID": "9999959",
    "parent_id": 9998140,
    "story_id": 9998140,
    "story_title": "LLVM for Grad Students",
    "story_url": "http://adriansampson.net/blog/llvm.html",
    "updated_at": "2015-08-01T00:00:00Z",
}


def reset() -> None:
    with _LOCK:
        RECEIVED.clear()


def _params(query: str) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(query, keep_blank_values=True).items()}


def _json_headers() -> dict[str, str]:
    return {"content-type": "application/json; charset=utf-8"}


def _html_503() -> tuple[int, object, dict]:
    return 503, OFFLINE_HTML, {"content-type": "text/html"}


def _wikipedia_api(params: dict[str, str]) -> tuple[int, object, dict]:
    if params.get("meta") == "siteinfo":
        body = {
            "batchcomplete": "",
            "query": {"general": {"sitename": "Wikipedia", "lang": "en"}},
        }
        return 200, body, _json_headers()
    if params.get("list") != "search":
        body = {
            "error": {
                "code": "badvalue",
                "info": "Unrecognized value for parameter list.",
            }
        }
        return 200, body, _json_headers()
    srsearch = unquote(params.get("srsearch", ""))
    if "ratelimited" in srsearch:
        body = {"error": {"code": "ratelimited", "info": "Too many requests."}}
        hdrs = _json_headers()
        hdrs["retry-after"] = "5"
        return 429, body, hdrs
    if "apierror" in srsearch or not srsearch:
        body = {
            "error": {
                "code": "missingparam",
                "info": 'The "srsearch" parameter must be set.',
                "*": "See https://en.wikipedia.org/w/api.php for API usage.",
            },
            "servedby": "mw-api-ext.fake",
        }
        return 200, body, _json_headers()
    try:
        limit = int(params.get("srlimit", "10"))
    except ValueError:
        limit = 10
    hits = [] if "nohits" in srsearch else WIKI_SEARCH_HITS[: max(limit, 0)]
    body = {
        "batchcomplete": "",
        "continue": {"sroffset": len(hits), "continue": "-||"},
        "query": {
            "searchinfo": {
                "totalhits": 0 if not hits else 4054,
                "suggestion": "model content protocol",
                "suggestionsnippet": "model content protocol",
            },
            "search": hits,
        },
    }
    return 200, body, _json_headers()


def _wikipedia_summary(title: str) -> tuple[int, object, dict]:
    if title == "Zzqx_No_Such_Page":
        return 404, {"status": 404, "type": "Internal error"}, _json_headers()
    if title == "Ratelimited_Page":
        hdrs = _json_headers()
        hdrs["retry-after"] = "7"
        return 429, {"status": 429, "type": "Too many requests"}, hdrs
    if title == "Server_Error":
        return _html_503()
    if title in WIKI_SUMMARIES:
        return 200, WIKI_SUMMARIES[title], _json_headers()
    return 404, {"status": 404, "type": "Internal error"}, _json_headers()


def _wayback_available(params: dict[str, str]) -> tuple[int, object, dict]:
    url = params.get("url", "")
    if "boom" in url:
        return _html_503()
    body: dict = {"url": url}
    if "never-archived" in url:
        body["archived_snapshots"] = {}
    else:
        stamp = params.get("timestamp") or "20260902040541"
        stamp = (stamp + "000000000000")[:14] if len(stamp) < 14 else stamp
        body["archived_snapshots"] = {
            "closest": {
                "status": "200",
                "available": True,
                "url": f"http://web.archive.org/web/{stamp}/https://example.com/",
                "timestamp": stamp,
            }
        }
    if params.get("timestamp"):
        body["timestamp"] = params["timestamp"]
    return 200, body, _json_headers()


def _cdx(params: dict[str, str]) -> tuple[int, object, dict]:
    url = params.get("url", "")
    if "offline" in url:
        return _html_503()
    if "never-archived-plain" in url:
        return 200, None, {"content-type": "text/plain"}  # plain mode: EMPTY body
    if "never-archived" in url:
        return 200, [], _json_headers()  # JSON mode: [] (measured 2026-09-02)
    rows = list(CDX_ROWS)
    since, until = params.get("from", ""), params.get("to", "")
    if since:
        rows = [r for r in rows if r[0][: len(since)] >= since]
    if until:
        rows = [r for r in rows if r[0][: len(until)] <= until]
    try:
        limit = int(params.get("limit", "0"))
    except ValueError:
        limit = 0
    if limit > 0:
        rows = rows[:limit]
    fields = [f for f in params.get("fl", ",".join(CDX_HEADER)).split(",") if f]
    index = {name: i for i, name in enumerate(CDX_HEADER)}
    header = [f for f in fields if f in index]
    payload = [header] + [[row[index[f]] for f in header] for row in rows]
    return 200, payload, _json_headers()


def _hn(route: str, params: dict[str, str], query: str) -> tuple[int, object, dict]:
    q = params.get("query", "")
    if "ratelimited" in q:
        return 429, {"message": "Too many requests", "status": 429}, _json_headers()
    try:
        per_page = int(params.get("hitsPerPage", "20"))
    except ValueError:
        per_page = 20
    tags = params.get("tags", "story")
    if "nohits" in q:
        hits: list[dict] = []
    elif "comment" in tags:
        hits = [HN_COMMENT_HIT]
    else:
        hits = list(HN_STORY_HITS)
        if route == "search_by_date":
            hits.sort(key=lambda h: h["created_at"], reverse=True)
    hits = hits[: max(per_page, 0)]
    body = {
        "exhaustive": {"nbHits": True, "typo": True},
        "exhaustiveNbHits": True,
        "exhaustiveTypo": True,
        "hits": hits,
        "hitsPerPage": per_page,
        "nbHits": len(hits) if not hits else 660,
        "nbPages": 0 if not hits else 330,
        "page": 0,
        "params": query,
        "processingTimeMS": 3,
        "query": q,
        "serverTimeMS": 1,
    }
    return 200, body, _json_headers()


def route(method: str, path: str, headers: dict[str, str]) -> tuple[int, object, dict]:
    """Pure router: (status, payload, response headers).

    ``payload`` is a JSON-able object, a ``str`` (served verbatim as text/html),
    or ``None`` (an EMPTY body -- the CDX "no captures" case).
    """
    lowered = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
    with _LOCK:
        RECEIVED.append(lowered)
    query = ""
    if "?" in path:
        path, query = path.split("?", 1)
    params = _params(query)
    if method != "GET":
        return 405, {"message": "method not allowed"}, _json_headers()
    if path == "/w/api.php":
        return _wikipedia_api(params)
    if path.startswith("/api/rest_v1/page/summary/"):
        return _wikipedia_summary(unquote(path.rsplit("/", 1)[1]))
    if path == "/wayback/available":
        return _wayback_available(params)
    if path == "/cdx/search/cdx":
        return _cdx(params)
    if path in ("/api/v1/search", "/api/v1/search_by_date"):
        return _hn(path.rsplit("/", 1)[1], params, query)
    return 404, {"message": "Not Found", "path": path}, _json_headers()


def _encode(payload) -> tuple[bytes, object]:
    """(raw bytes, parsed-or-None) for a routed payload."""
    if payload is None:
        return b"", None
    if isinstance(payload, str):
        return payload.encode("utf-8"), None
    return json.dumps(payload).encode("utf-8"), payload


def fake_caller(
    method: str, url: str, body: bytes | None, headers: dict, timeout: float
) -> tuple[int, dict | list | None, str, dict[str, str]]:
    """A stdlib-only ``adapters.HeaderCaller`` that never touches the network."""
    tail = url.split("://", 1)[-1]
    path = tail[tail.find("/") :] if "/" in tail else "/"
    status, payload, resp_headers = route(method, path, headers)
    raw, parsed = _encode(payload)
    return status, parsed, raw.decode("utf-8"), resp_headers


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler API)
        status, payload, resp_headers = route("GET", self.path, dict(self.headers))
        raw, _parsed = _encode(payload)
        self.send_response(status)
        for key, value in resp_headers.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        if raw:
            self.wfile.write(raw)

    def log_message(self, *_args) -> None:  # keep the test output quiet
        return


def main(argv: list[str]) -> int:
    port = int(argv[0]) if argv else 0
    server = HTTPServer(("127.0.0.1", port), _Handler)
    print(f"fake-grounding listening on http://127.0.0.1:{server.server_address[1]}")
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
