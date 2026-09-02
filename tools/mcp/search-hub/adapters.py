#!/usr/bin/env python3
"""Self-hosted, key-free search adapters for the search-hub multiplexer.

The four providers in ``providers.py`` are *hosted* APIs fronted by their own
stdio MCP servers (Exa/Tavily/Firecrawl) plus keyless SearXNG. This module adds
the SELF-HOSTED lane: a search backend the owner runs themselves (no vendor key,
no cloud dependency), fronted **in-process over HTTP** rather than by spawning a
child. That is the RAM win -- the adapter is pure stdlib (``json`` + ``urllib``,
already imported by ``usage.py``), so it adds **no** new process and **no** new
import to the running hub, and the heavy daemon it talks to is started on demand.

The first adapter targets **TrailSearch** (github ``jianjungki/tavily-open``),
which serves native Tavily-shaped ``POST /tavily/search`` and ``POST
/tavily/extract`` routes over SearXNG + a local SQLite index. Because the routes
are already Tavily-shaped, the adapter is a thin shape-preserving bridge; a
different backend (fastCRW's ``/v1/search``, OrioSearch's ``/search``) would be
wired as an ``emulated`` translation instead -- see the capability lattice below.

Two keyless PUBLIC-API siblings ride the same mechanism (in-process stdlib HTTP,
same lattice, same truthful degradation) and are wired DEFAULT ON with an env
kill switch each: ``GitHubSearchAdapter`` (``github_*``, first-party GitHub REST
search -- the "new & hot" repo ranking OSSInsight lost; ``ENABLE_GITHUB_SEARCH=0``
disables) and ``ReadUrlAdapter`` (``read_url``, a fetch that negotiates
Cloudflare's ``Accept: text/markdown`` and falls back to a stdlib tag-stripper;
``ENABLE_READ_URL=0`` disables). Both are ~0 MB: no child, no new dependency.

Capability lattice (the honesty contract -- never fake a result)
----------------------------------------------------------------
Every tool resolves to exactly one state, most-confident first:

* ``native``   -- the backend implements this tool's exact contract (TrailSearch
  ``/tavily/*`` IS the Tavily contract), known from the backend KIND. Reported
  when configured but not yet confirmed live this session.
* ``probed``   -- a live health probe THIS SESSION confirmed the backend answers.
  Strongest signal; carries ``realized_by`` = native|emulated underneath.
* ``declared`` -- present only from committed config/cache; backend kind gives no
  contract guarantee and no probe has run.
* ``emulated`` -- realized by translating a DIFFERENTLY-shaped backend endpoint
  (a non-Tavily backend), not confirmed live.
* ``absent``   -- no base URL configured, or a probe found the backend
  unreachable / unhealthy. A ``tools/call`` returns a truthful ``isError`` and
  **never** fabricates results.

``capabilities(probe=False)`` is the RAM-cheap default used to answer
``tools/list``/``search_usage`` with zero network; ``probe=True`` performs one
GET and upgrades the state to ``probed``/``absent`` from live evidence.
"""

from __future__ import annotations

import http.client
import ipaddress
import json
import os
import re
import socket
import time
import urllib.error
import urllib.request
import zlib
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from typing import Callable
from urllib.parse import quote, urlencode, urljoin, urlsplit, urlunsplit

# The onions-lane envelope guard (same directory; every importer of this module
# already puts the hub dir on sys.path, exactly as hub.py does for ``onions``).
import onions

# The lattice vocabulary, ordered most-confident-realized to least-available.
NATIVE = "native"
PROBED = "probed"
DECLARED = "declared"
EMULATED = "emulated"
ABSENT = "absent"
LATTICE = (NATIVE, PROBED, DECLARED, EMULATED, ABSENT)

DEFAULT_TIMEOUT = 30.0
PROBE_TIMEOUT = 5.0

# caller(method, url, body, headers, timeout) -> (status, parsed_json_or_None, raw)
# Injected in tests; the default uses stdlib urllib and never raises.
Caller = Callable[
    [str, str, "bytes | None", "dict[str, str]", float],
    "tuple[int, dict | list | None, str]",
]
# header_caller(...) -> (status, parsed_json_or_None, raw, response_headers)
# The same contract plus the response headers (keys lower-cased), for backends
# whose truthful degradation lives in headers (GitHub's ``x-ratelimit-*``).
HeaderCaller = Callable[
    [str, str, "bytes | None", "dict[str, str]", float],
    "tuple[int, dict | list | None, str, dict[str, str]]",
]


def _default_header_caller(
    method: str, url: str, body: bytes | None, headers: dict[str, str], timeout: float
) -> tuple[int, dict | list | None, str, dict[str, str]]:
    """Real HTTP call returning (status, parsed-json-or-None, raw-body, headers).

    A transport failure (backend down, DNS, reset, timeout) comes back as
    ``(0, None, "<reason>", {})`` so the caller can degrade truthfully rather
    than raise -- a backend being off must never crash the hub. Response header
    keys are lower-cased so callers can read ``x-ratelimit-*`` predictably.
    """
    req = urllib.request.Request(  # noqa: S310 (loopback/http backend by config)
        url, data=body, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            status = resp.getcode() or 0
            resp_headers = {k.lower(): v for k, v in resp.headers.items()}
            raw = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        status = exc.code
        resp_headers = {k.lower(): v for k, v in (exc.headers or {}).items()}
        raw = exc.read().decode("utf-8", "replace") if exc.fp else ""
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return 0, None, f"request failed: {exc}", {}
    try:
        return status, json.loads(raw), raw, resp_headers
    except (json.JSONDecodeError, ValueError):
        return status, None, raw, resp_headers


def _default_caller(
    method: str, url: str, body: bytes | None, headers: dict[str, str], timeout: float
) -> tuple[int, dict | list | None, str]:
    """Real HTTP call returning (status, parsed-json-or-None, raw-body). Safe.

    The historical 3-tuple ``Caller`` shape; delegates to the header-aware
    caller and drops the headers.
    """
    status, parsed, raw, _headers = _default_header_caller(
        method, url, body, headers, timeout
    )
    return status, parsed, raw


@dataclass
class AdapterTool:
    """One tool the adapter exposes, plus how it is realized against the backend."""

    name: str
    description: str
    input_schema: dict
    path: str  # backend route this tool hits (e.g. "/tavily/search")
    realized_by: str = (
        NATIVE  # NATIVE if the backend route IS this shape, else EMULATED
    )
    method: str = "POST"  # HTTP verb; GET tools template the path from arguments

    def definition(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


class SelfHostedAdapter:
    """Base class: an in-process, HTTP-backed, keyless search provider.

    Subclasses declare ``platform``/``label``/``prefix``, the backend ``kind``
    (whether its routes are natively this shape or need emulation), the tool set,
    and the request/response translation. The base owns the capability lattice,
    the health probe, and the truthful-degradation ``handle_call`` envelope.
    """

    platform = "selfhosted"
    label = "Self-Hosted Search"
    prefix = "sh"
    kind = "native"  # "native" => backend routes match the tool shape; else "emulated"
    health_path = "/docs"  # a cheap GET that a healthy backend answers 2xx/3xx
    error_tag = "self-hosted"  # the ``[search-hub:<tag>]`` prefix on isError texts

    def __init__(self, base_url: str, caller: Caller | None = None) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self._caller = caller or _default_caller
        self._tools: list[AdapterTool] = self._build_tools()

    # ---- subclass hooks -------------------------------------------------
    def _build_tools(self) -> list[AdapterTool]:  # pragma: no cover - overridden
        return []

    def _build_request(self, tool: AdapterTool, arguments: dict) -> dict:
        """Translate MCP tool arguments into the backend's request body."""
        return dict(arguments or {})

    # ---- advertised surface --------------------------------------------
    def tools(self) -> list[AdapterTool]:
        return list(self._tools)

    def tool_defs(self) -> list[dict]:
        return [t.definition() for t in self._tools]

    def tool_names(self) -> list[str]:
        return [t.name for t in self._tools]

    def _tool(self, name: str) -> AdapterTool | None:
        for tool in self._tools:
            if tool.name == name:
                return tool
        return None

    def owns(self, name: str) -> bool:
        return self._tool(name) is not None

    # ---- capability lattice --------------------------------------------
    def _resolved_state(self, tool: AdapterTool, probe_ok: bool | None) -> str:
        """Resolve one tool to a single lattice state (see module docstring)."""
        if not self.base_url:
            return ABSENT
        if probe_ok is False:
            return ABSENT
        if probe_ok is True:
            return PROBED
        # No probe this call: report the declared confidence from the backend kind.
        if tool.realized_by == EMULATED or self.kind == "emulated":
            return EMULATED
        if self.kind == "native":
            return NATIVE
        return DECLARED

    def probe(self) -> tuple[bool, str]:
        """One GET against ``health_path``: (reachable, human note). Never raises."""
        if not self.base_url:
            return False, "no base URL configured"
        status, _body, raw = self._caller(
            "GET", self.base_url + self.health_path, None, {}, PROBE_TIMEOUT
        )
        if status == 0:
            return False, raw or "unreachable"
        if 200 <= status < 400:
            return True, f"HTTP {status}"
        return False, f"HTTP {status}: {raw[:120]}"

    def capabilities(self, probe: bool = False) -> dict:
        """Per-tool lattice report. ``probe=False`` (default) does NO network."""
        probe_ok: bool | None = None
        note = "not probed (config-declared)"
        if probe:
            reachable, note = self.probe()
            probe_ok = reachable
        tools = []
        for tool in self._tools:
            tools.append(
                {
                    "tool": tool.name,
                    "state": self._resolved_state(tool, probe_ok),
                    "realized_by": tool.realized_by,
                    "backend_path": tool.path,
                    "note": note,
                }
            )
        return {
            "provider": self.platform,
            "label": self.label,
            "keyless": True,
            "self_hosted": True,
            "base_url": self.base_url or None,
            "backend_kind": self.kind,
            "probed": bool(probe),
            "tools": tools,
        }

    # ---- request preparation hooks --------------------------------------
    def _prepare(
        self, tool: AdapterTool, arguments: dict
    ) -> tuple[str, str, bytes | None, dict]:
        """Build (method, url, body, headers) for a call. May raise ValueError on
        bad arguments (turned into a truthful error by ``handle_call``).

        Default: POST the JSON body from ``_build_request`` to ``base_url + path``
        -- the shape every native Tavily-style backend uses. GET backends
        (OSSInsight) override this to template the path + query.
        """
        body = json.dumps(self._build_request(tool, arguments or {})).encode("utf-8")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        return tool.method, self.base_url + tool.path, body, headers

    def _postprocess(self, tool: AdapterTool, arguments: dict, parsed):
        """Optional local shaping of a 200 payload (e.g. a name filter). Never
        fabricates data -- it only trims/relabels what the backend returned."""
        return parsed

    # ---- the call path (always truthful) --------------------------------
    def handle_call(self, name: str, arguments: dict) -> dict:
        """Forward a tools/call to the backend; return an MCP result dict.

        On ANY failure (not configured, bad args, transport error, non-2xx) it
        returns an ``isError`` result with a readable reason -- it never
        fabricates a hit.
        """
        tool = self._tool(name)
        if tool is None:
            return self._error(f"unknown self-hosted tool {name!r}")
        if not self.base_url:
            return self._error(
                f"no self-hosted backend configured: set the base URL "
                f"(default env for {self.label}) then start the daemon; "
                f"{name} stays absent until it answers."
            )
        try:
            method, url, body, headers = self._prepare(tool, arguments or {})
        except ValueError as exc:
            return self._error(str(exc))
        status, parsed, raw = self._caller(method, url, body, headers, DEFAULT_TIMEOUT)
        if status == 0:
            return self._error(
                f"{self.label} backend at {self.base_url} not reachable ({raw}); "
                f"start the daemon or point the base URL at a running instance. "
                f"No results are fabricated."
            )
        if not (200 <= status < 300) or parsed is None:
            detail = raw[:300] if raw else "(empty body)"
            return self._error(
                f"{self.label} backend returned HTTP {status} for {tool.path}: {detail}"
            )
        return self._ok(self._postprocess(tool, arguments or {}, parsed))

    # ---- MCP result envelopes ------------------------------------------
    def _ok(self, payload) -> dict:
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(payload, ensure_ascii=False, indent=2),
                }
            ],
            "isError": False,
        }

    def _error(self, text: str) -> dict:
        return {
            "content": [
                {"type": "text", "text": f"[search-hub:{self.error_tag}] {text}"}
            ],
            "isError": True,
        }


def _int_arg(
    args: dict, field: str, default: int, lo: int, hi: int | None, tag: str
) -> int:
    """Read an optional integer argument with bounds; ValueError names the field.

    Accepts ints, integral floats and digit strings (MCP clients differ); rejects
    bools and anything else. Validation happens BEFORE any request is spent, so a
    bad argument never costs a rate-limited call.
    """
    value = args.get(field, default)
    if value is None or value == "":
        value = default
    if isinstance(value, bool):
        value = None
    elif isinstance(value, float) and value.is_integer():
        value = int(value)
    elif isinstance(value, str):
        value = int(value.strip()) if value.strip().lstrip("-").isdigit() else None
    if not isinstance(value, int) or value < lo or (hi is not None and value > hi):
        span = f"between {lo} and {hi}" if hi is not None else f">= {lo}"
        raise ValueError(f"{tag}: '{field}' must be an integer {span}")
    return value


