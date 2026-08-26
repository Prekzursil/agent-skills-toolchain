#!/usr/bin/env python3
"""Round 3: a LISTED model is not a CALLABLE model.

/v1/models returns the org catalogue; Sora, gpt-image and computer-use are commonly
gated behind org verification, and the listing does not say so. The cheap way to tell
access from entitlement WITHOUT paying for a render: send a request that is guaranteed
to fail VALIDATION, then read which error comes back.

  model_not_found / 403 / must be verified  -> NO entitlement
  invalid_request_error on the bad param    -> entitlement OK, request merely malformed

That inversion (a 400 is the GOOD outcome) is the whole trick - it proves the request
reached model dispatch instead of being rejected at the authorization boundary.
"""

from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request

BASE = "https://api.openai.com/v1"
CTX = ssl.create_default_context()
K = os.environ.get("OPENAI_API_KEY", "").strip()


def post(path: str, payload: dict, timeout: int = 45):
    req = urllib.request.Request(
        f"{BASE}{path}", data=json.dumps(payload).encode(), method="POST"
    )
    req.add_header("Authorization", f"Bearer {K}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return -1, f"{type(e).__name__}: {e}"


def verdict(status: int, body: str) -> tuple[str, str]:
    low = body.lower()
    for needle in ("model_not_found", "does not exist", "do not have access",
                   "must be verified", "unsupported_country", "insufficient_quota"):
        if needle in low:
            return "NO ACCESS", needle
    try:
        e = json.loads(body).get("error", {})
        msg = (e.get("message") or "")[:110]
        code = e.get("code") or e.get("type") or ""
    except Exception:
        msg, code = body[:110], ""
    if status in (400, 422):
        return "ENTITLED", f"validation-only ({code}) {msg}"
    if status == 200:
        return "ENTITLED", "200"
    if status in (401, 403):
        return "NO ACCESS", f"{code} {msg}"
    return f"HTTP {status}", f"{code} {msg}"


def main() -> int:
    if not K:
        print("FAILED:probe3 no OPENAI_API_KEY")
        return 1

    # Each entry deliberately carries ONE invalid field so nothing bills a render.
    cases = [
        ("sora-2",                "/videos",            {"model": "sora-2", "prompt": "x", "seconds": "-1"}),
        ("sora-2-pro",            "/videos",            {"model": "sora-2-pro", "prompt": "x", "seconds": "-1"}),
        ("gpt-image-2",           "/images/generations", {"model": "gpt-image-2", "prompt": "x", "size": "1x1"}),
        ("gpt-image-1.5",         "/images/generations", {"model": "gpt-image-1.5", "prompt": "x", "size": "1x1"}),
        ("computer-use-preview",  "/responses",         {"model": "computer-use-preview", "input": "x", "max_output_tokens": -1}),
        ("o3-deep-research",      "/responses",         {"model": "o3-deep-research", "input": "x", "max_output_tokens": -1}),
        ("gpt-5-pro",             "/responses",         {"model": "gpt-5-pro", "input": "x", "max_output_tokens": -1}),
        ("gpt-5-codex",           "/responses",         {"model": "gpt-5-codex", "input": "x", "max_output_tokens": -1}),
        ("gpt-realtime-2.1",      "/realtime/sessions", {"model": "gpt-realtime-2.1", "voice": "__bad__"}),
        ("gpt-4o-transcribe-diarize", "/audio/transcriptions", {"model": "gpt-4o-transcribe-diarize"}),
    ]

    print("entitlement probe (400 = GOOD: reached dispatch; 403/model_not_found = gated)")
    print(f"{'model':<28} {'verdict':<11} detail")
    gated = 0
    for name, path, payload in cases:
        st, body = post(path, payload)
        v, detail = verdict(st, body)
        if v == "NO ACCESS":
            gated += 1
        print(f"{name:<28} {v:<11} {detail[:96]}")

    print()
    print(f"gated: {gated} / {len(cases)}")
    print("SUCCESS:probe3")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
