#!/usr/bin/env python3
"""RES-0168 live UP/DOWN/QUOTA preflight and 16-class backend routing.

Auth diagnosis is read-only: env-name presence plus optional GitHub whoami.
Credential values are never printed, logged, or written to snapshots.
"""
from __future__ import annotations

import hashlib
import json
import os
import socket
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UA = "ast-integrate-RES-0168-preflight/1.0 (+read-only; no secrets)"
TIMEOUT_S = 8.0
MAX_BODY = 256 * 1024
GOOD_URL = "https://example.com/"
BAD_URL = "https://res-0168-deliberately-wrong.invalid/"
REFUSED_HOST = "127.0.0.1"
REFUSED_PORT = 1
LOCAL_TRANSCRIPTS = "/root/.cursor/projects/opt-p2-ast-integrate/agent-transcripts"

AUTH_ENV_NAMES = (
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "GITHUB_PAT",
    "EXA_API_KEY",
    "EXA_KEY",
    "TAVILY_API_KEY",
    "FIRECRAWL_API_KEY",
    "BRAVE_API_KEY",
    "BRAVE_SEARCH_API_KEY",
    "SERPER_API_KEY",
    "OPENALEX_MAIL",
    "OPENALEX_API_KEY",
    "S2_API_KEY",
    "SEMANTIC_SCHOLAR_API_KEY",
    "NCBI_API_KEY",
    "STACKEXCHANGE_KEY",
    "SEARXNG_URL",
    "SEARXNG_BASE_URL",
    "BRIGHTDATA_API_KEY",
    "BRIGHT_DATA_API_TOKEN",
    "CONTEXT7_API_KEY",
    "TOR_SOCKS",
    "TOR_SOCKS_PORT",
    "OWNER_ENABLE_TOR",
    "AST_ENABLE_TOR",
    "YOUTUBE_API_KEY",
    "USPTO_API_KEY",
)

