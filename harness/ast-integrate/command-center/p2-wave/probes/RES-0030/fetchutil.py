"""Small HTTP helper: no-follow redirect chains and body fetches."""
from __future__ import annotations

import hashlib
import os
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin

from constants import UA

CTX = ssl.create_default_context()


def _github_token() -> str | None:
    for key in ("GITHUB_TOKEN", "GH_TOKEN", "GITHUB_PAT"):
        val = os.environ.get(key)
        if val:
            return val
    return None


class _NoRedir(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(_NoRedir, urllib.request.HTTPSHandler(context=CTX))


def _headers(url: str) -> dict[str, str]:
    h = {"User-Agent": UA, "Accept": "*/*"}
    if "api.github.com" in url:
        h["Accept"] = "application/vnd.github+json"
    token = _github_token()
    if token and ("api.github.com" in url or "githubusercontent.com" in url or "github.com" in url):
        h["Authorization"] = f"Bearer {token}"
    return h


def _one(url: str, method: str = "GET") -> dict[str, Any]:
    req = urllib.request.Request(url, method=method, headers=_headers(url))
    opener = _opener()
    try:
        resp = opener.open(req, timeout=45)
        body = resp.read() if method != "HEAD" else b""
        headers = {k.lower(): v for k, v in resp.headers.items()}
        return {
            "url": url,
            "status": resp.getcode(),
            "location": headers.get("location"),
            "content_type": headers.get("content-type"),
            "body": body,
            "sha256": hashlib.sha256(body).hexdigest() if body else None,
            "bytes": len(body),
        }
    except urllib.error.HTTPError as exc:
        body = exc.read() if method != "HEAD" else b""
        headers = {k.lower(): v for k, v in (exc.headers.items() if exc.headers else [])}
        return {
            "url": url,
            "status": int(exc.code),
            "location": headers.get("location"),
            "content_type": headers.get("content-type"),
            "body": body,
            "sha256": hashlib.sha256(body).hexdigest() if body else None,
            "bytes": len(body),
            "reason": str(exc.reason),
        }


def fetch_chain(url: str, method: str = "GET", max_hops: int = 8) -> dict[str, Any]:
    """Follow Location headers ourselves so the hop list is explicit."""
    chain: list[dict[str, Any]] = []
    current = url
    last_body = b""
    for hop in range(max_hops):
        last: dict[str, Any] | None = None
        err: str | None = None
        for attempt in range(3):
            try:
                last = _one(current, method=method)
                if last["status"] in (429, 403) and attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                break
            except Exception as exc:  # noqa: BLE001
                err = f"{type(exc).__name__}: {exc}"
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                last = None
        if last is None:
            chain.append({"hop": hop, "url": current, "error": err or "fetch-failed"})
            break
        last_body = last.get("body") or b""
        rec = {
            "hop": hop,
            "url": last["url"],
            "status": last["status"],
            "location": last.get("location"),
            "content_type": last.get("content-type") or last.get("content_type"),
            "bytes": last.get("bytes"),
            "sha256": last.get("sha256"),
        }
        if last.get("reason"):
            rec["reason"] = last["reason"]
        chain.append(rec)
        loc = last.get("location")
        if loc and last["status"] in (301, 302, 303, 307, 308):
            current = urljoin(current, loc)
            continue
        break
    return {
        "request_url": url,
        "method": method,
        "final_url": chain[-1]["url"] if chain else url,
        "final_status": chain[-1].get("status") if chain else None,
        "chain": chain,
        "body": last_body,
        "fetched_at": _now(),
    }


def fetch_body(url: str) -> dict[str, Any]:
    rec = fetch_chain(url, method="GET", max_hops=4)
    body = rec.pop("body", b"")
    rec["sha256"] = hashlib.sha256(body).hexdigest() if body else None
    rec["bytes"] = len(body)
    rec["body"] = body
    rec["status"] = rec.get("final_status")
    rec["permalink"] = url
    return rec


def lineage(url: str, status: int | None, sha256: str | None, fetched_at: str, rail: str) -> dict[str, Any]:
    return {
        "permalink": url,
        "http_status": status,
        "sha256": sha256,
        "fetch_timestamp": fetched_at,
        "rail": rail,
    }
