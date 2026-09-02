#!/usr/bin/env python3
"""Fetch pinned source captures for RES-0125. Records HTTP status, sha256, timestamp."""
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
UA = (
    "Mozilla/5.0 (compatible; RES-0125-research/1.0; "
    "+https://ast-integrate.local/research)"
)

SOURCES = [
    {
        "id": "openai-row-terms",
        "url": "https://openai.com/policies/row-terms-of-use/",
        "kind": "vendor-terms",
    },
    {
        "id": "openai-terms-of-use",
        "url": "https://openai.com/policies/terms-of-use/",
        "kind": "vendor-terms",
    },
    {
        "id": "openai-services-agreement",
        "url": "https://openai.com/policies/service-terms/",
        "kind": "vendor-terms",
    },
    {
        "id": "anthropic-consumer-terms",
        "url": "https://www.anthropic.com/legal/consumer-terms",
        "kind": "vendor-terms",
    },
    {
        "id": "anthropic-commercial-terms",
        "url": "https://www.anthropic.com/legal/commercial-terms",
        "kind": "vendor-terms",
    },
    {
        "id": "google-genai-additional-terms",
        "url": "https://policies.google.com/terms/generative-ai",
        "kind": "vendor-terms",
    },
    {
        "id": "gemini-api-terms",
        "url": "https://ai.google.dev/gemini-api/terms",
        "kind": "vendor-terms",
    },
    {
        "id": "github-copilot-product-terms",
        "url": "https://github.com/customer-terms/github-copilot-product-specific-terms",
        "kind": "vendor-terms",
    },
    {
        "id": "github-additional-products-copilot",
        "url": (
            "https://docs.github.com/en/site-policy/github-terms/"
            "github-terms-for-additional-products-and-features"
        ),
        "kind": "vendor-terms",
    },
    {
        "id": "eurlex-ai-act-2024-1689",
        "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32024R1689",
        "kind": "law",
    },
    {
        "id": "us-fr-ai-copyright-registration-88fr16190",
        "url": "https://www.federalregister.gov/documents/2023/03/16/2023-05321/"
        "copyright-registration-guidance-works-containing-material-generated-by-artificial-intelligence",
        "kind": "law-guidance",
    },
    {
        "id": "github-api-c2pa-specifications",
        "url": "https://api.github.com/repos/c2pa-org/specifications",
        "kind": "api",
    },
    {
        "id": "github-api-spdx-3-model",
        "url": "https://api.github.com/repos/spdx/spdx-3-model",
        "kind": "api",
    },
    {
        "id": "creativecommons-cc-signals",
        "url": "https://creativecommons.org/cc-signals/",
        "kind": "proposed-norm",
    },
    {
        "id": "c2pa-spec-landing",
        "url": "https://c2pa.org/specifications/specifications/2.2/index.html",
        "kind": "proposed-norm",
    },
    {
        "id": "c2pa-explainer",
        "url": "https://c2pa.org/specifications/specifications/2.2/explainer/Explainer.html",
        "kind": "proposed-norm",
    },
    {
        "id": "nist-ai-600-1",
        "url": (
            "https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf"
        ),
        "kind": "proposed-norm",
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
        headers={
            "User-Agent": UA,
            "Accept": "*/*",
        },
        method="GET",
    )
    ctx = ssl.create_default_context()
    rec = {
        "id": src["id"],
        "kind": src["kind"],
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
        "tag": None,
        "default_branch": None,
    }
    try:
        with urllib.request.urlopen(req, timeout=45, context=ctx) as resp:
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
    except Exception as exc:  # noqa: BLE001 - capture any fetch failure
        rec["error"] = f"{type(exc).__name__}: {exc}"
        body = b""
    rec["bytes"] = len(body)
    rec["sha256"] = hashlib.sha256(body).hexdigest()
    suffix = ".bin"
    ctype = (rec["content_type"] or "").lower()
    if "json" in ctype:
        suffix = ".json"
    elif "html" in ctype:
        suffix = ".html"
    elif "pdf" in ctype:
        suffix = ".pdf"
    elif "text/plain" in ctype or "markdown" in ctype:
        suffix = ".txt"
    out = CAP / f"{src['id']}{suffix}"
    out.write_bytes(body)
    rec["capture_path"] = str(out.relative_to(HERE.parents[3]).as_posix())
    if rec["http_status"] == 200 and suffix == ".json":
        try:
            data = json.loads(body.decode("utf-8"))
            rec["git_sha"] = data.get("sha") or (data.get("commit") or {}).get("sha")
            rec["default_branch"] = data.get("default_branch")
            rec["tag"] = (data.get("license") or {}).get("spdx_id")
            rec["pushed_at"] = data.get("pushed_at")
            rec["html_url"] = data.get("html_url")
        except Exception:
            pass
    return rec


def main() -> int:
    CAP.mkdir(parents=True, exist_ok=True)
    rows = []
    for src in SOURCES:
        rec = fetch_one(src)
        rows.append(rec)
        print(
            f"{rec['id']} status={rec['http_status']} bytes={rec['bytes']} "
            f"err={rec['error']}"
        )
        time.sleep(0.4)
    index = {
        "unit_id": "RES-0125",
        "fetched_at": utcnow(),
        "captures": rows,
    }
    (CAP / "_index.json").write_text(
        json.dumps(index, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    ok = sum(1 for r in rows if r["http_status"] == 200)
    print(f"fetched {ok}/{len(rows)} HTTP 200")
    return 0 if ok >= 6 else 1


if __name__ == "__main__":
    raise SystemExit(main())
