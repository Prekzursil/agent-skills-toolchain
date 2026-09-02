#!/usr/bin/env python3
"""The keyless ``grounding`` lane: Wikipedia + Wayback Machine + Hacker News (default ON).

Gem-hunt program, Wave 2: three public, keyless, first-party APIs that ground a
research answer -- an encyclopedia summary, a dated archived copy, and the
technical-community discussion -- wired through the SAME in-process mechanism as
``adapters.GitHubSearchAdapter``: stdlib ``urllib`` with a timeout on every
request, no child process, no new dependency, no request until a tool is called,
and the capability lattice + truthful degradation of ``adapters.SelfHostedAdapter``.
ONE adapter carries all three sources so ``hub.py --print-plan`` shows a single
``grounding`` bucket (it counts tools per platform, one adapter per platform);
``ENABLE_WIKIPEDIA=0`` / ``ENABLE_WAYBACK=0`` / ``ENABLE_HN=0`` each drop one
source's tools, and ``build`` returns ``[]`` when all three are killed.

Endpoints and shapes, measured live 2026-09-02 with curl (receipts in the README):

* Wikipedia search ``GET {WIKIPEDIA_API_URL}/w/api.php?action=query&list=search
  &format=json&srsearch=..&srlimit=N`` -> ``{batchcomplete, continue, query:
  {searchinfo: {totalhits, suggestion, suggestionsnippet}, search: [{ns, title,
  pageid, size, wordcount, snippet, timestamp}]}}``. ``snippet`` is HTML
  (``<span class="searchmatch">`` + entities) and is stripped and unescaped here.
  A bad request is HTTP **200** with ``{"error": {"code", "info"}}`` (measured:
  ``missingparam``) -> a truthful error, never "0 results". ``lang`` swaps the
  host's first label (``de.wikipedia.org`` answered 200) and is accepted only
  when it matches ``^[a-z]{2,3}(-[a-z]+)?$``.
* Wikipedia summary ``GET /api/rest_v1/page/summary/{title}`` -> ``{type, title,
  pageid, description, extract, thumbnail?, content_urls, lang, ...}``;
  ``type: disambiguation`` for ``Mercury`` (flagged, never hidden); a missing
  page is HTTP 404 with the body ``{"status":404,"type":"Internal error"}``
  (verbatim) -> "no such page". A ``/`` in a title travels as ``%2F``
  (``AC%2FDC`` answered 200 and Wikipedia's own ``content_urls`` encode it that
  way). Wikimedia's API policy requires a descriptive ``User-Agent`` with
  contact information: every request sends ``USER_AGENT``.
* Wayback availability ``GET {WAYBACK_API_URL}/wayback/available?url=..
  [&timestamp=..]`` -> ``{url, archived_snapshots: {closest: {status, available,
  url, timestamp}}}`` (+ the request ``timestamp`` echoed); a never-archived URL
  is HTTP 200 with ``archived_snapshots: {}`` -> ``available: false`` + note --
  the truthful answer, not an error. The API is INTERMITTENT: at 07:42Z
  ``example.com&timestamp=20200101`` answered ``{}`` although the CDX index lists
  2015 captures, so the note points at ``wayback_snapshots`` (the index) rather
  than asserting "never archived".
* Wayback CDX ``GET {WAYBACK_CDX_URL}/cdx/search/cdx?url=..&output=json&limit=N
  &fl=timestamp,original,statuscode,mimetype&filter=statuscode:200[&from=YYYY]
  [&to=YYYY]`` -> a JSON array of arrays whose FIRST row is the header (measured:
  ``["timestamp","original","statuscode","mimetype"]``); rows are mapped by that
  header, never by assumed position. "No captures" is ``[]`` in JSON mode
  (measured: HTTP 200, 3 bytes) and an EMPTY body in the plain mode -- both are
  zero captures here. The CDX host is ``web.archive.org``, a second env so one
  loopback fake can serve both hosts. The host FLAPS: four probes inside one
  minute (07:42Z) answered 503, 200, 503, 200, the 503 being an 11.8 KB text/html
  "Internet Archive: Temporarily Offline" page (earlier the same morning every
  CDX probe was 503). That is relayed as a truthful error carrying the page's
  words -- ``<style>``/``<script>`` subtrees dropped, tags stripped -- and the
  remedy is to retry later, never to report "no captures".
* Hacker News ``GET {HN_API_URL}/api/v1/search`` (relevance) or
  ``/api/v1/search_by_date`` (newest first) ``?query=..&tags=..&hitsPerPage=N``
  -> ``{hits, nbHits, nbPages, page, hitsPerPage, query, params, ...}``; story
  hits carry ``title, url, points, num_comments, author, created_at, objectID``,
  comment hits ``comment_text, story_title, story_url`` (no title/url) -- both
  shapes are relayed. An unknown ``tags`` value is HTTP 200 with ``nbHits: 0``
  (measured), so tags are validated locally against the documented grammar
  instead of letting a typo pass as an honest "nothing found".

Every success carries ``source`` (``wikipedia`` | ``wayback`` | ``hn``) and
``fetched_at`` (UTC, ``YYYY-MM-DDTHH:MM:SSZ``); every failure is an ``isError``
naming the source and the upstream status -- rate limits (429, with any
``Retry-After``), 404, non-JSON bodies, transport errors, timeouts -- and nothing
is ever fabricated. Arguments are validated BEFORE a request is spent. ``.onion``
URLs are refused before any request (``onions.is_onion_url``): the onions-lane
envelope forbids fetching or rendering onion services anywhere in this hub, and
the Wayback Machine would replay one.
"""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from typing import Callable
from urllib.parse import quote, urlencode, urlsplit, urlunsplit

import onions
from adapters import (
    ABSENT,
    NATIVE,
    PROBE_TIMEOUT,
    PROBED,
    AdapterTool,
    HeaderCaller,
    SelfHostedAdapter,
    _default_header_caller,
    _int_arg,
    _lane_killed,
)

PLATFORM = "grounding"
WIKIPEDIA = "wikipedia"
WAYBACK = "wayback"
HN = "hn"
SOURCES: tuple[str, ...] = (WIKIPEDIA, WAYBACK, HN)