# --------------------------------------------------------------------------- #
# TrailSearch -- native Tavily-shaped self-hosted backend
# --------------------------------------------------------------------------- #
_SEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "the search query"},
        "max_results": {
            "type": "integer",
            "minimum": 1,
            "maximum": 20,
            "default": 5,
            "description": "how many results to return (1-20)",
        },
        "mode": {
            "type": "string",
            "enum": ["crawl", "search"],
            "default": "crawl",
            "description": "'search' = provider hits only; 'crawl' = also extract page content",
        },
        "search_depth": {
            "type": "string",
            "enum": ["basic", "advanced"],
            "default": "basic",
        },
        "include_answer": {"type": "boolean", "default": False},
        "include_raw_content": {"type": "boolean", "default": False},
        "chunks_per_source": {
            "type": "integer",
            "minimum": 0,
            "maximum": 8,
            "default": 0,
        },
        "include_domains": {"type": "array", "items": {"type": "string"}},
        "exclude_domains": {"type": "array", "items": {"type": "string"}},
        "topic": {
            "type": "string",
            "description": "general | news | academic | code | ...",
        },
        "days": {
            "type": "integer",
            "description": "time filter in days (1=day,7=week,...)",
        },
    },
    "required": ["query"],
}

_EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "urls": {
            "type": "array",
            "items": {"type": "string"},
            "description": "URLs to extract clean content from",
        },
        "query": {
            "type": "string",
            "default": "",
            "description": "optional relevance query",
        },
        "include_raw_content": {"type": "boolean", "default": True},
        "chunks_per_source": {
            "type": "integer",
            "minimum": 0,
            "maximum": 8,
            "default": 0,
        },
    },
    "required": ["urls"],
}

# Whitelisted argument passthrough per route -- the backend ignores unknown keys,
# but pinning the set keeps the emitted body predictable and testable.
_SEARCH_KEYS = (
    "query",
    "max_results",
    "mode",
    "search_depth",
    "include_answer",
    "include_raw_content",
    "chunks_per_source",
    "include_domains",
    "exclude_domains",
    "topic",
    "days",
)
_EXTRACT_KEYS = ("urls", "query", "include_raw_content", "chunks_per_source")


class TrailSearchAdapter(SelfHostedAdapter):
    """Front TrailSearch's native Tavily-shaped ``/tavily/search`` + ``/tavily/extract``.

    Keyless and self-hosted: the base URL points at the owner's TrailSearch app
    (default ``http://127.0.0.1:8794``, overridable by ``TRAILSEARCH_URL`` /
    ``SELFHOSTED_SEARCH_URL``). Tool names are prefixed ``selfhosted_`` so they
    never collide with the keyed ``tavily_*`` provider; both can coexist and a
    caller picks the keyless lane when it wants no vendor dependency.
    """

    platform = "selfhosted"
    label = "TrailSearch (self-hosted)"
    prefix = "sh"
    kind = "native"  # /tavily/* IS the Tavily contract -> native, not emulated
    health_path = "/docs"  # FastAPI serves Swagger UI here (200 when healthy)

    def _build_tools(self) -> list[AdapterTool]:
        return [
            AdapterTool(
                name="selfhosted_search",
                description=(
                    "Keyless, self-hosted web search + content extraction (Tavily-shaped) "
                    "via a local TrailSearch daemon over SearXNG. Returns "
                    "query/answer/results[title,url,content,score]/failed_results. Use this "
                    "when you want search with NO vendor API key or cloud dependency. Returns "
                    "a truthful error (never fabricated hits) if the daemon is not running."
                ),
                input_schema=_SEARCH_SCHEMA,
                path="/tavily/search",
                realized_by=NATIVE,
            ),
            AdapterTool(
                name="selfhosted_extract",
                description=(
                    "Keyless, self-hosted clean-content extraction (Tavily-shaped) for known "
                    "URLs via the local TrailSearch daemon. Returns "
                    "results[url,content]/failed_results. Truthful error if the daemon is down."
                ),
                input_schema=_EXTRACT_SCHEMA,
                path="/tavily/extract",
                realized_by=NATIVE,
            ),
        ]

    def _build_request(self, tool: AdapterTool, arguments: dict) -> dict:
        keys = _SEARCH_KEYS if tool.name == "selfhosted_search" else _EXTRACT_KEYS
        body = {k: arguments[k] for k in keys if k in arguments}
        if tool.name == "selfhosted_search" and "query" not in body:
            body["query"] = ""
        if tool.name == "selfhosted_extract" and "urls" not in body:
            body["urls"] = []
        return body


# Env vars that carry the self-hosted base URL (config, NOT a secret).
_URL_ENVS = ("TRAILSEARCH_URL", "SELFHOSTED_SEARCH_URL")
DEFAULT_TRAILSEARCH_URL = "http://127.0.0.1:8794"


def resolve_base_url(environ) -> str:
    for name in _URL_ENVS:
        value = (environ.get(name) or "").strip()
        if value:
            return value
    return DEFAULT_TRAILSEARCH_URL


# --------------------------------------------------------------------------- #
# OSSInsight -- keyless repo-discovery over the PUBLIC OSSInsight API
# --------------------------------------------------------------------------- #
# Endpoint verification 2026-09-02 (see the decision record): the public API is
# PARTIALLY degraded. Live HTTP 200, data-bearing:
#   * GET /gh/repo/{owner}/{repo}      -> a GitHub repo object (stars/forks/lang/...)
#   * GET /v1/collections/             -> {data:{rows:[{id,name}, ...138]}}
# Degraded but truthful (200 with a data_quality:"unavailable" block since
# 2026-03-01, event-firehose starvation):
#   * GET /v1/collections/{id}/ranking_by_{stars|prs}/  (rows empty; note relayed)
# Broken (HTTP 500, NOT used): /v1/repos/{owner}/{repo}, /v1/collections/{id}/.
# We build ONLY on endpoints we personally received a 200 from and pass the
# API's own data_quality through verbatim -- never fabricated.
_OSSINSIGHT_REPO_SCHEMA = {
    "type": "object",
    "properties": {
        "owner": {"type": "string", "description": "GitHub owner/org, e.g. 'pingcap'"},
        "repo": {"type": "string", "description": "GitHub repo name, e.g. 'tidb'"},
    },
    "required": ["owner", "repo"],
}
_OSSINSIGHT_SEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "keyword": {
            "type": "string",
            "description": "repo-name keyword to search, e.g. 'vector database'",
        }
    },
    "required": ["keyword"],
}
_OSSINSIGHT_COLLECTIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "optional case-insensitive substring filter over collection names",
        }
    },
}
_OSSINSIGHT_COLLECTION_REPOS_SCHEMA = {
    "type": "object",
    "properties": {
        "collection_id": {
            "type": "string",
            "description": "a collection id from ossinsight_collections",
        }
    },
    "required": ["collection_id"],
}
_OSSINSIGHT_RANKING_SCHEMA = {
    "type": "object",
    "properties": {
        "collection_id": {
            "type": "string",
            "description": "a collection id from ossinsight_collections",
        },
        "by": {
            "type": "string",
            "enum": ["stars", "prs"],
            "default": "stars",
            "description": "rank metric (NOTE: event-derived rankings are currently degraded upstream)",
        },
    },
    "required": ["collection_id"],
}
# owner/repo/id path segments must be safe: GitHub names + numeric collection ids.
_SEGMENT_RE = re.compile(r"^[A-Za-z0-9._-]+$")
DEFAULT_OSSINSIGHT_URL = "https://api.ossinsight.io"
ENABLE_OSSINSIGHT_ENV = "ENABLE_OSSINSIGHT"


class OSSInsightAdapter(SelfHostedAdapter):
    """Keyless GitHub repo-discovery over the public OSSInsight API (default OFF).

    Not self-hosted (a public API), but wired through the SAME adapter mechanism:
    in-process HTTP, the capability lattice, and truthful degradation. Only the
    verified-200 endpoints are exposed; degraded rankings relay the API's own
    ``data_quality`` note rather than hiding or faking it.
    """

    platform = "ossinsight"
    label = "OSSInsight (public API)"
    prefix = "oi"
    kind = "native"  # documented public API, native shapes
    health_path = "/v1/collections/"  # cheap verified-200 GET

    def _build_tools(self) -> list[AdapterTool]:
        return [
            AdapterTool(
                name="ossinsight_repo_stats",
                description=(
                    "Keyless GitHub repo stats (stars/forks/language/topics/description) "
                    "via the public OSSInsight API GET /gh/repo/{owner}/{repo}. Truthful "
                    "error if the API is unreachable; never fabricated."
                ),
                input_schema=_OSSINSIGHT_REPO_SCHEMA,
                path="/gh/repo/{owner}/{repo}",
                realized_by=NATIVE,
                method="GET",
            ),
            AdapterTool(
                name="ossinsight_repo_search",
                description=(
                    "Keyless GitHub repo SEARCH by keyword via the public OSSInsight "
                    "API GET /gh/repos/search?keyword=. Returns matching repos "
                    "(id + fullName). The primary discovery tool; truthful error if "
                    "the API is unreachable, never fabricated."
                ),
                input_schema=_OSSINSIGHT_SEARCH_SCHEMA,
                path="/gh/repos/search",
                realized_by=NATIVE,
                method="GET",
            ),
            AdapterTool(
                name="ossinsight_collections",
                description=(
                    "Keyless repo-discovery: list OSSInsight's curated collections "
                    "(id + name) via GET /v1/collections/, optionally filtered by a "
                    "name substring. The entry point for finding curated repo lists."
                ),
                input_schema=_OSSINSIGHT_COLLECTIONS_SCHEMA,
                path="/v1/collections/",
                realized_by=NATIVE,
                method="GET",
            ),
            AdapterTool(
                name="ossinsight_collection_repos",
                description=(
                    "Keyless repo-discovery: the repos in an OSSInsight collection via "
                    "GET /v1/collections/{id}/repos/ (repo_id + repo_name). Real "
                    "membership data, unlike the degraded event-ranking below."
                ),
                input_schema=_OSSINSIGHT_COLLECTION_REPOS_SCHEMA,
                path="/v1/collections/{collection_id}/repos/",
                realized_by=NATIVE,
                method="GET",
            ),
            AdapterTool(
                name="ossinsight_collection_ranking",
                description=(
                    "Keyless per-collection repo ranking via GET "
                    "/v1/collections/{id}/ranking_by_{stars|prs}/. NOTE: the "
                    "event-derived ranking is degraded upstream (data_quality: "
                    "unavailable since 2026-03-01); the API's own data_quality note "
                    "is relayed verbatim -- an empty result means the metric cannot "
                    "be computed, not that there are no repos."
                ),
                input_schema=_OSSINSIGHT_RANKING_SCHEMA,
                path="/v1/collections/{collection_id}/ranking_by_{by}/",
                realized_by=NATIVE,
                method="GET",
            ),
        ]

    def _segment(self, value, field: str) -> str:
        token = str(value or "").strip()
        if not token:
            raise ValueError(f"OSSInsight: '{field}' is required")
        if not _SEGMENT_RE.match(token):
            raise ValueError(
                f"OSSInsight: '{field}' must match {_SEGMENT_RE.pattern} (got {token!r})"
            )
        return token

    def _prepare(
        self, tool: AdapterTool, arguments: dict
    ) -> tuple[str, str, bytes | None, dict]:
        args = arguments or {}
        headers = {"Accept": "application/json"}
        if tool.name == "ossinsight_repo_stats":
            owner = self._segment(args.get("owner"), "owner")
            repo = self._segment(args.get("repo"), "repo")
            return "GET", f"{self.base_url}/gh/repo/{owner}/{repo}", None, headers
        if tool.name == "ossinsight_repo_search":
            keyword = str(args.get("keyword") or "").strip()
            if not keyword:
                raise ValueError("OSSInsight: 'keyword' is required")
            url = f"{self.base_url}/gh/repos/search?keyword={quote(keyword)}"
            return "GET", url, None, headers
        if tool.name == "ossinsight_collections":
            return "GET", f"{self.base_url}/v1/collections/", None, headers
        if tool.name == "ossinsight_collection_repos":
            cid = self._segment(args.get("collection_id"), "collection_id")
            return "GET", f"{self.base_url}/v1/collections/{cid}/repos/", None, headers
        if tool.name == "ossinsight_collection_ranking":
            cid = self._segment(args.get("collection_id"), "collection_id")
            by = str(args.get("by") or "stars").strip().lower()
            if by not in ("stars", "prs"):
                raise ValueError("OSSInsight: 'by' must be 'stars' or 'prs'")
            url = f"{self.base_url}/v1/collections/{cid}/ranking_by_{by}/"
            return "GET", url, None, headers
        raise ValueError(f"OSSInsight: unknown tool {tool.name!r}")

    def _postprocess(self, tool: AdapterTool, arguments: dict, parsed):
        # Local name-substring filter over the already-fetched collection list.
        if tool.name != "ossinsight_collections" or not isinstance(parsed, dict):
            return parsed
        query = str((arguments or {}).get("query") or "").strip().lower()
        if not query:
            return parsed
        data = parsed.get("data")
        rows = data.get("rows") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            return parsed
        kept = [r for r in rows if query in str(r.get("name", "")).lower()]
        out = dict(parsed)
        out_data = dict(data)
        out_data["rows"] = kept
        out_data["result"] = {"row_count": len(kept)}
        out["data"] = out_data
        out["filtered_by"] = query
        return out


