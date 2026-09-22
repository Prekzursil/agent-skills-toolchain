#!/usr/bin/env python3
"""Z.AI coding-plan dual-key failover — RUNNER variant (GitHub Actions).

Reads ZAI_API_KEY_A / ZAI_API_KEY_B (repo secrets), probes both with a
1-token chat completion, and exports the HEALTHY key as ZAI_API_KEY via
$GITHUB_ENV so every later step in the job uses it. Selection between two
existing credentials only — never regeneration or revocation.

Job usage:
  - name: pick a healthy Z.AI plan key
    env:
      ZAI_API_KEY_A: ${{ secrets.ZAI_API_KEY_A }}
      ZAI_API_KEY_B: ${{ secrets.ZAI_API_KEY_B }}
    run: python tools/zai/zai_key_failover_runner.py

Exit 0 = a healthy key was exported (see step summary for which).
Exit 1 = both keys exhausted/unreachable (job should fail loudly).
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request

ENDPOINT = "https://api.z.ai/api/coding/paas/v4/chat/completions"
EXHAUST_MARKERS = ("insufficient", "quota", "exceeded", "balance", "rate limit")


def sha8(v: str) -> str:
    return hashlib.sha256(v.encode()).hexdigest()[:8]


def probe(key: str) -> dict:
    body = json.dumps(
        {
            "model": "glm-4.6",
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 1,
            "stream": False,
        }
    ).encode()
    req = urllib.request.Request(
        ENDPOINT,
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return {"ok": True, "status": r.status, "ms": int((time.time() - t0) * 1000), "exhausted": False, "note": ""}
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")[:300]
        except Exception:
            pass
        return {
            "ok": False,
            "status": e.code,
            "ms": int((time.time() - t0) * 1000),
            "exhausted": e.code == 429 or any(m in detail.lower() for m in EXHAUST_MARKERS),
            "note": detail[:160],
        }
    except Exception as e:
        return {"ok": False, "status": 0, "ms": 0, "exhausted": False, "note": f"{type(e).__name__}"}


def main() -> int:
    cands = {n: os.environ[n] for n in ("ZAI_API_KEY_A", "ZAI_API_KEY_B") if os.environ.get(n)}
    if not cands:
        print("FAILED:zai-runner-failover no ZAI_API_KEY_A/B env (set the repo secrets)")
        return 1
    results = {n: probe(k) for n, k in cands.items()}
    for n, r in results.items():
        print(f"{n} sha8={sha8(cands[n])}: ok={r['ok']} status={r['status']} exhausted={r['exhausted']} {r['note'][:80]}")
    healthy = [n for n, r in results.items() if r["ok"]]
    if not healthy:
        print("FAILED:zai-runner-failover both keys exhausted or unreachable")
        return 1
    # prefer A when both healthy (stable ordering); prefer the healthy one otherwise
    pick = "ZAI_API_KEY_A" if "ZAI_API_KEY_A" in healthy else healthy[0]
    genv = os.environ.get("GITHUB_ENV")
    if genv:
        with open(genv, "a", encoding="utf-8") as f:
            f.write(f"ZAI_API_KEY<<__ZAI_EOF__\n{cands[pick]}\n__ZAI_EOF__\n")
    print(f"SUCCESS:zai-runner-failover exported {pick} (sha8={sha8(cands[pick])}) as ZAI_API_KEY for subsequent steps")
    return 0


if __name__ == "__main__":
    sys.exit(main())
