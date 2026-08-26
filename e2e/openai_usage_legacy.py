#!/usr/bin/env python3
"""The admin Usage/Costs API is 403 (`api.usage.read`, admin-key-only) -- but the
LEGACY `/v1/usage?date=` returned 200. Find out whether that 200 carries real data or
is an empty shell, and if real, build the 3-month / per-model / daily picture from it.

A 200 is not a result. An endpoint that returns `{"data": []}` for every date looks
identical to one that works but has no traffic, and both look like success. So probe a
KNOWN-BUSY day as a control before concluding "no usage": if every day is empty AND the
key demonstrably made calls today (this session's own probes billed tokens), then the
endpoint is not reporting for this key class and the emptiness means nothing.
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
KEY = os.environ.get("OPENAI_API_KEY", "").strip()


def get(path: str, params: dict | None = None, timeout: int = 45):
    url = f"{BASE}{path}"
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {KEY}")
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return -1, f"{type(e).__name__}: {e}"


def main() -> int:
    if not KEY:
        print("FAILED:legacy no key")
        return 1
    today = dt.datetime.now(dt.timezone.utc).date()

    # ---- 1. what does the 200 actually contain? ---------------------------------
    print(f"[1] raw shape of GET /v1/usage?date={today}")
    st, body = get("/usage", {"date": today.isoformat()})
    print(f"    HTTP {st}   {len(body)} bytes")
    print(f"    {body[:700]}")
    print()

    try:
        doc = json.loads(body)
    except Exception as e:
        print(f"    unparseable ({e}) - stopping")
        return 1
    print(f"    top-level keys: {sorted(doc.keys())}")
    for k, v in doc.items():
        n = len(v) if isinstance(v, (list, dict)) else v
        print(f"      {k}: {type(v).__name__}  {n}")
    print()

    # ---- 2. CONTROL: today MUST be non-empty - this session billed tokens --------
    #  Round-2/3 probes made real chat/completions + responses calls today. If today
    #  reads empty, the endpoint is not reporting for a project key and every other
    #  empty day is meaningless rather than "no spend".
    data = doc.get("data") or []
    print("[2] control - this session billed tokens TODAY via chat/completions")
    print(f"    today's line items: {len(data)}")
    if not data:
        print("    CONTROL FAILED -> the endpoint reports nothing even for a day with")
        print("    known traffic. Emptiness here is a DETECTOR limitation, not evidence")
        print("    of zero usage. Do not read any other date as authoritative.")
    else:
        print(f"    CONTROL OK -> endpoint reports real traffic; sample: {json.dumps(data[0])[:300]}")
    print()

    # ---- 3. only meaningful if the control passed -------------------------------
    if data:
        print("[3] sampling back over 90 days (weekly stride)")
        per_model: dict[str, list[int]] = {}
        days_with = 0
        for back in range(0, 91, 7):
            d = today - dt.timedelta(days=back)
            s, b = get("/usage", {"date": d.isoformat()})
            if s != 200:
                continue
            try:
                items = json.loads(b).get("data") or []
            except Exception:
                continue
            if items:
                days_with += 1
            for it in items:
                m = it.get("snapshot_id") or it.get("model") or "?"
                tot = (it.get("n_context_tokens_total", 0)
                       + it.get("n_generated_tokens_total", 0))
                per_model.setdefault(m, []).append(tot)
        print(f"    sampled days with data: {days_with}/14")
        for m, vals in sorted(per_model.items(), key=lambda kv: -sum(kv[1])):
            print(f"      {m:<34} {sum(vals):>14,} tokens")
    else:
        print("[3] SKIPPED - control failed, sampling would produce a false 'zero usage'")
    print()
    print("SUCCESS:legacy-usage")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
