#!/usr/bin/env python3
"""Fetch dual-rail external sources for RES-0174 and snapshot bytes + sha256."""
from __future__ import annotations

import hashlib
import json
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAP = HERE / "fixtures" / "captures"
INDEX = HERE / "fixtures" / "lineage.json"
UA = {
    "User-Agent": "ast-integrate-RES-0174-evidence/1.0 (research design; local worktree)",
    "Accept": "*/*",
}

# Dual rails: Wikipedia REST JSON + HTML; arXiv Atom API + ar5iv HTML.
# 1912.02724 is RCA on a known causal DAG (not accident-graph extraction).
SOURCES = (
    {
        "id": "wiki-wba-summary",
        "kind": "structured-api",
        "url": "https://en.wikipedia.org/api/rest_v1/page/summary/Why%E2%80%93because_analysis",
        "supports": ("dag-not-tree", "multi-cause", "falsifiable-edges"),
        "suffix": ".json",
    },
    {
        "id": "wiki-wba-html",
        "kind": "prose-source",
        "url": "https://en.wikipedia.org/wiki/Why%E2%80%93because_analysis",
        "supports": ("dag-not-tree", "multi-cause", "falsifiable-edges"),
        "suffix": ".html",
    },
    {
        "id": "wiki-fivewhys-summary",
        "kind": "structured-api",
        "url": "https://en.wikipedia.org/api/rest_v1/page/summary/Five_whys",
        "supports": ("linear-chain-failure",),
        "suffix": ".json",
    },
    {
        "id": "wiki-fivewhys-html",
        "kind": "prose-source",
        "url": "https://en.wikipedia.org/wiki/Five_whys",
        "supports": ("linear-chain-failure",),
        "suffix": ".html",
    },
    {
        "id": "arxiv-1912.02724-atom",
        "kind": "structured-api",
        "url": "http://export.arxiv.org/api/query?id_list=1912.02724",
        "supports": ("causal-rca-on-dag",),
        "suffix": ".atom.xml",
    },
    {
        "id": "ar5iv-1912.02724",
        "kind": "prose-source",
        "url": "https://ar5iv.labs.arxiv.org/html/1912.02724",
        "supports": ("causal-rca-on-dag",),
        "suffix": ".html",
    },
)


def fetch(url: str) -> dict:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers=UA)
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=60) as resp:
            body = resp.read()
            return {
                "resolved_url": resp.geturl(),
                "http_status": int(getattr(resp, "status", None) or resp.getcode()),
                "fetch_timestamp": fetched_at,
                "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
                "content_type": resp.headers.get("Content-Type"),
                "body": body,
            }
    except urllib.error.HTTPError as exc:
        body = exc.read() if hasattr(exc, "read") else b""
        return {
            "resolved_url": url,
            "http_status": int(exc.code),
            "fetch_timestamp": fetched_at,
            "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest() if body else "",
            "content_type": None,
            "body": body,
            "error": f"HTTPError:{exc.code}",
        }


def capture() -> dict:
    CAP.mkdir(parents=True, exist_ok=True)
    rows = []
    for spec in SOURCES:
        rec = fetch(spec["url"])
        body = rec.pop("body")
        suffix = spec["suffix"]
        rel = (
            "command-center/p2-wave/probes/RES-0174/fixtures/captures/"
            f"{spec['id']}{suffix}"
        )
        (CAP / f"{spec['id']}{suffix}").write_bytes(body)
        if rec.get("http_status") != 200:
            raise RuntimeError(
                f"capture {spec['id']} HTTP {rec.get('http_status')} {spec['url']}"
            )
        rec.update(
            {
                "id": spec["id"],
                "kind": spec["kind"],
                "requested_url": spec["url"],
                "supports": list(spec["supports"]),
                "path": rel,
            }
        )
        rows.append(rec)
        print(
            f"captured {spec['id']} status={rec['http_status']} "
            f"sha256={rec['sha256'][:12]} bytes={rec['bytes']}"
        )
    index = {
        "unit_id": "RES-0174",
        "captured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fetched": rows,
    }
    INDEX.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return index


def load_index() -> dict:
    if not INDEX.is_file():
        return capture()
    return json.loads(INDEX.read_text(encoding="utf-8"))


def main() -> int:
    capture()
    print("SUCCESS:RES-0174-capture")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
