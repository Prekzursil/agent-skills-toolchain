"""Live upstream reads with the unit retry policy.

Three attempts with staggered backoff for transient network/429.
ZERO retries on a non-transient upstream answer (404/410/license change).
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Optional

TRANSIENT = frozenset({408, 425, 429, 500, 502, 503, 504})
NON_TRANSIENT = frozenset({400, 401, 403, 404, 410, 451})
UA = "WFA-0159-freshness-monitor (+local-serialized; no-key-rotation)"


def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def fetch_url(
    url: str,
    *,
    timeout: float = 12.0,
    attempts: int = 3,
) -> dict:
    headers = {
        "User-Agent": UA,
        "Accept": "application/vnd.github+json, application/json;q=0.9, */*;q=0.1",
    }
    last_err = "untried"
    for i in range(max(1, attempts)):
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                status = int(getattr(resp, "status", 200) or 200)
                return _ok_payload(url, status, raw)
        except urllib.error.HTTPError as exc:
            status = int(exc.code)
            raw = b""
            try:
                raw = exc.read() or b""
            except OSError:
                raw = b""
            if status in NON_TRANSIENT:
                return {
                    "ok": False,
                    "url": url,
                    "fetch_date": iso_now(),
                    "http_status": status,
                    "error": f"non-transient HTTP {status}",
                    "retries": i,
                    "sha256": _digest(raw) if raw else None,
                }
            last_err = f"HTTP {status}"
            if status not in TRANSIENT:
                return {
                    "ok": False,
                    "url": url,
                    "fetch_date": iso_now(),
                    "http_status": status,
                    "error": last_err,
                    "retries": i,
                    "sha256": _digest(raw) if raw else None,
                }
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_err = f"{type(exc).__name__}: {exc}"
        if i + 1 < attempts:
            time.sleep(0.4 * (2**i))
    return {
        "ok": False,
        "url": url,
        "fetch_date": iso_now(),
        "http_status": None,
        "error": last_err,
        "retries": attempts,
        "sha256": None,
    }


def _ok_payload(url: str, status: int, raw: bytes) -> dict:
    fetch_date = iso_now()
    sha = _digest(raw)
    license_id = None
    archived = None
    version = None
    pushed_at = None
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        data = None
    if isinstance(data, dict):
        lic = data.get("license")
        if isinstance(lic, dict):
            license_id = lic.get("spdx_id") or lic.get("key")
        elif isinstance(lic, str):
            license_id = lic
        if "archived" in data:
            archived = bool(data.get("archived"))
        version = data.get("tag_name") or data.get("default_branch")
        pushed_at = data.get("pushed_at")
    return {
        "ok": True,
        "url": url,
        "fetch_date": fetch_date,
        "http_status": status,
        "license": license_id,
        "archived": archived,
        "version": version,
        "pushed_at": pushed_at,
        "sha256": sha,
        "bytes": len(raw),
    }


def fetch_github_repo(owner_repo: str) -> dict:
    return fetch_url(f"https://api.github.com/repos/{owner_repo}")


def load_fixture_live(path, url: Optional[str] = None) -> dict:
    """Rerunnable live read of a fixture upstream file, with fetch_date."""
    raw = path.read_bytes()
    doc = json.loads(raw.decode("utf-8"))
    if not isinstance(doc, dict):
        raise ValueError(f"fixture live is not an object: {path}")
    out = dict(doc)
    out.setdefault("url", url or path.as_posix())
    out.setdefault("fetch_date", iso_now())
    out.setdefault("sha256", _digest(raw))
    if "ok" not in out:
        out["ok"] = out.get("http_status") == 200
    return out
