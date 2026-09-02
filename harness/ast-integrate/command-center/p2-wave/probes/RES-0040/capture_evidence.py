#!/usr/bin/env python3
"""Fetch official permission docs/source into captures/ with HTTP status and sha256."""
from __future__ import annotations

import hashlib
import json
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAP = HERE / "captures"

UA = "ast-integrate-RES-0040-evidence/1.0 (research capture; +https://example.invalid)"

# Two rails per client: R1 structured (schema/source/key-list) and R2 prose docs.
SOURCES = [
    {
        "id": "claude-permissions-prose",
        "client_id": "claude-code",
        "rail": "R2-prose",
        "url": "https://code.claude.com/docs/en/permissions",
    },
    {
        "id": "claude-mcp-prose",
        "client_id": "claude-code",
        "rail": "R2-prose",
        "url": "https://code.claude.com/docs/en/mcp",
        "optional": True,
    },
    {
        "id": "codex-config-reference",
        "client_id": "codex",
        "rail": "R1-structured",
        "url": "https://developers.openai.com/codex/config-reference",
    },
    {
        "id": "codex-approvals-prose",
        "client_id": "codex",
        "rail": "R2-prose",
        "url": "https://developers.openai.com/codex/agent-approvals-security",
    },
    {
        "id": "codex-github-config-rs",
        "client_id": "codex",
        "rail": "R1-structured",
        "url": "https://raw.githubusercontent.com/openai/codex/main/codex-rs/core/src/config/mod.rs",
        "optional": True,
    },
    {
        "id": "cursor-permissions-prose",
        "client_id": "cursor",
        "rail": "R2-prose",
        "url": "https://cursor.com/docs/reference/permissions",
    },
    {
        "id": "cursor-cli-reference",
        "client_id": "cursor",
        "rail": "R1-structured",
        "url": "https://cursor.com/docs/cli/reference",
        "optional": True,
    },
    {
        "id": "antigravity-permissions-prose",
        "client_id": "antigravity",
        "rail": "R2-prose",
        "url": "https://www.antigravity.google/docs/permissions",
    },
    {
        "id": "antigravity-mcp-prose",
        "client_id": "antigravity",
        "rail": "R2-prose",
        "url": "https://antigravity.google/docs/mcp/",
        "optional": True,
    },
    {
        "id": "antigravity-cli-permissions",
        "client_id": "antigravity",
        "rail": "R1-structured",
        "url": "https://antigravity.google/docs/cli/permissions/",
        "optional": True,
    },
]


def fetch(url: str) -> tuple[int, bytes, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,text/plain,application/json;q=0.9,*/*;q=0.8",
        },
        method="GET",
    )
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=45, context=ctx) as resp:
            body = resp.read()
            final = str(resp.geturl())
            return int(resp.status), body, final
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp else b""
        return int(exc.code), body, url
    except urllib.error.URLError as exc:
        return 0, str(exc).encode("utf-8"), url


def main() -> int:
    CAP.mkdir(parents=True, exist_ok=True)
    index = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    hard_fail = 0
    for src in SOURCES:
        status, body, final = fetch(src["url"])
        sha = hashlib.sha256(body).hexdigest()
        body_path = CAP / f"{src['id']}.body"
        meta_path = CAP / f"{src['id']}.meta.json"
        body_path.write_bytes(body)
        meta = {
            "id": src["id"],
            "client_id": src["client_id"],
            "rail": src["rail"],
            "url": src["url"],
            "final_url": final,
            "http_status": status,
            "fetched_at": now,
            "sha256": sha,
            "bytes": len(body),
            "optional": bool(src.get("optional")),
        }
        meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        index.append(meta)
        print(f"{src['id']} status={status} bytes={len(body)} sha256={sha[:16]}...")
        if status not in {200, 301, 302} and not src.get("optional"):
            hard_fail += 1
        time.sleep(0.3)
    (CAP / "INDEX.json").write_text(
        json.dumps({"fetched_at": now, "sources": index}, indent=2) + "\n",
        encoding="utf-8",
    )
    if hard_fail:
        print(f"FAILED:RES-0040-capture required sources failed={hard_fail}")
        return 1
    print("SUCCESS:RES-0040-capture")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
