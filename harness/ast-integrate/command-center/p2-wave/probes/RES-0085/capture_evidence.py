#!/usr/bin/env python3
"""Fetch two-rail evidence (structured API + prose) for RES-0085.

Writes fixtures/captures/<id>.meta.json plus body bytes. No secrets.
"""
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
UA = "ast-integrate-RES-0085/1.0 (research capture; local worktree; mailto:none)"

TARGETS = [
    {
        "id": "crossref-dung-1995",
        "rail": "structured-api",
        "kind": "crossref",
        "permalink": "https://api.crossref.org/works/10.1016/0004-3702(94)00041-X",
        "doi": "10.1016/0004-3702(94)00041-X",
    },
    {
        "id": "s2-dung-1995",
        "rail": "structured-api",
        "kind": "semantic-scholar",
        "permalink": (
            "https://api.semanticscholar.org/graph/v1/paper/"
            "DOI:10.1016/0004-3702(94)00041-X"
            "?fields=title,year,abstract,citationCount,url,externalIds,authors"
        ),
        "doi": "10.1016/0004-3702(94)00041-X",
    },
    {
        "id": "prose-dung-pdf",
        "rail": "prose",
        "kind": "author-pdf",
        "permalink": "https://www.cs.ait.ac.th/~dung/Site/Publications_files/n-games.pdf",
        "doi": "10.1016/0004-3702(94)00041-X",
    },
    {
        "id": "wiki-af-prose",
        "rail": "prose",
        "kind": "wikipedia-html",
        "permalink": "https://en.wikipedia.org/wiki/Argumentation_framework",
    },
    {
        "id": "crossref-gibis-1988",
        "rail": "structured-api",
        "kind": "crossref",
        "permalink": "https://api.crossref.org/works/10.1145/58566.59297",
        "doi": "10.1145/58566.59297",
    },
    {
        "id": "wiki-ibis-prose",
        "rail": "prose",
        "kind": "wikipedia-html",
        "permalink": "https://en.wikipedia.org/wiki/Issue-based_information_system",
    },
    {
        "id": "crossref-toulmin-2003",
        "rail": "structured-api",
        "kind": "crossref",
        "permalink": "https://api.crossref.org/works/10.1017/CBO9780511840005",
        "doi": "10.1017/CBO9780511840005",
    },
    {
        "id": "wiki-toulmin-prose",
        "rail": "prose",
        "kind": "wikipedia-html",
        "permalink": "https://en.wikipedia.org/wiki/Toulmin_method",
    },
    {
        "id": "arxiv-prakken-aspic",
        "rail": "structured-api",
        "kind": "arxiv-api",
        "permalink": (
            "https://export.arxiv.org/api/query?search_query="
            "ti:%22An%20abstract%20framework%20for%20argumentation%20with%20structured%20arguments%22"
            "&start=0&max_results=3"
        ),
    },
    {
        "id": "sep-informal-logic-prose",
        "rail": "prose",
        "kind": "sep-html",
        "permalink": "https://plato.stanford.edu/entries/logic-informal/",
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url: str, timeout: int = 45) -> tuple[int, bytes, str]:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "*/*",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            body = resp.read()
            status = int(getattr(resp, "status", 200) or 200)
            final = str(resp.geturl() or url)
            return status, body, final
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp else b""
        return int(exc.code), body, url


def main() -> int:
    CAP.mkdir(parents=True, exist_ok=True)
    index = []
    for t in TARGETS:
        status, body, final = fetch(t["permalink"])
        sha = hashlib.sha256(body.replace(b"\r\n", b"\n")).hexdigest()
        body_name = f"{t['id']}.body"
        (CAP / body_name).write_bytes(body)
        rec = {
            "id": t["id"],
            "rail": t["rail"],
            "kind": t["kind"],
            "permalink": t["permalink"],
            "resolved_url": final,
            "doi": t.get("doi"),
            "fetched_at": utc_now(),
            "http_status": status,
            "bytes": len(body),
            "sha256": sha,
            "body_rel": f"fixtures/captures/{body_name}",
            "ok": 200 <= status < 300 and len(body) > 0,
        }
        (CAP / f"{t['id']}.meta.json").write_text(
            json.dumps(rec, indent=2) + "\n", encoding="utf-8"
        )
        index.append(rec)
        print(f"{t['id']} status={status} bytes={len(body)} sha256={sha[:16]} ok={rec['ok']}")
    (CAP / "index.json").write_text(
        json.dumps({"fetched_at": utc_now(), "captures": index}, indent=2) + "\n",
        encoding="utf-8",
    )
    ok = sum(1 for r in index if r["ok"])
    print(f"captured {ok}/{len(index)} ok")
    return 0 if ok >= 6 else 1


if __name__ == "__main__":
    raise SystemExit(main())
