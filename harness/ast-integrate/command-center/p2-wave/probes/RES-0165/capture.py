#!/usr/bin/env python3
"""Fetch dual-rail published sources (structured API + prose) into snapshots/.

Each paper: arXiv Atom API (structured) + abs HTML (prose). Semantic Scholar
is a second structured rail when it answers. Failures are recorded; emit
refuses to promote a paper with no 200 rail.
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
SNAP = HERE / "snapshots"
UA = {
    "User-Agent": "ast-integrate-RES-0165-evidence/1.0 (research; local measurement)",
    "Accept": "*/*",
}

PAPERS = (
    {
        "id": "more-agents",
        "arxiv": "2402.05120",
        "title_expect": "More Agents Is All You Need",
        "prose": "https://arxiv.org/abs/2402.05120",
        "structured": "https://export.arxiv.org/api/query?id_list=2402.05120",
        "s2": "https://api.semanticscholar.org/graph/v1/paper/ARXIV:2402.05120?fields=title,year,abstract,citationCount,externalIds,authors",
    },
    {
        "id": "llm-monkeys",
        "arxiv": "2407.21787",
        "title_expect": "Large Language Monkeys",
        "prose": "https://arxiv.org/abs/2407.21787",
        "structured": "https://export.arxiv.org/api/query?id_list=2407.21787",
        "s2": "https://api.semanticscholar.org/graph/v1/paper/ARXIV:2407.21787?fields=title,year,abstract,citationCount,externalIds,authors",
    },
    {
        "id": "multiagent-debate",
        "arxiv": "2305.14325",
        "title_expect": "Improving Factuality and Reasoning through Multiagent Debate",
        "prose": "https://arxiv.org/abs/2305.14325",
        "structured": "https://export.arxiv.org/api/query?id_list=2305.14325",
        "s2": "https://api.semanticscholar.org/graph/v1/paper/ARXIV:2305.14325?fields=title,year,abstract,citationCount,externalIds,authors",
    },
    {
        "id": "snell-test-time",
        "arxiv": "2408.03314",
        "title_expect": "Scaling LLM Test-Time Compute Optimally",
        "prose": "https://arxiv.org/abs/2408.03314",
        "structured": "https://export.arxiv.org/api/query?id_list=2408.03314",
        "s2": "https://api.semanticscholar.org/graph/v1/paper/ARXIV:2408.03314?fields=title,year,abstract,citationCount,externalIds,authors",
    },
)


def fetch(url: str, timeout: int = 45) -> dict:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers=UA)
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
            body = resp.read()
            return {
                "permalink": url,
                "final_url": resp.geturl(),
                "http_status": int(getattr(resp, "status", None) or resp.getcode()),
                "fetched_at": fetched_at,
                "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
                "content_type": resp.headers.get("Content-Type"),
                "body": body,
            }
    except urllib.error.HTTPError as exc:
        body = exc.read() if hasattr(exc, "read") else b""
        return {
            "permalink": url,
            "final_url": url,
            "http_status": int(exc.code),
            "fetched_at": fetched_at,
            "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest() if body else "",
            "content_type": None,
            "body": body,
            "error": f"HTTPError:{exc.code}",
        }
    except Exception as exc:  # noqa: BLE001 — capture must not abort the rest
        return {
            "permalink": url,
            "final_url": url,
            "http_status": 0,
            "fetched_at": fetched_at,
            "bytes": 0,
            "sha256": "",
            "content_type": None,
            "body": b"",
            "error": f"{type(exc).__name__}:{exc}",
        }


def _store(eid: str, rec: dict) -> dict:
    SNAP.mkdir(parents=True, exist_ok=True)
    body = rec.pop("body")
    body_path = SNAP / f"{eid}.body"
    body_path.write_bytes(body)
    rec["snapshot"] = f"command-center/p2-wave/probes/RES-0165/snapshots/{eid}.body"
    rec["id"] = eid
    print(
        f"captured {eid} status={rec.get('http_status')} "
        f"sha256={(rec.get('sha256') or '')[:12]} bytes={rec.get('bytes')} "
        f"err={rec.get('error') or '-'}"
    )
    return rec


def capture() -> dict:
    SNAP.mkdir(parents=True, exist_ok=True)
    rails = []
    for paper in PAPERS:
        pid = paper["id"]
        for kind, url in (
            ("structured-api", paper["structured"]),
            ("prose-source", paper["prose"]),
            ("structured-api-s2", paper["s2"]),
        ):
            rec = fetch(url)
            rec["kind"] = "structured-api" if kind.startswith("structured") else "prose-source"
            rec["paper_id"] = pid
            rec["arxiv"] = paper["arxiv"]
            rec["title_expect"] = paper["title_expect"]
            rails.append(_store(f"{pid}-{kind}", rec))
    index = {
        "unit_id": "RES-0165",
        "captured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rails": rails,
        "papers": list(PAPERS),
    }
    (SNAP / "index.json").write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return index


def load_index() -> dict:
    path = SNAP / "index.json"
    if not path.is_file():
        return capture()
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    capture()
    print("SUCCESS:RES-0165-capture")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
