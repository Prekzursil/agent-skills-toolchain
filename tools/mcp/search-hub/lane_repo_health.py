#!/usr/bin/env python3
"""Repo-health lane: bestofjs v2 + deps.dev + OpenSSF Scorecard (keyless, default ON).

Platform ``repohealth``; three public, keyless, read-only APIs wired through the
``adapters.SelfHostedAdapter`` mechanism (in-process stdlib ``urllib``, the
capability lattice, truthful ``isError`` degradation). Nothing here is
self-hosted; nothing costs anything at rest: no import-time network, no child
process, no third-party dependency. ``ENABLE_REPO_HEALTH=0`` is the kill switch
(unset or truthy = wired); ``build(environ)`` returns ``[]`` when killed.

Endpoints, verified live 2026-09-02 (commands + receipts in the search-hub README,
"Repo health" section):

* **bestofjs v2** -- ``GET {BESTOFJS_API_URL}/projects.json`` is the WHOLE dataset
  in one static file (1,444,851 bytes; ``{date, tags[254], projects[2157]}``;
  each project ``name, slug, full_name, description, stars, status, tags[],
  trends{daily,weekly,monthly,quarterly,yearly}, contributor_count, created_at,
  pushed_at, added_at`` + optional ``npm, downloads, url, logo``). Longer trend
  windows are simply ABSENT for young projects (yearly on 1,955 of 2,157), so a
  ranking excludes them and says so (``excluded_without_trend``) rather than
  scoring them 0. Fetched lazily on the first call, cached in-process for
  ``BESTOFJS_TTL_S`` seconds (default 6 h), never at import.
  **Trap (recorded by the lens):** the v1 host ``bestofjs-static-api.vercel.app``
  still answers 200 but is FROZEN at ``2024-08-10`` (2,005 projects).
  ``build``/the adapter refuse it; the default is the v2 host.
* **deps.dev v3** -- ``GET /v3/projects/github.com%2F{owner}%2F{repo}`` (the
  slashes MUST be percent-encoded: the literal form is ``404 page not found``)
  and ``GET /v3/systems/{system}/packages/{name}`` (``name`` percent-encoded,
  e.g. ``%40types%2Fnode``). A miss is a text/plain 404 ``project not found`` /
  ``package not found``. There is NO ``/v3/search`` (404); none is invented.
* **OpenSSF Scorecard** -- ``GET /projects/github.com/{owner}/{repo}`` (slashes
  literal here; the encoded form is 404). An unscanned repo is a 404 with an
  EMPTY body -> a truthful "not scanned" error, never a zero score. Check scores
  of ``-1`` (inconclusive) are relayed verbatim.

Every request carries a timeout; every success carries ``fetched_at`` (and the
bestofjs tools additionally ``dataset_fetched_at`` / ``dataset_date`` /
``dataset_projects`` / ``cache`` so staleness is visible); every failure is an
``isError`` naming the upstream HTTP status. Nothing is fabricated.
"""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable
from urllib.parse import quote, urlsplit

from adapters import (
    DEFAULT_TIMEOUT,
    NATIVE,
    PROBE_TIMEOUT,
    USER_AGENT,
    AdapterTool,
    Caller,
    SelfHostedAdapter,
    _default_caller,
    _int_arg,
    _lane_killed,
)

ENABLE_REPO_HEALTH_ENV = "ENABLE_REPO_HEALTH"

BESTOFJS_API_URL_ENV = "BESTOFJS_API_URL"
DEFAULT_BESTOFJS_API_URL = "https://bestofjs-static-api-v2.vercel.app"
#: The v1 static API: still 200, frozen at 2024-08-10 (2,005 projects). Refused.
FROZEN_BESTOFJS_V1_HOST = "bestofjs-static-api.vercel.app"
FROZEN_BESTOFJS_V1_DATE = "2024-08-10"
BESTOFJS_TTL_S_ENV = "BESTOFJS_TTL_S"
DEFAULT_BESTOFJS_TTL_S = 6 * 3600
BESTOFJS_DATASET_PATH = "/projects.json"
BESTOFJS_SITE = "https://bestofjs.org/projects/"
PERIODS = ("daily", "weekly", "monthly", "quarterly", "yearly")
DEFAULT_PERIOD = "weekly"
DEFAULT_TRENDING_LIMIT = 20
MAX_TRENDING_LIMIT = 50
PROJECT_CANDIDATES = 5

DEPSDEV_API_URL_ENV = "DEPSDEV_API_URL"
DEFAULT_DEPSDEV_API_URL = "https://api.deps.dev"
DEPSDEV_SYSTEMS = ("npm", "pypi", "cargo", "go", "maven", "nuget", "rubygems")
DEPSDEV_RECENT_VERSIONS = 10
# A tiny, permanent real package: the deps.dev probe target (15 versions live).
DEPSDEV_PROBE_PATH = "/v3/systems/npm/packages/left-pad"

SCORECARD_API_URL_ENV = "SCORECARD_API_URL"
DEFAULT_SCORECARD_API_URL = "https://api.securityscorecards.dev"

