#!/usr/bin/env python3
"""Wait for CS :4096, verify session exists, POST the resume prompt. No secrets."""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SID = "ses_f9c9ab90cffetNo68ohzF6RZAq"
BASE = "http://127.0.0.1:4096"
DIR = r"C:\Users\Prekzursil\Cowork\private\cyberstrike-engagements\cursor-auth-recovery-2026-09-02"
PROMPT = Path(r"D:\opt\cyberstrike-mcp\resume-prompt.txt").read_text(encoding="utf-8").strip()


def req(method: str, path: str, body: dict | None = None, timeout: float = 15.0):
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
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        raw = resp.read()
        return resp.status, raw.decode("utf-8", "replace")


def wait_up() -> None:
    for i in range(40):
        try:
            code, _ = req("GET", "/global/health")
            if code == 200:
                print("health", code, flush=True)
                return
        except Exception as e:
            print("wait", i, type(e).__name__, flush=True)
        time.sleep(0.5)
    raise SystemExit("CS :4096 never became healthy")


def main() -> int:
    wait_up()
    code, body = req("GET", f"/session/{SID}")
    print("get-session", code, body[:180].replace("\n", " "), flush=True)
    if code != 200 or "not found" in body.lower():
        print("FAILED:session-missing", flush=True)
        return 2
    payloads = [
        {"parts": [{"type": "text", "text": PROMPT}]},
        {"content": PROMPT},
        {"text": PROMPT},
        {"message": PROMPT},
    ]
    last = None
    for p in payloads:
        try:
            code, body = req("POST", f"/session/{SID}/message", p)
            print("post", code, body[:160].replace("\n", " "), flush=True)
            if 200 <= code < 300:
                print("SUCCESS:prompt-injected", flush=True)
                return 0
            last = (code, body[:200])
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", "replace")[:200]
            print("post-http", e.code, err.replace("\n", " "), flush=True)
            last = (e.code, err)
            if e.code in (404, 405):
                continue
        except Exception as e:
            print("post-err", type(e).__name__, e, flush=True)
            last = e
    print("FAILED:prompt-inject", last, flush=True)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