DEFAULT_WIKIPEDIA_URL = "https://en.wikipedia.org"
DEFAULT_WAYBACK_URL = "https://archive.org"
DEFAULT_WAYBACK_CDX_URL = "https://web.archive.org"
DEFAULT_HN_URL = "https://hn.algolia.com"
WIKIPEDIA_API_URL_ENV = "WIKIPEDIA_API_URL"
WAYBACK_API_URL_ENV = "WAYBACK_API_URL"
WAYBACK_CDX_URL_ENV = "WAYBACK_CDX_URL"
HN_API_URL_ENV = "HN_API_URL"
ENABLE_WIKIPEDIA_ENV = "ENABLE_WIKIPEDIA"
ENABLE_WAYBACK_ENV = "ENABLE_WAYBACK"
ENABLE_HN_ENV = "ENABLE_HN"
KILL_SWITCHES: dict[str, str] = {
    WIKIPEDIA: ENABLE_WIKIPEDIA_ENV,
    WAYBACK: ENABLE_WAYBACK_ENV,
    HN: ENABLE_HN_ENV,
}
URL_ENVS: dict[str, tuple[str, str]] = {
    WIKIPEDIA: (WIKIPEDIA_API_URL_ENV, DEFAULT_WIKIPEDIA_URL),
    WAYBACK: (WAYBACK_API_URL_ENV, DEFAULT_WAYBACK_URL),
    HN: (HN_API_URL_ENV, DEFAULT_HN_URL),
}

GROUNDING_TIMEOUT = 15.0  # seconds, on every tool request (probes: PROBE_TIMEOUT)
# Wikimedia's User-Agent policy asks for a descriptive agent with contact
# information (a project URL qualifies); the same header goes to every source.
USER_AGENT = (
    "search-hub/0.1 (https://github.com/prekzursil/agent-skills-toolchain; "
    "grounding lane: Wikipedia, Wayback Machine, Hacker News) python-urllib"
)
DEFAULT_LANG = "en"

TOOL_SOURCES: dict[str, str] = {
    "wikipedia_search": WIKIPEDIA,
    "wikipedia_summary": WIKIPEDIA,
    "wayback_available": WAYBACK,
    "wayback_snapshots": WAYBACK,
    "hn_search": HN,
}

WIKIPEDIA_DEFAULT_LIMIT = 10
WIKIPEDIA_MAX_LIMIT = 20
# CirrusSearch rejects a search request "longer than the maximum allowed length"
# past 300 characters; MediaWiki page titles are at most 255 bytes.
WIKIPEDIA_MAX_QUERY = 300
WIKIPEDIA_MAX_TITLE = 255
WAYBACK_DEFAULT_LIMIT = 20
WAYBACK_MAX_LIMIT = 50
WAYBACK_MAX_URL = 2048
HN_DEFAULT_LIMIT = 20
HN_MAX_LIMIT = 50
HN_MAX_QUERY = 512  # Algolia rejects queries over 512 bytes
HN_SORTS = ("relevance", "date")
HN_ITEM_URL = "https://news.ycombinator.com/item?id={id}"
CDX_FIELDS = ("timestamp", "original", "statuscode", "mimetype")

_LANG_RE = re.compile(r"^[a-z]{2,3}(-[a-z]+)?$")
# A Wikipedia language host: <label>.wikipedia.org or <label>.m.wikipedia.org.
_WIKI_LANG_HOST_RE = re.compile(r"^([a-z0-9-]+)\.((?:m\.)?wikipedia\.org)$")
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
_WAYBACK_TIMESTAMP_RE = re.compile(r"^[0-9]{4,14}$")
_YEAR_RE = re.compile(r"^[0-9]{4}$")
# Anything naming a .onion host, even inside a replay URL such as
# web.archive.org/web/<ts>/http://x.onion/ -- the Wayback Machine would render it.
# ".onion" must END the host (optionally FQDN-dotted): a clearnet
# "foo.onion.example" is not an onion service and is not refused.
_ONION_ANYWHERE_RE = re.compile(r"\.onion\.?(?=[/:?#]|$)", re.IGNORECASE)
# HN Algolia tags: the documented tokens; comma = AND, one (a,b) group = OR.
_HN_TOKEN = (
    r"(?:story|comment|poll|pollopt|show_hn|ask_hn|front_page"
    r"|author_[A-Za-z0-9_-]{1,64}|story_[0-9]{1,12})"
)
_HN_ITEM = rf"(?:{_HN_TOKEN}|\({_HN_TOKEN}(?:,{_HN_TOKEN})*\))"
_HN_TAGS_RE = re.compile(rf"^{_HN_ITEM}(?:,{_HN_ITEM})*$")
# strip_html: <script>/<style> subtrees go first (the CDX 503 page carries a
# <style> block whose CSS would otherwise survive as "text"), then block /
# line-break tags become a space, inline tags vanish (so a highlight span around
# "open" in "open-source" never splits the token), entities decode and
# whitespace collapses.
_DROP_SUBTREE_RE = re.compile(
    r"<(script|style)\b[^>]*>.*?</\1\s*>", re.IGNORECASE | re.DOTALL
)
_BREAK_TAG_RE = re.compile(
    r"</?(?:br|p|div|li|ul|ol|tr|td|th|h[1-6]|title|head|body|html|blockquote"
    r"|pre|hr|table)\b[^>]*>",
    re.IGNORECASE,
)
_TAG_RE = re.compile(r"<[^>]*>")
_WS_RE = re.compile(r"\s+")
# MediaWiki's canonical URL encoding (wfUrlencode) leaves ;:@$!*(), unencoded;
# "/" travels as %2F because the REST route is ONE path segment and Wikipedia's
# own content_urls encode it that way (measured: AC%2FDC).
_TITLE_SAFE = ";:@$!*(),"