# owner/repo path segments: GitHub names only, so nothing else can be templated in.
_SEGMENT_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_GITHUB_URL_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?github\.com/([^/\s#?]+)/([^/\s#?]+)", re.IGNORECASE
)
_MAX_TEXT_ARG = 256

_NEVER = "Nothing is fabricated."


class _UpstreamError(Exception):
    """A truthful upstream failure, surfaced verbatim as the ``isError`` text."""


def _stamp(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_frozen_v1(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    if not host:  # a bare "host/path" without a scheme
        host = (urlsplit("//" + url).hostname or "").lower()
    return host == FROZEN_BESTOFJS_V1_HOST


def _frozen_v1_message(url: str) -> str:
    return (
        f"{BESTOFJS_API_URL_ENV}={url!r} points at the bestofjs v1 static API, "
        f"which is FROZEN at {FROZEN_BESTOFJS_V1_DATE} (2,005 projects, still "
        f"answering 200). Use the v2 host {DEFAULT_BESTOFJS_API_URL} (the default)."
    )


def _segment(value, field: str, who: str) -> str:
    token = str(value if value is not None else "").strip()
    if not token:
        raise ValueError(f"{who}: '{field}' is required")
    if not _SEGMENT_RE.match(token):
        raise ValueError(
            f"{who}: '{field}' must match {_SEGMENT_RE.pattern} (got {token!r})"
        )
    return token


def _text(value, field: str, who: str, required: bool) -> str:
    text = str(value if value is not None else "").strip()
    if not text:
        if required:
            raise ValueError(f"{who}: '{field}' is required")
        return ""
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in text):
        raise ValueError(f"{who}: '{field}' must not contain control characters")
    if len(text) > _MAX_TEXT_ARG:
        raise ValueError(f"{who}: '{field}' is longer than {_MAX_TEXT_ARG} characters")
    return text


def _stars(project: dict) -> int:
    stars = project.get("stars")
    return stars if isinstance(stars, int) and not isinstance(stars, bool) else 0


class _RepoHealthAdapter(SelfHostedAdapter):
    """Shared plumbing: clock, headers, GET, truthful checks, the call envelope."""

    platform = "repohealth"
    label = "Repo health (public APIs)"
    prefix = "rh"
    kind = "native"  # documented public APIs, native shapes
    error_tag = "repohealth"
    service = ""  # bestofjs | depsdev | scorecard
    url_env = ""  # the env var that overrides base_url
    default_url = ""

    def __init__(
        self,
        base_url: str,
        caller: Caller | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        super().__init__(base_url, caller=caller or _default_caller)
        self._clock = clock or time.time

    # ---- surface ----------------------------------------------------------
    def capabilities(self, probe: bool = False) -> dict:
        report = super().capabilities(probe=probe)
        report["self_hosted"] = False  # public APIs, not daemons we run
        report["service"] = self.service
        report["url_env"] = self.url_env
        return report

    def probe(self) -> tuple[bool, str]:
        """One cheap GET against ``health_path`` with the lane's headers."""
        if not self.base_url:
            return False, "no base URL configured"
        status, _parsed, raw = self._caller(
            "GET",
            self.base_url + self.health_path,
            None,
            self._headers(),
            PROBE_TIMEOUT,
        )
        if status == 0:
            return False, raw or "unreachable"
        if 200 <= status < 400:
            return True, f"HTTP {status}"
        return False, f"HTTP {status}: {raw[:120]}"

    # ---- HTTP plumbing ----------------------------------------------------
    def _now(self) -> float:
        return float(self._clock())

    @staticmethod
    def _headers() -> dict[str, str]:
        return {"Accept": "application/json", "User-Agent": USER_AGENT}

    def _get(self, url: str, timeout: float = DEFAULT_TIMEOUT):
        status, parsed, raw = self._caller("GET", url, None, self._headers(), timeout)
        return status, parsed, raw or ""

    def _check(self, status: int, parsed, raw: str, what: str) -> dict:
        """Raise a truthful ``_UpstreamError`` unless the response is a 2xx JSON
        object; return that object."""
        if status == 0:
            raise _UpstreamError(
                f"{self.label} at {self.base_url} not reachable ({raw}); "
                f"start with a network path to it or point {self.url_env} at a "
                f"mirror. {_NEVER}"
            )
        if not (200 <= status < 300):
            message = parsed.get("message") if isinstance(parsed, dict) else None
            detail = str(message or raw[:200] or "(empty body)")
            raise _UpstreamError(
                f"{self.label} returned HTTP {status} for {what}: {detail}. {_NEVER}"
            )
        if not isinstance(parsed, dict):
            raise _UpstreamError(
                f"{self.label} returned HTTP {status} for {what} but the body is not "
                f"the expected JSON object ({raw[:120]!r}). {_NEVER}"
            )
        return parsed

    # ---- the call path (always truthful) ----------------------------------
    def _call(self, tool: AdapterTool, args: dict) -> dict:  # pragma: no cover
        raise NotImplementedError

    def handle_call(self, name: str, arguments: dict) -> dict:
        tool = self._tool(name)
        if tool is None:
            return self._error(f"unknown repo-health tool {name!r}")
        if not self.base_url:
            return self._error(
                f"no base URL configured for {self.label}: set {self.url_env} "
                f"(default {self.default_url}); {name} stays absent until then."
            )
        try:
            return self._ok(self._call(tool, arguments or {}))
        except ValueError as exc:
            return self._error(str(exc))
        except _UpstreamError as exc:
            return self._error(str(exc))


# --------------------------------------------------------------------------- #
# bestofjs v2 -- one static dataset, cached in-process with a TTL
# --------------------------------------------------------------------------- #
@dataclass
class _Dataset:
    fetched_epoch: float
    fetched_at: str
    date: str | None
    projects: list[dict]
    tags: dict[str, str]  # code -> display name
    source: str


_BESTOFJS_NOTE = (
    "bestofjs is a CURATED list of ~2,200 JavaScript/TypeScript projects "
    "(bestofjs.org), not a GitHub index: absence means 'not curated', not "
    "'does not exist'. The whole dataset is one static file fetched lazily and "
    "cached in-process (default 6 h, BESTOFJS_TTL_S); every answer carries "
    "dataset_fetched_at, dataset_date, dataset_projects and cache{hit, age_s, "
    "ttl_s} so staleness is visible. Nothing is fabricated: the ranking is the "
    "dataset's own star-delta figures, and a project without the chosen window "
    "is excluded and counted, not scored 0."
)

_TRENDING_SCHEMA = {
    "type": "object",
    "properties": {
        "period": {
            "type": "string",
            "enum": list(PERIODS),
            "default": DEFAULT_PERIOD,
            "description": "trend window: the star delta over that window ranks",
        },
        "tag": {
            "type": "string",
            "default": "",
            "description": (
                "optional bestofjs tag code or display name (e.g. framework, react, "
                "'Node.js framework'); an unknown tag is an error listing similar ones"
            ),
        },
        "limit": {
            "type": "integer",
            "minimum": 1,
            "maximum": MAX_TRENDING_LIMIT,
            "default": DEFAULT_TRENDING_LIMIT,
            "description": "how many ranked projects to return (1-50)",
        },
    },
}

_PROJECT_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": (
                "project name (e.g. 'Vue.js'), owner/repo (e.g. vuejs/core), a "
                "github.com URL, or the bestofjs slug; case-insensitive exact match "
                "first, else up to 5 substring candidates by stars"
            ),
        }
    },
    "required": ["query"],
}


