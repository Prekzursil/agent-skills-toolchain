#!/usr/bin/env python3
"""Second-wave captures: archive/source-code/issue-tracker pivot after 403/500."""
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
UA = "Mozilla/5.0 (compatible; RES-0125-research/1.0)"

SOURCES = [
    {
        "id": "wayback-openai-terms-2026-01",
        "url": (
            "https://web.archive.org/web/20260101000000/"
            "https://openai.com/policies/row-terms-of-use/"
        ),
    },
    {
        "id": "wayback-openai-terms-latest",
        "url": "https://web.archive.org/web/2026/https://openai.com/policies/terms-of-use/",
    },
    {
        "id": "wayback-openai-business-terms",
        "url": (
            "https://web.archive.org/web/2026/"
            "https://openai.com/policies/business-terms/"
        ),
    },
    {
        "id": "github-tos",
        "url": "https://docs.github.com/en/site-policy/github-terms/github-terms-of-service",
    },
    {
        "id": "github-copilot-product-terms-docs",
        "url": (
            "https://docs.github.com/en/site-policy/github-terms/"
            "github-copilot-product-specific-terms"
        ),
    },
    {
        "id": "github-api-c2pa-commits-main",
        "url": "https://api.github.com/repos/c2pa-org/specifications/commits/main",
    },
    {
        "id": "github-api-spdx-commits-develop",
        "url": "https://api.github.com/repos/spdx/spdx-3-model/commits/develop",
    },
    {
        "id": "github-api-spdx-tags",
        "url": "https://api.github.com/repos/spdx/spdx-3-model/tags?per_page=10",
    },
    {
        "id": "c2pa-spec-2-3-index",
        "url": "https://spec.c2pa.org/specifications/specifications/2.3/index.html",
    },
    {
        "id": "c2pa-spec-2-3-html",
        "url": (
            "https://spec.c2pa.org/specifications/specifications/2.3/"
            "specs/C2PA_Specification.html"
        ),
    },
    {
        "id": "spdx-ai-package-md",
        "url": (
            "https://raw.githubusercontent.com/spdx/spdx-3-model/"
            "develop/model/AI/AIPackage.md"
        ),
    },
    {
        "id": "spdx-ai-profile-md",
        "url": (
            "https://raw.githubusercontent.com/spdx/spdx-3-model/"
            "develop/docs/ai.md"
        ),
    },
    {
        "id": "google-genai-additional-terms-text",
        "url": "https://policies.google.com/terms/generative-ai?hl=en",
    },
    {
        "id": "california-ab2013-text",
        "url": (
            "https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml"
            "?bill_id=202320240AB2013"
        ),
    },
]


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def fetch_one(src: dict) -> dict:
    url = src["url"]
    ts = utcnow()
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept": "*/*"},
        method="GET",
    )
    rec = {
        "id": src["id"],
        "requested_url": url,
        "fetch_timestamp": ts,
        "http_status": None,
        "final_url": url,
        "error": None,
        "content_type": None,
        "bytes": 0,
        "sha256": None,
        "capture_path": None,
        "git_sha": None,
    }
    try:
        with urllib.request.urlopen(
            req, timeout=60, context=ssl.create_default_context()
        ) as resp:
            body = resp.read()
            rec["http_status"] = int(resp.status)
            rec["final_url"] = str(resp.geturl())
            rec["content_type"] = resp.headers.get("Content-Type")
    except urllib.error.HTTPError as exc:
        body = exc.read() or b""
        rec["http_status"] = int(exc.code)
        rec["error"] = f"HTTPError: {exc.code} {exc.reason}"
        rec["final_url"] = str(exc.geturl() or url)
        rec["content_type"] = exc.headers.get("Content-Type") if exc.headers else None
    except Exception as exc:  # noqa: BLE001
        rec["error"] = f"{type(exc).__name__}: {exc}"
        body = b""
    rec["bytes"] = len(body)
    rec["sha256"] = hashlib.sha256(body).hexdigest()
    ctype = (rec["content_type"] or "").lower()
    if "json" in ctype:
        suffix = ".json"
    elif "html" in ctype:
        suffix = ".html"
    elif "markdown" in ctype or src["id"].endswith("-md"):
        suffix = ".md"
    else:
        suffix = ".bin"
    out = CAP / f"{src['id']}{suffix}"
    out.write_bytes(body)
    rec["capture_path"] = str(out.relative_to(HERE.parents[3]).as_posix())
    if rec["http_status"] == 200 and suffix == ".json":
        try:
            data = json.loads(body.decode("utf-8"))
            if isinstance(data, dict):
                rec["git_sha"] = data.get("sha")
                rec["html_url"] = data.get("html_url")
            elif isinstance(data, list) and data and isinstance(data[0], dict):
                rec["git_sha"] = data[0].get("commit", {}).get("sha") or data[0].get(
                    "name"
                )
                rec["tag_names"] = [x.get("name") for x in data[:8] if isinstance(x, dict)]
        except Exception:
            pass
    return rec


def main() -> int:
    rows = []
    for src in SOURCES:
        rec = fetch_one(src)
        rows.append(rec)
        print(
            f"{rec['id']:42} {rec['http_status']} bytes={rec['bytes']} "
            f"sha={rec['sha256'][:12]} git={rec.get('git_sha')} err={rec['error']}"
        )
        time.sleep(0.3)
    path = CAP / "_index_wave2.json"
    path.write_text(
        json.dumps({"unit_id": "RES-0125", "fetched_at": utcnow(), "captures": rows}, indent=1)
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