# --------------------------------------------------------------------------- #
# GitHub REST search -- keyless repo discovery over the FIRST-PARTY API
# --------------------------------------------------------------------------- #
# Endpoint verification 2026-09-02 (see the gemhunt plan doc, Wave 1 item 6), all
# KEYLESS unless noted:
#   * GET /search/repositories?q=<kw> created:>YYYY-MM-DD&sort=stars -> 200,
#     x-ratelimit-limit: 10 per minute unauthenticated (30 with a token); the
#     core pool is 60/h keyless, 5000/h with a token. ``pushed:>`` + ``stars:>N``
#     is the "popular and alive" shape; ``created:>`` + ``sort=stars`` is the
#     "new and hot" ranking OSSInsight lost (its event firehose starved ~2025-10).
#   * GET /search/topics?q=            -> 200, no preview header needed any more.
#   * GET /repos/{o}/{r}/stats/commit_activity + /stats/participation -> 200 with
#     a 52-week series, OR 202 with an empty body while GitHub computes the
#     statistics (surfaced truthfully as ``computing: true`` after ONE retry).
#   * GraphQL is 403 keyless and /repos/{o}/{r}/stargazers is 401 keyless, so
#     there is NO star velocity here -- the descriptions say so.
#   * GET /rate_limit -> 200 and does not count against any pool: the probe.
# Search results expose at most the first 1000 hits (per_page * page <= 1000) and
# a query is at most 256 characters / 5 boolean operators (422 beyond).
DEFAULT_GITHUB_API_URL = "https://api.github.com"
GITHUB_API_URL_ENV = "GITHUB_API_URL"
GITHUB_TOKEN_ENVS = ("GITHUB_TOKEN", "GH_TOKEN")  # names only; values never logged
ENABLE_GITHUB_SEARCH_ENV = "ENABLE_GITHUB_SEARCH"
GITHUB_API_VERSION = "2022-11-28"
USER_AGENT = "search-hub/0.1 (stdlib urllib; agent-skills-toolchain)"
_GITHUB_SEARCH_MAX_Q = 256
_GITHUB_SEARCH_MAX_RESULTS = 1000
_GITHUB_MAX_PER_PAGE = 50
_GITHUB_DEFAULT_PER_PAGE = 20
_GITHUB_MAX_DAYS = 3650
_GITHUB_REPO_SORTS = ("stars", "forks", "help-wanted-issues", "updated")
# GitHub language names: letters/digits plus the few symbols real names use
# ("C++", "C#", "F*", "Objective-C", "Jupyter Notebook", "Vim script").
_LANGUAGE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 +#*'._-]{0,63}$")
# GitHub topics are lower-case letters, digits and hyphens, at most 50 chars.
_TOPIC_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,49}$")
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")

_GITHUB_PAGING_PROPS = {
    "per_page": {
        "type": "integer",
        "minimum": 1,
        "maximum": _GITHUB_MAX_PER_PAGE,
        "default": _GITHUB_DEFAULT_PER_PAGE,
        "description": "results per page (1-50)",
    },
    "page": {
        "type": "integer",
        "minimum": 1,
        "default": 1,
        "description": (
            "page number; GitHub search exposes only the first 1000 results "
            "(per_page * page <= 1000)"
        ),
    },
}
_GITHUB_QUALIFIER_PROPS = {
    "language": {
        "type": "string",
        "default": "",
        "description": "GitHub language name, e.g. 'Python', 'Jupyter Notebook'",
    },
    "topic": {
        "type": "string",
        "default": "",
        "description": "one GitHub topic, e.g. 'mcp' (lower-cased before sending)",
    },
}
_GITHUB_REPO_SEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "q": {
            "type": "string",
            "description": (
                "GitHub repository search syntax, e.g. 'vector database "
                "language:rust stars:>500 pushed:>2026-06-01' (<= 256 chars, "
                "<= 5 AND/OR/NOT operators)"
            ),
        },
        "sort": {
            "type": "string",
            "enum": list(_GITHUB_REPO_SORTS),
            "description": "omit for GitHub's best-match ranking",
        },
        "order": {
            "type": "string",
            "enum": ["desc", "asc"],
            "default": "desc",
            "description": "only meaningful together with sort",
        },
        **_GITHUB_PAGING_PROPS,
    },
    "required": ["q"],
}
_GITHUB_NEW_HOT_SCHEMA = {
    "type": "object",
    "properties": {
        "keyword": {
            "type": "string",
            "default": "",
            "description": "optional free-text terms (name/description/readme)",
        },
        "days": {
            "type": "integer",
            "minimum": 1,
            "maximum": _GITHUB_MAX_DAYS,
            "default": 30,
            "description": "window: repos CREATED within the last N days",
        },
        **_GITHUB_QUALIFIER_PROPS,
        "min_stars": {
            "type": "integer",
            "minimum": 0,
            "default": 0,
            "description": "adds stars:>=N (0 adds no qualifier)",
        },
        **_GITHUB_PAGING_PROPS,
    },
}
_GITHUB_POPULAR_ALIVE_SCHEMA = {
    "type": "object",
    "properties": {
        "keyword": {
            "type": "string",
            "default": "",
            "description": "optional free-text terms (name/description/readme)",
        },
        "pushed_days": {
            "type": "integer",
            "minimum": 1,
            "maximum": _GITHUB_MAX_DAYS,
            "default": 30,
            "description": "window: repos PUSHED TO within the last N days (alive)",
        },
        **_GITHUB_QUALIFIER_PROPS,
        "min_stars": {
            "type": "integer",
            "minimum": 0,
            "default": 100,
            "description": "adds stars:>=N (popular); 0 adds no qualifier",
        },
        **_GITHUB_PAGING_PROPS,
    },
}
_GITHUB_TOPIC_SEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "q": {"type": "string", "description": "topic search terms, e.g. 'mcp'"},
        **_GITHUB_PAGING_PROPS,
    },
    "required": ["q"],
}
_GITHUB_ACTIVITY_SCHEMA = {
    "type": "object",
    "properties": {
        "owner": {"type": "string", "description": "GitHub owner/org, e.g. 'pingcap'"},
        "repo": {"type": "string", "description": "GitHub repo name, e.g. 'tidb'"},
    },
    "required": ["owner", "repo"],
}
_GITHUB_LIMITS_NOTE = (
    "Keyless rate limit: 10 search requests/min (30 with GITHUB_TOKEN or GH_TOKEN), "
    "first 1000 results only. "
)
_GITHUB_NO_VELOCITY_NOTE = (
    "No star velocity: stargazer timestamps and GraphQL are not available keyless, "
    "so this is a snapshot ranking, not a growth curve. "
)


class _UpstreamError(Exception):
    """A truthful upstream failure text raised from inside a multi-request tool."""


