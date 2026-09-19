#!/usr/bin/env python3
"""Official identity REFRESH (tokens expire ~1h). Requires the HackBrowser SSO session
(chat.z.ai logged in) + the zcode:// capture handler (re-register if needed, see receipts).
Flow: navigate authorize URL -> checkbox+Continue -> handler writes code to
%TEMP%/zcode_protocol_capture.log -> exchange -> rewrite ~/.zcode/official-identity.txt."""

import json
import urllib.request
from pathlib import Path

CAP = Path.home() / "AppData/Local/Temp/zcode_protocol_capture.log"
STATE = json.loads(
    (Path.home() / "AppData/Local/Temp/zai_oauth_state.json").read_text()
)
URL = (
    "https://chat.z.ai/api/oauth/authorize?response_type=code&client_id=client_P8X5CMWmlaRO9gyO-KSqtg"
    "&redirect_uri=zcode%3A%2F%2Fzai-auth%2Fcallback&state=" + STATE["state"]
)
print("1. Open in logged-in browser:", URL)
print("2. Check the ToS box, click Continue")
print("3. Then run: zai-refresh.py exchange")
if len(__import__("sys").argv) > 1 and __import__("sys").argv[1] == "exchange":
    line = CAP.read_text().strip().splitlines()[-1]
    code = line.split("code=")[1].split("&")[0]
    body = {
        "provider": "zai",
        "code": code,
        "redirect_uri": "zcode://zai-auth/callback",
        "state": STATE["state"],
    }
    r = urllib.request.Request(
        "https://zcode.z.ai/api/v1/oauth/token",
        data=json.dumps(body).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(r, timeout=30) as resp:
        d = json.loads(resp.read().decode())["data"]
    (Path.home() / ".zcode" / "official-identity.txt").write_text(
        f"Authorization: Bearer {d['token']}\nX-Bigmodel-Authorization: {d['zai']['access_token']}",
        encoding="utf-8",
    )
    print("identity refreshed: ~/.zcode/official-identity.txt")