_LANG_PROP = {
    "type": "string",
    "default": DEFAULT_LANG,
    "pattern": "^[a-z]{2,3}(-[a-z]+)?$",
    "description": (
        "Wikipedia language edition, e.g. 'en', 'de', 'zh-yue': swaps the host's "
        "language subdomain; only ^[a-z]{2,3}(-[a-z]+)?$ is accepted"
    ),
}
_WIKIPEDIA_SEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": f"full-text search terms (<= {WIKIPEDIA_MAX_QUERY} characters)",
        },
        "limit": {
            "type": "integer",
            "minimum": 1,
            "maximum": WIKIPEDIA_MAX_LIMIT,
            "default": WIKIPEDIA_DEFAULT_LIMIT,
            "description": f"how many results (1-{WIKIPEDIA_MAX_LIMIT})",
        },
        "lang": _LANG_PROP,
    },
    "required": ["query"],
}
_WIKIPEDIA_SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {
            "type": "string",
            "description": (
                "exact page title, e.g. 'Model Context Protocol' or 'Mercury (planet)' "
                f"(<= {WIKIPEDIA_MAX_TITLE} characters; spaces and underscores are "
                "equivalent)"
            ),
        },
        "lang": _LANG_PROP,
    },
    "required": ["title"],
}
_WAYBACK_URL_PROP = {
    "type": "string",
    "description": (
        "the URL (or bare host/path) to look up in the Wayback Machine; .onion "
        "hosts are refused"
    ),
}
_WAYBACK_AVAILABLE_SCHEMA = {
    "type": "object",
    "properties": {
        "url": _WAYBACK_URL_PROP,
        "timestamp": {
            "type": "string",
            "default": "",
            "pattern": "^[0-9]{4,14}$",
            "description": (
                "optional YYYYMMDD (4-14 digits, YYYY[MM[DD[hhmmss]]]): return the "
                "capture closest to it instead of the latest"
            ),
        },
    },
    "required": ["url"],
}
_WAYBACK_SNAPSHOTS_SCHEMA = {
    "type": "object",
    "properties": {
        "url": _WAYBACK_URL_PROP,
        "limit": {
            "type": "integer",
            "minimum": 1,
            "maximum": WAYBACK_MAX_LIMIT,
            "default": WAYBACK_DEFAULT_LIMIT,
            "description": f"how many captures (1-{WAYBACK_MAX_LIMIT}), oldest first",
        },
        "from_year": {
            "type": "string",
            "default": "",
            "pattern": "^[0-9]{4}$",
            "description": "optional 4-digit year: captures from this year on",
        },
        "to_year": {
            "type": "string",
            "default": "",
            "pattern": "^[0-9]{4}$",
            "description": "optional 4-digit year: captures up to and including it",
        },
    },
    "required": ["url"],
}
_HN_SEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": f"search terms (<= {HN_MAX_QUERY} characters)",
        },
        "tags": {
            "type": "string",
            "default": "story",
            "description": (
                "AND-list of story|comment|poll|pollopt|show_hn|ask_hn|front_page|"
                "author_<username>|story_<id>, e.g. 'story,author_pg'; one (a,b) "
                "group is OR"
            ),
        },
        "limit": {
            "type": "integer",
            "minimum": 1,
            "maximum": HN_MAX_LIMIT,
            "default": HN_DEFAULT_LIMIT,
            "description": f"how many hits (1-{HN_MAX_LIMIT})",
        },
        "sort": {
            "type": "string",
            "enum": list(HN_SORTS),
            "default": "relevance",
            "description": (
                "'relevance' (Algolia ranking, /api/v1/search) or 'date' (newest "
                "first, /api/v1/search_by_date)"
            ),
        },
    },
    "required": ["query"],
}


class _UpstreamError(Exception):
    """A truthful upstream failure text raised from inside a tool handler."""


# --------------------------------------------------------------------------- #
# pure helpers (unit-tested directly)
# --------------------------------------------------------------------------- #
def strip_html(text) -> str:
    """Plain text from an HTML fragment.

    ``<script>``/``<style>`` subtrees are dropped (the CDX 503 page ships CSS),
    block / line-break tags become a space, inline tags are removed (so a
    ``<span class="searchmatch">`` around one token never splits it), entities
    are decoded and whitespace is collapsed. Meant for MediaWiki search snippets,
    HN comment bodies and upstream HTML error pages -- it is NOT a sanitiser.
    """
    if not isinstance(text, str) or not text:
        return ""
    text = _DROP_SUBTREE_RE.sub(" ", text)
    text = _BREAK_TAG_RE.sub(" ", text)
    text = _TAG_RE.sub("", text)
    return _WS_RE.sub(" ", html.unescape(text)).strip()


def _host_lang(base_url: str) -> str | None:
    """The language label of a ``*.wikipedia.org`` host, else ``None``."""
    host = (urlsplit(base_url).hostname or "").lower()
    match = _WIKI_LANG_HOST_RE.match(host)
    return match.group(1) if match else None


def wikipedia_host_for(base_url: str, lang: str) -> str:
    """The Wikipedia base URL for ``lang``: the host's language label swapped.

    ``lang`` must match ``^[a-z]{2,3}(-[a-z]+)?$`` (``en``, ``de``, ``zh-yue``,
    ``ceb``); anything else raises ``ValueError`` and no request is spent. On a
    ``*.wikipedia.org`` (or ``*.m.wikipedia.org``) host the first label is
    replaced, keeping scheme, port and path. On any other host -- a loopback
    fake, a mirror -- there is no language subdomain to swap, so only the default
    ``lang`` passes through unchanged and another one is refused honestly.
    """
    if not isinstance(lang, str) or not _LANG_RE.match(lang):
        raise ValueError(
            f"'lang' must match ^[a-z]{{2,3}}(-[a-z]+)?$ (a Wikipedia language "
            f"code such as en, de or zh-yue); got {lang!r}"
        )
    base = (base_url or "").rstrip("/")
    parts = urlsplit(base)
    host = (parts.hostname or "").lower()
    match = _WIKI_LANG_HOST_RE.match(host)
    if match:
        if match.group(1) == lang:
            return base
        netloc = f"{lang}.{match.group(2)}"
        if parts.port:
            netloc = f"{netloc}:{parts.port}"
        return urlunsplit(
            (parts.scheme, netloc, parts.path.rstrip("/"), parts.query, "")
        )
    if lang == DEFAULT_LANG:
        return base
    raise ValueError(
        f"'lang' {lang!r} cannot be honoured: the configured Wikipedia host "
        f"{host!r} ({WIKIPEDIA_API_URL_ENV}) is not a *.wikipedia.org language "
        f"host, so there is no language subdomain to swap. Use the default lang "
        f"({DEFAULT_LANG}) or point {WIKIPEDIA_API_URL_ENV} at "
        f"https://{lang}.wikipedia.org. No request was made."
    )


