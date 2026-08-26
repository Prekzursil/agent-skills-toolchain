#!/usr/bin/env python3
"""Round 2: settle the ambiguous readings from openai_key_probe.py, and read the
Codex auth.json side for a like-for-like comparison. Never prints a secret.

Three things round 1 could NOT honestly conclude:

  1. "/responses is DENIED".  That verdict came from a GET on a route that is not a
     listing endpoint (the real shape is GET /v1/responses/{id}).  A 401 there is
     ambiguous.  The mechanically different probe is an actual POST with a minimal
     body - if it returns 200, the GET reading was an artifact and the API works.
  2. "Tier 5".  Inferred from ONE model's headers.  gpt-4o-mini limits are the most
     generous in the catalogue; confirm against a FLAGSHIP model before claiming a
     tier, since tiers are per-model tables.
  3. The gpt family printed 6 of 98.  Enumerate the ones that actually matter.
"""

from __future__ import annotations

import base64
import json
import os
import ssl
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://api.openai.com/v1"
CTX = ssl.create_default_context()
K = os.environ.get("OPENAI_API_KEY", "").strip()


def call(path: str, payload=None, timeout=60, method=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        f"{BASE}{path}", data=data, method=method or ("POST" if data else "GET")
    )
    req.add_header("Authorization", f"Bearer {K}")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            return r.status, dict(r.headers), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode("utf-8", "replace")
    except Exception as e:
        return -1, {}, f"{type(e).__name__}: {e}"


def err_code(body: str) -> str:
    try:
        e = json.loads(body).get("error", {})
        return f"{e.get('code') or e.get('type') or ''}: {(e.get('message') or '')[:150]}"
    except Exception:
        return body[:150]


def main() -> int:
    if not K:
        print("FAILED:probe2 no OPENAI_API_KEY")
        return 1

    # ---- 1. Responses API: the REAL test is a POST -------------------------------
    print("[1] Responses API - POST (the GET in round 1 was not a listing route)")
    st, _, body = call("/responses", {
        "model": "gpt-4o-mini", "input": "say ok", "max_output_tokens": 16,
    })
    print(f"    POST /responses -> HTTP {st}")
    if st == 200:
        try:
            d = json.loads(body)
            print(f"    VERDICT: WORKS. status={d.get('status')} model={d.get('model')}")
        except Exception:
            print("    VERDICT: WORKS (200, unparsed)")
    else:
        print(f"    VERDICT: blocked -> {err_code(body)}")
    print()

    # built-in server-side tools are the reason Responses matters at all
    print("    built-in tool reach (Responses-only capabilities):")
    for tool, label in [
        ({"type": "web_search"}, "web_search"),
        ({"type": "code_interpreter", "container": {"type": "auto"}}, "code_interpreter"),
    ]:
        s, _, b = call("/responses", {
            "model": "gpt-4o-mini", "input": "ping",
            "tools": [tool], "max_output_tokens": 16,
        }, timeout=90)
        mark = "OK     " if s == 200 else "BLOCKED"
        print(f"      {mark} {s:>4}  {label}"
              + ("" if s == 200 else f"  {err_code(b)[:90]}"))
    print()

    # ---- 2. tier: confirm against a FLAGSHIP, not just the cheapest model ---------
    print("[2] tier confirmation - rate limits per model (tiers are per-model tables)")
    for m in ("gpt-4o", "gpt-5", "gpt-5.1", "o3", "gpt-4o-mini"):
        s, h, b = call("/chat/completions", {
            "model": m, "messages": [{"role": "user", "content": "hi"}],
            "max_completion_tokens": 16,
        }, timeout=60)
        rpm = h.get("x-ratelimit-limit-requests", "-")
        tpm = h.get("x-ratelimit-limit-tokens", "-")
        note = "" if s == 200 else f"  ({err_code(b)[:70]})"
        print(f"    {m:<12} HTTP {s:<4} RPM={rpm:<8} TPM={tpm:<12}{note}")
    print()

    # ---- 3. the models that actually matter --------------------------------------
    print("[3] catalogue highlights")
    s, _, b = call("/models")
    ids = sorted(m["id"] for m in json.loads(b).get("data", [])) if s == 200 else []
    groups = {
        "gpt-5 family": [m for m in ids if m.startswith("gpt-5")],
        "reasoning (o-series)": [m for m in ids if m[:2] in ("o1", "o3", "o4")],
        "deep research": [m for m in ids if "deep-research" in m],
        "realtime": [m for m in ids if "realtime" in m],
        "audio / speech": [m for m in ids if "audio" in m or "tts" in m
                           or "whisper" in m or "transcribe" in m],
        "image": [m for m in ids if "image" in m or "dall-e" in m],
        "video (Sora)": [m for m in ids if m.startswith("sora")],
        "computer use": [m for m in ids if "computer" in m],
        "embeddings": [m for m in ids if "embedding" in m],
    }
    for label, ms in groups.items():
        print(f"    {label:<22} {len(ms):>3}  {', '.join(ms[:9])}"
              + (" ..." if len(ms) > 9 else ""))
    print()

    # ---- 4. the Codex side, for a like-for-like comparison -----------------------
    print("[4] Codex auth.json - structure + non-secret JWT claims (NO token values)")
    p = Path.home() / ".codex" / "auth.json"
    print(f"    path: {p}  exists={p.exists()}")
    if p.exists():
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"    unparseable: {e}")
            return 0
        print(f"    top-level keys: {sorted(d.keys())}")
        print(f"    OPENAI_API_KEY field present: "
              f"{bool(d.get('OPENAI_API_KEY'))}  <- Codex can ALSO hold an API key")
        tok = (d.get("tokens") or {})
        print(f"    tokens.* keys: {sorted(tok.keys())}")
        idt = tok.get("id_token")
        if isinstance(idt, str) and idt.count(".") == 2:
            try:
                seg = idt.split(".")[1]
                seg += "=" * (-len(seg) % 4)
                claims = json.loads(base64.urlsafe_b64decode(seg))
                safe = {}
                for kk, vv in claims.items():
                    lk = kk.lower()
                    if any(x in lk for x in ("token", "secret", "key", "email",
                                             "sub", "sid", "nonce")):
                        continue
                    safe[kk] = vv
                auth = claims.get("https://api.openai.com/auth", {})
                print(f"    plan / auth claims: "
                      f"{json.dumps(auth, default=str)[:260]}")
                for kk in ("exp", "iat", "iss", "aud"):
                    if kk in safe:
                        print(f"      {kk}: {safe[kk]}")
            except Exception as e:
                print(f"    id_token undecodable: {type(e).__name__}")
    print()
    print("SUCCESS:probe2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
