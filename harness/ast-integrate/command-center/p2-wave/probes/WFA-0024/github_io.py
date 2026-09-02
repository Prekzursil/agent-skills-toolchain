"""Read-only GitHub helpers. Never prints credentials."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from typing import Any

UA = "ast-integrate-WFA-0024 (read-only acquisition)"


def _token() -> str | None:
    for key in ("GITHUB_TOKEN", "GH_TOKEN"):
        val = os.environ.get(key)
        if val:
            return val
    return None


def http_get(url: str, accept: str = "application/vnd.github+json", timeout: int = 45) -> dict:
    headers = {"User-Agent": UA, "Accept": accept}
    token = _token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            return {
                "ok": True,
                "status": int(resp.status),
                "url": url,
                "final_url": str(resp.geturl()),
                "body": body,
                "content_type": resp.headers.get("Content-Type"),
            }
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp else b""
        return {
            "ok": False,
            "status": int(exc.code),
            "url": url,
            "error": f"HTTPError:{exc.code}",
            "body": body,
        }
    except urllib.error.URLError as exc:
        return {"ok": False, "status": 0, "url": url, "error": f"URLError:{exc.reason}", "body": b""}


def gh_api(path: str, timeout: int = 45) -> dict:
    gh = shutil.which("gh")
    if not gh:
        return {"ok": False, "status": 0, "error": "gh-not-on-path", "body": b""}
    try:
        p = subprocess.run(
            [gh, "api", "-H", "Accept: application/vnd.github+json", path],
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "status": 0, "error": type(exc).__name__, "body": b""}
    body = p.stdout or b""
    if p.returncode != 0:
        return {
            "ok": False,
            "status": p.returncode,
            "error": (p.stderr or b"")[:400].decode("utf-8", "replace"),
            "body": body,
        }
    return {"ok": True, "status": 200, "body": body, "path": path}


http_get = http_get
gh_api = gh_api


def json_body(result: dict) -> Any:
    raw = result.get("body") or b""
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


json_body = json_body
