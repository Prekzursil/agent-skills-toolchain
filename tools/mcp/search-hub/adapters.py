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

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable
from urllib.parse import quote

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


def _default_caller(
    method: str, url: str, body: bytes | None, headers: dict[str, str], timeout: float
) -> tuple[int, dict | list | None, str]:
    """Real HTTP call returning (status, parsed-json-or-None, raw-body). Safe.

    A transport failure (backend down, DNS, reset, timeout) comes back as
    ``(0, None, "<reason>")`` so the caller can degrade truthfully rather than
    raise -- the self-hosted daemon being off must never crash the hub.
    """
    req = urllib.request.Request(  # noqa: S310 (loopback/http backend by config)
        url, data=body, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            status = resp.getcode() or 0
            raw = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        status = exc.code
        raw = exc.read().decode("utf-8", "replace") if exc.fp else ""
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return 0, None, f"request failed: {exc}"
    try:
        return status, json.loads(raw), raw
    except (json.JSONDecodeError, ValueError):
        return status, None, raw


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
            "content": [{"type": "text", "text": f"[search-hub:self-hosted] {text}"}],
            "isError": True,
        }


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


def default_adapters(environ, caller: Caller | None = None) -> list[SelfHostedAdapter]:
    """The self-hosted adapters wired into the hub.

    TrailSearch (the Tavily slot) is always present. The OSSInsight repo-discovery
    lane is default OFF and wired only when ``ENABLE_OSSINSIGHT`` is truthy
    (see docs/legal/onions-lane-envelope.md).
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


def _flag_enabled(environ, name: str) -> bool:
    value = environ.get(name)
    return isinstance(value, str) and value.strip().lower() not in (
        "",
        "0",
        "false",
        "no",
        "off",
    )