class BestOfJSAdapter(_RepoHealthAdapter):
    """``bestofjs_trending`` + ``bestofjs_project`` over the v2 static dataset."""

    label = "bestofjs v2 (public static API)"
    prefix = "bj"
    service = "bestofjs"
    url_env = BESTOFJS_API_URL_ENV
    default_url = DEFAULT_BESTOFJS_API_URL
    health_path = BESTOFJS_DATASET_PATH  # the probe IS the dataset fetch

    def __init__(
        self,
        base_url: str,
        caller: Caller | None = None,
        clock: Callable[[], float] | None = None,
        ttl_s: int = DEFAULT_BESTOFJS_TTL_S,
    ) -> None:
        if base_url and _is_frozen_v1(base_url):
            raise ValueError(_frozen_v1_message(base_url))
        super().__init__(base_url, caller=caller, clock=clock)
        self.ttl_s = int(ttl_s)
        self._lock = threading.Lock()
        self._snapshot: _Dataset | None = None

    # ---- surface ----------------------------------------------------------
    def _build_tools(self) -> list[AdapterTool]:
        return [
            AdapterTool(
                name="bestofjs_trending",
                description=(
                    "Trending JavaScript/TypeScript projects from the bestofjs v2 "
                    "static dataset, ranked by the star delta of the chosen window "
                    "(period=daily|weekly|monthly|quarterly|yearly, default weekly), "
                    "optionally within one tag, limit<=50. Items carry rank, delta, "
                    "name, full_name, description, stars, all trends, tags, status, "
                    "created_at, pushed_at, npm, downloads, url, repo_url, "
                    "bestofjs_url. " + _BESTOFJS_NOTE
                ),
                input_schema=_TRENDING_SCHEMA,
                path=BESTOFJS_DATASET_PATH,
                realized_by=NATIVE,
                method="GET",
            ),
            AdapterTool(
                name="bestofjs_project",
                description=(
                    "Look one project up in the bestofjs v2 dataset: case-insensitive "
                    "exact match on name, then owner/repo (full_name; github.com URLs "
                    "are accepted), then the bestofjs slug; otherwise the top-5 "
                    "substring candidates by stars (candidates_total counts them "
                    "all). Other curated entries sharing the matched repository "
                    "(monorepo packages) are listed in same_repo_entries. A miss "
                    "is an honest empty match, not an error. " + _BESTOFJS_NOTE
                ),
                input_schema=_PROJECT_SCHEMA,
                path=BESTOFJS_DATASET_PATH,
                realized_by=NATIVE,
                method="GET",
            ),
        ]

    def capabilities(self, probe: bool = False) -> dict:
        report = super().capabilities(probe=probe)
        snap = self._snapshot
        report["dataset"] = {
            "cached": snap is not None,
            "fetched_at": snap.fetched_at if snap else None,
            "dataset_date": snap.date if snap else None,
            "projects": len(snap.projects) if snap else None,
            "ttl_s": self.ttl_s,
        }
        return report

    def probe(self) -> tuple[bool, str]:
        """Fetch (or reuse) the dataset: the only request this API has."""
        if not self.base_url:
            return False, "no base URL configured"
        try:
            snap, hit = self._dataset()
        except _UpstreamError as exc:
            return False, str(exc)
        how = "served from the in-process cache" if hit else "fetched now"
        return True, (
            f"HTTP 200: {len(snap.projects)} projects, dataset date {snap.date}, "
            f"{how} (dataset_fetched_at {snap.fetched_at}, ttl {self.ttl_s}s)"
        )

    # ---- the dataset cache -------------------------------------------------
    @property
    def dataset_url(self) -> str:
        return self.base_url + BESTOFJS_DATASET_PATH

    def _dataset(self) -> tuple[_Dataset, bool]:
        """Return ``(snapshot, cache_hit)``; fetch when absent or older than the TTL.

        A failed refetch raises truthfully and leaves the previous snapshot in
        place (visible via ``capabilities``) -- stale data is never served as
        fresh, and a transient failure never wipes a good copy.
        """
        with self._lock:
            now = self._now()
            snap = self._snapshot
            if snap is not None and (now - snap.fetched_epoch) < self.ttl_s:
                return snap, True
            fresh = self._fetch_dataset(now)
            self._snapshot = fresh
            return fresh, False

    def _fetch_dataset(self, now: float) -> _Dataset:
        url = self.dataset_url
        status, parsed, raw = self._get(url)
        if status == 0:
            raise _UpstreamError(
                f"{self.label} at {self.base_url} not reachable ({raw}); the "
                f"dataset could not be fetched, so no ranking is fabricated."
            )
        if not (200 <= status < 300):
            raise _UpstreamError(
                f"{self.label} dataset fetch failed: HTTP {status} for {url} "
                f"({raw[:200] or '(empty body)'}); no ranking is fabricated."
            )
        projects = parsed.get("projects") if isinstance(parsed, dict) else None
        if not isinstance(projects, list):
            raise _UpstreamError(
                f"{self.label} dataset at {url} is not the expected "
                f"{{date, tags[], projects[]}} document (HTTP {status}; body starts "
                f"{raw[:120]!r}); no ranking is fabricated."
            )
        tags: dict[str, str] = {}
        for tag in parsed.get("tags") or []:
            if isinstance(tag, dict) and tag.get("code"):
                tags[str(tag["code"])] = str(tag.get("name") or tag["code"])
        for project in projects:
            for code in project.get("tags") or [] if isinstance(project, dict) else []:
                tags.setdefault(str(code), str(code))
        date = parsed.get("date")
        return _Dataset(
            fetched_epoch=now,
            fetched_at=_stamp(now),
            date=str(date) if date is not None else None,
            projects=[p for p in projects if isinstance(p, dict)],
            tags=tags,
            source=url,
        )

    def _decorate(self, payload: dict, snap: _Dataset, hit: bool, now: float) -> dict:
        payload["cache"] = {
            "hit": hit,
            "age_s": int(max(0.0, now - snap.fetched_epoch)),
            "ttl_s": self.ttl_s,
        }
        payload["dataset_fetched_at"] = snap.fetched_at
        payload["dataset_date"] = snap.date
        payload["dataset_projects"] = len(snap.projects)
        payload["dataset_source"] = snap.source
        payload["fetched_at"] = _stamp(now)
        return payload

    # ---- shaping ------------------------------------------------------------
    @staticmethod
    def _item(project: dict, rank: int | None = None, delta=None) -> dict:
        full_name = str(project.get("full_name") or "")
        slug = project.get("slug")
        item: dict = {}
        if rank is not None:
            item["rank"] = rank
            item["delta"] = delta
        item.update(
            {
                "name": project.get("name"),
                "full_name": full_name or None,
                "description": project.get("description"),
                "stars": project.get("stars"),
                "trends": project.get("trends") or {},
                "tags": project.get("tags") or [],
                "status": project.get("status"),
                "created_at": project.get("created_at"),
                "pushed_at": project.get("pushed_at"),
                "added_at": project.get("added_at"),
                "contributor_count": project.get("contributor_count"),
                "npm": project.get("npm"),
                "downloads": project.get("downloads"),
                "url": project.get("url") or None,
                "repo_url": f"https://github.com/{full_name}" if full_name else None,
                "bestofjs_url": f"{BESTOFJS_SITE}{slug}" if slug else None,
            }
        )
        return item

    def _resolve_tag(self, snap: _Dataset, raw: str) -> tuple[str, str]:
        key = " ".join(raw.split()).lower()
        for code, name in snap.tags.items():
            if key in (code.lower(), name.lower()):
                return code, name
        similar = sorted(
            code
            for code, name in snap.tags.items()
            if key in code.lower() or key in name.lower() or code.lower() in key
        )
        hint = (
            "similar tags: " + ", ".join(similar[:8])
            if similar
            else "no similar tag in the dataset"
        )
        raise ValueError(
            f"bestofjs: unknown tag {raw!r} ({hint}; {len(snap.tags)} tag codes "
            f"or display names are accepted)"
        )

    # ---- the tools ------------------------------------------------------------
    def _call(self, tool: AdapterTool, args: dict) -> dict:
        if tool.name == "bestofjs_trending":
            return self._trending(args)
        if tool.name == "bestofjs_project":
            return self._project(args)
        raise ValueError(f"bestofjs: unknown tool {tool.name!r}")

    def _trending(self, args: dict) -> dict:
        # Validate BEFORE the (possibly 1.4 MB) dataset fetch is spent.
        period = args.get("period")
        if period is None or period == "":
            period = DEFAULT_PERIOD
        if not isinstance(period, str) or period.strip().lower() not in PERIODS:
            raise ValueError(
                f"bestofjs: 'period' must be one of {'|'.join(PERIODS)} "
                f"(got {period!r})"
            )
        period = period.strip().lower()
        tag = _text(args.get("tag"), "tag", "bestofjs", required=False)
        limit = _int_arg(
            args, "limit", DEFAULT_TRENDING_LIMIT, 1, MAX_TRENDING_LIMIT, "bestofjs"
        )
        snap, hit = self._dataset()
        now = self._now()
        tag_code = tag_name = None
        projects = snap.projects
        if tag:
            tag_code, tag_name = self._resolve_tag(snap, tag)
            projects = [p for p in projects if tag_code in (p.get("tags") or [])]
        ranked: list[tuple[float, dict]] = []
        excluded = 0
        for project in projects:
            trends = project.get("trends")
            delta = trends.get(period) if isinstance(trends, dict) else None
            if isinstance(delta, bool) or not isinstance(delta, (int, float)):
                excluded += 1  # no figure for this window yet: excluded, not 0
                continue
            ranked.append((delta, project))
        ranked.sort(
            key=lambda dp: (-dp[0], -_stars(dp[1]), str(dp[1].get("full_name") or ""))
        )
        items = [
            self._item(project, rank=i + 1, delta=delta)
            for i, (delta, project) in enumerate(ranked[:limit])
        ]
        scope = f"tag {tag_code!r}" if tag_code else "the whole dataset"
        payload = {
            "tool": "bestofjs_trending",
            "period": period,
            "tag": tag_code,
            "tag_name": tag_name,
            "limit": limit,
            "count": len(items),
            "total_ranked": len(ranked),
            "excluded_without_trend": excluded,
            "items": items,
            "note": (
                f"ranked by trends.{period} (stars gained over that window, ties by "
                f"stars) across {scope}; {excluded} project(s) have no {period} "
                f"figure yet and are excluded, not scored 0. Curated dataset, not "
                f"a GitHub-wide index."
            ),
        }
        return self._decorate(payload, snap, hit, now)

    def _project(self, args: dict) -> dict:
        raw = args.get("query")
        query = _text(raw, "query", "bestofjs", required=True)
        snap, hit = self._dataset()
        now = self._now()
        needle = self._normalize_repo_query(query)
        key = needle.lower()
        match = matched_on = None
        for field in ("name", "full_name", "slug"):
            for project in snap.projects:
                if str(project.get(field) or "").lower() == key:
                    match, matched_on = project, field
                    break
            if match is not None:
                break
        candidates: list[dict] = []
        same_repo: list[dict] = []
        total = 0
        if match is not None:
            # bestofjs curates monorepo packages as separate projects that share one
            # full_name (live 2026-09-02: 7 repos, e.g. TanStack Start + TanStack
            # Router on TanStack/router). List the siblings; never drop them.
            repo_key = str(match.get("full_name") or "").lower()
            same_repo = [
                self._item(p)
                for p in snap.projects
                if p is not match and str(p.get("full_name") or "").lower() == repo_key
            ]
        else:
            hits = [
                p
                for p in snap.projects
                if any(
                    key in str(p.get(f) or "").lower()
                    for f in ("name", "full_name", "slug")
                )
            ]
            hits.sort(key=lambda p: (-_stars(p), str(p.get("full_name") or "")))
            total = len(hits)
            candidates = [self._item(p) for p in hits[:PROJECT_CANDIDATES]]
        if match is not None:
            note = f"exact case-insensitive match on {matched_on}."
            if same_repo:
                note += (
                    f" {len(same_repo)} other curated entr"
                    f"{'y' if len(same_repo) == 1 else 'ies'} share this repository "
                    f"(monorepo packages), listed in same_repo_entries."
                )
        elif candidates:
            note = (
                f"no exact match on name, full_name or slug; {total} substring "
                f"candidates, the top {len(candidates)} by stars are shown."
            )
        else:
            note = (
                "no exact or substring match: bestofjs is a curated list, not a "
                "GitHub index, so this project is most likely not curated there "
                "(try github_repo_search or depsdev_project for any public repo)."
            )
        payload = {
            "tool": "bestofjs_project",
            "query": raw if isinstance(raw, str) else query,
            "normalized_query": needle,
            "match": self._item(match) if match is not None else None,
            "matched_on": matched_on,
            "same_repo_entries": same_repo,
            "candidates": candidates,
            "candidates_total": total,
            "note": note,
        }
        return self._decorate(payload, snap, hit, now)

    @staticmethod
    def _normalize_repo_query(query: str) -> str:
        found = _GITHUB_URL_RE.match(query)
        if not found:
            return query
        owner, repo = found.group(1), found.group(2)
        if repo.lower().endswith(".git"):
            repo = repo[:-4]
        return f"{owner}/{repo}"


