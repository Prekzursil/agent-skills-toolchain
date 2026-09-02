"""Live package-registry and trademark-database lookups for ADV-0052."""
from __future__ import annotations

import hashlib
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

UA = "ADV-0052-naming-review/1.0 (ast-integrate G-1; local-parallel)"
CTX = ssl.create_default_context()
TIMEOUT = 12
_CACHE: dict[str, dict[str, Any]] = {}

TRADEMARK_DBS = (
    {
        "id": "uspto-tmsearch",
        "url": "https://tmsearch.uspto.gov/search/search-results?query={q}",
        "classes_field": "Nice/US classes when structured results exist",
    },
    {
        "id": "wipo-branddb",
        "url": "https://branddb.wipo.int/branddb/en/",
        "classes_field": "Nice classes when structured results exist",
    },
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url: str, timeout: int = TIMEOUT) -> dict[str, Any]:
    cached = _CACHE.get(url)
    if cached is not None:
        return dict(cached)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept": "application/json, text/html;q=0.8"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as resp:
            body = resp.read(250000)
            status = int(resp.status)
            ctype = resp.headers.get("content-type") or ""
            error = None
    except urllib.error.HTTPError as exc:
        body = exc.read(250000) if exc.fp else b""
        status = int(exc.code)
        ctype = (exc.headers.get("content-type") if exc.headers else "") or ""
        error = None
    except Exception as exc:  # noqa: BLE001 - record transport failures
        row = {
            "url": url,
            "status": None,
            "error": f"{type(exc).__name__}: {exc}",
            "bytes": 0,
            "sha256": None,
            "content_type": "",
            "json": None,
            "structured": False,
            "preview": "",
        }
        _CACHE[url] = dict(row)
        return dict(row)

    payload = None
    structured = False
    if "json" in ctype.lower() or (body[:1] in (b"{", b"[") and error is None):
        try:
            payload = json.loads(body.decode("utf-8"))
            structured = True
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = None
            structured = False
    row = {
        "url": url,
        "status": status,
        "error": error,
        "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
        "content_type": ctype,
        "json": _summarize_registry(payload) if structured else None,
        "structured": structured,
        "preview": body[:180].decode("utf-8", "replace").replace("\n", " "),
    }
    _CACHE[url] = dict(row)
    return dict(row)


def _summarize_registry(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return {"type": type(payload).__name__}
    if payload.get("error") or payload.get("message") or payload.get("errors"):
        return {
            "exists": False,
            "error": payload.get("error")
            or payload.get("message")
            or payload.get("errors"),
        }
    name = payload.get("name") or (payload.get("info") or {}).get("name")
    if name:
        info = payload.get("info") or {}
        return {
            "exists": True,
            "name": name,
            "description": (payload.get("description") or info.get("summary") or "")[:240],
            "latest": (payload.get("dist-tags") or {}).get("latest")
            or info.get("version"),
        }
    if "objects" in payload:
        objs = []
        for item in (payload.get("objects") or [])[:5]:
            pkg = item.get("package") or {}
            objs.append(
                {
                    "name": pkg.get("name"),
                    "description": (pkg.get("description") or "")[:160],
                    "searchScore": item.get("searchScore"),
                }
            )
        return {"exists": "search", "hits": objs}
    return {"keys": sorted(payload)[:12]}


def npm_name(name: str) -> str:
    if name.startswith("@"):
        return urllib.parse.quote(name, safe="")
    return urllib.parse.quote(name)


def pypi_name(name: str) -> str:
    return name.lstrip("@").replace("/", "-").lower()


def crates_name(name: str) -> str:
    return name.lstrip("@").replace("/", "-").lower()


def search_name(name: str) -> dict[str, Any]:
    urls = (
        ("npm", f"https://registry.npmjs.org/{npm_name(name)}"),
        ("pypi", f"https://pypi.org/pypi/{pypi_name(name)}/json"),
        ("crates.io", f"https://crates.io/api/v1/crates/{crates_name(name)}"),
    )
    with ThreadPoolExecutor(max_workers=3) as pool:
        fetched = list(pool.map(lambda item: (item[0], fetch(item[1])), urls))
    by_reg = {k: v for k, v in fetched}
    collisions = []
    for registry, row in by_reg.items():
        exists = bool(
            row.get("status") == 200 and (row.get("json") or {}).get("exists") is True
        )
        if exists:
            collisions.append(
                {
                    "registry": registry,
                    "class": f"registry:{registry}",
                    "status": row["status"],
                    "name": (row.get("json") or {}).get("name"),
                    "url": row["url"],
                    "sha256": row["sha256"],
                }
            )
    return {
        "name": name,
        "npm": by_reg["npm"],
        "pypi": by_reg["pypi"],
        "crates": by_reg["crates.io"],
        "exact_collisions": collisions,
    }


def search_trademark_databases(query: str) -> list[dict[str, Any]]:
    encoded = urllib.parse.quote(query)
    urls = [(db, db["url"].format(q=encoded)) for db in TRADEMARK_DBS]
    with ThreadPoolExecutor(max_workers=2) as pool:
        fetched = list(pool.map(lambda item: (item[0], fetch(item[1])), urls))
    rows = []
    for db, hit in fetched:
        structured_hits = 1 if hit.get("structured") else 0
        rows.append(
            {
                "database": db["id"],
                "url": hit["url"],
                "status": hit.get("status"),
                "bytes": hit.get("bytes"),
                "sha256": hit.get("sha256"),
                "content_type": hit.get("content_type"),
                "structured_hits": structured_hits,
                "classes": [],
                "note": (
                    "reachable SPA/HTML; no Nice-class payload in the HTTP body"
                    if hit.get("status") == 200 and structured_hits == 0
                    else hit.get("error") or "ok"
                ),
            }
        )
    return rows