def _title_path(title: str) -> str:
    """A page title as one URL path segment (spaces -> ``_``, MediaWiki-safe set)."""
    return quote(title.strip().replace(" ", "_"), safe=_TITLE_SAFE)


def parse_cdx_rows(parsed) -> list[dict[str, str | None]]:
    """Rows of a CDX ``output=json`` body keyed by ITS header row.

    The body is a JSON array of arrays; the first row names the columns in the
    order the server chose (``fl`` order), so every row is mapped by that header
    and never by an assumed position. ``[]`` (how JSON mode says "no captures",
    measured 2026-09-02) is zero rows. Anything else -- a dict, a non-list row, a
    header without ``timestamp`` / ``original`` -- raises ``ValueError``.
    """
    if isinstance(parsed, list) and not parsed:
        return []
    if not isinstance(parsed, list) or not all(isinstance(r, list) for r in parsed):
        kind = type(parsed).__name__
        raise ValueError(f"the CDX body is not a JSON array of arrays (got {kind})")
    header = [str(name) for name in parsed[0]]
    if "timestamp" not in header or "original" not in header:
        raise ValueError(
            f"the CDX header row {header!r} lacks 'timestamp' / 'original'"
        )
    rows: list[dict[str, str | None]] = []
    for row in parsed[1:]:
        entry: dict[str, str | None] = {}
        for index, name in enumerate(header):
            value = row[index] if index < len(row) else None
            entry[name] = None if value is None else str(value)
        rows.append(entry)
    return rows


def _detail(parsed, raw: str) -> str:
    """A readable upstream detail: the API's own error/message, else the body's
    text with HTML tags stripped (an HTML 503 page becomes its words)."""
    if isinstance(parsed, dict):
        err = parsed.get("error")
        if isinstance(err, dict):
            code = err.get("code")
            info = err.get("info") or err.get("message")
            joined = ": ".join(str(p).strip() for p in (code, info) if p)
            if joined:
                return joined.rstrip(".")
        for key in ("message", "detail", "title", "info", "type"):
            value = parsed.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip().rstrip(".")
    text = strip_html(raw)
    return text[:300] if text else "(empty body)"


def _env_url(environ, name: str, default: str) -> str:
    value = environ.get(name)
    text = value.strip() if isinstance(value, str) else ""
    return (text or default).rstrip("/")


