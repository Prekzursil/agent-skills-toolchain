#!/usr/bin/env python3
"""Pair CyberStrike with local Bolt. Token from env/file only; never printed."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:4096"
BOLT = "http://127.0.0.1:3001"
NAME = "bolt-lab"
DIR = r"C:\Users\Prekzursil\Cowork\private\cyberstrike-engagements\cursor-auth-recovery-2026-09-02"
TOKEN_FILE = Path(r"D:\opt\bolt\admin.token")


def req(method: str, path: str, body: dict | None = None, timeout: float = 60.0):
    data = None if body is None else json.dumps(body).encode("utf-8")
    r = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "x-cyberstrike-directory": DIR,
        },
    )
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            return resp.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        return e.code, raw


def redact(s: str) -> str:
    out = s
    for t in tokens:
        if t:
            out = out.replace(t, "<redacted>")
    return out[:400]


def pick_token() -> str:
    disk = TOKEN_FILE.read_text(encoding="ascii").strip() if TOKEN_FILE.exists() else ""
    user = (os.environ.get("BOLT_ADMIN_TOKEN") or "").strip()
    print(f"token-disk-len={len(disk)} token-env-len={len(user)}", flush=True)
    if user and disk and user == disk:
        print("token-source=both-match", flush=True)
        return disk
    if user and disk and (disk.startswith(user) or user.startswith(disk)):
        print("token-source=disk-env-prefix-match", flush=True)
        return disk if len(disk) >= len(user) else user
    if user:
        print("token-source=env", flush=True)
        return user
    if disk:
        print("token-source=disk", flush=True)
        return disk
    raise SystemExit("no token")


tokens: list[str] = []


def main() -> int:
    token = pick_token()
    tokens.append(token)
    code, body = req("GET", "/bolt")
    print("GET /bolt", code, redact(body), flush=True)
    code, body = req(
        "POST",
        "/bolt",
        {"name": NAME, "config": {"url": BOLT, "enabled": True, "timeout": 900000}},
    )
    print("POST /bolt", code, redact(body), flush=True)
    code, body = req(
        "POST",
        f"/bolt/{NAME}/pair",
        {"url": BOLT, "adminToken": token},
        timeout=120.0,
    )
    print("POST /bolt/pair", code, redact(body), flush=True)
    if code >= 400:
        disk = TOKEN_FILE.read_text(encoding="ascii").strip() if TOKEN_FILE.exists() else ""
        if disk and disk != token:
            print("pair-failed-retry-disk", flush=True)
            tokens.append(disk)
            code, body = req(
                "POST",
                f"/bolt/{NAME}/pair",
                {"url": BOLT, "adminToken": disk},
                timeout=120.0,
            )
            print("POST /bolt/pair-retry", code, redact(body), flush=True)
    if code >= 400:
        print("FAILED:bolt-pair", flush=True)
        return 2
    code, body = req("POST", f"/bolt/{NAME}/connect")
    print("POST /bolt/connect", code, redact(body), flush=True)
    code, body = req("GET", "/bolt")
    print("GET /bolt-after", code, redact(body), flush=True)
    code, body = req("GET", "/mcp/bolt-tools")
    print("GET /mcp/bolt-tools", code, redact(body)[:300], flush=True)
    keys = Path(r"C:\Users\Prekzursil\.local\share\cyberstrike\bolt-keys")
    names = [p.name for p in keys.glob("*")] if keys.exists() else []
    print("bolt-key-files", names, flush=True)
    if code < 400 or "connected" in body.lower() or names:
        print("SUCCESS:bolt-pair", flush=True)
        return 0
    print("FAILED:bolt-pair-unconfirmed", flush=True)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