class GitHubSearchAdapter(SelfHostedAdapter):
    """Keyless repo discovery over the FIRST-PARTY GitHub REST search API (default ON).

    Why default ON when the OSSInsight sibling is default OFF: this is GitHub's own
    public API -- keyless, no cost, no third-party terms and no legal shadow (no
    scraping, no dark-web adjacency), first-party data about public repos. The
    ``ENABLE_GITHUB_SEARCH`` flag therefore exists only as a KILL SWITCH (an
    explicit falsey value unwires the ``github_*`` tools); unset means wired.

    Not self-hosted (a public API), but wired through the SAME adapter mechanism:
    in-process stdlib HTTP, the capability lattice, truthful degradation. The
    optional token (``GITHUB_TOKEN``, fallback ``GH_TOKEN``) is sent as a Bearer
    header, is never logged or echoed, and only ever surfaces as
    ``authenticated: true|false``. Every response relays the ``x-ratelimit-*``
    headers as ``rate_limit`` and a 403/429/422 becomes a readable ``isError``
    (rate-limited / forbidden / validation) -- never a fabricated empty success.
    """

    platform = "github"
    label = "GitHub REST search (public API)"
    prefix = "gh"
    kind = "native"  # documented first-party API, native shapes
    health_path = "/rate_limit"  # verified 200 keyless; does not count against pools
    error_tag = "github"
    # One short pause before the single retry of a 202 "computing" stats response.
    # GitHub says "give the job a few moments"; one retry keeps a call bounded and
    # never turns into a busy loop -- a second 202 is reported as ``computing``.
    stats_retry_pause_s = 1.5

    def __init__(
        self,
        base_url: str,
        caller: HeaderCaller | None = None,
        token: str | None = None,
        today: Callable[[], date] | None = None,
        sleeper: Callable[[float], None] | None = None,
    ) -> None:
        super().__init__(base_url)
        self._hcaller: HeaderCaller = caller or _default_header_caller
        # Keep the base-class 3-tuple caller coherent (unused by the overrides).
        self._caller = lambda *a: self._hcaller(*a)[:3]
        self._token = (token or "").strip()
        self._today = today or (lambda: datetime.now(timezone.utc).date())
        self._sleep = sleeper or time.sleep

    # ---- surface --------------------------------------------------------
    @property
    def authenticated(self) -> bool:
        return bool(self._token)

    def _build_tools(self) -> list[AdapterTool]:
        return [
            AdapterTool(
                name="github_repo_search",
                description=(
                    "Keyless GitHub repository search via the first-party REST API "
                    "GET /search/repositories (full GitHub search syntax in q; "
                    "sort=stars|forks|help-wanted-issues|updated or best match). "
                    "Returns compact items[full_name, html_url, description, "
                    "stargazers_count, forks_count, language, created_at, pushed_at, "
                    "topics, license] plus rate_limit{limit, remaining, reset_epoch}. "
                    + _GITHUB_LIMITS_NOTE
                    + "A 403/429 rate limit or 422 validation error is returned as a "
                    "truthful error, never as an empty result."
                ),
                input_schema=_GITHUB_REPO_SEARCH_SCHEMA,
                path="/search/repositories",
                realized_by=NATIVE,
                method="GET",
            ),
            AdapterTool(
                name="github_new_and_hot",
                description=(
                    "Keyless 'new & hot' repo ranking: repos CREATED in the last N "
                    "days sorted by stars (created:>YYYY-MM-DD + optional keyword, "
                    "language:, topic:, stars:>=N), composed over GitHub REST "
                    "/search/repositories -- the ranking OSSInsight lost when its "
                    "event feed starved. "
                    + _GITHUB_NO_VELOCITY_NOTE
                    + _GITHUB_LIMITS_NOTE
                    + "Same compact items + rate_limit as github_repo_search."
                ),
                input_schema=_GITHUB_NEW_HOT_SCHEMA,
                path="/search/repositories",
                realized_by=NATIVE,
                method="GET",
            ),
            AdapterTool(
                name="github_popular_and_alive",
                description=(
                    "Keyless 'popular & alive' repo ranking: repos with stars:>=N "
                    "(default 100) that were PUSHED TO in the last N days "
                    "(pushed:>YYYY-MM-DD), sorted by stars, optional keyword / "
                    "language: / topic:, composed over GitHub REST "
                    "/search/repositories. "
                    + _GITHUB_NO_VELOCITY_NOTE
                    + _GITHUB_LIMITS_NOTE
                    + "Same compact items + rate_limit as github_repo_search."
                ),
                input_schema=_GITHUB_POPULAR_ALIVE_SCHEMA,
                path="/search/repositories",
                realized_by=NATIVE,
                method="GET",
            ),
            AdapterTool(
                name="github_topic_search",
                description=(
                    "Keyless GitHub TOPIC search via GET /search/topics (no preview "
                    "header needed). Returns compact items[name, display_name, "
                    "short_description, created_by, released, created_at, "
                    "updated_at, featured, curated] + rate_limit. Use a topic name "
                    "with github_new_and_hot's topic= to rank repos under it. "
                    + _GITHUB_LIMITS_NOTE
                ),
                input_schema=_GITHUB_TOPIC_SEARCH_SCHEMA,
                path="/search/topics",
                realized_by=NATIVE,
                method="GET",
            ),
            AdapterTool(
                name="github_repo_activity",
                description=(
                    "Keyless repo activity via GET /repos/{owner}/{repo}/stats/"
                    "commit_activity (52 weekly commit totals) + /stats/participation "
                    "(all vs owner commits, 52 weeks), with totals and the last 4 "
                    "weeks summed. GitHub answers HTTP 202 with no body while it "
                    "computes fresh statistics: the tool pauses once, retries once, "
                    "and otherwise reports computing:true truthfully (call again "
                    "shortly). Core pool: 60 requests/h keyless, 5000/h with a token. "
                    "No star velocity (stargazers need a token)."
                ),
                input_schema=_GITHUB_ACTIVITY_SCHEMA,
                path="/repos/{owner}/{repo}/stats/{commit_activity|participation}",
                realized_by=NATIVE,
                method="GET",
            ),
        ]

    def capabilities(self, probe: bool = False) -> dict:
        report = super().capabilities(probe=probe)
        report["self_hosted"] = False  # a public API, not a daemon we run
        report["authenticated"] = self.authenticated
        report["auth_env"] = (
            "GITHUB_TOKEN or GH_TOKEN (optional; lifts search 10->30/min and core "
            "60->5000/h; the value is never shown)"
        )
        return report

    # ---- HTTP plumbing ---------------------------------------------------
    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
            "User-Agent": USER_AGENT,
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def _get(
        self, url: str, timeout: float
    ) -> tuple[int, dict | list | None, str, dict[str, str]]:
        status, parsed, raw, headers = self._hcaller(
            "GET", url, None, self._headers(), timeout
        )
        lowered = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
        return status, parsed, raw or "", lowered

    @staticmethod
    def _rate_limit(headers: dict[str, str]) -> dict:
        def _int(key: str) -> int | None:
            try:
                return int(headers.get(key, ""))
            except ValueError:
                return None

        return {
            "limit": _int("x-ratelimit-limit"),
            "remaining": _int("x-ratelimit-remaining"),
            "reset_epoch": _int("x-ratelimit-reset"),
            "resource": headers.get("x-ratelimit-resource") or None,
        }

    def probe(self) -> tuple[bool, str]:
        """One GET /rate_limit (free: not counted) reporting the pools' headroom."""
        if not self.base_url:
            return False, "no base URL configured"
        status, parsed, raw, _headers = self._get(
            self.base_url + self.health_path, PROBE_TIMEOUT
        )
        if status == 0:
            return False, raw or "unreachable"
        if status == 401:
            return False, (
                "HTTP 401: the token in GITHUB_TOKEN/GH_TOKEN was rejected "
                "(value never shown); unset it to fall back to keyless access"
            )
        if not (200 <= status < 300) or not isinstance(parsed, dict):
            return False, f"HTTP {status}: {self._scrub(raw[:120])}"
        resources = parsed.get("resources") or {}
        pools = []
        for name in ("search", "core"):
            pool = resources.get(name) if isinstance(resources, dict) else None
            if isinstance(pool, dict) and "limit" in pool:
                pools.append(f"{name} {pool.get('remaining')}/{pool.get('limit')}")
        who = "authenticated" if self._token else "unauthenticated"
        return True, f"HTTP {status} ({who}; {', '.join(pools) or 'no pools reported'})"

    def _scrub(self, text: str) -> str:
        # Belt and braces: the token is never placed in any text, but if an
        # upstream body ever echoed it, it must not reach the client.
        return text.replace(self._token, "[redacted]") if self._token else text

    def _error(self, text: str) -> dict:
        return super()._error(self._scrub(text))

    # ---- argument validation (before any request is spent) ----------------
    def _segment(self, value, field: str) -> str:
        token = str(value or "").strip()
        if not token:
            raise ValueError(f"GitHub: '{field}' is required")
        if not _SEGMENT_RE.match(token):
            raise ValueError(
                f"GitHub: '{field}' must match {_SEGMENT_RE.pattern} (got {token!r})"
            )
        return token

    @staticmethod
    def _text(value, field: str, required: bool) -> str:
        text = str(value if value is not None else "").strip()
        if not text:
            if required:
                raise ValueError(f"GitHub: '{field}' is required")
            return ""
        if _CONTROL_RE.search(text):
            raise ValueError(f"GitHub: '{field}' must not contain control characters")
        return text

    @staticmethod
    def _check_q(q: str) -> str:
        if len(q) > _GITHUB_SEARCH_MAX_Q:
            raise ValueError(
                f"GitHub: the search query is {len(q)} characters; GitHub rejects "
                f"queries longer than {_GITHUB_SEARCH_MAX_Q} (HTTP 422). Shorten it."
            )
        return q

    @staticmethod
    def _order(value) -> str:
        order = str(value if value is not None else "desc").strip().lower() or "desc"
        if order not in ("desc", "asc"):
            raise ValueError("GitHub: 'order' must be 'desc' or 'asc'")
        return order

    @staticmethod
    def _sort(value) -> str | None:
        sort = str(value if value is not None else "").strip().lower()
        if not sort:
            return None
        if sort not in _GITHUB_REPO_SORTS:
            raise ValueError(
                f"GitHub: 'sort' must be one of {'|'.join(_GITHUB_REPO_SORTS)} "
                "(omit it for best-match ranking)"
            )
        return sort

    @staticmethod
    def _language(value) -> str:
        language = str(value if value is not None else "").strip()
        if language and not _LANGUAGE_RE.match(language):
            raise ValueError(
                f"GitHub: 'language' must match {_LANGUAGE_RE.pattern} (got {language!r})"
            )
        return language

    @staticmethod
    def _topic(value) -> str:
        topic = str(value if value is not None else "").strip()
        if topic and not _TOPIC_RE.match(topic):
            raise ValueError(
                f"GitHub: 'topic' must match {_TOPIC_RE.pattern} (got {topic!r})"
            )
        return topic.lower()

    @staticmethod
    def _paging(args: dict) -> dict[str, str]:
        per_page = _int_arg(args, "per_page", _GITHUB_DEFAULT_PER_PAGE, 1, 50, "GitHub")
        page = _int_arg(args, "page", 1, 1, None, "GitHub")
        if per_page * page > _GITHUB_SEARCH_MAX_RESULTS:
            raise ValueError(
                f"GitHub: search exposes only the first {_GITHUB_SEARCH_MAX_RESULTS} "
                f"results (per_page * page must be <= {_GITHUB_SEARCH_MAX_RESULTS}; "
                f"got {per_page} * {page})"
            )
        return {"per_page": str(per_page), "page": str(page)}

    def _window(self, args: dict, field: str, qualifier: str) -> tuple[str, int]:
        days = _int_arg(args, field, 30, 1, _GITHUB_MAX_DAYS, "GitHub")
        since = (self._today() - timedelta(days=days)).isoformat()
        return f"{qualifier}:>{since}", days

    def _composed_query(self, args: dict, window: str, default_stars: int) -> str:
        parts = []
        keyword = self._text(args.get("keyword"), "keyword", required=False)
        if keyword:
            parts.append(keyword)
        parts.append(window)
        language = self._language(args.get("language"))
        if language:
            quoted = f'"{language}"' if " " in language else language
            parts.append(f"language:{quoted}")
        topic = self._topic(args.get("topic"))
        if topic:
            parts.append(f"topic:{topic}")
        min_stars = _int_arg(args, "min_stars", default_stars, 0, None, "GitHub")
        if min_stars > 0:
            parts.append(f"stars:>={min_stars}")
        return self._check_q(" ".join(parts))

    def _search_request(self, name: str, args: dict) -> tuple[str, dict]:
        """(url, echo) for the four search tools; ValueError on bad arguments."""
        if name == "github_topic_search":
            q = self._check_q(self._text(args.get("q"), "q", required=True))
            params = {"q": q, **self._paging(args)}
            return f"{self.base_url}/search/topics?{urlencode(params)}", {"q": q}
        if name == "github_repo_search":
            q = self._check_q(self._text(args.get("q"), "q", required=True))
            order = self._order(args.get("order"))  # validated even without sort
            sort = self._sort(args.get("sort"))
            params = {"q": q}
            if sort:
                params.update(sort=sort, order=order)
            params.update(self._paging(args))
            echo: dict = {"q": q}
        else:
            if name == "github_new_and_hot":
                window, days = self._window(args, "days", "created")
                q = self._composed_query(args, window, default_stars=0)
            else:  # github_popular_and_alive
                window, days = self._window(args, "pushed_days", "pushed")
                q = self._composed_query(args, window, default_stars=100)
            params = {"q": q, "sort": "stars", "order": "desc", **self._paging(args)}
            echo = {"q": q, "window": {"qualifier": window, "days": days}}
        return f"{self.base_url}/search/repositories?{urlencode(params)}", echo

    # ---- truthful degradation --------------------------------------------
    def _problem(
        self, status: int, parsed, raw: str, headers: dict[str, str], what: str
    ) -> str | None:
        """The isError text for a non-usable response, or None when it is usable."""
        who = "authenticated" if self._token else "unauthenticated"
        if status == 0:
            return (
                f"{self.label} at {self.base_url} not reachable ({raw}); "
                f"no results are fabricated."
            )
        rl = self._rate_limit(headers)
        message = parsed.get("message") if isinstance(parsed, dict) else None
        message = str(message or raw[:200] or "(empty body)")
        pool = f"{who} pool, remaining={rl['remaining']}/{rl['limit']}"
        rate_limited = status == 429 or (
            status == 403 and (rl["remaining"] == 0 or "rate limit" in message.lower())
        )
        if rate_limited:
            retry = headers.get("retry-after")
            remedy = (
                "Set GITHUB_TOKEN (or GH_TOKEN) to move from the 10/min unauthenticated "
                "search pool to 30/min (core 60/h -> 5000/h)"
                if not self._token
                else "Wait for the reset; this token's pool is exhausted"
            )
            return (
                f"GitHub rate limit hit: HTTP {status} for {what} ({pool}, resets at "
                f"epoch {rl['reset_epoch']}"
                + (f", retry-after {retry}s" if retry else "")
                + f"). GitHub said: {message} {remedy}. No results are fabricated."
            )
        if status == 403:
            return (
                f"GitHub HTTP 403 forbidden for {what} (not a rate limit: {pool}). "
                f"GitHub said: {message}. No results are fabricated."
            )
        if status == 401:
            return (
                f"GitHub HTTP 401 for {what}: the token in GITHUB_TOKEN/GH_TOKEN was "
                f"rejected (value never shown). GitHub said: {message}. Unset it to "
                f"fall back to keyless access."
            )
        if status == 422:
            details = []
            errors = parsed.get("errors") if isinstance(parsed, dict) else None
            for err in errors if isinstance(errors, list) else []:
                if isinstance(err, dict):
                    details.append(f"{err.get('message')} (field {err.get('field')})")
            return (
                f"GitHub HTTP 422 validation error for {what}: {message}"
                + (": " + "; ".join(details) if details else "")
                + ". Typical causes: a query over 256 characters, more than 5 "
                "AND/OR/NOT operators, or an invalid qualifier. No results are "
                "fabricated."
            )
        if not (200 <= status < 300):
            return (
                f"GitHub returned HTTP {status} for {what}: {message}. "
                f"No results are fabricated."
            )
        if parsed is None:
            return (
                f"GitHub returned HTTP {status} for {what} but the body is not JSON "
                f"({raw[:120]!r}); no results are fabricated."
            )
        return None

    # ---- result shaping ---------------------------------------------------
    @staticmethod
    def _compact_repo(item: dict) -> dict:
        lic = item.get("license")
        return {
            "full_name": item.get("full_name"),
            "html_url": item.get("html_url"),
            "description": item.get("description"),
            "stargazers_count": item.get("stargazers_count"),
            "forks_count": item.get("forks_count"),
            "language": item.get("language"),
            "created_at": item.get("created_at"),
            "pushed_at": item.get("pushed_at"),
            "topics": list(item.get("topics") or []),
            "license": (lic.get("spdx_id") or lic.get("key"))
            if isinstance(lic, dict)
            else lic,
        }

    @staticmethod
    def _compact_topic(item: dict) -> dict:
        keys = (
            "name",
            "display_name",
            "short_description",
            "created_by",
            "released",
            "created_at",
            "updated_at",
            "featured",
            "curated",
        )
        return {k: item.get(k) for k in keys}

    def _stats(self, url: str, what: str) -> tuple[dict, dict[str, str]]:
        """One stats GET with the 202 'computing' semantics: pause once, retry once."""
        status, parsed, raw, headers = self._get(url, DEFAULT_TIMEOUT)
        if status == 202:
            self._sleep(self.stats_retry_pause_s)
            status, parsed, raw, headers = self._get(url, DEFAULT_TIMEOUT)
        if status == 202:
            return {
                "status": status,
                "computing": True,
                "note": (
                    "GitHub is still computing these statistics (HTTP 202 twice; one "
                    "retry after a short pause). Call again in a few seconds -- "
                    "nothing is fabricated in the meantime."
                ),
            }, headers
        if status == 204:
            return {
                "status": 204,
                "computing": False,
                "note": "HTTP 204: GitHub has no content for this series (empty repo).",
            }, headers
        problem = self._problem(status, parsed, raw, headers, what)
        if problem:
            raise _UpstreamError(problem)
        return {"status": status, "computing": False, "data": parsed}, headers

    def _repo_activity(self, args: dict) -> dict:
        owner = self._segment(args.get("owner"), "owner")
        repo = self._segment(args.get("repo"), "repo")
        full = f"{owner}/{repo}"
        base = f"{self.base_url}/repos/{owner}/{repo}/stats/"
        commits, _h = self._stats(base + "commit_activity", f"{full} commit_activity")
        participation, headers = self._stats(
            base + "participation", f"{full} participation"
        )
        series = commits.pop("data", None)
        if isinstance(series, list):
            weeks = [w for w in series if isinstance(w, dict)]
            totals = [int(w.get("total") or 0) for w in weeks]
            commits.update(
                weeks=len(weeks),
                total_commits=sum(totals),
                recent_4_weeks_commits=sum(totals[-4:]),
                series=weeks,
            )
        shares = participation.pop("data", None)
        if isinstance(shares, dict):
            everyone = [int(x or 0) for x in (shares.get("all") or [])]
            owner_only = [int(x or 0) for x in (shares.get("owner") or [])]
            participation.update(
                all_total=sum(everyone),
                owner_total=sum(owner_only),
                all=everyone,
                owner=owner_only,
            )
        return {
            "tool": "github_repo_activity",
            "repo": full,
            "commit_activity": commits,
            "participation": participation,
            "authenticated": self.authenticated,
            "rate_limit": self._rate_limit(headers),
            "note": (
                "weekly series are GitHub's own computed statistics (week = epoch "
                "seconds of the week start); star velocity is not available keyless."
            ),
        }

    # ---- the call path (always truthful) ----------------------------------
    def handle_call(self, name: str, arguments: dict) -> dict:
        tool = self._tool(name)
        if tool is None:
            return self._error(f"unknown GitHub tool {name!r}")
        if not self.base_url:
            return self._error(
                f"no GitHub API base URL configured: set {GITHUB_API_URL_ENV} "
                f"(default {DEFAULT_GITHUB_API_URL}). No results are fabricated."
            )
        args = arguments or {}
        try:
            if name == "github_repo_activity":
                return self._ok(self._repo_activity(args))
            url, echo = self._search_request(name, args)
        except (ValueError, _UpstreamError) as exc:
            return self._error(str(exc))
        status, parsed, raw, headers = self._get(url, DEFAULT_TIMEOUT)
        problem = self._problem(status, parsed, raw, headers, tool.path)
        if problem:
            return self._error(problem)
        body = parsed if isinstance(parsed, dict) else {}
        raw_items = body.get("items") if isinstance(body.get("items"), list) else []
        compact = (
            self._compact_topic if name == "github_topic_search" else self._compact_repo
        )
        items = [compact(i) for i in raw_items if isinstance(i, dict)]
        payload = {
            "tool": name,
            **echo,
            "total_count": body.get("total_count"),
            "incomplete_results": bool(body.get("incomplete_results", False)),
            "count": len(items),
            "items": items,
            "authenticated": self.authenticated,
            "rate_limit": self._rate_limit(headers),
        }
        if payload["incomplete_results"]:
            payload["note"] = (
                "GitHub reported incomplete_results: the search timed out upstream "
                "and returned a partial set (truthfully relayed, not padded)."
            )
        return self._ok(payload)