# Reconstructed 16-class set. Primary spec _USER-PROMPTS.md:10683-10700 is
# absent on this worktree; each row cites catalog fragments that name it.
SOURCE_CLASSES: list[dict[str, Any]] = [
    {
        "id": "official-docs",
        "catalog_lineage": [
            "WORK-UNIT-CATALOG.json IMP-0137 source_policy example official-docs",
            "RES-0140 comparison vs blog-post / official-docs",
        ],
        "primary_backend": "python-docs-http",
        "fallback_backends": ["github-api"],
        "search_hub_needed": False,
        "owner_gated": False,
    },
    {
        "id": "source-code",
        "catalog_lineage": [
            "IMP-0137 source_policy example code",
            "retry_policy official-doc -> source-code -> issue-tracker -> archive",
        ],
        "primary_backend": "github-api",
        "fallback_backends": ["github-raw", "gitlab-api"],
        "search_hub_needed": False,
        "owner_gated": False,
    },
    {
        "id": "scholarly-papers",
        "catalog_lineage": [
            "IMP-0137 source_policy example papers",
            "catalog MCP mcp__paper-search__search_arxiv / search_openalex / search_semantic",
        ],
        "primary_backend": "arxiv-api",
        "fallback_backends": ["openalex-api", "crossref-api"],
        "search_hub_needed": False,
        "owner_gated": False,
    },
    {
        "id": "issue-trackers",
        "catalog_lineage": [
            "retry_policy official-doc -> source-code -> issue-tracker -> archive",
            "WFA-0026 upstream issue trackers",
        ],
        "primary_backend": "github-api",
        "fallback_backends": ["gitlab-api"],
        "search_hub_needed": False,
        "owner_gated": False,
    },
    {
        "id": "q-and-a-forums",
        "catalog_lineage": [
            "IMP-0137 source_policy example forums",
        ],
        "primary_backend": "stackexchange-api",
        "fallback_backends": ["hn-algolia"],
        "search_hub_needed": False,
        "owner_gated": False,
    },
    {
        "id": "practitioner-forums",
        "catalog_lineage": [
            "WFA-0026 practitioner forums",
            "RES-0026 mine practitioner forums",
        ],
        "primary_backend": "hn-algolia",
        "fallback_backends": ["stackexchange-api"],
        "search_hub_needed": False,
        "owner_gated": False,
    },
    {
        "id": "engineering-blogs",
        "catalog_lineage": [
            "_USER-PROMPTS.md:10694 (engineering blogs) via RES-0140 inputs",
            "RES-0140 blog-post vs official-docs vs video/talk",
        ],
        "primary_backend": "python-blog-http",
        "fallback_backends": ["github-blog-http", "search-hub-exa"],
        "search_hub_needed": False,
        "owner_gated": False,
    },
    {
        "id": "video-talk-transcripts",
        "catalog_lineage": [
            "RES-0140 conference-talk and video-transcript source class",
        ],
        "primary_backend": "youtube-oembed",
        "fallback_backends": ["search-hub-firecrawl"],
        "search_hub_needed": False,
        "owner_gated": False,
    },
    {
        "id": "patents-prior-art",
        "catalog_lineage": [
            "IMP-0209 blueprints 9-12 prior-art-patent",
            "AUD-0051 estate path tools/mcp/patent-search-mcp",
        ],
        "primary_backend": "google-patents-http",
        "fallback_backends": ["search-hub-tavily"],
        "search_hub_needed": False,
        "owner_gated": False,
    },
    {
        "id": "standards-regulatory",
        "catalog_lineage": [
            "_USER-PROMPTS.md:10689 (standards) via RES-0139 inputs",
            "RES-0139 IETF datatracker / W3C / OpenSSF",
        ],
        "primary_backend": "ietf-datatracker",
        "fallback_backends": ["python-docs-http"],
        "search_hub_needed": False,
        "owner_gated": False,
    },
    {
        "id": "niche-forums",
        "catalog_lineage": [
            "_USER-PROMPTS.md:10696 niche communities via RES-0137",
            "_USER-PROMPTS.md:10696-10699 niche, multilingual, archival",
        ],
        "primary_backend": "lobsters-http",
        "fallback_backends": ["search-hub-exa", "search-hub-tavily"],
        "search_hub_needed": True,
        "owner_gated": False,
        "discovery_note": (
            "A named venue can be fetched without search-hub; discovering "
            "across niche forums needs Exa/Tavily/SearxNG."
        ),
    },
    {
        "id": "multilingual-non-english",
        "catalog_lineage": [
            "_USER-PROMPTS.md:10696-10699 multilingual",
            "IMP-0209 multilingual blueprint",
        ],
        "primary_backend": "wikipedia-ja-api",
        "fallback_backends": ["wikipedia-en-api"],
        "search_hub_needed": False,
        "owner_gated": False,
    },
    {
        "id": "archival-web",
        "catalog_lineage": [
            "IMP-0137 source_policy example archival",
            "ADV-0020 archival fallback web.archive.org",
        ],
        "primary_backend": "wayback-available",
        "fallback_backends": ["github-raw"],
        "search_hub_needed": False,
        "owner_gated": False,
    },
    {
        "id": "public-tor",
        "catalog_lineage": [
            "IMP-0137 source_policy public-tor requires owner flag",
            "RES-0138 Tor/onion safety policy owner-gated",
        ],
        "primary_backend": "tor-socks",
        "fallback_backends": [],
        "search_hub_needed": False,
        "owner_gated": True,
    },
    {
        "id": "session-transcripts",
        "catalog_lineage": [
            "IMP-0153 discovery adapter for documentation, papers and session transcripts",
        ],
        "primary_backend": "local-agent-transcripts",
        "fallback_backends": [],
        "search_hub_needed": False,
        "owner_gated": False,
    },
    {
        "id": "encyclopedic-reference",
        "catalog_lineage": [
            "RES-0087 wikipedia capture used as an encyclopedic rail on this estate",
        ],
        "primary_backend": "wikipedia-en-api",
        "fallback_backends": ["wikipedia-ja-api"],
        "search_hub_needed": False,
        "owner_gated": False,
    },
]

