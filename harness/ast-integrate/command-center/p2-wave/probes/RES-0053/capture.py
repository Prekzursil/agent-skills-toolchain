#!/usr/bin/env python3
"""Fetch dual-rail evidence for RES-0053: structured registry APIs + official prose.

Each capture stores raw bytes plus a sidecar with permalink, HTTP status,
fetch timestamp, and sha256. Probes re-hash the bytes; they do not trust this
sidecar for the digest.
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
CAP = HERE / "captures"
UA = "RES-0053-research/1.0 (ast-integrate; registry-revocation-study)"
TIMEOUT = 45

# Dual rails: structured API (R1) and official/prose policy (R2) per registry,
# plus the cited incident pair.
SOURCES = [
    {
        "id": "npm-api-unpublished-flatmap-stream",
        "registry": "npm",
        "kind": "api",
        "url": "https://registry.npmjs.org/flatmap-stream",
        "role": "unpublished-package-lookup",
    },
    {
        "id": "npm-api-event-stream",
        "registry": "npm",
        "kind": "api",
        "url": "https://registry.npmjs.org/event-stream",
        "role": "surviving-package-lookup",
    },
    {
        "id": "npm-prose-unpublish-policy",
        "registry": "npm",
        "kind": "prose",
        "url": "https://docs.npmjs.com/policies/unpublish/",
        "role": "registry-action-policy",
    },
    {
        "id": "npm-prose-deprecate-cli",
        "registry": "npm",
        "kind": "prose",
        "url": "https://docs.npmjs.com/cli/v10/commands/npm-deprecate",
        "role": "deprecate-action",
    },
    {
        "id": "pypi-api-simple-urllib3",
        "registry": "pypi",
        "kind": "api",
        "url": "https://pypi.org/simple/urllib3/",
        "accept": "application/vnd.pypi.simple.v1+json",
        "role": "yanked-file-index",
    },
    {
        "id": "pypi-prose-pep592",
        "registry": "pypi",
        "kind": "prose",
        "url": "https://peps.python.org/pep-0592/",
        "role": "yank-semantics",
    },
    {
        "id": "crates-api-futures-0-2-0",
        "registry": "crates.io",
        "kind": "api",
        "url": "https://crates.io/api/v1/crates/futures/0.2.0",
        "role": "yanked-version-lookup",
    },
    {
        "id": "crates-prose-cargo-yank",
        "registry": "crates.io",
        "kind": "prose",
        "url": "https://doc.rust-lang.org/cargo/commands/cargo-yank.html",
        "role": "yank-installed-client",
    },
    {
        "id": "vscode-api-material-theme",
        "registry": "vs-code-marketplace",
        "kind": "api",
        "url": (
            "https://marketplace.visualstudio.com/_apis/public/gallery/"
            "extensionquery?api-version=7.1-preview.1"
        ),
        "method": "POST",
        "content_type": "application/json",
        "body": json.dumps(
            {
                "filters": [
                    {
                        "criteria": [
                            {
                                "filterType": 7,
                                "value": "equinusocio.vsc-material-theme",
                            }
                        ]
                    }
                ],
                "flags": 914,
            }
        ).encode("utf-8"),
        "role": "removed-extension-lookup",
    },
    {
        "id": "vscode-prose-runtime-security",
        "registry": "vs-code-marketplace",
        "kind": "prose",
        "url": (
            "https://raw.githubusercontent.com/microsoft/vscode-docs/main/"
            "docs/configure/extensions/extension-runtime-security.md"
        ),
        "role": "blocklist-auto-uninstall",
    },
    {
        "id": "jetbrains-api-python-plugin",
        "registry": "jetbrains-marketplace",
        "kind": "api",
        "url": "https://plugins.jetbrains.com/api/plugins/631",
        "role": "plugin-record-lookup",
    },
    {
        "id": "jetbrains-prose-hidden-release",
        "registry": "jetbrains-marketplace",
        "kind": "prose",
        "url": "https://plugins.jetbrains.com/docs/marketplace/hidden-plugin.html",
        "role": "hide-does-not-reach-installed",
    },
    {
        "id": "chrome-api-safe-browsing-help",
        "registry": "chrome-web-store",
        "kind": "api",
        "url": "https://support.google.com/chrome/answer/13844634?hl=en",
        "role": "safe-browsing-disable-installed",
        "note": (
            "Chrome has no public package JSON analogous to npm/PyPI; this "
            "support document is the structured product contract for the "
            "installed-client malware disable path."
        ),
    },
    {
        "id": "chrome-prose-disabled-extensions",
        "registry": "chrome-web-store",
        "kind": "prose",
        "url": "https://support.google.com/chrome_webstore/answer/2811969?hl=en",
        "role": "cws-disabled-extensions",
    },
    {
        "id": "incident-npm-blog-event-stream",
        "registry": "npm",
        "kind": "prose",
        "url": (
            "https://blog.npmjs.org/post/180565383195/"
            "details-about-the-event-stream-incident"
        ),
        "role": "cited-incident",
    },
    {
        "id": "incident-snyk-event-stream",
        "registry": "npm",
        "kind": "prose",
        "url": "https://snyk.io/blog/a-post-mortem-of-the-malicious-event-stream-backdoor/",
        "role": "cited-incident-second-rail",
    },
]


def fetch_one(src: dict) -> dict:
    url = src["url"]
    method = src.get("method", "GET")
    headers = {"User-Agent": UA, "Accept": src.get("accept", "*/*")}
    if src.get("content_type"):
        headers["Content-Type"] = src["content_type"]
    req = urllib.request.Request(url, data=src.get("body"), method=method, headers=headers)
    ctx = ssl.create_default_context()
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as resp:
            raw = resp.read()
            status = int(resp.status)
            final_url = str(resp.geturl())
            ctype = resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        raw = exc.read() if exc.fp else b""
        status = int(exc.code)
        final_url = url
        ctype = exc.headers.get("Content-Type", "") if exc.headers else ""
    except Exception as exc:
        raw = f"FETCH-ERROR:{type(exc).__name__}:{exc}".encode("utf-8", errors="replace")
        status = 0
        final_url = url
        ctype = "text/plain"
    digest = hashlib.sha256(raw).hexdigest()
    body_path = CAP / f"{src['id']}.body"
    meta_path = CAP / f"{src['id']}.meta.json"
    body_path.write_bytes(raw)
    meta = {
        "id": src["id"],
        "registry": src["registry"],
        "kind": src["kind"],
        "role": src["role"],
        "permalink": url,
        "resolved_url": final_url,
        "method": method,
        "http_status": status,
        "fetch_timestamp": fetched_at,
        "sha256": digest,
        "bytes": len(raw),
        "content_type": ctype,
        "body_path": f"command-center/p2-wave/probes/RES-0053/captures/{src['id']}.body",
        "note": src.get("note"),
    }
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return meta


def main() -> int:
    CAP.mkdir(parents=True, exist_ok=True)
    index = []
    failures = []
    for src in SOURCES:
        meta = fetch_one(src)
        index.append(meta)
        ok = meta["http_status"] in {200, 404} or (
            src["id"].startswith("vscode") and meta["http_status"] in {200, 204}
        )
        # 404 is a valid API observation for unpublished packages.
        if meta["http_status"] == 0:
            failures.append(meta["id"])
            ok = False
        print(
            f"{meta['id']:<42} HTTP {meta['http_status']:>3} "
            f"bytes={meta['bytes']:<8} sha256={meta['sha256'][:12]} ok={ok}"
        )
    (CAP / "INDEX.json").write_text(
        json.dumps({"sources": index, "failures": failures}, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    if failures:
        print(f"FAILED:capture network-zero {failures}")
        return 1
    print(f"SUCCESS:RES-0053-capture n={len(index)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
