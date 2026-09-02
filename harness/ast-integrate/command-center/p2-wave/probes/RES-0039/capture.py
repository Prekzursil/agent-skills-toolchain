#!/usr/bin/env python3
"""Capture dual-rail evidence (GitHub API + prose) into snapshots/index.json."""
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
    "User-Agent": "ast-integrate-RES-0039-evidence/1.0",
    "Accept": "*/*",
}

# Each tuple: id, kind (structured-api|prose-source), url, used_by class ids
EVIDENCE = (
    (
        "gh-api-experiments-repo",
        "structured-api",
        "https://api.github.com/repos/invariantlabs-ai/mcp-injection-experiments",
        ("tool-poisoning", "description-injection", "rug-pull-update", "cross-server-shadowing"),
    ),
    (
        "gh-api-experiments-contents",
        "structured-api",
        "https://api.github.com/repos/invariantlabs-ai/mcp-injection-experiments/contents/",
        ("tool-poisoning", "description-injection", "rug-pull-update", "cross-server-shadowing"),
    ),
    (
        "gh-api-direct-poisoning",
        "structured-api",
        "https://api.github.com/repos/invariantlabs-ai/mcp-injection-experiments/contents/direct-poisoning.py",
        ("tool-poisoning", "description-injection"),
    ),
    (
        "gh-api-shadowing",
        "structured-api",
        "https://api.github.com/repos/invariantlabs-ai/mcp-injection-experiments/contents/shadowing.py",
        ("cross-server-shadowing",),
    ),
    (
        "gh-api-whatsapp",
        "structured-api",
        "https://api.github.com/repos/invariantlabs-ai/mcp-injection-experiments/contents/whatsapp-takeover.py",
        ("rug-pull-update",),
    ),
    (
        "gh-api-mcp-repo",
        "structured-api",
        "https://api.github.com/repos/modelcontextprotocol/modelcontextprotocol",
        ("confused-deputy", "description-injection"),
    ),
    (
        "gh-api-mcp-auth-mdx",
        "structured-api",
        "https://api.github.com/repos/modelcontextprotocol/modelcontextprotocol/contents/docs/specification/2025-11-25/basic/authorization.mdx",
        ("confused-deputy",),
    ),
    (
        "inv-blog-poison",
        "prose-source",
        "https://invariantlabs.ai/blog/mcp-security-notification-tool-poisoning-attacks",
        ("tool-poisoning", "description-injection", "rug-pull-update", "cross-server-shadowing"),
    ),
    (
        "simon-blog",
        "prose-source",
        "https://simonwillison.net/2025/Apr/9/mcp-prompt-injection/",
        ("tool-poisoning", "description-injection", "rug-pull-update", "cross-server-shadowing"),
    ),
    (
        "mcp-auth-mdx",
        "prose-source",
        "https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/docs/specification/2025-11-25/basic/authorization.mdx",
        ("confused-deputy",),
    ),
    (
        "mcp-tools-mdx",
        "prose-source",
        "https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/docs/specification/2025-11-25/server/tools.mdx",
        ("tool-poisoning", "description-injection"),
    ),
    (
        "mcp-security-practices",
        "prose-source",
        "https://modelcontextprotocol.io/docs/2025-11-25/tutorials/security/security_best_practices",
        ("confused-deputy",),
    ),
)


def fetch(url: str) -> dict:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers=UA)
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
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


def capture() -> dict:
    SNAP.mkdir(parents=True, exist_ok=True)
    rows = []
    for eid, kind, url, classes in EVIDENCE:
        rec = fetch(url)
        body = rec.pop("body")
        body_path = SNAP / f"{eid}.body"
        body_path.write_bytes(body)
        rec.update(
            {
                "id": eid,
                "kind": kind,
                "classes": list(classes),
                "snapshot": f"command-center/p2-wave/probes/RES-0039/snapshots/{eid}.body",
            }
        )
        if rec.get("http_status") != 200:
            raise RuntimeError(f"capture {eid} HTTP {rec.get('http_status')} {url}")
        rows.append(rec)
        print(f"captured {eid} status={rec['http_status']} sha256={rec['sha256'][:12]} bytes={rec['bytes']}")
    index = {
        "unit_id": "RES-0039",
        "captured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rails": rows,
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


def rails_for(class_id: str, index: dict) -> list[dict]:
    api = None
    prose = None
    for rec in index.get("rails") or []:
        if class_id not in (rec.get("classes") or []):
            continue
        row = {
            "kind": rec["kind"],
            "permalink": rec.get("final_url") or rec["permalink"],
            "fetched_at": rec["fetched_at"],
            "http_status": rec["http_status"],
            "sha256": rec["sha256"],
            "bytes": rec["bytes"],
            "snapshot": rec["snapshot"],
            "id": rec["id"],
        }
        if rec["kind"] == "structured-api" and api is None:
            api = row
        elif rec["kind"] == "prose-source" and prose is None:
            prose = row
        if api and prose:
            break
    if not api or not prose:
        raise RuntimeError(f"missing dual rails for {class_id}")
    return [api, prose]


def main() -> int:
    capture()
    print("SUCCESS:RES-0039-capture")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