BACKENDS: list[dict[str, Any]] = [
    {"id": "example-http", "kind": "http", "url": GOOD_URL, "role": "detector-good", "auth_env": ()},
    {"id": "invalid-dns", "kind": "http", "url": BAD_URL, "role": "detector-bad", "auth_env": ()},
    {
        "id": "loopback-refused",
        "kind": "tcp",
        "host": REFUSED_HOST,
        "port": REFUSED_PORT,
        "role": "detector-bad-tcp",
        "auth_env": (),
    },
    {
        "id": "github-api",
        "kind": "http",
        "url": "https://api.github.com/rate_limit",
        "whoami_url": "https://api.github.com/user",
        "role": "search-api",
        "auth_env": ("GITHUB_TOKEN", "GH_TOKEN", "GITHUB_PAT"),
    },
    {
        "id": "github-raw",
        "kind": "http",
        "url": "https://raw.githubusercontent.com/python/cpython/main/README.rst",
        "role": "content-http",
        "auth_env": (),
    },
    {
        "id": "gitlab-api",
        "kind": "http",
        "url": "https://gitlab.com/api/v4/projects?per_page=1&simple=true",
        "role": "search-api",
        "auth_env": (),
    },
    {
        "id": "python-docs-http",
        "kind": "http",
        "url": "https://docs.python.org/3/",
        "role": "content-http",
        "auth_env": (),
    },
    {
        "id": "python-blog-http",
        "kind": "http",
        "url": "https://blog.python.org/",
        "role": "content-http",
        "auth_env": (),
    },
    {
        "id": "github-blog-http",
        "kind": "http",
        "url": "https://github.blog/",
        "role": "content-http",
        "auth_env": (),
    },
    {
        "id": "arxiv-api",
        "kind": "http",
        "url": "https://export.arxiv.org/api/query?search_query=all:electron&start=0&max_results=1",
        "role": "search-api",
        "auth_env": (),
        "published_limit": "arXiv asks clients to sleep ~3s between requests",
    },
    {
        "id": "openalex-api",
        "kind": "http",
        "url": "https://api.openalex.org/works?search=electron&per-page=1",
        "role": "search-api",
        "auth_env": ("OPENALEX_MAIL", "OPENALEX_API_KEY"),
    },
    {
        "id": "crossref-api",
        "kind": "http",
        "url": "https://api.crossref.org/works?query=electron&rows=1",
        "role": "search-api",
        "auth_env": (),
    },
    {
        "id": "stackexchange-api",
        "kind": "http",
        "url": "https://api.stackexchange.com/2.3/info?site=stackoverflow",
        "role": "search-api",
        "auth_env": ("STACKEXCHANGE_KEY",),
    },
    {
        "id": "hn-algolia",
        "kind": "http",
        "url": "https://hn.algolia.com/api/v1/search?query=temporal&hitsPerPage=1",
        "role": "search-api",
        "auth_env": (),
    },
    {
        "id": "ietf-datatracker",
        "kind": "http",
        "url": "https://datatracker.ietf.org/doc/html/rfc2119",
        "role": "content-http",
        "auth_env": (),
    },
    {
        "id": "wikipedia-en-api",
        "kind": "http",
        "url": "https://en.wikipedia.org/w/api.php?action=query&meta=siteinfo&format=json",
        "role": "search-api",
        "auth_env": (),
    },
    {
        "id": "wikipedia-ja-api",
        "kind": "http",
        "url": "https://ja.wikipedia.org/w/api.php?action=query&meta=siteinfo&format=json",
        "role": "search-api",
        "auth_env": (),
    },
    {
        "id": "wayback-available",
        "kind": "http",
        "url": "https://archive.org/wayback/available?url=example.com",
        "role": "search-api",
        "auth_env": (),
        "note": "CDX search timed out on this host; available-API is the live archival probe",
    },
    {
        "id": "youtube-oembed",
        "kind": "http",
        "url": "https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=jNQXAC9IVRw&format=json",
        "role": "metadata-http",
        "auth_env": ("YOUTUBE_API_KEY",),
    },
    {
        "id": "google-patents-http",
        "kind": "http",
        "url": "https://patents.google.com/patent/US5000000",
        "role": "content-http",
        "auth_env": (),
    },
    {
        "id": "lobsters-http",
        "kind": "http",
        "url": "https://lobste.rs/",
        "role": "content-http",
        "auth_env": (),
    },
    {
        "id": "search-hub-exa",
        "kind": "auth-only",
        "url": "https://api.exa.ai/",
        "role": "search-hub",
        "auth_env": ("EXA_API_KEY", "EXA_KEY"),
        "catalog_mcp": "mcp__search-hub__web_search_exa",
    },
    {
        "id": "search-hub-tavily",
        "kind": "auth-only",
        "url": "https://api.tavily.com/",
        "role": "search-hub",
        "auth_env": ("TAVILY_API_KEY",),
        "catalog_mcp": "mcp__search-hub__tavily_search",
    },
    {
        "id": "search-hub-firecrawl",
        "kind": "auth-only",
        "url": "https://api.firecrawl.dev/",
        "role": "search-hub",
        "auth_env": ("FIRECRAWL_API_KEY",),
        "catalog_mcp": "mcp__search-hub__firecrawl_scrape",
    },
    {
        "id": "searxng",
        "kind": "auth-only",
        "url": None,
        "role": "search-hub",
        "auth_env": ("SEARXNG_URL", "SEARXNG_BASE_URL"),
        "catalog_mcp": "mcp__searxng__searxng_web_search",
    },
    {
        "id": "tor-socks",
        "kind": "tcp",
        "host": "127.0.0.1",
        "port": 9050,
        "role": "owner-gated",
        "auth_env": ("OWNER_ENABLE_TOR", "AST_ENABLE_TOR", "TOR_SOCKS", "TOR_SOCKS_PORT"),
    },
    {
        "id": "local-agent-transcripts",
        "kind": "local-dir",
        "path": LOCAL_TRANSCRIPTS,
        "role": "local-corpus",
        "auth_env": (),
    },
]

