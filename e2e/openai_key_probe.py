#!/usr/bin/env python3
"""Probe the owner's OPENAI_API_KEY: identity, tier, model catalogue, endpoint reach.

NEVER prints the key. Emits prefix + length + a truncated SHA-256 so the owner can
correlate it with their dashboard without the literal ever entering a transcript,
a log, or an agent context.

stdlib only (urllib) - `requests` is not guaranteed on this box and a probe that
needs an install is a probe that does not run.
"""

from __future__ import annotations

import hashlib
import json
import os
import ssl
import urllib.error
import urllib.request

BASE = "https://api.openai.com/v1"
CTX = ssl.create_default_context()


def key() -> str | None:
    k = os.environ.get("OPENAI_API_KEY", "").strip()
    return k or None


def call(path: str, k: str, payload: dict | None = None, timeout: int = 45):
    """-> (status, headers, body). Never raises on HTTP error; a 401/403/404 IS data."""
    url = f"{BASE}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    req.add_header("Authorization", f"Bearer {k}")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            return r.status, dict(r.headers), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode("utf-8", "replace")
    except Exception as e:  # network/DNS/TLS
        return -1, {}, f"{type(e).__name__}: {e}"


def redact_identity(k: str) -> str:
    h = hashlib.sha256(k.encode()).hexdigest()[:12]
    # prefix only up to the first structural dash group - never the entropy body
    parts = k.split("-")
    pfx = "-".join(parts[:2]) if len(parts) > 2 else parts[0]
    return f"prefix={pfx}-...  len={len(k)}  sha256[:12]={h}"


def classify(k: str) -> str:
    table = [
        ("sk-admin-", "ADMIN key - org-wide management (members, projects, usage, keys)"),
        ("sk-svcacct-", "SERVICE ACCOUNT key - project-scoped, not tied to a human user"),
        ("sk-proj-", "PROJECT key - scoped to one project inside the org"),
        ("sk-", "LEGACY user key - org-wide inference, no project scoping"),
    ]
    for pfx, desc in table:
        if k.startswith(pfx):
            return f"{pfx}* -> {desc}"
    return "UNRECOGNISED prefix - not an OpenAI-shaped key"


def main() -> int:
    k = key()
    print("=" * 78)
    print("OPENAI_API_KEY probe")
    print("=" * 78)
    if not k:
        print("ABSENT from this process env.")
        print("  NOTE: `setx` does NOT populate an already-running shell; a Windows")
        print("  env var set after this session started is invisible here.")
        print("FAILED:key-probe no OPENAI_API_KEY in env")
        return 1
    print(f"  {redact_identity(k)}")
    print(f"  class: {classify(k)}")
    print()

    # ---- 1. does it authenticate at all, and what is the catalogue? --------------
    st, hdr, body = call("/models", k)
    print(f"[1] GET /models -> HTTP {st}")
    if st != 200:
        print(f"    body: {body[:400]}")
        print("FAILED:key-probe key did not authenticate")
        return 1
    try:
        models = sorted(m["id"] for m in json.loads(body).get("data", []))
    except Exception as e:
        print(f"    unparseable: {e}")
        return 1
    print(f"    {len(models)} models visible")
    fam: dict[str, list[str]] = {}
    for m in models:
        head = m.split("-")[0]
        fam.setdefault(head, []).append(m)
    for head in sorted(fam, key=lambda h: -len(fam[h])):
        print(f"      {head:<16} {len(fam[head]):>3}  {', '.join(sorted(fam[head])[:6])}"
              + (" ..." if len(fam[head]) > 6 else ""))
    print()

    # ---- 2. rate-limit headers reveal the spend tier ----------------------------
    #  A 1-token completion is the cheapest way to make the server emit x-ratelimit-*.
    cheap = next((m for m in ("gpt-4o-mini", "gpt-4.1-mini", "gpt-4o") if m in models),
                 models[0] if models else None)
    print(f"[2] rate-limit headers via POST /chat/completions  (model={cheap})")
    if cheap:
        st2, hdr2, body2 = call("/chat/completions", k, {
            "model": cheap,
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 1,
        })
        print(f"    HTTP {st2}")
        rl = {kk: vv for kk, vv in hdr2.items() if kk.lower().startswith("x-ratelimit")}
        if rl:
            for kk in sorted(rl):
                print(f"      {kk}: {rl[kk]}")
        else:
            print(f"      (no x-ratelimit headers)  body: {body2[:300]}")
    print()

    # ---- 3. endpoint reach: what SURFACES does this key unlock? -----------------
    #  404/400 on a GET of a POST-only route still proves the route is REACHABLE;
    #  401/403 is the real "no access" signal. Distinguishing them is the point.
    print("[3] endpoint reach (401/403 = denied; 200/400/404/405 = reachable)")
    surfaces = [
        ("/models", "inference catalogue"),
        ("/embeddings", "embeddings"),
        ("/images/generations", "image gen (gpt-image / DALL-E)"),
        ("/audio/speech", "TTS"),
        ("/audio/transcriptions", "STT (whisper / gpt-4o-transcribe)"),
        ("/moderations", "moderation"),
        ("/batches", "Batch API (50% discount, 24h window)"),
        ("/files", "Files"),
        ("/vector_stores", "Vector stores (managed RAG)"),
        ("/fine_tuning/jobs", "Fine-tuning"),
        ("/responses", "Responses API (agents, built-in tools)"),
        ("/realtime/sessions", "Realtime (speech-to-speech, WebRTC)"),
        ("/organization/projects", "Org admin: projects  [admin key only]"),
        ("/organization/costs", "Org admin: cost reporting  [admin key only]"),
    ]
    for path, label in surfaces:
        s, _, b = call(path, k, timeout=25)
        verdict = "DENIED " if s in (401, 403) else ("ERR    " if s < 0 else "reach  ")
        extra = ""
        if s in (401, 403):
            try:
                extra = "  " + (json.loads(b).get("error", {}).get("code") or "")[:40]
            except Exception:
                pass
        print(f"    {verdict} {s:>4}  {label}{extra}")
    print()
    print("SUCCESS:key-probe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