# --------------------------------------------------------------------------- #
# deps.dev v3 -- project record (with its Scorecard snapshot) + package versions
# --------------------------------------------------------------------------- #
_DEPSDEV_PROJECT_SCHEMA = {
    "type": "object",
    "properties": {
        "owner": {"type": "string", "description": "GitHub owner (user or org)"},
        "repo": {"type": "string", "description": "GitHub repository name"},
    },
    "required": ["owner", "repo"],
}

_DEPSDEV_PACKAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "system": {
            "type": "string",
            "enum": list(DEPSDEV_SYSTEMS),
            "description": "package ecosystem",
        },
        "name": {
            "type": "string",
            "description": (
                "exact package name as the registry spells it (e.g. express, "
                "@types/node, Flask, github.com/gin-gonic/gin, "
                "com.google.guava:guava); percent-encoded on the wire"
            ),
        },
    },
    "required": ["system", "name"],
}


class DepsDevAdapter(_RepoHealthAdapter):
    """``depsdev_project`` + ``depsdev_package`` over Google's public deps.dev v3 API."""

    label = "deps.dev (public API)"
    prefix = "dd"
    service = "depsdev"
    url_env = DEPSDEV_API_URL_ENV
    default_url = DEFAULT_DEPSDEV_API_URL
    health_path = DEPSDEV_PROBE_PATH

    def _build_tools(self) -> list[AdapterTool]:
        return [
            AdapterTool(
                name="depsdev_project",
                description=(
                    "Keyless GitHub project record from the public deps.dev v3 API: "
                    "GET /v3/projects/github.com%2F{owner}%2F{repo} (the slashes "
                    "MUST be percent-encoded; the literal form is a 404). Returns "
                    "stars, forks, open_issues, license, description, homepage, "
                    "deps.dev's periodic OpenSSF Scorecard snapshot "
                    "(overall_score, date, scorecard_version, commit, checks[{name, "
                    "score, reason}]) or null when it holds none, and oss_fuzz. "
                    "deps.dev only knows repos linked from a package it indexes: a "
                    "404 ('project not found') is returned as a truthful error, "
                    "never as zeros. Nothing is fabricated."
                ),
                input_schema=_DEPSDEV_PROJECT_SCHEMA,
                path="/v3/projects/github.com%2F{owner}%2F{repo}",
                realized_by=NATIVE,
                method="GET",
            ),
            AdapterTool(
                name="depsdev_package",
                description=(
                    "Keyless package version summary from the public deps.dev v3 "
                    "API: GET /v3/systems/{system}/packages/{name} (system in "
                    + "|".join(DEPSDEV_SYSTEMS)
                    + "; name percent-encoded, e.g. %40types%2Fnode). Returns "
                    "package_key (deps.dev's normalized key), versions_count, "
                    "default_version (the registry's isDefault), latest_published "
                    "(newest publishedAt -- may be a pre-release), deprecated_count "
                    "and the 10 most recent versions. deps.dev has NO search "
                    "endpoint, so the name must be exact; a 404 ('package not "
                    "found') is a truthful error. Nothing is fabricated."
                ),
                input_schema=_DEPSDEV_PACKAGE_SCHEMA,
                path="/v3/systems/{system}/packages/{name}",
                realized_by=NATIVE,
                method="GET",
            ),
        ]

    def _call(self, tool: AdapterTool, args: dict) -> dict:
        if tool.name == "depsdev_project":
            return self._project(args)
        if tool.name == "depsdev_package":
            return self._package(args)
        raise ValueError(f"deps.dev: unknown tool {tool.name!r}")

    def _project(self, args: dict) -> dict:
        owner = _segment(args.get("owner"), "owner", "deps.dev")
        repo = _segment(args.get("repo"), "repo", "deps.dev")
        key = f"github.com/{owner}/{repo}"
        url = f"{self.base_url}/v3/projects/{quote(key, safe='')}"
        status, parsed, raw = self._get(url)
        now = self._now()
        if status == 404:
            raise _UpstreamError(
                f"deps.dev has no project record for {key}: HTTP 404 "
                f"({raw[:120].strip() or 'empty body'}). deps.dev only knows "
                f"repositories linked from a package it indexes (npm, PyPI, Go, "
                f"Maven, NuGet, Cargo, RubyGems); try github_repo_search or "
                f"scorecard_project instead. {_NEVER}"
            )
        doc = self._check(status, parsed, raw, f"project {key}")
        sc = doc.get("scorecard")
        scorecard = None
        if isinstance(sc, dict):
            checks = [
                {
                    "name": c.get("name"),
                    "score": c.get("score"),
                    "reason": c.get("reason"),
                }
                for c in (sc.get("checks") or [])
                if isinstance(c, dict)
            ]
            repository = (
                sc.get("repository") if isinstance(sc.get("repository"), dict) else {}
            )
            version = (
                sc.get("scorecard") if isinstance(sc.get("scorecard"), dict) else {}
            )
            scorecard = {
                "overall_score": sc.get("overallScore"),
                "date": sc.get("date"),
                "scorecard_version": version.get("version"),
                "commit": repository.get("commit"),
                "checks_count": len(checks),
                "checks": checks,
            }
            note = (
                "scorecard is deps.dev's periodic snapshot (see scorecard.date), not "
                "a live scan; scorecard_project queries the live OpenSSF API."
            )
        else:
            note = (
                "deps.dev holds no OpenSSF Scorecard snapshot for this project "
                "(reported as null, never as a zero score); scorecard_project asks "
                "the live OpenSSF API, which answers 404 = not scanned."
            )
        project_key = doc.get("projectKey")
        oss_fuzz = doc.get("ossFuzz")
        return {
            "tool": "depsdev_project",
            "project": (
                project_key.get("id") if isinstance(project_key, dict) else None
            )
            or key,
            "stars": doc.get("starsCount"),
            "forks": doc.get("forksCount"),
            "open_issues": doc.get("openIssuesCount"),
            "license": doc.get("license") or None,
            "description": doc.get("description") or None,
            "homepage": doc.get("homepage") or None,
            "scorecard": scorecard,
            "oss_fuzz": oss_fuzz if isinstance(oss_fuzz, dict) else None,
            "note": note,
            "source": url,
            "fetched_at": _stamp(now),
        }

    @staticmethod
    def _version(entry: dict) -> dict:
        version_key = entry.get("versionKey")
        out = {
            "version": (
                version_key.get("version") if isinstance(version_key, dict) else None
            ),
            "published_at": entry.get("publishedAt"),
            "is_default": bool(entry.get("isDefault")),
            "is_deprecated": bool(entry.get("isDeprecated")),
        }
        if entry.get("deprecatedReason"):
            out["deprecated_reason"] = entry["deprecatedReason"]
        return out

    def _package(self, args: dict) -> dict:
        raw_system = args.get("system")
        system = str(raw_system if raw_system is not None else "").strip().lower()
        if system not in DEPSDEV_SYSTEMS:
            raise ValueError(
                f"deps.dev: 'system' must be one of {'|'.join(DEPSDEV_SYSTEMS)} "
                f"(got {raw_system!r})"
            )
        name = _text(args.get("name"), "name", "deps.dev", required=True)
        url = f"{self.base_url}/v3/systems/{system}/packages/{quote(name, safe='')}"
        status, parsed, raw = self._get(url)
        now = self._now()
        what = f"package {name!r} in {system}"
        if status == 404:
            raise _UpstreamError(
                f"deps.dev has no {what}: HTTP 404 "
                f"({raw[:120].strip() or 'empty body'}). deps.dev has no search "
                f"endpoint, so the name must be the registry's exact spelling "
                f"(scoped npm names as @scope/name, Maven as group:artifact, Go as "
                f"the module path). {_NEVER}"
            )
        doc = self._check(status, parsed, raw, what)
        versions = [v for v in (doc.get("versions") or []) if isinstance(v, dict)]
        ordered = sorted(
            versions, key=lambda v: str(v.get("publishedAt") or ""), reverse=True
        )
        default = next((v for v in versions if v.get("isDefault")), None)
        latest = ordered[0] if ordered and ordered[0].get("publishedAt") else None
        default_out = self._version(default) if default else None
        latest_out = self._version(latest) if latest else None
        recent = [self._version(v) for v in ordered[:DEPSDEV_RECENT_VERSIONS]]
        if (
            default_out
            and latest_out
            and default_out["version"] != latest_out["version"]
        ):
            note = (
                f"latest_published ({latest_out['version']}) is newer than the "
                f"registry default ({default_out['version']}): isDefault is the "
                f"registry's default tag, so the newest publish may be a pre-release "
                f"or a maintenance backport. recent_versions is the newest "
                f"{len(recent)} of {len(versions)} by publishedAt."
            )
        else:
            note = (
                f"default_version is the registry's isDefault tag; recent_versions is "
                f"the newest {len(recent)} of {len(versions)} by publishedAt "
                f"(pre-releases included as published)."
            )
        return {
            "tool": "depsdev_package",
            "system": system,
            "name": name,
            "package_key": doc.get("packageKey"),
            "versions_count": len(versions),
            "default_version": default_out,
            "latest_published": latest_out,
            "deprecated_count": sum(1 for v in versions if v.get("isDeprecated")),
            "recent_versions": recent,
            "note": note,
            "source": url,
            "fetched_at": _stamp(now),
        }