FAILURE_SIGNATURES = [
    {
        "id": "dns-nxdomain",
        "example": BAD_URL,
        "signal": "URLError / Name or service not known",
        "preflight_status": "DOWN",
    },
    {
        "id": "tcp-refused",
        "example": f"{REFUSED_HOST}:{REFUSED_PORT}",
        "signal": "ConnectionRefusedError",
        "preflight_status": "DOWN",
    },
    {
        "id": "timeout",
        "example": "web.archive.org CDX on this host",
        "signal": "TimeoutError",
        "preflight_status": "DOWN",
    },
    {
        "id": "http-401-403",
        "signal": "HTTP 401 or 403",
        "preflight_status": "AUTH_FAIL",
    },
    {
        "id": "http-429",
        "signal": "HTTP 429 / Retry-After / remaining=0",
        "preflight_status": "QUOTA",
    },
    {"id": "http-5xx", "signal": "HTTP 5xx", "preflight_status": "DOWN"},
    {
        "id": "auth-absent",
        "signal": "required env name unset; no live vendor call",
        "preflight_status": "AUTH_ABSENT",
    },
    {
        "id": "owner-gated-tor",
        "signal": "owner tor flag unset or SOCKS 9050 closed",
        "preflight_status": "OWNER_GATED",
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def env_present(names: tuple[str, ...] | tuple[()]) -> list[str]:
    return [n for n in names if os.environ.get(n)]


def diagnose_auth() -> dict[str, Any]:
    rows = []
    for name in AUTH_ENV_NAMES:
        present = bool(os.environ.get(name))
        row: dict[str, Any] = {"name": name, "present": present}
        if present:
            val = os.environ[name]
            row["value_len"] = len(val)
            row["value_sha256_12"] = hashlib.sha256(val.encode("utf-8")).hexdigest()[:12]
        rows.append(row)
    return {
        "mode": "read-only",
        "credential_values_printed": False,
        "credential_values_modified": False,
        "vars": rows,
        "any_search_hub_key": any(
            os.environ.get(n)
            for n in (
                "EXA_API_KEY",
                "EXA_KEY",
                "TAVILY_API_KEY",
                "FIRECRAWL_API_KEY",
                "BRAVE_API_KEY",
                "SEARXNG_URL",
                "SEARXNG_BASE_URL",
            )
        ),
        "any_github_token": any(
            os.environ.get(n) for n in ("GITHUB_TOKEN", "GH_TOKEN", "GITHUB_PAT")
        ),
        "owner_tor_flag": any(
            os.environ.get(n) for n in ("OWNER_ENABLE_TOR", "AST_ENABLE_TOR")
        ),
    }


def _rate_headers(headers: Any) -> dict[str, str]:
    interesting = {
        "x-ratelimit-limit",
        "x-ratelimit-remaining",
        "x-ratelimit-reset",
        "x-ratelimit-used",
        "retry-after",
        "x-oauth-scopes",
        "x-accepted-oauth-scopes",
    }
    out: dict[str, str] = {}
    for k, v in headers.items():
        lk = k.lower()
        if lk in interesting:
            out[lk] = v
    return out


def http_probe(url: str, extra_headers: dict[str, str] | None = None) -> dict[str, Any]:
    hdrs = {"User-Agent": UA, "Accept": "*/*"}
    if extra_headers:
        hdrs.update(extra_headers)
    t0 = time.time()
    req = urllib.request.Request(url, headers=hdrs, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            body = resp.read(MAX_BODY)
            return {
                "ok": True,
                "status": "UP",
                "http_status": int(resp.status),
                "final_url": resp.geturl(),
                "elapsed_ms": int((time.time() - t0) * 1000),
                "body_bytes": len(body),
                "sha256": sha256_bytes(body),
                "content_type": resp.headers.get("Content-Type"),
                "rate_headers": _rate_headers(resp.headers),
                "body": body,
                "error_type": None,
                "error": None,
            }
    except Exception as exc:
        http_status = None
        err_body = b""
        if isinstance(exc, urllib.error.HTTPError):
            http_status = int(exc.code)
            try:
                err_body = exc.read(MAX_BODY)
            except Exception:
                err_body = b""
        status = "DOWN"
        if http_status in (401, 403):
            status = "AUTH_FAIL"
        elif http_status == 429:
            status = "QUOTA"
        return {
            "ok": False,
            "status": status,
            "http_status": http_status,
            "final_url": url,
            "elapsed_ms": int((time.time() - t0) * 1000),
            "body_bytes": len(err_body),
            "sha256": sha256_bytes(err_body) if err_body else None,
            "content_type": None,
            "rate_headers": {},
            "body": err_body,
            "error_type": type(exc).__name__,
            "error": str(exc)[:240],
        }


def tcp_probe(host: str, port: int, timeout: float = 0.6) -> dict[str, Any]:
    t0 = time.time()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        return {
            "ok": True,
            "status": "UP",
            "elapsed_ms": int((time.time() - t0) * 1000),
            "error_type": None,
            "error": None,
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": "DOWN",
            "elapsed_ms": int((time.time() - t0) * 1000),
            "error_type": type(exc).__name__,
            "error": str(exc)[:160],
        }
    finally:
        sock.close()


def local_dir_probe(path: str) -> dict[str, Any]:
    p = Path(path)
    if not p.is_dir():
        return {
            "ok": False,
            "status": "DOWN",
            "entries": 0,
            "error_type": "NotADirectory",
            "error": "path missing",
        }
    entries = [x.name for x in p.iterdir()]
    return {
        "ok": True,
        "status": "UP",
        "entries": len(entries),
        "sample_names": entries[:8],
        "error_type": None,
        "error": None,
    }


def github_auth_headers() -> dict[str, str]:
    for name in ("GITHUB_TOKEN", "GH_TOKEN", "GITHUB_PAT"):
        val = os.environ.get(name)
        if val:
            return {"Authorization": f"Bearer {val}"}
    return {}


def _maybe_int(v: str | None) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except ValueError:
        return None


def parse_github_quota(body: bytes, rate_headers: dict[str, str]) -> dict[str, Any]:
    out: dict[str, Any] = {"source": "headers-or-json"}
    if rate_headers.get("x-ratelimit-remaining") is not None:
        out["limit"] = _maybe_int(rate_headers.get("x-ratelimit-limit"))
        out["remaining"] = _maybe_int(rate_headers.get("x-ratelimit-remaining"))
        out["reset"] = _maybe_int(rate_headers.get("x-ratelimit-reset"))
    try:
        doc = json.loads(body.decode("utf-8"))
        core = (doc.get("resources") or {}).get("core") or {}
        if core:
            out["core_limit"] = core.get("limit")
            out["core_remaining"] = core.get("remaining")
            out["core_reset"] = core.get("reset")
            out["core_used"] = core.get("used")
    except Exception:
        pass
    return out


def parse_stackexchange_quota(body: bytes) -> dict[str, Any]:
    try:
        doc = json.loads(body.decode("utf-8"))
        return {
            "quota_max": doc.get("quota_max"),
            "quota_remaining": doc.get("quota_remaining"),
            "backoff": doc.get("backoff"),
            "error_id": doc.get("error_id"),
            "error_name": doc.get("error_name"),
        }
    except Exception:
        return {}


def probe_backend(spec: dict[str, Any], *, save_body: bool = False) -> dict[str, Any]:
    kind = spec["kind"]
    auth_names = tuple(spec.get("auth_env") or ())
    present = env_present(auth_names)
    base: dict[str, Any] = {
        "id": spec["id"],
        "kind": kind,
        "role": spec.get("role"),
        "url": spec.get("url"),
        "auth_env_names": list(auth_names),
        "auth_present_names": present,
        "auth_state": (
            "PRESENT" if present else ("NOT_REQUIRED" if not auth_names else "ABSENT")
        ),
        "catalog_mcp": spec.get("catalog_mcp"),
        "fetched_at": utc_now(),
    }
    if kind == "http":
        extra = github_auth_headers() if spec["id"] == "github-api" else None
        result = http_probe(spec["url"], extra)
        body = result.pop("body")
        if spec["id"] == "github-api" and body:
            result["quota"] = parse_github_quota(body, result.get("rate_headers") or {})
        if spec["id"] == "stackexchange-api" and body:
            result["quota"] = parse_stackexchange_quota(body)
        if spec["id"] == "github-api" and extra:
            who = http_probe(str(spec["whoami_url"]), extra)
            who.pop("body", None)
            base["whoami"] = {
                "http_status": who.get("http_status"),
                "authenticated": who.get("http_status") == 200,
                "scopes": (who.get("rate_headers") or {}).get("x-oauth-scopes"),
            }
        base.update(result)
        if save_body and body:
            snap = HERE / "snapshots" / f"{spec['id']}.bin"
            snap.parent.mkdir(parents=True, exist_ok=True)
            snap.write_bytes(body)
            base["snapshot"] = str(snap.relative_to(REPO)).replace("\\", "/")
        status = base.get("status") or "DOWN"
        if status == "UP" and spec["id"] == "github-api":
            remaining = (base.get("quota") or {}).get("core_remaining")
            if remaining == 0:
                status = "QUOTA"
        if status == "UP" and spec["id"] == "stackexchange-api":
            remaining = (base.get("quota") or {}).get("quota_remaining")
            if remaining == 0:
                status = "QUOTA"
        base["preflight_status"] = status
        return base
    if kind == "tcp":
        result = tcp_probe(spec["host"], int(spec["port"]))
        base.update(result)
        if spec["id"] == "tor-socks":
            owner = bool(env_present(("OWNER_ENABLE_TOR", "AST_ENABLE_TOR")))
            base["owner_flag_present"] = owner
            if not owner:
                base["preflight_status"] = "OWNER_GATED"
                base["status"] = "OWNER_GATED"
                return base
        base["preflight_status"] = result["status"]
        return base
    if kind == "local-dir":
        result = local_dir_probe(spec["path"])
        base.update(result)
        base["path"] = spec["path"]
        base["preflight_status"] = result["status"]
        return base
    if kind == "auth-only":
        base["preflight_status"] = "AUTH_PRESENT_UNPROBED" if present else "AUTH_ABSENT"
        base["status"] = base["preflight_status"]
        base["ok"] = False
        base["error"] = (
            "no credential; live search call not attempted"
            if not present
            else "credential present; live vendor call skipped to avoid spending quota"
        )
        return base
    raise RuntimeError(f"unknown backend kind {kind}")


def detector_control(*, mutant_always_up: bool = False) -> dict[str, Any]:
    good = http_probe(GOOD_URL)
    good.pop("body", None)
    bad = http_probe(BAD_URL)
    bad.pop("body", None)
    refused = tcp_probe(REFUSED_HOST, REFUSED_PORT)
    if mutant_always_up:
        good_status = "UP"
        bad_status = "UP"
        refused_status = "UP"
    else:
        good_status = "UP" if good.get("http_status") == 200 else (good.get("status") or "DOWN")
        bad_status = "DOWN" if not bad.get("ok") else "UP"
        refused_status = refused.get("status") or "DOWN"
    return {
        "mutant_always_up": mutant_always_up,
        "good": {
            "url": GOOD_URL,
            "observed_http_status": good.get("http_status"),
            "observed_error": good.get("error"),
            "reported_status": good_status,
            "elapsed_ms": good.get("elapsed_ms"),
            "sha256": good.get("sha256"),
        },
        "bad": {
            "url": BAD_URL,
            "observed_http_status": bad.get("http_status"),
            "observed_error": bad.get("error"),
            "observed_error_type": bad.get("error_type"),
            "reported_status": bad_status,
            "elapsed_ms": bad.get("elapsed_ms"),
        },
        "bad_tcp": {
            "endpoint": f"{REFUSED_HOST}:{REFUSED_PORT}",
            "observed_error_type": refused.get("error_type"),
            "reported_status": refused_status,
            "elapsed_ms": refused.get("elapsed_ms"),
        },
        "pass": good_status == "UP" and bad_status == "DOWN" and refused_status == "DOWN",
    }


def usable(status: str) -> bool:
    return status in {"UP", "AUTH_PRESENT_UNPROBED"}


def fanout_decision(
    classes: list[dict[str, Any]],
    backends: dict[str, dict[str, Any]],
    detector: dict[str, Any],
) -> dict[str, Any]:
    reasons: list[str] = []
    if not detector.get("pass"):
        reasons.append("detector-control-failed")
    class_verdicts = []
    for cls in classes:
        cid = cls["id"]
        primary = backends.get(cls["primary_backend"], {})
        pstatus = primary.get("preflight_status") or "DOWN"
        fallbacks = []
        any_up = usable(pstatus)
        for fid in cls.get("fallback_backends") or []:
            fst = (backends.get(fid) or {}).get("preflight_status") or "DOWN"
            fallbacks.append({"id": fid, "preflight_status": fst})
            if usable(fst):
                any_up = True
        if cls.get("owner_gated") and pstatus in {"OWNER_GATED", "DOWN", "AUTH_ABSENT"}:
            any_up = False
            reasons.append(f"{cid}:owner-gated-or-down")
        hub_ids = [
            fid
            for fid in (cls.get("fallback_backends") or [])
            if str(fid).startswith("search-hub") or fid == "searxng"
        ]
        discovery_blocked = bool(cls.get("search_hub_needed")) and not any(
            usable((backends.get(fid) or {}).get("preflight_status") or "DOWN")
            for fid in hub_ids
        )
        verdict = "SERVABLE"
        if not any_up:
            verdict = "UNSERVABLE"
            reasons.append(f"{cid}:no-usable-backend")
        elif discovery_blocked and cls.get("search_hub_needed"):
            verdict = "VENUE-ONLY"
            reasons.append(f"{cid}:discovery-search-hub-absent")
        class_verdicts.append(
            {
                "source_class": cid,
                "primary": cls["primary_backend"],
                "primary_status": pstatus,
                "fallbacks": fallbacks,
                "verdict": verdict,
                "owner_gated": bool(cls.get("owner_gated")),
            }
        )
    abort = bool(reasons)
    return {
        "planned_classes": [c["id"] for c in classes],
        "abort_fanout": abort,
        "would_launch_50_agents": (not abort),
        "reasons": reasons,
        "class_verdicts": class_verdicts,
        "rule": (
            "Abort before fan-out when detector control fails, when a planned "
            "class has no usable backend, when public-tor lacks owner flag, or "
            "when a class that needs search-hub discovery has AUTH_ABSENT keys."
        ),
    }


def measure_all(*, save_snapshots: bool = False) -> dict[str, Any]:
    auth = diagnose_auth()
    detector = detector_control(mutant_always_up=False)
    mutant = detector_control(mutant_always_up=True)
    backend_rows = []
    by_id: dict[str, dict[str, Any]] = {}
    snap_ids = {
        "example-http",
        "github-api",
        "arxiv-api",
        "wayback-available",
        "stackexchange-api",
    }
    for spec in BACKENDS:
        row = probe_backend(spec, save_body=save_snapshots and spec["id"] in snap_ids)
        dumped = json.dumps(row)
        if "Authorization" in dumped and "Bearer " in dumped:
            raise RuntimeError("refusing to persist Authorization material")
        backend_rows.append(row)
        by_id[row["id"]] = row
    gate = fanout_decision(SOURCE_CLASSES, by_id, detector)
    return {
        "fetched_at": utc_now(),
        "auth": auth,
        "detector": detector,
        "detector_always_up_mutant": mutant,
        "backends": backend_rows,
        "backends_by_id": by_id,
        "fanout": gate,
        "source_class_count": len(SOURCE_CLASSES),
        "failure_signatures": FAILURE_SIGNATURES,
    }


if __name__ == "__main__":
    doc = measure_all(save_snapshots=False)
    slim = {
        "detector_pass": doc["detector"]["pass"],
        "mutant_pass": doc["detector_always_up_mutant"]["pass"],
        "abort_fanout": doc["fanout"]["abort_fanout"],
        "auth_any_search_hub": doc["auth"]["any_search_hub_key"],
        "backend_status": {b["id"]: b.get("preflight_status") for b in doc["backends"]},
    }
    print(json.dumps(slim, indent=2, sort_keys=True))
