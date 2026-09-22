#!/usr/bin/env python3
"""zai-oauth-bridge — manual ZCode OAuth flow for Windows.

Why: the official speech channel (zcode.z.ai/api/v1/mcp/server/video_edit) requires a
plan-entitled identity. Plan API key -> 1006; Sep-14 JWT -> 3101. A FRESH OAuth token
carries the plan binding. The CLI blocks browser OAuth on Windows (zcode:// callback is
macOS-registered) — this bridge completes the flow manually:

  1. Generate state + PKCE (S256) and print the authorize URL(s).
  2. Open the URL in the controlled browser (HackBrowser). Operator logs into z.ai there
     (one time) and approves. The browser fails to navigate zcode://zai-auth/callback?code=…
  3. Capture the code from that failed navigation (browser address bar / navigation log).
  4. Exchange: POST https://zcode.z.ai/api/v1/oauth/token
       {"provider":"zai","code":CODE,"redirect_uri":"zcode://zai-auth/callback","state":STATE}
  5. Save tokens; use as Authorization header (via --identity-file for zai-asr.py, or answer
     interaction/requestOfficialMcpAuthHeaders in the app-server driver).

Usage:
  python zai-oauth-bridge.py url            # step 1: print authorize URLs
  python zai-oauth-bridge.py exchange CODE   # step 4-5: exchange + save to %TEMP%/zai_oauth_fresh.json
Constants extracted from zcode.cjs: client_id candidates zcode-agent / zcode-cli / zcode_desktop;
response_type=code; redirect zcode://zai-auth/callback.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import sys
import urllib.request
from pathlib import Path

REDIRECT = "zcode://zai-auth/callback"
STATE = secrets.token_urlsafe(24)
VERIFIER = secrets.token_urlsafe(64)
CHALLENGE = (
    base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest())
    .rstrip(b"=")
    .decode()
)
CLIENTS = ["zcode-agent", "zcode-cli", "zcode_desktop"]
ISSUERS = ["https://zcode.z.ai", "https://zcode.z.ai/api/v1/oauth", "https://z.ai"]


def urls():
    out = []
    for issuer in ISSUERS:
        for cid in CLIENTS:
            u = (
                f"{issuer.rstrip('/')}/authorize?response_type=code&client_id={cid}"
                f"&redirect_uri={urllib.request.quote(REDIRECT, safe='')}"
                f"&code_challenge={CHALLENGE}&code_challenge_method=S256&state={STATE}"
            )
            out.append(u)
    return out


def exchange(code: str) -> dict:
    body = {"provider": "zai", "code": code, "redirect_uri": REDIRECT, "state": STATE}
    r = urllib.request.Request(
        "https://zcode.z.ai/api/v1/oauth/token",
        data=json.dumps(body).encode(),
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            out = {"http": resp.status, "body": resp.read().decode("utf-8", "replace")}
    except urllib.error.HTTPError as e:
        out = {"http": e.code, "body": e.read().decode("utf-8", "replace")[:400]}
    p = Path(os.environ.get("TEMP", "/tmp")) / "zai_oauth_fresh.json"
    p.write_text(
        json.dumps({"state": STATE, "verifier": VERIFIER, "result": out}, indent=2),
        encoding="utf-8",
    )
    out["_saved"] = str(p)
    return out


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "url":
        meta = Path(os.environ.get("TEMP", "/tmp")) / "zai_oauth_state.json"
        meta.write_text(
            json.dumps({"state": STATE, "verifier": VERIFIER}, indent=2),
            encoding="utf-8",
        )
        print(f"# state+verifier saved: {meta}")
        for u in urls():
            print(u)
    elif len(sys.argv) >= 3 and sys.argv[1] == "exchange":
        print(json.dumps(exchange(sys.argv[2]), indent=2)[:800])
    else:
        print(__doc__)
