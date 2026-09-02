#!/usr/bin/env python3
"""Fetch official Claude Code docs and pin sha256 of the captured bytes."""
from __future__ import annotations

import json
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import CAPTURE_DIR, DOC_URLS, INDEX_PATH, OLD_DOCS_URL, sha256_bytes

UA = "ast-integrate-RES-0022-doc-capture/1.0"
TIMEOUT = 45


def fetch(url: str, method: str = "GET", follow: bool = True) -> dict:
    headers = {"User-Agent": UA, "Accept": "text/plain, text/markdown, text/html, */*"}
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers=headers, method=method)

    class NoRedir(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ARG002
            return None

    handlers: list = [
        urllib.request.HTTPSHandler(context=ctx),
        urllib.request.HTTPHandler(),
    ]
    if not follow:
        handlers.insert(0, NoRedir())
    opener = urllib.request.build_opener(*handlers)
    try:
        with opener.open(req, timeout=TIMEOUT) as resp:
            body = resp.read() if method == "GET" else b""
            return {
                "ok": True,
                "status": int(resp.status),
                "final_url": str(resp.geturl()),
                "location": resp.headers.get("Location") or "",
                "content_type": resp.headers.get("Content-Type") or "",
                "body": body,
                "error": "",
            }
    except urllib.error.HTTPError as exc:
        loc = exc.headers.get("Location") if exc.headers else ""
        body = b""
        try:
            body = exc.read() or b""
        except Exception:
            body = b""
        return {
            "ok": False,
            "status": int(exc.code),
            "final_url": url,
            "location": loc or "",
            "content_type": (exc.headers.get("Content-Type") if exc.headers else "") or "",
            "body": body,
            "error": f"HTTPError:{exc.code}",
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": 0,
            "final_url": url,
            "location": "",
            "content_type": "",
            "body": b"",
            "error": f"{type(exc).__name__}:{exc}",
        }


def main() -> int:
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    docs: dict = {}
    failures = 0
    for doc_id, url in DOC_URLS.items():
        rec = fetch(url, method="GET", follow=True)
        body: bytes = rec.pop("body")
        digest = sha256_bytes(body) if body else ""
        dest = CAPTURE_DIR / f"{doc_id}.body"
        dest.write_bytes(body)
        docs[doc_id] = {
            "url": url,
            "status": rec["status"],
            "final_url": rec["final_url"],
            "content_type": rec["content_type"],
            "sha256": digest,
            "bytes": len(body.replace(b"\r\n", b"\n")),
            "path": str(dest.relative_to(CAPTURE_DIR.parent).as_posix())
            if False
            else f"captures/{doc_id}.body",
            "error": rec["error"],
        }
        print(
            f"fetch {doc_id} status={rec['status']} sha256={digest[:12] or '-'} "
            f"bytes={len(body)} err={rec['error'] or '-'}"
        )
        if rec["status"] != 200 or not body:
            failures += 1

    nofollow = fetch(OLD_DOCS_URL, method="GET", follow=False)
    follow = fetch(OLD_DOCS_URL, method="GET", follow=True)
    redirect = {
        "url": OLD_DOCS_URL,
        "nofollow_status": nofollow["status"],
        "nofollow_location": nofollow["location"],
        "follow_status": follow["status"],
        "follow_final_url": follow["final_url"],
        "follow_sha256": sha256_bytes(follow["body"]) if follow["body"] else "",
        "error": nofollow["error"] or follow["error"],
    }
    (CAPTURE_DIR / "old-hooks-redirect.json").write_text(
        json.dumps(redirect, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"redirect old-hooks nofollow={nofollow['status']} "
        f"loc={nofollow['location'][:80]!r} follow={follow['status']} "
        f"final={follow['final_url']}"
    )

    INDEX_PATH.write_text(
        json.dumps(
            {"fetched_at": now, "docs": docs, "old_hooks_redirect": redirect},
            indent=1,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    if failures:
        print(f"WARN:capture {failures} doc fetches not HTTP 200 with body")
    print("SUCCESS:RES-0022-capture")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
