"""Fetch live sources for RES-0008; record HTTP status, timestamp, sha256."""
from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timezone

from common import (
    DOCS_MARKETPLACES,
    DOCS_REFERENCE,
    GITHUB_ISSUE,
    REPO,
    SCHEMA_URL,
    SNAP,
    digest_bytes,
)

UA = "RES-0008-ast-integrate-research/1.0 (local measurement; no secrets)"
TIMEOUT = 45

SOURCES = {
    "marketplace_schema": {
        "url": SCHEMA_URL,
        "filename": "claude-code-marketplace.schema.json",
        "kind": "json",
    },
    "plugin_marketplaces_docs": {
        "url": DOCS_MARKETPLACES,
        "filename": "plugin-marketplaces.md",
        "kind": "text",
    },
    "plugins_reference_docs": {
        "url": DOCS_REFERENCE,
        "filename": "plugins-reference.md",
        "kind": "text",
    },
    "github_issue_54280": {
        "url": GITHUB_ISSUE,
        "filename": "github-54280.json",
        "kind": "json",
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_one(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "application/json, text/plain, text/markdown, */*",
        },
        method="GET",
    )
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as resp:
            raw = resp.read()
            headers = {k.lower(): v for k, v in resp.headers.items()}
            return {
                "ok": True,
                "url": url,
                "final_url": resp.geturl(),
                "http_status": int(getattr(resp, "status", 200) or 200),
                "content_type": headers.get("content-type", ""),
                "raw": raw,
                "error": None,
            }
    except urllib.error.HTTPError as exc:
        raw = exc.read() if exc.fp else b""
        return {
            "ok": False,
            "url": url,
            "final_url": url,
            "http_status": int(exc.code),
            "content_type": "",
            "raw": raw,
            "error": f"HTTPError:{exc.code}",
        }
    except Exception as exc:
        return {
            "ok": False,
            "url": url,
            "final_url": url,
            "http_status": None,
            "content_type": "",
            "raw": b"",
            "error": f"{type(exc).__name__}:{exc}",
        }


def ensure_snapshots(*, force: bool = False) -> dict:
    SNAP.mkdir(parents=True, exist_ok=True)
    log_path = SNAP / "FETCH-LOG.json"
    if log_path.is_file() and not force:
        existing = json.loads(log_path.read_text(encoding="utf-8"))
        missing = [
            spec["filename"]
            for spec in SOURCES.values()
            if not (SNAP / spec["filename"]).is_file()
        ]
        if not missing and isinstance(existing, dict) and existing.get("sources"):
            return existing
    fetched_at = _now()
    sources: dict[str, dict] = {}
    for key, spec in SOURCES.items():
        dest = SNAP / spec["filename"]
        result = fetch_one(spec["url"])
        raw = result.pop("raw")
        sha = digest_bytes(raw) if raw else None
        if result["ok"] and raw:
            dest.write_bytes(raw.replace(b"\r\n", b"\n") if spec["kind"] != "bin" else raw)
        row = {
            "key": key,
            "url": spec["url"],
            "final_url": result["final_url"],
            "http_status": result["http_status"],
            "content_type": result["content_type"],
            "fetched_at": fetched_at,
            "sha256": sha,
            "bytes": len(raw.replace(b"\r\n", b"\n")) if raw else 0,
            "ok": bool(result["ok"] and dest.is_file()),
            "error": result["error"],
            "path": None,
            "permalink": result["final_url"] or spec["url"],
        }
        sources[key] = row

    for key, spec in SOURCES.items():
        dest = SNAP / spec["filename"]
        if dest.is_file():
            sources[key]["path"] = str(dest.relative_to(REPO).as_posix())
    log = {
        "unit_id": "RES-0008",
        "fetched_at": fetched_at,
        "user_agent": UA,
        "sources": sources,
    }
    log_path.write_text(
        json.dumps(log, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return log


def main() -> int:
    log = ensure_snapshots(force=True)
    failed = [k for k, v in log["sources"].items() if not v.get("ok")]
    for key, row in sorted(log["sources"].items()):
        print(
            f"{key} status={row.get('http_status')} ok={row.get('ok')} "
            f"sha256={row.get('sha256')} err={row.get('error')}"
        )
    if failed:
        print(f"FAILED:RES-0008-capture missing={failed}")
        return 1
    print("SUCCESS:RES-0008-capture")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