# --------------------------------------------------------------------------- #
# OpenSSF Scorecard -- the live public API
# --------------------------------------------------------------------------- #
_SCORECARD_SCHEMA = {
    "type": "object",
    "properties": {
        "owner": {"type": "string", "description": "GitHub owner (user or org)"},
        "repo": {"type": "string", "description": "GitHub repository name"},
    },
    "required": ["owner", "repo"],
}


class ScorecardAdapter(_RepoHealthAdapter):
    """``scorecard_project`` over the public OpenSSF Scorecard API."""

    label = "OpenSSF Scorecard (public API)"
    prefix = "sc"
    service = "scorecard"
    url_env = SCORECARD_API_URL_ENV
    default_url = DEFAULT_SCORECARD_API_URL
    health_path = "/"  # the API root serves its Swagger UI (200)

    def _build_tools(self) -> list[AdapterTool]:
        return [
            AdapterTool(
                name="scorecard_project",
                description=(
                    "Keyless OpenSSF Scorecard result for a GitHub repo from the "
                    "public API: GET /projects/github.com/{owner}/{repo}. Returns "
                    "score (0-10), date, commit, scorecard_version and checks[{name, "
                    "score, reason}] relayed verbatim (a check score of -1 means "
                    "inconclusive). The API only holds repos its weekly cron scanned "
                    "(~1M by criticality): a 404 is returned as a truthful 'not "
                    "scanned' error -- never a zero score -- with the local remedy "
                    "(scorecard --repo=...). Nothing is fabricated."
                ),
                input_schema=_SCORECARD_SCHEMA,
                path="/projects/github.com/{owner}/{repo}",
                realized_by=NATIVE,
                method="GET",
            )
        ]

    def _call(self, tool: AdapterTool, args: dict) -> dict:
        if tool.name != "scorecard_project":
            raise ValueError(f"Scorecard: unknown tool {tool.name!r}")
        owner = _segment(args.get("owner"), "owner", "Scorecard")
        repo = _segment(args.get("repo"), "repo", "Scorecard")
        key = f"github.com/{owner}/{repo}"
        url = f"{self.base_url}/projects/{key}"
        status, parsed, raw = self._get(url)
        now = self._now()
        if status == 404:
            raise _UpstreamError(
                f"OpenSSF Scorecard has NOT scanned {key}: HTTP 404 from {url}. The "
                f"public API only holds repositories its weekly cron scanned; "
                f"absence is NOT a zero score and none is fabricated. Score it "
                f"locally with `scorecard --repo={key}` (github.com/ossf/scorecard), "
                f"or check depsdev_project for deps.dev's periodic snapshot."
            )
        doc = self._check(status, parsed, raw, f"project {key}")
        checks = [
            {"name": c.get("name"), "score": c.get("score"), "reason": c.get("reason")}
            for c in (doc.get("checks") or [])
            if isinstance(c, dict)
        ]
        repo_info = doc.get("repo") if isinstance(doc.get("repo"), dict) else {}
        version = doc.get("scorecard") if isinstance(doc.get("scorecard"), dict) else {}
        return {
            "tool": "scorecard_project",
            "repo": repo_info.get("name") or key,
            "score": doc.get("score"),
            "date": doc.get("date"),
            "commit": repo_info.get("commit"),
            "scorecard_version": version.get("version"),
            "checks_count": len(checks),
            "checks": checks,
            "note": (
                "check scores are 0-10; -1 means the check was inconclusive and is "
                "relayed verbatim (never rewritten to 0). date is the scan date, "
                "commit the revision scanned."
            ),
            "source": url,
            "fetched_at": _stamp(now),
        }


