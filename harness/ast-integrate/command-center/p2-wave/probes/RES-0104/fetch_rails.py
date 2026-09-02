#!/usr/bin/env python3
"""Live-fetch two-rail sources for RES-0104. Records HTTP status, timestamp, sha256."""
from __future__ import annotations

import hashlib
import json
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAP = HERE / "captures"
UA = "ast-integrate-RES-0104 (+https://github.com/ast-integrate; research-probe)"
CTX = ssl.create_default_context()

RAILS = [
    {
        "id": "vscode-activation-events-md",
        "kind": "prose",
        "url": "https://raw.githubusercontent.com/microsoft/vscode-docs/main/api/references/activation-events.md",
    },
    {
        "id": "vscode-command-guide-md",
        "kind": "prose",
        "url": "https://raw.githubusercontent.com/microsoft/vscode-docs/main/api/extension-guides/command.md",
    },
    {
        "id": "vscode-commands-quickaccess-ts",
        "kind": "api",
        "url": "https://raw.githubusercontent.com/microsoft/vscode/main/src/vs/workbench/contrib/quickaccess/browser/commandsQuickAccess.ts",
    },
    {
        "id": "k8s-kep-3352-readme",
        "kind": "prose",
        "url": "https://raw.githubusercontent.com/kubernetes/enhancements/master/keps/sig-api-machinery/3352-aggregated-discovery/README.md",
    },
    {
        "id": "k8s-openapi-v3-listing",
        "kind": "api",
        "url": "https://api.github.com/repos/kubernetes/kubernetes/contents/api/openapi-spec/v3?ref=v1.32.2",
        "headers": {"Accept": "application/vnd.github+json"},
    },
    {
        "id": "k8s-api-concepts-md",
        "kind": "prose",
        "url": "https://raw.githubusercontent.com/kubernetes/website/master/content/en/docs/concepts/overview/kubernetes-api.md",
    },
    {
        "id": "npm-registry-api-md",
        "kind": "prose",
        "url": "https://raw.githubusercontent.com/npm/registry/main/docs/REGISTRY-API.md",
    },
    {
        "id": "npm-search-total",
        "kind": "api",
        "url": "https://registry.npmjs.org/-/v1/search?text=boost-exact:false&size=1",
    },
    {
        "id": "mcp-tools-spec-mdx",
        "kind": "prose",
        "url": "https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/docs/specification/2026-07-28/server/tools.mdx",
    },
    {
        "id": "mcp-schema-ts",
        "kind": "api",
        "url": "https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/schema/2026-07-28/schema.ts",
    },
    {
        "id": "mcp-sep2636-pr",
        "kind": "api",
        "url": "https://api.github.com/repos/modelcontextprotocol/modelcontextprotocol/pulls/2636",
        "headers": {"Accept": "application/vnd.github+json"},
    },
    {
        "id": "anthropic-skills-overview",
        "kind": "prose",
        "url": "https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview.md",
    },
    {
        "id": "agentskills-spec",
        "kind": "prose",
        "url": "https://agentskills.io/specification",
    },
    {
        "id": "anthropic-skill-dev-skillmd",
        "kind": "api",
        "url": "https://raw.githubusercontent.com/anthropics/claude-plugins-official/HEAD/plugins/plugin-dev/skills/skill-development/SKILL.md",
    },
    {
        "id": "mcp-client-best-practices",
        "kind": "prose",
        "url": "https://modelcontextprotocol.io/docs/2026-07-28/develop/clients/client-best-practices.md",
    },
]


def fetch_one(spec: dict) -> dict:
    url = spec["url"]
    headers = {"User-Agent": UA, "Accept": "*/*"}
    extra = spec.get("headers") or {}
    headers.update(extra)
    data = spec.get("body")
    method = spec.get("method", "GET")
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        with urllib.request.urlopen(req, timeout=60, context=CTX) as resp:
            body = resp.read()
            status = int(resp.status)
            final = str(resp.geturl())
            ctype = resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp else b""
        status = int(exc.code)
        final = url
        ctype = exc.headers.get("Content-Type", "") if exc.headers else ""
    except Exception as exc:
        return {
            "id": spec["id"],
            "kind": spec["kind"],
            "requested_url": url,
            "permalink": url,
            "fetched_at": fetched_at,
            "http_status": 0,
            "error": f"{type(exc).__name__}:{exc}",
            "sha256": None,
            "bytes": 0,
        }
    digest = hashlib.sha256(body).hexdigest()
    out = CAP / f"{spec['id']}.bin"
    out.write_bytes(body)
    return {
        "id": spec["id"],
        "kind": spec["kind"],
        "requested_url": url,
        "permalink": final,
        "fetched_at": fetched_at,
        "http_status": status,
        "content_type": ctype,
        "sha256": digest,
        "bytes": len(body),
        "path": f"command-center/p2-wave/probes/RES-0104/captures/{spec['id']}.bin",
        "error": None,
    }


def fetch_marketplace() -> dict:
    payload = json.dumps(
        {
            "filters": [
                {
                    "criteria": [
                        {"filterType": 8, "value": "Microsoft.VisualStudio.Code"}
                    ],
                    "pageNumber": 1,
                    "pageSize": 1,
                    "sortBy": 0,
                    "sortOrder": 0,
                }
            ],
            "assetTypes": [],
            "flags": 0,
        }
    ).encode("utf-8")
    return fetch_one(
        {
            "id": "vscode-marketplace-query",
            "kind": "api",
            "url": (
                "https://marketplace.visualstudio.com/_apis/public/gallery/"
                "extensionquery?api-version=7.1-preview.1"
            ),
            "method": "POST",
            "body": payload,
            "headers": {
                "Content-Type": "application/json",
                "Accept": "application/json;api-version=7.1-preview.1",
            },
        }
    )


def main() -> int:
    CAP.mkdir(parents=True, exist_ok=True)
    rows = []
    for spec in RAILS:
        row = fetch_one(spec)
        print(
            f"{row['id']} status={row['http_status']} bytes={row.get('bytes', 0)} "
            f"err={row.get('error')}"
        )
        rows.append(row)
        time.sleep(0.15)
    mkt = fetch_marketplace()
    print(
        f"{mkt['id']} status={mkt['http_status']} bytes={mkt.get('bytes', 0)} "
        f"err={mkt.get('error')}"
    )
    rows.append(mkt)
    index = {
        "unit_id": "RES-0104",
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rails": rows,
    }
    (CAP / "index.json").write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    ok = sum(1 for r in rows if r.get("http_status") == 200)
    print(f"ok_200={ok}/{len(rows)}")
    return 0 if ok >= 8 else 1


if __name__ == "__main__":
    raise SystemExit(main())