# --------------------------------------------------------------------------- #
# read_url -- in-process fetch negotiating Cloudflare "Markdown for Agents" (v0)
# --------------------------------------------------------------------------- #
# Why in-process: the hub has NO fetch path of its own. ``web_url_read`` belongs
# to the downstream mcp-searxng child (no boilerplate removal, cannot add request
# headers) and ``selfhosted_extract`` fetches server-side inside TrailSearch. This
# Wave 1 shipped the minimal honest v0 (markdown negotiation + a stdlib
# tag-stripper); Wave 2 upgraded it IN PLACE (same name, same output shape,
# additive fields only) with an extractor LADDER whose middle rung is the
# OPTIONAL trafilatura / rs-trafilatura readability pass -- imported only when an
# HTML body needs extracting, never required, faked through ``sys.modules`` in the
# suite so CI stays stdlib-only.
# Evidence (Cloudflare "Markdown for Agents" docs + blog, read 2026-09-02): a
# client sending ``Accept: text/markdown, text/html;q=0.9`` gets, from an OPTED-IN
# zone (Pro/Business/Enterprise; Cloudflare's own docs and blog are), a response
# with ``Content-Type: text/markdown`` plus ``x-markdown-tokens`` /
# ``x-original-tokens`` headers whose body is YAML frontmatter + cleaned markdown
# (+ a fenced JSON-LD block); origin HTML up to 2 MB is converted. The hit-rate
# across the web is unknown, so every result names the ``extractor`` that
# produced its text, the ``quality`` that follows from it and the whole
# ``extractor_ladder`` that was tried.
ENABLE_READ_URL_ENV = "ENABLE_READ_URL"
READ_URL_ALLOW_PRIVATE_ENV = "READ_URL_ALLOW_PRIVATE"
# A readability extract shorter than this is retried with favor_recall=True and,
# if that retry is used, labelled ``quality: medium`` instead of ``high``.
READ_URL_MIN_CHARS_ENV = "READ_URL_MIN_CHARS"
READ_URL_DEFAULT_MIN_CHARS = 200
READ_URL_MAX_MIN_CHARS = 100_000
# A favor_recall extract that is STILL shorter than min_chars is kept (medium) only
# when it covers at least this share of the page's visible text -- i.e. the page
# itself is short. Below it the extractor evidently missed the content and the
# stdlib text is the more useful (if noisier) answer.
_RECALL_MIN_COVERAGE = 0.25
# The optional readability rung, most-preferred first: (import name, label). The
# Rust build (PyPI ``rs-trafilatura``, module ``rs_trafilatura``) is preferred
# when importable; plain ``trafilatura`` is the documented install.
_READABILITY_MODULES = (
    ("rs_trafilatura", "rs-trafilatura"),
    ("trafilatura", "trafilatura"),
)
# page_type heuristic thresholds (a HINT computed from the tag-stripper's single
# pass; documented as a heuristic, never a classifier).
_SHELL_MAX_CHARS = 80  # visible text below this + scripts + a big body = app shell
_SHELL_MIN_BYTES = 2048
_LISTING_MIN_LINKS = 8
_LISTING_LINK_DENSITY = 0.5
_DOCS_MIN_CODE_BLOCKS = 2
_ARTICLE_MIN_PARAGRAPHS = 3
_ARTICLE_MIN_CHARS = 500
_DOCS_URL_RE = re.compile(
    r"(^https?://docs\.|readthedocs\.|/docs?/|/documentation/|/reference/|/api/"
    r"|/manual/|/guide/)",
    re.IGNORECASE,
)
_MD_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_MD_FENCE_RE = re.compile(r"^```", re.MULTILINE)
_HEADING_TAGS = frozenset(("h1", "h2", "h3", "h4", "h5", "h6"))
READ_URL_MAX_REDIRECTS = 5
READ_URL_DEFAULT_MAX_BYTES = 2_000_000  # Cloudflare converts origin HTML up to 2 MB
READ_URL_MIN_MAX_BYTES = 256
READ_URL_HARD_MAX_BYTES = 10_000_000  # memory bound: one body is held in RAM once
READ_URL_DEFAULT_TIMEOUT_S = 20
READ_URL_MAX_TIMEOUT_S = 120
# Exactly the negotiation Cloudflare documents, then HTML, then anything textual.
READ_URL_ACCEPT = "text/markdown, text/html;q=0.9, text/plain;q=0.8, */*;q=0.1"
_REDIRECT_STATUSES = (301, 302, 303, 307, 308)
_HTML_TYPES = frozenset(("text/html", "application/xhtml+xml"))
# Non-``text/*`` media types that are still text and pass through as ``text``.
_TEXT_TYPES = frozenset(
    (
        "application/json",
        "application/ld+json",
        "application/xml",
        "application/rss+xml",
        "application/atom+xml",
        "application/javascript",
    )
)
# The boilerplate SUBTREES the stdlib fallback drops entirely.
_SKIP_TAGS = frozenset(
    (
        "script",
        "style",
        "noscript",
        "svg",
        "template",
        "nav",
        "footer",
        "aside",
        "header",
    )
)
# Block tags yield a paragraph break (blank line); line tags a single newline;
# cells a separating space. Consecutive breaks coalesce to the strongest one.
_PARAGRAPH_TAGS = frozenset(
    (
        "address",
        "article",
        "blockquote",
        "body",
        "center",
        "details",
        "dialog",
        "div",
        "dl",
        "fieldset",
        "figcaption",
        "figure",
        "form",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "hr",
        "html",
        "legend",
        "main",
        "menu",
        "ol",
        "p",
        "pre",
        "section",
        "summary",
        "table",
        "ul",
    )
)
_LINE_TAGS = frozenset(
    ("br", "caption", "dd", "dt", "li", "option", "tbody", "tfoot", "thead", "tr")
)
_CELL_TAGS = frozenset(("td", "th"))
_WS_RUN_RE = re.compile(r"\s+")
_HSPACE_RUN_RE = re.compile(r"[ \t\f\v\xa0]+")
_SPACE_AROUND_NL_RE = re.compile(r" *\n *")
_MANY_NEWLINES_RE = re.compile(r"\n{3,}")
_META_CHARSET_RE = re.compile(
    rb"""<meta[^>]+charset=["']?\s*([A-Za-z0-9_.:-]+)""", re.IGNORECASE
)
_MARKDOWN_H1_RE = re.compile(r"^#[ \t]+(.+?)[ \t]*$", re.MULTILINE)

_READ_URL_SCHEMA = {
    "type": "object",
    "properties": {
        "url": {
            "type": "string",
            "description": "http(s) URL of a PUBLIC web page (no .onion, no credentials)",
        },
        "max_bytes": {
            "type": "integer",
            "minimum": READ_URL_MIN_MAX_BYTES,
            "maximum": READ_URL_HARD_MAX_BYTES,
            "default": READ_URL_DEFAULT_MAX_BYTES,
            "description": (
                "stop reading the body at this many bytes and cap the returned text "
                "to it (truncated:true when hit)"
            ),
        },
        "timeout_s": {
            "type": "number",
            "minimum": 1,
            "maximum": READ_URL_MAX_TIMEOUT_S,
            "default": READ_URL_DEFAULT_TIMEOUT_S,
            "description": "connect + read timeout in seconds, applied to every hop",
        },
    },
    "required": ["url"],
}

# fetch(url, request_headers, timeout, max_bytes) -> (status, response_headers,
# body, reason). Reads at most ``max_bytes + 1`` body bytes (one over, so the
# caller can tell "exactly full" from "capped"); a transport failure is
# ``(0, {}, b"", "request failed: <why>")`` and NEVER an exception; 3xx come back
# as ordinary responses so the adapter validates every hop itself.
Fetcher = Callable[
    [str, "dict[str, str]", float, int],
    "tuple[int, dict[str, str], bytes, str]",
]
# resolver(host) -> address strings; raises socket.gaierror when unresolvable.
Resolver = Callable[[str], "list[str]"]


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Make urllib hand 3xx back (as HTTPError) instead of following silently.

    The adapter follows redirects itself so it can re-run the scheme / .onion /
    private-address checks on EVERY hop; urllib's default handler would happily
    follow a public page's redirect into ``http://169.254.169.254/``.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _urllib_fetch(
    url: str, headers: dict[str, str], timeout: float, max_bytes: int
) -> tuple[int, dict[str, str], bytes, str]:
    """The default ``Fetcher``: one stdlib GET, no redirects, no cookies, capped.

    No cookie jar or auth handler is installed, so the only headers on the wire
    are the ones passed in. Certificate verification is urllib's default (on).
    """
    req = urllib.request.Request(url, headers=headers, method="GET")  # noqa: S310
    opener = urllib.request.build_opener(_NoRedirectHandler)
    try:
        with opener.open(req, timeout=timeout) as resp:  # noqa: S310 (scheme checked)
            status = resp.getcode() or 0
            resp_headers = {k.lower(): v for k, v in resp.headers.items()}
            body = resp.read(max_bytes + 1)
    except urllib.error.HTTPError as exc:
        status = exc.code
        resp_headers = {k.lower(): v for k, v in (exc.headers or {}).items()}
        try:
            body = exc.read(max_bytes + 1) if exc.fp else b""
        except (OSError, http.client.HTTPException):
            body = b""
    except (
        urllib.error.URLError,
        http.client.HTTPException,
        OSError,
        ValueError,
    ) as exc:
        return 0, {}, b"", f"request failed: {exc}"
    return status, resp_headers, body, ""


def _default_resolver(host: str) -> list[str]:
    """Resolve ``host`` (a DNS name OR a literal address) to its address strings.

    Literals go through ``getaddrinfo`` too, so ``127.0.0.1``, ``[::1]``,
    ``0.0.0.0``, ``169.254.169.254`` and DNS names all take the ONE code path the
    private-address check guards; an IPv4-mapped or scoped IPv6 literal comes
    back in a form ``ipaddress`` understands.
    """
    infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    return sorted({str(info[4][0]) for info in infos})


def _is_public_address(addr) -> bool:
    """False for loopback, RFC1918, link-local (169.254/16, fe80::/10), fc00::/7,
    unspecified, multicast, reserved and shared (100.64/10) space -- everything a
    server-side fetch must never be steered into by a URL or a redirect."""
    mapped = getattr(addr, "ipv4_mapped", None)
    if mapped is not None:
        addr = mapped
    if (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    ):
        return False
    return bool(addr.is_global)


def _scrub_url(url: str) -> str:
    """A URL safe to echo: any ``user:password@`` userinfo is replaced."""
    parts = urlsplit(url)
    if parts.username is None and parts.password is None:
        return url
    host = parts.hostname or ""
    if ":" in host:
        host = f"[{host}]"
    try:
        port = parts.port
    except ValueError:
        port = None
    netloc = f"[redacted]@{host}" + (f":{port}" if port else "")
    return urlunsplit(parts._replace(netloc=netloc))


def _split_content_type(value: str | None) -> tuple[str, str | None]:
    """``"text/html; charset=ISO-8859-1"`` -> ``("text/html", "iso-8859-1")``."""
    if not value:
        return "", None
    parts = [p.strip() for p in value.split(";")]
    charset = None
    for param in parts[1:]:
        key, _sep, val = param.partition("=")
        if key.strip().lower() == "charset":
            charset = val.strip().strip("\"'").lower() or None
    return parts[0].lower(), charset


def _sniff_media(body: bytes) -> str:
    """Media type for a response that declared none: HTML markers, else text unless
    NUL bytes say binary."""
    head = body[:2048].lstrip().lower()
    if head.startswith(b"<!doctype html") or any(
        marker in head for marker in (b"<html", b"<head", b"<body")
    ):
        return "text/html"
    if b"\x00" in body[:4096]:
        return "application/octet-stream"
    return "text/plain"


def _decode_body(body: bytes, charset: str | None, html: bool) -> str:
    """Decode with the declared charset, else (HTML only) a ``<meta charset>`` sniff,
    else UTF-8 -- always with replacement, never raising on a hostile body."""
    if body.startswith(b"\xef\xbb\xbf"):
        body, charset = body[3:], "utf-8"
    candidates = [charset] if charset else []
    if html and not charset:
        match = _META_CHARSET_RE.search(body[:4096])
        if match:
            candidates.append(match.group(1).decode("ascii", "ignore").lower())
    for name in candidates:
        try:
            b"".decode(name)
        except LookupError:
            continue
        return body.decode(name, "replace")
    return body.decode("utf-8", "replace")


def _inflate(body: bytes, encoding: str, limit: int) -> bytes | None:
    """Undo a gzip/deflate Content-Encoding an origin applied despite our
    ``Accept-Encoding: identity``; ``None`` for encodings stdlib cannot decode
    (br, zstd). Bounded by ``limit`` output bytes; partial input is fine."""
    enc = encoding.strip().lower()
    if enc in ("gzip", "x-gzip"):
        wbits_options = (16 + zlib.MAX_WBITS,)
    elif enc == "deflate":
        wbits_options = (zlib.MAX_WBITS, -zlib.MAX_WBITS)  # zlib-wrapped, then raw
    else:
        return None
    for wbits in wbits_options:
        try:
            return zlib.decompressobj(wbits).decompress(body, limit)
        except zlib.error:
            continue
    return None


def _cap_text(text: str, max_bytes: int) -> tuple[str, bool]:
    """Trim ``text`` to at most ``max_bytes`` UTF-8 bytes on a character boundary."""
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text, False
    return encoded[:max_bytes].decode("utf-8", "ignore"), True


def _normalize_plain(text: str) -> str:
    """Collapse horizontal whitespace runs and 3+ blank lines; unify newlines."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _HSPACE_RUN_RE.sub(" ", text)
    text = _SPACE_AROUND_NL_RE.sub("\n", text)
    return _MANY_NEWLINES_RE.sub("\n\n", text).strip()


def _frontmatter_field(markdown: str, key: str) -> str | None:
    """``key:`` from a leading YAML frontmatter block (Cloudflare emits one),
    unquoted; ``None`` when there is no block or no such key."""
    if not markdown.startswith("---"):
        return None
    end = markdown.find("\n---", 3)
    if end == -1:
        return None
    match = re.search(rf"^{key}:[ \t]*(.+?)[ \t]*$", markdown[3:end], re.MULTILINE)
    if not match:
        return None
    return match.group(1).strip().strip("\"'").strip() or None


def _markdown_title(markdown: str) -> str | None:
    """``title:`` from Cloudflare's YAML frontmatter, else the first ``# `` heading."""
    title = _frontmatter_field(markdown, "title")
    if title:
        return title
    match = _MARKDOWN_H1_RE.search(markdown)
    return match.group(1).strip() if match else None


def _int_header(headers: dict[str, str], key: str) -> int | None:
    try:
        return int(str(headers.get(key, "")).strip())
    except ValueError:
        return None