# --------------------------------------------------------------------------- #
# the adapter
# --------------------------------------------------------------------------- #
class GroundingAdapter(SelfHostedAdapter):
    """One in-process adapter for the three keyless grounding sources.

    Not self-hosted (public APIs) but wired through the same adapter mechanism:
    stdlib HTTP, the capability lattice, truthful degradation. Each enabled
    source has its own base URL (``sources``; the CDX host is separate in
    ``wayback_cdx_url``) so tests point every one at a loopback fake; a source
    passed as ``None`` is killed and contributes no tool. ``probe()`` spends one
    cheap GET per enabled source and ``capabilities(probe=True)`` marks only the
    sources that failed as ``absent`` -- HN being down never hides Wikipedia.
    """

    platform = PLATFORM
    label = "Grounding: Wikipedia + Wayback Machine + Hacker News (public APIs)"
    prefix = "gr"
    kind = "native"  # documented public APIs, native shapes
    health_path = ""  # no single backend: one probe route per source (below)
    error_tag = "grounding"

    def __init__(
        self,
        wikipedia_url: str | None = DEFAULT_WIKIPEDIA_URL,
        wayback_url: str | None = DEFAULT_WAYBACK_URL,
        wayback_cdx_url: str | None = DEFAULT_WAYBACK_CDX_URL,
        hn_url: str | None = DEFAULT_HN_URL,
        caller: HeaderCaller | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.sources: dict[str, str] = {}
        for source, url in (
            (WIKIPEDIA, wikipedia_url),
            (WAYBACK, wayback_url),
            (HN, hn_url),
        ):
            if url:
                self.sources[source] = url.rstrip("/")
        self.wayback_cdx_url = (wayback_cdx_url or DEFAULT_WAYBACK_CDX_URL).rstrip("/")
        self.timeout_s = GROUNDING_TIMEOUT
        super().__init__("")  # no single base URL: every source names its own
        self._hcaller: HeaderCaller = caller or _default_header_caller
        # Keep the base-class 3-tuple caller coherent (unused by the overrides).
        self._caller = lambda *a: self._hcaller(*a)[:3]
        self._now = now or (lambda: datetime.now(timezone.utc))

    # ---- surface --------------------------------------------------------
    def _build_tools(self) -> list[AdapterTool]:
        tools: list[AdapterTool] = []
        if WIKIPEDIA in self.sources:
            tools.append(
                AdapterTool(
                    name="wikipedia_search",
                    description=(
                        "Keyless Wikipedia full-text search via the MediaWiki API GET "
                        "/w/api.php?action=query&list=search (default en.wikipedia.org; "
                        "lang='de' etc. swaps the language subdomain, only "
                        "^[a-z]{2,3}(-[a-z]+)?$ is accepted). Returns results[title, "
                        "pageid, snippet (HTML stripped, entities decoded), url] plus "
                        "total_hits, suggestion, source and fetched_at. A rate limit "
                        "(HTTP 429), a MediaWiki error object or an unreachable host is a "
                        "truthful isError -- no results are fabricated."
                    ),
                    input_schema=_WIKIPEDIA_SEARCH_SCHEMA,
                    path="/w/api.php?action=query&list=search",
                    realized_by=NATIVE,
                    method="GET",
                )
            )
            tools.append(
                AdapterTool(
                    name="wikipedia_summary",
                    description=(
                        "Keyless Wikipedia page summary via the REST API GET "
                        "/api/rest_v1/page/summary/{title}: title, pageid, extract, "
                        "description, url, thumbnail (only when Wikipedia has one) and "
                        "type. type='disambiguation' is flagged truthfully "
                        "(disambiguation: true + note) instead of pretending the extract "
                        "describes one topic. HTTP 404 = no such page (a truthful isError "
                        "pointing at wikipedia_search), 429 = rate limited. Nothing is "
                        "fabricated."
                    ),
                    input_schema=_WIKIPEDIA_SUMMARY_SCHEMA,
                    path="/api/rest_v1/page/summary/{title}",
                    realized_by=NATIVE,
                    method="GET",
                )
            )
        if WAYBACK in self.sources:
            tools.append(
                AdapterTool(
                    name="wayback_available",
                    description=(
                        "Keyless Wayback Machine availability check via GET "
                        "archive.org/wayback/available?url=...[&timestamp=YYYYMMDD]: the "
                        "closest capture as available, snapshot_url, timestamp, status "
                        "(available: false + note when the URL was never archived). "
                        ".onion URLs are refused before any request (onions-lane "
                        "envelope). HTTP errors and an unreachable host are truthful "
                        "isError results; no capture is fabricated."
                    ),
                    input_schema=_WAYBACK_AVAILABLE_SCHEMA,
                    path="/wayback/available",
                    realized_by=NATIVE,
                    method="GET",
                )
            )
            tools.append(
                AdapterTool(
                    name="wayback_snapshots",
                    description=(
                        "Keyless Wayback Machine capture list via the CDX API GET "
                        "web.archive.org/cdx/search/cdx?url=...&output=json&"
                        "filter=statuscode:200 (limit<=50, optional from_year/to_year): "
                        "snapshots[timestamp, original, statuscode, mimetype, "
                        "snapshot_url], oldest first. The CDX header row is parsed (never "
                        "assumed), an empty answer is reported as zero captures, .onion "
                        "URLs are refused before any request. A truthful isError when the "
                        "CDX host is offline (it answers HTTP 503 at times); nothing is "
                        "fabricated."
                    ),
                    input_schema=_WAYBACK_SNAPSHOTS_SCHEMA,
                    path="/cdx/search/cdx",
                    realized_by=NATIVE,
                    method="GET",
                )
            )
        if HN in self.sources:
            tools.append(
                AdapterTool(
                    name="hn_search",
                    description=(
                        "Keyless Hacker News search via the Algolia HN API GET "
                        "hn.algolia.com/api/v1/search (sort=relevance) or "
                        "/api/v1/search_by_date (sort=date, newest first); tags = "
                        "AND-list of story|comment|poll|pollopt|show_hn|ask_hn|front_page|"
                        "author_<user>|story_<id> with one optional (a,b) OR group, "
                        "limit<=50. Returns hits[title, url, points, num_comments, author, "
                        "created_at, objectID, hn_url] (+ story_title, story_url, "
                        "comment_text for comment hits) with total_hits and pages. Unknown "
                        "tags are refused locally because Algolia answers HTTP 200 with "
                        "zero hits for them; a 429 is a truthful isError; nothing is "
                        "fabricated."
                    ),
                    input_schema=_HN_SEARCH_SCHEMA,
                    path="/api/v1/search | /api/v1/search_by_date",
                    realized_by=NATIVE,
                    method="GET",
                )
            )
        return tools

    # ---- capability lattice --------------------------------------------
    def _probe_source(self, source: str) -> tuple[bool, str]:
        """One cheap GET per source: MediaWiki siteinfo, the availability API for
        example.com, one front-page HN hit. Reachable = 2xx AND a JSON body (a
        captive portal's HTML 200 is not a working API)."""
        base = self.sources[source]
        if source == WIKIPEDIA:
            params = {
                "action": "query",
                "meta": "siteinfo",
                "siprop": "general",
                "format": "json",
            }
            url = f"{base}/w/api.php?{urlencode(params)}"
        elif source == WAYBACK:
            url = f"{base}/wayback/available?{urlencode({'url': 'example.com'})}"
        else:
            params = {"tags": "front_page", "hitsPerPage": "1"}
            url = f"{base}/api/v1/search?{urlencode(params)}"
        status, parsed, raw, _headers = self._get(url, PROBE_TIMEOUT)
        if status == 0:
            return False, raw or "unreachable"
        if 200 <= status < 300 and parsed is not None:
            return True, f"HTTP {status}"
        return False, f"HTTP {status}: {_detail(parsed, raw)[:120]}"

    def _probe_sources(self) -> dict[str, tuple[bool, str]]:
        return {s: self._probe_source(s) for s in SOURCES if s in self.sources}

    def probe(self) -> tuple[bool, str]:
        """(all enabled sources reachable, per-source notes). Never raises."""
        results = self._probe_sources()
        if not results:
            return False, "no grounding source enabled"
        notes = "; ".join(f"{src}: {note}" for src, (_ok, note) in results.items())
        return all(ok for ok, _note in results.values()), notes

    def capabilities(self, probe: bool = False) -> dict:
        """Per-tool lattice report, per source. ``probe=False`` does NO network;
        ``probe=True`` spends one GET per enabled source and marks only the
        sources that did not answer as ``absent``."""
        results = self._probe_sources() if probe else {}
        tools = []
        for tool in self._tools:
            source = TOOL_SOURCES[tool.name]
            if probe:
                ok, note = results[source]
                state = PROBED if ok else ABSENT
            else:
                state, note = NATIVE, "not probed (config-declared)"
            tools.append(
                {
                    "tool": tool.name,
                    "source": source,
                    "state": state,
                    "realized_by": tool.realized_by,
                    "backend_path": tool.path,
                    "note": note,
                }
            )
        base_urls: dict[str, str] = {}
        for source in SOURCES:
            if source in self.sources:
                base_urls[source] = self.sources[source]
                if source == WAYBACK:
                    base_urls["wayback_cdx"] = self.wayback_cdx_url
        return {
            "provider": self.platform,
            "label": self.label,
            "keyless": True,
            "self_hosted": False,  # public APIs, no daemon of ours
            "sources": sorted(self.sources),
            "base_urls": base_urls,
            "kill_switches": dict(KILL_SWITCHES),
            "backend_kind": self.kind,
            "probed": bool(probe),
            "tools": tools,
        }

    # ---- HTTP plumbing ---------------------------------------------------
    @staticmethod
    def _headers() -> dict[str, str]:
        return {"Accept": "application/json", "User-Agent": USER_AGENT}

    def _get(
        self, url: str, timeout: float
    ) -> tuple[int, dict | list | None, str, dict[str, str]]:
        status, parsed, raw, headers = self._hcaller(
            "GET", url, None, self._headers(), timeout
        )
        lowered = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
        return status, parsed, raw or "", lowered

    def _fetched_at(self) -> str:
        stamp = self._now()
        if stamp.tzinfo is not None:
            stamp = stamp.astimezone(timezone.utc)
        return stamp.strftime("%Y-%m-%dT%H:%M:%SZ")

    # ---- truthful degradation --------------------------------------------
    @staticmethod
    def _failure(
        source: str,
        base: str,
        what: str,
        status: int,
        parsed,
        raw: str,
        headers: dict[str, str],
        not_found: str | None = None,
    ) -> str | None:
        """The isError text for a non-usable response, or None when it is usable."""
        if status == 0:
            return (
                f"grounding source '{source}' ({base}) not reachable "
                f"({raw or 'unreachable'}); no results are fabricated."
            )
        detail = _detail(parsed, raw)
        if status == 429:
            retry = headers.get("retry-after")
            return (
                f"grounding source '{source}' rate limit hit: HTTP 429 for {what}"
                + (f", retry-after {retry}s" if retry else "")
                + f". Upstream said: {detail}. Wait and retry later; no results "
                f"are fabricated."
            )
        if status == 404:
            why = not_found or f"nothing at {what}"
            return (
                f"grounding source '{source}' ({base}) returned HTTP 404 for {what}: "
                f"{why}. Upstream said: {detail}. No results are fabricated."
            )
        if not (200 <= status < 300):
            return (
                f"grounding source '{source}' ({base}) returned HTTP {status} for "
                f"{what}: {detail}. No results are fabricated."
            )
        if parsed is None:
            return (
                f"grounding source '{source}' ({base}) returned HTTP {status} for "
                f"{what} but the body is not JSON ({raw[:120]!r}); no results are "
                f"fabricated."
            )
        return None

    @staticmethod
    def _unexpected(source: str, base: str, what: str, why: str) -> _UpstreamError:
        return _UpstreamError(
            f"grounding source '{source}' ({base}) answered {what} with an "
            f"unexpected shape: {why}; nothing is returned and nothing is fabricated."
        )

    # ---- argument validation (before any request is spent) ----------------
    @staticmethod
    def _text(args: dict, field: str, tag: str, max_len: int, limit_note: str) -> str:
        value = args.get(field)
        if value is None:
            raise ValueError(f"{tag}: '{field}' is required (a non-empty string)")
        if not isinstance(value, str):
            raise ValueError(f"{tag}: '{field}' must be a string")
        if _CONTROL_RE.search(value):
            raise ValueError(f"{tag}: '{field}' must not contain control characters")
        text = value.strip()
        if not text:
            raise ValueError(f"{tag}: '{field}' is required (a non-empty string)")
        if len(text) > max_len:
            raise ValueError(
                f"{tag}: '{field}' is {len(text)} characters; {limit_note} {max_len}. "
                f"Shorten it."
            )
        return text

    @staticmethod
    def _digits(args: dict, field: str, pattern, tag: str, expectation: str) -> str:
        value = args.get(field)
        if value is None:
            return ""
        if isinstance(value, int) and not isinstance(value, bool):
            value = str(value)
        if not isinstance(value, str):
            raise ValueError(f"{tag}: '{field}' must be {expectation}")
        text = value.strip()
        if not text:
            return ""
        if not pattern.match(text):
            raise ValueError(f"{tag}: '{field}' must be {expectation} (got {text!r})")
        return text

    def _wikipedia_base(self, args: dict) -> tuple[str, str]:
        """(base URL for the call, lang echoed). No ``lang`` = the configured host
        as-is, echoing its language label (``en`` for a host without one)."""
        configured = self.sources[WIKIPEDIA]
        raw = args.get("lang")
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            return configured, _host_lang(configured) or DEFAULT_LANG
        lang = raw.strip() if isinstance(raw, str) else raw
        return wikipedia_host_for(configured, lang), lang

    def _wayback_url_arg(self, args: dict, tag: str) -> str:
        url = self._text(
            args, "url", tag, WAYBACK_MAX_URL, "the Wayback Machine URL is capped at"
        )
        if onions.is_onion_url(url) or _ONION_ANYWHERE_RE.search(url):
            raise ValueError(
                f"{tag}: refused: {url!r} names a .onion host. The onions-lane "
                f"envelope forbids fetching or rendering onion services anywhere in "
                f"this hub, and the Wayback Machine would replay one, so no request "
                f"was made. See {onions.ENVELOPE_DOC}."
            )
        return url

    # ---- the five tools ---------------------------------------------------
    def _wikipedia_search(self, args: dict) -> dict:
        tag = "wikipedia_search"
        query = self._text(
            args, "query", tag, WIKIPEDIA_MAX_QUERY, "the MediaWiki search API caps at"
        )
        limit = _int_arg(
            args, "limit", WIKIPEDIA_DEFAULT_LIMIT, 1, WIKIPEDIA_MAX_LIMIT, tag
        )
        base, lang = self._wikipedia_base(args)
        params = {
            "action": "query",
            "list": "search",
            "format": "json",
            "srsearch": query,
            "srlimit": str(limit),
        }
        what = "/w/api.php?action=query&list=search"
        status, parsed, raw, headers = self._get(
            f"{base}/w/api.php?{urlencode(params)}", self.timeout_s
        )
        problem = self._failure(WIKIPEDIA, base, what, status, parsed, raw, headers)
        if problem:
            raise _UpstreamError(problem)
        if not isinstance(parsed, dict):
            raise self._unexpected(
                WIKIPEDIA, base, what, "the body is not a JSON object"
            )
        if isinstance(parsed.get("error"), dict):
            # MediaWiki reports a bad request as HTTP 200 + an error object.
            raise _UpstreamError(
                f"grounding source '{WIKIPEDIA}' ({base}) answered a MediaWiki API "
                f"error for {what}: {_detail(parsed, raw)}. No results are fabricated."
            )
        block = parsed.get("query")
        block = block if isinstance(block, dict) else {}
        hits = block.get("search")
        if not isinstance(hits, list):
            raise self._unexpected(WIKIPEDIA, base, what, "no query.search list")
        info = block.get("searchinfo")
        info = info if isinstance(info, dict) else {}
        results = []
        for hit in hits:
            if not isinstance(hit, dict):
                continue
            title = hit.get("title")
            results.append(
                {
                    "title": title,
                    "pageid": hit.get("pageid"),
                    "snippet": strip_html(hit.get("snippet")),
                    "url": f"{base}/wiki/{_title_path(title)}"
                    if isinstance(title, str) and title
                    else None,
                }
            )
        return {
            "lang": lang,
            "query": query,
            "total_hits": info.get("totalhits"),
            "suggestion": info.get("suggestion"),
            "count": len(results),
            "results": results,
        }

    def _wikipedia_summary(self, args: dict) -> dict:
        tag = "wikipedia_summary"
        title = self._text(
            args, "title", tag, WIKIPEDIA_MAX_TITLE, "MediaWiki titles are at most"
        )
        base, lang = self._wikipedia_base(args)
        segment = _title_path(title)
        what = f"/api/rest_v1/page/summary/{segment}"
        host = urlsplit(base).hostname or base
        status, parsed, raw, headers = self._get(f"{base}{what}", self.timeout_s)
        problem = self._failure(
            WIKIPEDIA,
            base,
            what,
            status,
            parsed,
            raw,
            headers,
            not_found=(
                f"no such page {title!r} on {host} (titles are case-sensitive after "
                f"the first letter); find the exact title with wikipedia_search"
            ),
        )
        if problem:
            raise _UpstreamError(problem)
        if not isinstance(parsed, dict):
            raise self._unexpected(
                WIKIPEDIA, base, what, "the body is not a JSON object"
            )
        page_type = parsed.get("type")
        content_urls = parsed.get("content_urls")
        desktop = (
            content_urls.get("desktop") if isinstance(content_urls, dict) else None
        )
        page_url = desktop.get("page") if isinstance(desktop, dict) else None
        if not isinstance(page_url, str) or not page_url:
            page_url = f"{base}/wiki/{_title_path(str(parsed.get('title') or title))}"
        payload: dict = {
            "lang": lang,
            "title": parsed.get("title"),
            "pageid": parsed.get("pageid"),
            "type": page_type,
            "disambiguation": page_type == "disambiguation",
            "description": parsed.get("description"),
            "extract": parsed.get("extract"),
            "url": page_url,
        }
        thumbnail = parsed.get("thumbnail")
        if isinstance(thumbnail, dict):
            payload["thumbnail"] = {
                "source": thumbnail.get("source"),
                "width": thumbnail.get("width"),
                "height": thumbnail.get("height"),
            }
        if payload["disambiguation"]:
            payload["note"] = (
                "this title is a disambiguation page (type: disambiguation): the "
                "extract lists the meanings rather than describing one topic. Pick a "
                "specific title from wikipedia_search and call wikipedia_summary again."
            )
        return payload

    def _wayback_available(self, args: dict) -> dict:
        tag = "wayback_available"
        url = self._wayback_url_arg(args, tag)
        stamp = self._digits(
            args,
            "timestamp",
            _WAYBACK_TIMESTAMP_RE,
            tag,
            "4 to 14 digits (YYYY[MM[DD[hhmmss]]])",
        )
        base = self.sources[WAYBACK]
        params = {"url": url}
        if stamp:
            params["timestamp"] = stamp
        what = "/wayback/available"
        status, parsed, raw, headers = self._get(
            f"{base}{what}?{urlencode(params)}", self.timeout_s
        )
        problem = self._failure(WAYBACK, base, what, status, parsed, raw, headers)
        if problem:
            raise _UpstreamError(problem)
        if not isinstance(parsed, dict):
            raise self._unexpected(WAYBACK, base, what, "the body is not a JSON object")
        archived = parsed.get("archived_snapshots")
        closest = archived.get("closest") if isinstance(archived, dict) else None
        payload: dict = {"url": url, "requested_timestamp": stamp or None}
        if isinstance(closest, dict) and closest.get("url"):
            payload.update(
                available=bool(closest.get("available", True)),
                snapshot_url=closest.get("url"),
                timestamp=closest.get("timestamp"),
                status=closest.get("status"),
            )
        else:
            payload.update(
                available=False,
                snapshot_url=None,
                timestamp=None,
                status=None,
                note=(
                    "the Wayback Machine availability API reports no capture for this "
                    "URL (archived_snapshots is empty); nothing is fabricated. That API "
                    "answers empty intermittently even for archived URLs (measured), so "
                    "confirm with wayback_snapshots, which reads the CDX index, or check "
                    "the spelling / a broader URL."
                ),
            )
        return payload

    def _wayback_snapshots(self, args: dict) -> dict:
        tag = "wayback_snapshots"
        url = self._wayback_url_arg(args, tag)
        limit = _int_arg(
            args, "limit", WAYBACK_DEFAULT_LIMIT, 1, WAYBACK_MAX_LIMIT, tag
        )
        since = self._digits(args, "from_year", _YEAR_RE, tag, "a 4-digit year")
        until = self._digits(args, "to_year", _YEAR_RE, tag, "a 4-digit year")
        if since and until and int(since) > int(until):
            raise ValueError(
                f"{tag}: 'from_year' {since} is after 'to_year' {until}; swap them"
            )
        base = self.wayback_cdx_url
        params = {
            "url": url,
            "output": "json",
            "limit": str(limit),
            "fl": ",".join(CDX_FIELDS),
            "filter": "statuscode:200",
        }
        if since:
            params["from"] = since
        if until:
            params["to"] = until
        what = "/cdx/search/cdx"
        status, parsed, raw, headers = self._get(
            f"{base}{what}?{urlencode(params, safe=',:')}", self.timeout_s
        )
        payload: dict = {
            "url": url,
            "from_year": since or None,
            "to_year": until or None,
            "limit": limit,
        }
        empty_body = parsed is None and not raw.strip()
        if 200 <= status < 300 and empty_body:
            # The plain CDX mode says "no captures" with an EMPTY body; JSON mode
            # says [] (handled by parse_cdx_rows). Neither is an error.
            rows: list[dict[str, str | None]] = []
        else:
            problem = self._failure(WAYBACK, base, what, status, parsed, raw, headers)
            if problem:
                raise _UpstreamError(problem)
            try:
                rows = parse_cdx_rows(parsed)
            except ValueError as exc:
                raise self._unexpected(WAYBACK, base, what, str(exc)) from None
        captures = []
        for row in rows:
            stamp, original = row.get("timestamp"), row.get("original")
            captures.append(
                {
                    "timestamp": stamp,
                    "original": original,
                    "statuscode": row.get("statuscode"),
                    "mimetype": row.get("mimetype"),
                    "snapshot_url": f"{base}/web/{stamp}/{original}"
                    if stamp and original
                    else None,
                }
            )
        payload["count"] = len(captures)
        payload["snapshots"] = captures
        if not captures:
            payload["note"] = (
                "the CDX API returned no captures for this URL"
                + (" and year window" if since or until else "")
                + " (HTTP 200, empty answer); nothing is fabricated."
            )
        return payload

    @staticmethod
    def _compact_hit(hit: dict) -> dict:
        object_id = hit.get("objectID")
        compact = {
            "title": hit.get("title"),
            "url": hit.get("url"),
            "points": hit.get("points"),
            "num_comments": hit.get("num_comments"),
            "author": hit.get("author"),
            "created_at": hit.get("created_at"),
            "objectID": object_id,
            "hn_url": HN_ITEM_URL.format(id=object_id) if object_id else None,
        }
        # Comment hits: the story they belong to plus the comment body (HTML upstream).
        for key in ("story_title", "story_url"):
            if key in hit:
                compact[key] = hit[key]
        if "comment_text" in hit:
            compact["comment_text"] = strip_html(hit.get("comment_text"))
        return compact

    def _hn_search(self, args: dict) -> dict:
        tag = "hn_search"
        query = self._text(args, "query", tag, HN_MAX_QUERY, "Algolia caps a query at")
        tags = args.get("tags")
        if tags is None or (isinstance(tags, str) and not tags.strip()):
            tags = "story"
        if not isinstance(tags, str) or not _HN_TAGS_RE.match(tags.strip()):
            raise ValueError(
                f"{tag}: 'tags' must be a comma-separated (AND) list of story|comment|"
                f"poll|pollopt|show_hn|ask_hn|front_page|author_<username>|story_<id>, "
                f"with at most one (a,b) OR group (got {tags!r}). Algolia answers "
                f"HTTP 200 with zero hits for an unknown tag, so it is refused here "
                f"instead of looking like an honest empty result."
            )
        tags = tags.strip()
        sort = str(args.get("sort") or "relevance").strip().lower()
        if sort not in HN_SORTS:
            raise ValueError(f"{tag}: 'sort' must be 'relevance' or 'date'")
        limit = _int_arg(args, "limit", HN_DEFAULT_LIMIT, 1, HN_MAX_LIMIT, tag)
        base = self.sources[HN]
        what = "/api/v1/search" if sort == "relevance" else "/api/v1/search_by_date"
        params = {"query": query, "tags": tags, "hitsPerPage": str(limit)}
        status, parsed, raw, headers = self._get(
            f"{base}{what}?{urlencode(params)}", self.timeout_s
        )
        problem = self._failure(HN, base, what, status, parsed, raw, headers)
        if problem:
            raise _UpstreamError(problem)
        hits = parsed.get("hits") if isinstance(parsed, dict) else None
        if not isinstance(hits, list):
            raise self._unexpected(HN, base, what, "no hits list in the JSON object")
        compact = [self._compact_hit(h) for h in hits if isinstance(h, dict)]
        return {
            "query": query,
            "tags": tags,
            "sort": sort,
            "total_hits": parsed.get("nbHits"),
            "pages": parsed.get("nbPages"),
            "count": len(compact),
            "hits": compact,
        }

    # ---- the call path (always truthful) ----------------------------------
    def handle_call(self, name: str, arguments: dict) -> dict:
        tool = self._tool(name)
        if tool is None:
            return self._error(f"unknown grounding tool {name!r}")
        handlers = {
            "wikipedia_search": self._wikipedia_search,
            "wikipedia_summary": self._wikipedia_summary,
            "wayback_available": self._wayback_available,
            "wayback_snapshots": self._wayback_snapshots,
            "hn_search": self._hn_search,
        }
        try:
            body = handlers[name](arguments or {})
        except (ValueError, _UpstreamError) as exc:
            return self._error(str(exc))
        payload = {"tool": name, "source": TOOL_SOURCES[name], **body}
        payload["fetched_at"] = self._fetched_at()
        return self._ok(payload)


# --------------------------------------------------------------------------- #
# the lane entry point (lanes.py contract)
# --------------------------------------------------------------------------- #
def build(environ) -> list[SelfHostedAdapter]:
    """DEFAULT ON with one kill switch per source; ``[]`` when all three are killed.

    ``ENABLE_WIKIPEDIA`` / ``ENABLE_WAYBACK`` / ``ENABLE_HN`` are kill switches
    (unset or "" = on; an explicit ``0``/``false``/``no``/``off`` unwires that
    source's tools). ``WIKIPEDIA_API_URL`` / ``WAYBACK_API_URL`` /
    ``WAYBACK_CDX_URL`` / ``HN_API_URL`` override the public hosts (config, not
    secrets; blank falls back to the default) so tests point at a loopback fake.
    """
    urls: dict[str, str | None] = {}
    for source, (env_name, default) in URL_ENVS.items():
        killed = _lane_killed(environ, KILL_SWITCHES[source])
        urls[source] = None if killed else _env_url(environ, env_name, default)
    if all(url is None for url in urls.values()):
        return []
    return [
        GroundingAdapter(
            wikipedia_url=urls[WIKIPEDIA],
            wayback_url=urls[WAYBACK],
            wayback_cdx_url=_env_url(
                environ, WAYBACK_CDX_URL_ENV, DEFAULT_WAYBACK_CDX_URL
            ),
            hn_url=urls[HN],
        )
    ]