# --------------------------------------------------------------------------- #
# the lane builder (lanes.py contract)
# --------------------------------------------------------------------------- #
def _base_url(environ, name: str, default: str) -> str:
    value = environ.get(name)
    text = value.strip() if isinstance(value, str) else ""
    return (text or default).rstrip("/")


def _ttl_from_env(environ) -> int:
    raw = environ.get(BESTOFJS_TTL_S_ENV)
    text = raw.strip() if isinstance(raw, str) else ""
    if not text:
        return DEFAULT_BESTOFJS_TTL_S
    if not text.isdigit():
        raise ValueError(
            f"{BESTOFJS_TTL_S_ENV} must be a non-negative integer number of seconds "
            f"(got {raw!r}; default {DEFAULT_BESTOFJS_TTL_S})"
        )
    return int(text)


def build(environ) -> list[SelfHostedAdapter]:
    """The lane's adapters, or ``[]`` when ``ENABLE_REPO_HEALTH`` is falsey.

    Raises ``ValueError`` (which ``lanes.extra_adapters`` reports as a degraded
    lane rather than a crash) for the frozen bestofjs v1 host or a bad TTL --
    a misconfigured lane is refused truthfully, not wired half-right.
    """
    if _lane_killed(environ, ENABLE_REPO_HEALTH_ENV):
        return []
    bestofjs_url = _base_url(environ, BESTOFJS_API_URL_ENV, DEFAULT_BESTOFJS_API_URL)
    if _is_frozen_v1(bestofjs_url):
        raise ValueError(_frozen_v1_message(bestofjs_url))
    ttl_s = _ttl_from_env(environ)
    return [
        BestOfJSAdapter(bestofjs_url, ttl_s=ttl_s),
        DepsDevAdapter(
            _base_url(environ, DEPSDEV_API_URL_ENV, DEFAULT_DEPSDEV_API_URL)
        ),
        ScorecardAdapter(
            _base_url(environ, SCORECARD_API_URL_ENV, DEFAULT_SCORECARD_API_URL)
        ),
    ]