def _min_chars_setting(environ) -> int:
    """``READ_URL_MIN_CHARS`` as a bounded int; anything else is the default."""
    raw = environ.get(READ_URL_MIN_CHARS_ENV)
    if isinstance(raw, str) and raw.strip().isdigit():
        value = int(raw.strip())
        if 1 <= value <= READ_URL_MAX_MIN_CHARS:
            return value
    return READ_URL_DEFAULT_MIN_CHARS


def _optional_module(name: str):
    """Import an OPTIONAL dependency by name; ``None`` when it is not importable.

    Looked up per call (a ``sys.modules`` hit after the first import) so a test
    can fake presence with a module -- or absence with ``None`` -- in
    ``sys.modules``. ANY import-time failure counts as absent: a broken optional
    install must degrade the ladder, never break ``read_url``.
    """
    import importlib  # local on purpose: the read_url block owns its own imports

    try:
        return importlib.import_module(name)
    except Exception:
        return None


def _module_available(name: str) -> bool:
    """Is ``name`` importable -- answered WITHOUT importing it (``find_spec``), so
    ``capabilities()`` stays RAM-cheap; a ``sys.modules`` entry (a test's fake or
    ``None``) is honoured first."""
    import importlib.util  # local on purpose, see _optional_module
    import sys

    if name in sys.modules:
        return sys.modules[name] is not None
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _readability_label() -> str | None:
    """The label of the readability rung that WOULD run now, or ``None``."""
    for module_name, label in _READABILITY_MODULES:
        if _module_available(module_name):
            return label
    return None


def _parses_public(text: str) -> bool:
    try:
        return _is_public_address(ipaddress.ip_address(text))
    except ValueError:
        return False


def _pick_meta(source) -> dict[str, str]:
    """``title`` / ``author`` / ``date`` from a trafilatura 2.x ``Document``, a 1.x
    dict or an rs-trafilatura ``ExtractResult`` -- non-empty strings only, with
    whitespace runs collapsed (rs hands ``<title>`` text back verbatim)."""
    if source is None:
        return {}
    picked: dict[str, str] = {}
    for key in ("title", "author", "date"):
        value = (
            source.get(key) if isinstance(source, dict) else getattr(source, key, None)
        )
        if isinstance(value, str) and value.strip():
            picked[key] = _WS_RUN_RE.sub(" ", value).strip()
    return picked


@dataclass
class _Readable:
    """One readability pass: the body, which payload key it belongs under
    (``markdown`` or ``text``), metadata, an optional confidence score, and --
    once the ladder picks it -- the ``extractor`` label and ``quality`` it earns."""

    text: str
    key: str
    meta: dict[str, str]
    confidence: float | None = None
    note: str = ""
    label: str = ""
    quality: str = ""

    @property
    def chars(self) -> int:
        return len(self.text.strip())


def _run_trafilatura(mod, html: str, url: str, favor_recall: bool) -> _Readable:
    """One ``trafilatura.extract`` pass, markdown output when the installed
    version has it (>= 1.9; an unknown format raises AttributeError in 2.x,
    ValueError in 1.x), plain text otherwise. Exceptions propagate to the ladder."""
    kwargs = dict(
        url=url, include_links=False, include_tables=True, favor_recall=favor_recall
    )
    try:
        text = mod.extract(html, output_format="markdown", **kwargs)
        key, note = "markdown", ""
    except (AttributeError, ValueError, TypeError):
        text = mod.extract(html, output_format="txt", **kwargs)
        key, note = "text", "txt output: this trafilatura has no markdown format"
    return _Readable(text if isinstance(text, str) else "", key, {}, note=note)


def _trafilatura_metadata(mod, html: str, url: str) -> dict[str, str]:
    """title/author/date via ``bare_extraction``; ``fast=True`` skips the fallback
    algorithms (measured 6 ms on a 98 KB page, trafilatura 2.2.0, 2026-09-02).
    Any failure is just no metadata."""
    kwargs = dict(url=url, with_metadata=True, include_comments=False)
    try:
        try:
            doc = mod.bare_extraction(html, fast=True, **kwargs)
        except TypeError:  # < 1.9 spells the flag no_fallback
            doc = mod.bare_extraction(html, no_fallback=True, **kwargs)
    except Exception:
        return {}
    return _pick_meta(doc)


def _run_rs_trafilatura(mod, html: str, url: str, favor_recall: bool) -> _Readable:
    """One ``rs_trafilatura.extract`` pass (PyO3 build; keyword-only API returning
    an ``ExtractResult`` with content_markdown / main_content / title / author /
    date / extraction_quality). Exceptions propagate to the ladder."""
    result = mod.extract(
        html,
        url=url,
        favor_recall=favor_recall,
        include_tables=True,
        include_comments=False,
        output_markdown=True,
    )
    if result is None:
        return _Readable("", "markdown", {})
    markdown = getattr(result, "content_markdown", None)
    plain = getattr(result, "main_content", None)
    if isinstance(markdown, str) and markdown.strip():
        text, key = markdown, "markdown"
    else:
        text, key = (plain if isinstance(plain, str) else ""), "text"
    score = getattr(result, "extraction_quality", None)
    confidence = (
        round(float(score), 3)
        if isinstance(score, (int, float)) and not isinstance(score, bool)
        else None
    )
    return _Readable(text, key, _pick_meta(result), confidence=confidence)


_READABILITY_RUNNERS = {
    "rs_trafilatura": _run_rs_trafilatura,
    "trafilatura": _run_trafilatura,
}
# Extra metadata pass per module, run ONLY for the rung that wins (rs-trafilatura's
# result already carries title/author/date, so it needs none).
_READABILITY_METADATA = {"trafilatura": _trafilatura_metadata}


@dataclass
class _PageStats:
    """Counters the tag-stripper gathers in its single pass -- the page_type and
    link_density inputs. Skipped subtrees are excluded except ``scripts``, which
    counts every ``<script>`` (an app shell is mostly script)."""

    links: int = 0
    link_chars: int = 0
    article: bool = False
    paragraphs: int = 0
    headings: int = 0
    code_blocks: int = 0
    scripts: int = 0


def _link_density(stats: _PageStats, text_chars: int) -> float:
    """Share of the visible text that sits inside ``<a>``, 0.0 .. 1.0."""
    if text_chars <= 0:
        return 0.0
    return round(min(stats.link_chars / text_chars, 1.0), 3)


def _classify_html(
    text_chars: int, stats: _PageStats, html_bytes: int, url: str
) -> str:
    """The ``page_type`` HINT for an HTML body: article|docs|listing|shell|other.

    A cheap heuristic over text density, link density, ``<article>`` presence,
    code blocks and a URL hint -- shells first (no text, scripts, a big body),
    then code-heavy docs, then link-dominated listings, then docs by URL/headings,
    then articles. Wrong sometimes by design; it is a hint, never a gate.
    """
    if text_chars < _SHELL_MAX_CHARS:
        if stats.scripts and html_bytes >= _SHELL_MIN_BYTES:
            return "shell"
        return "other"
    if stats.code_blocks >= _DOCS_MIN_CODE_BLOCKS:
        return "docs"
    if (
        stats.links >= _LISTING_MIN_LINKS
        and _link_density(stats, text_chars) >= _LISTING_LINK_DENSITY
    ):
        return "listing"
    if _DOCS_URL_RE.search(url) or (stats.headings >= 4 and stats.code_blocks):
        return "docs"
    if stats.article or (
        stats.paragraphs >= _ARTICLE_MIN_PARAGRAPHS and text_chars >= _ARTICLE_MIN_CHARS
    ):
        return "article"
    return "other"


def _classify_markdown(markdown: str) -> tuple[str, float]:
    """``(page_type, link_density)`` for a markdown body (negotiated or origin):
    fenced blocks say docs, ``[label](url)`` density says listing, else article."""
    chars = len(markdown)
    labels = [m.group(1) for m in _MD_LINK_RE.finditer(markdown)]
    link_chars = sum(len(label) for label in labels)
    density = round(min(link_chars / chars, 1.0), 3) if chars else 0.0
    if chars < _SHELL_MAX_CHARS:
        return "other", density
    if len(_MD_FENCE_RE.findall(markdown)) >= 2 * _DOCS_MIN_CODE_BLOCKS:
        return "docs", density
    if len(labels) >= _LISTING_MIN_LINKS and density >= _LISTING_LINK_DENSITY:
        return "listing", density
    return "article", density


