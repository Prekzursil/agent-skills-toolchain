#!/usr/bin/env python3
"""Can THIS key read usage + cost history? Test the real endpoints, not a bare GET.

Round 1 saw 403 on `GET /organization/costs`, but that call carried no parameters and
the Costs API requires `start_time`. A 403 on a malformed request is weak evidence for
"no access" -- the request may have died at validation, not authorization. So issue
each documented endpoint CORRECTLY, with a real time window, and read the error code.

Distinguishes the two failure modes that look identical from the outside:
  * 401/403 + invalid_api_key / insufficient_permissions -> the KEY CLASS is wrong
    (Usage + Costs are Admin-key-only; a project key can never read them)
  * 400 -> reached the endpoint, parameters wrong (would mean access DOES exist)
"""

from __future__ import annotations

import datetime as dt
import json
import os
import ssl
import urllib.error
import urllib.request

BASE = "https://api.openai.com/v1"
CTX = ssl.create_default_context()


def get(path: str, key: str, params: dict | None = None, timeout: int = 45):
    url = f"{BASE}{path}"
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {key}")
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return -1, f"{type(e).__name__}: {e}"


def detail(body: str) -> str:
    try:
        e = json.loads(body).get("error", {})
        return f"{e.get('code') or e.get('type') or '?'} | {(e.get('message') or '')[:120]}"
    except Exception:
        return body[:120]


def main() -> int:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        print("FAILED:usage no OPENAI_API_KEY")
        return 1

    now = dt.datetime.now(dt.timezone.utc)
    start_90 = int((now - dt.timedelta(days=90)).timestamp())
    start_month = int(now.replace(day=1, hour=0, minute=0, second=0,
                                  microsecond=0).timestamp())

    print(f"key class: {key.split('-')[1] if key.count('-') > 1 else '?'}"
          f"  (admin endpoints require an sk-admin-* key)")
    print(f"window: last 90d from {dt.datetime.fromtimestamp(start_90, dt.timezone.utc):%Y-%m-%d}"
          f"   month-to-date from {dt.datetime.fromtimestamp(start_month, dt.timezone.utc):%Y-%m-%d}")
    print()

    # ---- 1. other OpenAI-shaped credentials in THIS process env ------------------
    print("[1] other OpenAI credentials in env (an admin key would change the answer)")
    found = False
    for name, val in sorted(os.environ.items()):
        if "OPENAI" not in name.upper() and "OAI" not in name.upper():
            continue
        v = (val or "").strip()
        shape = ("sk-admin-*" if v.startswith("sk-admin-") else
                 "sk-proj-*" if v.startswith("sk-proj-") else
                 "sk-svcacct-*" if v.startswith("sk-svcacct-") else
                 "sk-* legacy" if v.startswith("sk-") else
                 f"(non-key, len={len(v)})")
        print(f"    {name:<28} {shape}")
        found = True
    if not found:
        print("    (none)")
    print()

    # ---- 2. the documented Usage + Costs endpoints, called correctly -------------
    print("[2] Usage + Costs endpoints, with required params")
    endpoints = [
        ("/organization/costs", {"start_time": start_90, "limit": 7,
                                 "group_by": "line_item"}, "COST by line item, 90d"),
        ("/organization/costs", {"start_time": start_month, "limit": 7},
         "COST month-to-date"),
        ("/organization/usage/completions", {"start_time": start_90,
                                             "bucket_width": "1d", "limit": 7,
                                             "group_by": "model"},
         "USAGE completions by MODEL, 90d"),
        ("/organization/usage/embeddings", {"start_time": start_90,
                                            "bucket_width": "1d", "limit": 7},
         "USAGE embeddings"),
        ("/organization/usage/images", {"start_time": start_90,
                                        "bucket_width": "1d", "limit": 7},
         "USAGE images"),
        ("/organization/usage/audio_speeches", {"start_time": start_90,
                                                "bucket_width": "1d", "limit": 7},
         "USAGE TTS"),
    ]
    reachable = 0
    for path, params, label in endpoints:
        st, body = get(path, key, params)
        if st == 200:
            reachable += 1
            print(f"    OK    200  {label}")
            print(f"          {body[:400]}")
        elif st == 400:
            reachable += 1
            print(f"    REACH 400  {label}  (access OK, params wrong) {detail(body)}")
        else:
            print(f"    DENY  {st:<4} {label}  {detail(body)}")
    print()

    # ---- 3. is there ANY per-key self-usage surface? ------------------------------
    print("[3] legacy / self-service usage surfaces")
    for path, params, label in [
        ("/usage", {"date": f"{now:%Y-%m-%d}"}, "legacy /v1/usage (dashboard-era)"),
        ("/dashboard/billing/usage", {}, "legacy billing endpoint"),
    ]:
        st, body = get(path, key, params)
        print(f"    {st:<5} {label}  {detail(body)}")
    print()

    print(f"admin-surface endpoints reachable: {reachable}/{len(endpoints)}")
    print("SUCCESS:usage-probe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