class _TextExtractor(HTMLParser):
    """The stdlib fallback: ``<title>`` + body text with paragraph/line breaks kept.

    This is tag-stripping, NOT readability: it drops the boilerplate SUBTREES in
    ``_SKIP_TAGS`` and keeps everything else, so a menu inside ``<main>`` or a
    cookie banner in a ``<div>`` survives (hence ``quality: low``). Whitespace
    collapses the way a browser renders it -- any run of source whitespace,
    newlines included, is one space -- except inside ``<pre>``. Block tags yield
    a blank line, ``li``/``br``/``tr`` a newline, and consecutive breaks coalesce
    to the strongest (``</li><li>`` is ONE newline). Entities are decoded by
    ``HTMLParser(convert_charrefs=True)``. Skipped subtrees are tracked as a
    stack so an unclosed inner ``<header>`` cannot swallow the rest of the page.
    The same pass fills ``stats`` (links, link text, ``<article>``, paragraphs,
    headings, ``<pre>`` blocks, scripts) for the page_type / link_density hints.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._out: list[str] = []
        self._title: list[str] = []
        self._skip: list[str] = []
        self._pre = 0
        self._in_link = 0
        self._in_title = False
        self._title_done = False
        # Named ``_brk``, not ``_pending``: CPython 3.11.16+'s HTMLParser keeps its
        # own ``_pending`` buffer list and the name collision broke ``close()`` in CI.
        self._brk = 0  # 0 = none, 1 = line break, 2 = paragraph break
        self.stats = _PageStats()

    # -- tags ---------------------------------------------------------------
    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "script":
            self.stats.scripts += 1
        if self._skip:
            if tag in _SKIP_TAGS:
                self._skip.append(tag)
            return
        if tag in _SKIP_TAGS:
            self._skip.append(tag)
        elif tag == "title":
            self._in_title = not self._title_done
        elif tag in _PARAGRAPH_TAGS:
            self._brk = 2
            if tag == "pre":
                self._pre += 1
                self.stats.code_blocks += 1
            elif tag == "p":
                self.stats.paragraphs += 1
            elif tag == "article":
                self.stats.article = True
            elif tag in _HEADING_TAGS:
                self.stats.headings += 1
        elif tag in _LINE_TAGS:
            self._brk = max(self._brk, 1)
        elif tag in _CELL_TAGS:
            self._space()
        elif tag == "a":
            self._in_link += 1
            self.stats.links += 1

    def handle_endtag(self, tag: str) -> None:
        if self._skip:
            if tag in self._skip:
                del self._skip[len(self._skip) - 1 - self._skip[::-1].index(tag) :]
            return
        if tag == "title":
            self._in_title = False
            self._title_done = True
        elif tag in _PARAGRAPH_TAGS:
            self._brk = 2
            if tag == "pre" and self._pre:
                self._pre -= 1
        elif tag in _LINE_TAGS:
            self._brk = max(self._brk, 1)
        elif tag in _CELL_TAGS:
            self._space()
        elif tag == "a" and self._in_link:
            self._in_link -= 1

    # -- text ---------------------------------------------------------------
    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        if self._in_title:
            self._title.append(data)
            return
        if self._pre:
            chunk = data.lstrip("\n") if self._brk or not self._out else data
            if self._in_link:
                self.stats.link_chars += len(chunk.strip())
            self._emit(chunk, verbatim=True)
            return
        collapsed = _WS_RUN_RE.sub(" ", data)
        if self._in_link:
            self.stats.link_chars += len(collapsed.strip())
        if collapsed.strip():
            self._emit(collapsed, verbatim=False)
        elif collapsed and not self._brk:
            self._space()  # whitespace between inline runs is one separator

    def _space(self) -> None:
        if self._out and not self._out[-1].endswith((" ", "\n")):
            self._out.append(" ")

    def _emit(self, chunk: str, verbatim: bool) -> None:
        if self._brk and self._out:
            self._out[-1] = self._out[-1].rstrip(" ")
            self._out.append("\n" * self._brk)
        at_boundary = not self._out or self._out[-1].endswith((" ", "\n"))
        self._brk = 0
        if not verbatim and at_boundary:
            chunk = chunk.lstrip(" ")
        if chunk:
            self._out.append(chunk)

    def result(self) -> tuple[str | None, str]:
        self.close()
        title = _WS_RUN_RE.sub(" ", "".join(self._title)).strip() or None
        text = _MANY_NEWLINES_RE.sub("\n\n", "".join(self._out)).strip()
        return title, text


class ReadUrlAdapter(SelfHostedAdapter):
    """``read_url``: fetch one public page in-process and return its text (default ON).

    The text comes off an extractor LADDER and every result names what happened
    (``extractor``, ``quality``, ``extractor_ladder`` = rungs tried, chosen last):

    1. Cloudflare "Markdown for Agents" negotiated with ``Accept: text/markdown``
       -> ``cloudflare-markdown`` (server-side clean markdown, ``high``); an
       origin serving ``text/markdown`` itself -> ``origin-markdown`` (``high``).
    2. For HTML, the OPTIONAL readability rung when importable: ``rs-trafilatura``
       (Rust build) preferred, else ``trafilatura`` -- a precision pass first;
       ``high`` when the extract is >= ``READ_URL_MIN_CHARS`` (default 200) chars,
       else ONE ``favor_recall`` retry labelled ``medium`` (kept below min_chars
       only when it still covers a quarter of the page's visible text). Metadata
       (``title`` / ``author`` / ``date``) comes from the extractor when cheap.
       Empty results, too-short results and exceptions fall through truthfully
       (the note says why); CI never has the module, tests fake it.
    3. ``stdlib-text``: the ``html.parser`` tag-stripper / plain-text
       pass-through, ``quality: low`` because tag-stripping is not readability.

    Quality signals ride along: ``chars``, ``link_density``, ``boilerplate_removed``
    (true for rungs 1-2), ``min_chars``, and ``page_type`` -- a cheap stdlib
    HEURISTIC hint (article|docs|listing|shell|other) from text / link density,
    ``<article>`` presence and code blocks, never a classifier.

    Default ON because it is keyless, costless at rest (no child, no dependency,
    no request until called) and fetches the public web under the origin's own
    terms; ``ENABLE_READ_URL=0`` is the kill switch. Safety is enforced BEFORE
    any request and again on EVERY redirect hop: http/https only, ``.onion``
    refused (the onions-lane envelope forbids onion fetches everywhere), URL
    credentials refused, at most ``READ_URL_MAX_REDIRECTS`` hops, and hosts that
    resolve to private / loopback / link-local space refused -- EVERY address in
    the answer is checked, and after each hop's fetch the host is re-resolved: a
    changed answer (or none) is a ``dns_rebound: true`` error and the fetched
    bytes are discarded. That is the cheap stdlib mitigation of the v0 TOCTOU gap
    (the check resolves once, urllib resolves again to connect); the RESIDUAL
    risk is a resolver that flips public -> private -> public exactly between our
    two lookups, which only connecting to the checked address ourselves would
    close (a custom HTTPS connection class; not stdlib-cheap, not done here).
    ``READ_URL_ALLOW_PRIVATE=1`` -- a test/dev escape hatch (the test origin is
    127.0.0.1), default off -- skips both the check and the pin. No cookies or
    credentials are ever sent; a modest UA is.
    """

    platform = "read_url"
    label = "read_url (in-process fetch)"
    prefix = "ru"
    kind = "native"  # the fetch IS the tool; nothing is emulated
    health_path = ""  # no single backend to probe: the target is the public web
    error_tag = "read_url"

    def __init__(
        self,
        environ=None,
        fetch: Fetcher | None = None,
        resolver: Resolver | None = None,
    ) -> None:
        super().__init__("")  # no base URL: every call names its own origin
        self.environ = environ if environ is not None else os.environ
        self._fetch: Fetcher = fetch or _urllib_fetch
        self._resolver: Resolver = resolver or _default_resolver
        self._allow_private = _flag_enabled(self.environ, READ_URL_ALLOW_PRIVATE_ENV)
        self._min_chars = _min_chars_setting(self.environ)

    # ---- surface --------------------------------------------------------
    def _build_tools(self) -> list[AdapterTool]:
        return [
            AdapterTool(
                name="read_url",
                description=(
                    "Fetch ONE public http(s) page in-process (stdlib urllib; no child, "
                    "no cookies or credentials ever sent) and return its text off an "
                    "extractor ladder that names what happened. (1) Cloudflare "
                    "'Markdown for Agents' negotiated with Accept: text/markdown -- an "
                    "opted-in zone answers server-side clean markdown (extractor "
                    "cloudflare-markdown, quality high, tokens{markdown, original}); a "
                    "text/markdown origin is passed through as origin-markdown (high). "
                    "(2) For HTML, the OPTIONAL readability rung when installed: "
                    "rs-trafilatura (Rust) preferred, else trafilatura (pip install "
                    "trafilatura) -- quality high when the extract has >= "
                    "READ_URL_MIN_CHARS (default 200) chars, else one favor_recall retry "
                    "labelled medium; title/author/date come from its metadata. (3) The "
                    "stdlib html.parser tag-stripper (extractor stdlib-text, quality "
                    "low: it drops script/style/noscript/svg/template/nav/footer/aside/"
                    "header subtrees and collapses whitespace, which is NOT "
                    "readability). Every result carries extractor_ladder (rungs tried, "
                    "chosen last), page_type (a cheap HEURISTIC hint: article|docs|"
                    "listing|shell|other), chars, link_density, boilerplate_removed and "
                    "min_chars. Follows at most 5 redirects, re-checking each hop; "
                    "refuses .onion hosts (onions-lane envelope), non-http(s) schemes, "
                    "URLs with credentials, and hosts resolving to private/loopback/"
                    "link-local addresses -- EVERY resolved address is checked and the "
                    "host is re-resolved after the fetch: a changed answer is a "
                    "dns_rebound error and the bytes are discarded (READ_URL_ALLOW_"
                    "PRIVATE=1 is a dev/test escape hatch that skips both). Returns "
                    "{url, final_url, status, redirects, title, author, date, "
                    "content_type, extractor, quality, extractor_ladder, markdown|text, "
                    "tokens?, extractor_confidence?, chars, page_type, link_density, "
                    "boilerplate_removed, min_chars, bytes, truncated, note}. Truthful "
                    "isError on HTTP errors, binary content or an unreachable origin -- "
                    "never fabricated."
                ),
                input_schema=_READ_URL_SCHEMA,
                path="GET <url>",
                realized_by=NATIVE,
                method="GET",
            )
        ]

    def _resolved_state(self, tool: AdapterTool, probe_ok: bool | None) -> str:
        # No single backend can be absent: each call names its own public origin,
        # so the tool is natively realized whenever it is wired.
        return PROBED if probe_ok is True else NATIVE

    def probe(self) -> tuple[bool, str]:
        return (
            True,
            "in-process fetch; no backend to probe (each call names its origin)",
        )

    def capabilities(self, probe: bool = False) -> dict:
        report = super().capabilities(probe=probe)
        report["self_hosted"] = False  # fetches the public web, runs no daemon
        report["private_targets_allowed"] = self._allow_private
        report["negotiates"] = f"Accept: {READ_URL_ACCEPT}"
        report["max_redirects"] = READ_URL_MAX_REDIRECTS
        # The rung that WOULD run for HTML right now (find_spec, nothing imported).
        readability = _readability_label()
        report["readability_extractor"] = readability
        report["extractor_ladder"] = [
            "cloudflare-markdown | origin-markdown",
            *([readability] if readability else []),
            "stdlib-text",
        ]
        report["min_chars"] = self._min_chars
        report["dns_rebound_check"] = not self._allow_private
        return report

    # ---- argument validation (before any request) -------------------------
    @staticmethod
    def _url_arg(args: dict) -> str:
        url = args.get("url")
        if not isinstance(url, str) or not url.strip():
            raise ValueError("read_url: 'url' is required (an http(s) URL string)")
        return url.strip()

    @staticmethod
    def _timeout_arg(args: dict) -> float:
        value = args.get("timeout_s", READ_URL_DEFAULT_TIMEOUT_S)
        if value is None or value == "":
            value = READ_URL_DEFAULT_TIMEOUT_S
        if isinstance(value, str):
            try:
                value = float(value.strip())
            except ValueError:
                value = None
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not (1 <= value <= READ_URL_MAX_TIMEOUT_S)
        ):
            raise ValueError(
                f"read_url: 'timeout_s' must be a number between 1 and "
                f"{READ_URL_MAX_TIMEOUT_S} seconds"
            )
        return float(value)

    # ---- safety: scheme / .onion / credentials / private space -------------
    def _validate(self, url: str) -> tuple[str, frozenset[str] | None]:
        """The per-hop target check; ValueError names the refusal. No request is
        made for a refused URL, so the message can never leak a response.

        Returns ``(url, pinned)`` where ``pinned`` is the set of addresses the
        host resolved to and passed the public check with -- ``_verify_pin``
        compares the post-fetch answer against it -- or ``None`` when the
        private-target escape hatch skipped resolution altogether.
        """
        parts = urlsplit(url)
        host = parts.hostname or ""
        bare = host.lower().rstrip(".")
        if onions.is_onion_url(url) or bare.endswith(".onion") or bare == "onion":
            raise ValueError(
                f"read_url: refused: '{host}' is a .onion host. The onions-lane envelope "
                f"forbids fetching or rendering onion services anywhere in this hub "
                f"(index metadata only, no Tor), so no request was made. See "
                f"{onions.ENVELOPE_DOC}."
            )
        scheme = parts.scheme.lower()
        if scheme not in ("http", "https"):
            shown = f"scheme '{scheme}'" if scheme else "no scheme"
            raise ValueError(
                f"read_url: refused: only http and https URLs are fetched (got {shown} "
                f"in {_scrub_url(url)})."
            )
        if parts.username is not None or parts.password is not None:
            raise ValueError(
                "read_url: refused: the URL embeds credentials (user[:password]@host). "
                "read_url never sends credentials or cookies; remove them and pass the "
                "bare origin."
            )
        if not host:
            raise ValueError(f"read_url: refused: no host in {_scrub_url(url)}.")
        try:
            parts.port  # noqa: B018 (validation: raises on a malformed port)
        except ValueError as exc:
            raise ValueError(
                f"read_url: refused: invalid port in {url} ({exc})."
            ) from None
        if self._allow_private:
            return url, None
        return url, self._check_public(host)

    def _check_public(self, host: str) -> frozenset[str]:
        """Resolve ``host`` and refuse if ANY returned address is non-public; the
        full answer comes back as the pin ``_verify_pin`` re-checks after the fetch."""
        try:
            addresses = self._resolver(host)
        except (OSError, UnicodeError) as exc:  # socket.gaierror is an OSError
            raise ValueError(
                f"read_url: could not resolve host '{host}' ({exc}); no request was "
                f"made and no content is fabricated."
            ) from None
        if not addresses:
            raise ValueError(
                f"read_url: could not resolve host '{host}' (no addresses); no request "
                f"was made and no content is fabricated."
            )
        for text in addresses:
            try:
                addr = ipaddress.ip_address(text)
            except ValueError:
                raise ValueError(
                    f"read_url: refused: host '{host}' resolved to an unparseable "
                    f"address {text!r}; no request was made."
                ) from None
            if not _is_public_address(addr):
                raise ValueError(
                    f"read_url: refused: host '{host}' resolves to a private, loopback, "
                    f"link-local or otherwise non-public address ({text}); read_url "
                    f"fetches public web origins only, so no request was made. "
                    f"{READ_URL_ALLOW_PRIVATE_ENV}=1 is the test/dev escape hatch "
                    f"(default off) -- never set it in production."
                )
        return frozenset(addresses)

    def _verify_pin(self, url: str, pinned: frozenset[str] | None) -> None:
        """Re-resolve the host AFTER its fetch; an answer that differs from the one
        checked before the request is a ``dns_rebound`` refusal (bytes discarded).

        Cheap stdlib mitigation of the check-then-connect TOCTOU (urllib resolves
        again to connect). Sets are compared, so answer order and duplicates do
        not count. A rotating CDN with a very short TTL can trip this too -- the
        message says so and invites a retry, because the alternative is trusting
        bytes from an address that was never checked.
        """
        if pinned is None:
            return
        host = urlsplit(url).hostname or ""
        try:
            after = frozenset(self._resolver(host))
        except (OSError, UnicodeError) as exc:
            raise ValueError(
                f"read_url: dns_rebound: true -- '{host}' could not be re-resolved "
                f"after the fetch ({exc}), so the answer checked before the request "
                f"cannot be confirmed; the fetched bytes were discarded and no content "
                f"is returned. Retry once DNS for the host is stable."
            ) from None
        if after == pinned:
            return
        hostile = [text for text in sorted(after) if not _parses_public(text)]
        if hostile:
            why = (
                f" The new answer includes the non-public address(es) "
                f"{', '.join(hostile)} -- a DNS rebinding pattern; do not retry "
                f"without checking the host."
            )
        else:
            why = (
                " Both answers are public, which a rotating CDN answer or a very "
                "short TTL can also produce; retry if the host is expected to rotate."
            )
        raise ValueError(
            f"read_url: dns_rebound: true -- '{host}' resolved to "
            f"[{', '.join(sorted(pinned))}] before the fetch and to "
            f"[{', '.join(sorted(after))}] after it, so the connection may have gone "
            f"to an address that was never checked; the fetched bytes were discarded "
            f"and no content is returned.{why}"
        )

    # ---- the fetch chain ------------------------------------------------------
    @staticmethod
    def _request_headers() -> dict[str, str]:
        return {
            "Accept": READ_URL_ACCEPT,
            "Accept-Encoding": "identity",
            "User-Agent": USER_AGENT,
        }

    def _fetch_chain(
        self, url: str, max_bytes: int, timeout: float
    ) -> tuple[str, int, int, dict[str, str], bytes]:
        """Follow at most ``READ_URL_MAX_REDIRECTS`` hops, validating EVERY target
        before its fetch and re-resolving it (``_verify_pin``) right after.

        Returns ``(final_url, status, redirects, response_headers, body)``; body
        may hold ``max_bytes + 1`` bytes (the cap signal). ValueError on refusal,
        transport failure, a DNS answer that changed, a Location-less 3xx, or the
        hop cap.
        """
        current, pinned = self._validate(url)
        hops = 0
        while True:
            status, headers, body, reason = self._fetch(
                current, self._request_headers(), timeout, max_bytes
            )
            if status == 0:
                raise ValueError(
                    f"read_url: {reason or 'request failed'} ({current}); no content "
                    f"is fabricated."
                )
            self._verify_pin(current, pinned)
            if status not in _REDIRECT_STATUSES:
                return current, status, hops, headers, body
            location = str(headers.get("location") or "").strip()
            if not location:
                raise ValueError(
                    f"read_url: HTTP {status} redirect from {current} carries no "
                    f"Location header; nothing to follow, no content is fabricated."
                )
            if hops >= READ_URL_MAX_REDIRECTS:
                raise ValueError(
                    f"read_url: too many redirects (more than {READ_URL_MAX_REDIRECTS}) "
                    f"starting at {url}; last hop {current} -> "
                    f"{_scrub_url(urljoin(current, location))}. Refused."
                )
            hops += 1
            current, pinned = self._validate(urljoin(current, location))

    # ---- result shaping -----------------------------------------------------
    def _shape(
        self,
        url: str,
        final_url: str,
        status: int,
        redirects: int,
        headers: dict[str, str],
        body: bytes,
        max_bytes: int,
    ) -> dict:
        hit_cap = len(body) > max_bytes
        body = body[:max_bytes]
        encoding = str(headers.get("content-encoding") or "").strip().lower()
        if encoding not in ("", "identity"):
            inflated = _inflate(body, encoding, max_bytes + 1)
            if inflated is None:
                raise ValueError(
                    f"read_url: {final_url} answered Content-Encoding {encoding!r}, which "
                    f"this stdlib fetch cannot decode (it asked for identity); no "
                    f"content is fabricated."
                )
            hit_cap = hit_cap or len(inflated) > max_bytes
            body = inflated[:max_bytes]
        media, charset = _split_content_type(headers.get("content-type"))
        if not (200 <= status < 300):
            raise ValueError(
                f"read_url: HTTP {status} for {final_url} (Content-Type "
                f"{media or 'unknown'}); no content is fabricated."
            )
        if not media:
            media = _sniff_media(body)
        textual = (
            media in _HTML_TYPES or media.startswith("text/") or media in _TEXT_TYPES
        )
        if not textual:
            raise ValueError(
                f"read_url: {final_url} is {media}, not text -- read_url extracts text "
                f"from text/markdown, text/html and text/plain (plus JSON/XML) "
                f"responses only; nothing is fabricated for binary content."
            )
        payload: dict = {
            "tool": "read_url",
            "url": url,
            "final_url": final_url,
            "status": status,
            "redirects": redirects,
        }
        if media == "text/markdown":
            capped, notes = self._shape_markdown(
                payload, body, charset, headers, max_bytes
            )
        elif media in _HTML_TYPES:
            capped, notes = self._shape_html(
                payload, body, charset, media, final_url, max_bytes
            )
        else:
            capped, notes = self._shape_plain(payload, body, charset, media, max_bytes)
        payload["min_chars"] = self._min_chars
        payload["bytes"] = len(body)
        payload["truncated"] = bool(hit_cap or capped)
        payload["note"] = " ".join(notes)
        return payload

    @staticmethod
    def _shape_markdown(
        payload: dict,
        body: bytes,
        charset: str | None,
        headers: dict[str, str],
        max_bytes: int,
    ) -> tuple[bool, list[str]]:
        """Rung 1: negotiated (Cloudflare) or origin markdown, passed through."""
        markdown, capped = _cap_text(_decode_body(body, charset, html=False), max_bytes)
        tokens = {
            "markdown": _int_header(headers, "x-markdown-tokens"),
            "original": _int_header(headers, "x-original-tokens"),
        }
        cloudflare = any(v is not None for v in tokens.values())
        extractor = "cloudflare-markdown" if cloudflare else "origin-markdown"
        page_type, density = _classify_markdown(markdown)
        payload.update(
            title=_markdown_title(markdown),
            author=_frontmatter_field(markdown, "author"),
            date=_frontmatter_field(markdown, "date"),
            content_type="text/markdown",
            extractor=extractor,
            quality="high",
            extractor_ladder=[extractor],
            markdown=markdown,
        )
        if cloudflare:
            payload["tokens"] = tokens
            note = (
                "quality high: markdown produced server-side by Cloudflare Markdown "
                "for Agents (Accept: text/markdown negotiated; x-markdown-tokens / "
                "x-original-tokens relayed)."
            )
        else:
            note = (
                "quality high: the origin served text/markdown itself (no Cloudflare "
                "token headers); passed through verbatim."
            )
        payload.update(
            chars=len(markdown),
            page_type=page_type,
            link_density=density,
            boilerplate_removed=True,
        )
        return capped, [note]

    def _shape_html(
        self,
        payload: dict,
        body: bytes,
        charset: str | None,
        media: str,
        final_url: str,
        max_bytes: int,
    ) -> tuple[bool, list[str]]:
        """Rungs 2-3 for an HTML body. The tag-stripper ALWAYS runs: it is the
        fallback text, the ``<title>`` fallback, the page_type / link_density
        signal and the yardstick a too-short recall extract is measured against."""
        html = _decode_body(body, charset, html=True)
        parser = _TextExtractor()
        parser.feed(html)
        html_title, plain = parser.result()
        page_type = _classify_html(len(plain), parser.stats, len(body), final_url)
        density = _link_density(parser.stats, len(plain))
        ladder, notes, chosen = self._readability(html, final_url, len(plain))
        if chosen is None:
            ladder.append("stdlib-text")
            text, capped = _cap_text(plain, max_bytes)
            payload.update(
                title=html_title,
                author=None,
                date=None,
                content_type=media,
                extractor="stdlib-text",
                quality="low",
                extractor_ladder=ladder,
                text=text,
                chars=len(text),
                page_type=page_type,
                link_density=density,
                boilerplate_removed=False,
            )
            notes.insert(
                0,
                "quality low: stdlib html.parser tag-stripping is not readability -- "
                "boilerplate outside the dropped subtrees (script/style/noscript/svg/"
                "template/nav/footer/aside/header) survives.",
            )
            if len(ladder) == 1:  # no readability rung was importable at all
                notes.append(
                    "No readability extractor is installed: `pip install trafilatura` "
                    "(deploy/requirements-optional.txt) enables the trafilatura rung."
                )
            return capped, notes
        text, capped = _cap_text(chosen.text.strip(), max_bytes)
        payload.update(
            title=chosen.meta.get("title") or html_title,
            author=chosen.meta.get("author"),
            date=chosen.meta.get("date"),
            content_type=media,
            extractor=chosen.label,
            quality=chosen.quality,
            extractor_ladder=ladder,
        )
        payload[chosen.key] = text
        if chosen.confidence is not None:
            payload["extractor_confidence"] = chosen.confidence
        payload.update(
            chars=len(text),
            page_type=page_type,
            link_density=density,
            boilerplate_removed=True,
        )
        if chosen.note:
            notes.append(chosen.note)
        return capped, notes

    def _readability(
        self, html: str, url: str, page_chars: int
    ) -> tuple[list[str], list[str], _Readable | None]:
        """Rung 2: each importable readability module in preference order.

        Precision pass first; ``high`` when it reaches ``min_chars``. Otherwise ONE
        ``favor_recall`` retry (ladder entry ``<label>-recall``) labelled
        ``medium`` -- kept below ``min_chars`` only when it still covers
        ``_RECALL_MIN_COVERAGE`` of the page's visible text. Exceptions and
        too-little text fall through to the next module, then to the stdlib text,
        each leaving a note. Returns ``(ladder, notes, chosen | None)``; the
        metadata pass runs only for the winner.
        """
        ladder: list[str] = []
        history: list[str] = []
        for module_name, label in _READABILITY_MODULES:
            mod = _optional_module(module_name)
            if mod is None:
                continue
            run = _READABILITY_RUNNERS[module_name]
            ladder.append(label)
            try:
                first = run(mod, html, url, favor_recall=False)
            except Exception as exc:  # noqa: BLE001 -- a broken optional install
                history.append(  # must degrade the ladder, never break read_url
                    f"{label} raised {type(exc).__name__}: {exc}; fell through."
                )
                continue
            if first.chars >= self._min_chars:
                first.label, first.quality = label, "high"
                note = (
                    f"quality high: {label} readability extraction, {first.chars} "
                    f"chars (>= min_chars {self._min_chars}); boilerplate removed by "
                    f"the extractor."
                )
                return (
                    ladder,
                    [note, *history],
                    self._with_meta(module_name, mod, html, url, first),
                )
            ladder.append(f"{label}-recall")
            try:
                second = run(mod, html, url, favor_recall=True)
            except Exception as exc:  # noqa: BLE001 -- same reason as above
                history.append(
                    f"{label} precision pass {first.chars} chars; the favor_recall "
                    f"retry raised {type(exc).__name__}: {exc}; fell through."
                )
                continue
            # A page with NO visible text (an app shell) has nothing to cover: the
            # real rs-trafilatura returned the <title> three times on one.
            covers_page = (
                page_chars > 0 and second.chars >= _RECALL_MIN_COVERAGE * page_chars
            )
            if second.chars and (second.chars >= self._min_chars or covers_page):
                second.label, second.quality = label, "medium"
                note = (
                    f"quality medium: {label}'s precision pass yielded {first.chars} "
                    f"chars (< min_chars {self._min_chars}), so the favor_recall retry "
                    f"produced this text ({second.chars} chars)."
                )
                return (
                    ladder,
                    [note, *history],
                    self._with_meta(module_name, mod, html, url, second),
                )
            history.append(
                f"{label} found too little: precision pass {first.chars} chars, "
                f"favor_recall pass {second.chars} chars (min_chars {self._min_chars}; "
                f"the page's visible text is {page_chars} chars), so the stdlib text "
                f"is returned instead."
            )
        return ladder, history, None

    @staticmethod
    def _with_meta(
        module_name: str, mod, html: str, url: str, chosen: _Readable
    ) -> _Readable:
        fetch_meta = _READABILITY_METADATA.get(module_name)
        if fetch_meta is not None and not chosen.meta:
            chosen.meta = fetch_meta(mod, html, url)
        return chosen

    @staticmethod
    def _shape_plain(
        payload: dict, body: bytes, charset: str | None, media: str, max_bytes: int
    ) -> tuple[bool, list[str]]:
        """Rung 3 only: ``text/plain``, JSON, XML ... pass through; no extraction
        applies, so there is no page signal either."""
        text, capped = _cap_text(
            _normalize_plain(_decode_body(body, charset, html=False)), max_bytes
        )
        payload.update(
            title=None,
            author=None,
            date=None,
            content_type=media,
            extractor="stdlib-text",
            quality="low",
            extractor_ladder=["stdlib-text"],
            text=text,
            chars=len(text),
            page_type="other",
            link_density=0.0,
            boilerplate_removed=False,
        )
        note = (
            f"quality low: {media} passed through with whitespace collapsed (no "
            f"extraction applies; the readability rung targets HTML only)."
        )
        return capped, [note]

    # ---- the call path (always truthful) ----------------------------------
    def handle_call(self, name: str, arguments: dict) -> dict:
        tool = self._tool(name)
        if tool is None:
            return self._error(f"unknown read_url tool {name!r}")
        args = arguments or {}
        try:
            url = self._url_arg(args)
            max_bytes = _int_arg(
                args,
                "max_bytes",
                READ_URL_DEFAULT_MAX_BYTES,
                READ_URL_MIN_MAX_BYTES,
                READ_URL_HARD_MAX_BYTES,
                "read_url",
            )
            timeout = self._timeout_arg(args)
            final_url, status, redirects, headers, body = self._fetch_chain(
                url, max_bytes, timeout
            )
            payload = self._shape(
                url, final_url, status, redirects, headers, body, max_bytes
            )
        except ValueError as exc:
            return self._error(str(exc))
        return self._ok(payload)


def default_adapters(environ, caller: Caller | None = None) -> list[SelfHostedAdapter]:
    """The lane-gated self-hosted builder (its historical contract, unchanged).

    TrailSearch (the Tavily slot) is always present. The OSSInsight repo-discovery
    lane is default OFF and wired only when ``ENABLE_OSSINSIGHT`` is truthy
    (see docs/legal/onions-lane-envelope.md). The hub itself wires
    ``wired_adapters`` (this list + the default-ON public lanes below).
    """
    built: list[SelfHostedAdapter] = [
        TrailSearchAdapter(resolve_base_url(environ), caller=caller)
    ]
    if _flag_enabled(environ, ENABLE_OSSINSIGHT_ENV):
        oss_url = (
            environ.get("OSSINSIGHT_URL") or ""
        ).strip() or DEFAULT_OSSINSIGHT_URL
        built.append(OSSInsightAdapter(oss_url, caller=caller))
    return built


def keyless_public_adapters(environ) -> list[SelfHostedAdapter]:
    """The DEFAULT-ON public lanes: GitHub REST search + ``read_url``, kill switches.

    Default ON -- unlike the opt-in OSSInsight lane -- because each is keyless,
    costs nothing at rest (in-process stdlib HTTP, no child, no new dependency,
    no request until a tool is called), talks to a first-party public API or to
    the public web under the origin's own terms, and carries no legal shadow.
    ``ENABLE_GITHUB_SEARCH=0`` / ``ENABLE_READ_URL=0`` unwire one lane each; the
    GitHub token is read by env NAME only (``GITHUB_TOKEN``, then ``GH_TOKEN``)
    and never leaves the request header.
    """
    built: list[SelfHostedAdapter] = []
    if not _lane_killed(environ, ENABLE_GITHUB_SEARCH_ENV):
        base = (environ.get(GITHUB_API_URL_ENV) or "").strip() or DEFAULT_GITHUB_API_URL
        token = ""
        for name in GITHUB_TOKEN_ENVS:
            value = environ.get(name)
            if isinstance(value, str) and value.strip():
                token = value.strip()
                break
        built.append(GitHubSearchAdapter(base, token=token or None))
    if not _lane_killed(environ, ENABLE_READ_URL_ENV):
        built.append(ReadUrlAdapter(environ=environ))
    return built


def wired_adapters(environ, caller: Caller | None = None) -> list[SelfHostedAdapter]:
    """Everything the hub wires: ``default_adapters`` first (unchanged order), then
    ``keyless_public_adapters``. ``hub.py`` calls this; callers pinning the
    historical lane-gated list keep calling ``default_adapters``."""
    return default_adapters(environ, caller=caller) + keyless_public_adapters(environ)


def _flag_enabled(environ, name: str) -> bool:
    """An OPT-IN flag: only an explicit truthy value turns the lane on."""
    value = environ.get(name)
    return isinstance(value, str) and value.strip().lower() not in (
        "",
        "0",
        "false",
        "no",
        "off",
    )


def _lane_killed(environ, name: str) -> bool:
    """A DEFAULT-ON lane's kill switch: only an explicit falsey value unwires it.

    Mirrors ``onions.is_kill_switched`` -- unset and "" both mean ON, so a lane
    that is keyless and costless cannot be lost to a missing variable.
    """
    value = environ.get(name)
    return isinstance(value, str) and value.strip().lower() in (
        "0",
        "false",
        "no",
        "off",
    )
