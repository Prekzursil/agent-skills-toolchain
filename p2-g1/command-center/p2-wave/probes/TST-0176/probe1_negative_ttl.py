#!/usr/bin/env python3
"""TST-0176 probe1 -- transient failures negatively cached SHORT, retried after TTL.

Two independent signals: (a) the second attempt's observed network call (fetch
counter unchanged while the negative entry is live, incremented after the SHORT
ttl expires), and (b) the cache entry's recorded type + ttl.
Exit 0 on pass, 1 on any failure.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import negative_cache as NC  # noqa: E402

UNIT = "TST-0176"


def main() -> int:
    c = NC.NegativeCache()
    calls = {"n": 0}

    def flaky_fetch():
        calls["n"] += 1
        raise NC.TransientFetchError("connection reset by peer (fixture)")

    err = None
    try:
        c.get("pkg/x", flaky_fetch)
    except NC.TransientFetchError as e:
        err = str(e)

    e1 = c.entry("pkg/x")
    has_negative_entry = e1 is not None and e1.kind == "negative-transient"

    before = calls["n"]
    try:
        c.get("pkg/x", flaky_fetch)
    except NC.TransientFetchError:
        pass
    network_quiet_during_ttl = calls["n"] == before

    time.sleep(c.transient_negative_ttl + 0.05)
    before2 = calls["n"]
    try:
        c.get("pkg/x", flaky_fetch)
    except NC.TransientFetchError:
        pass
    retry_hit_network = calls["n"] == before2 + 1

    payload = {
        "probe": "probe1-negative-ttl",
        "unit_id": UNIT,
        "pass": has_negative_entry and network_quiet_during_ttl and retry_hit_network,
        "first_failure": err,
        "entry": {
            "kind": e1.kind if e1 else None,
            "ttl": e1.ttl if e1 else None,
            "short_ttl_s": c.transient_negative_ttl,
        },
        "second_attempt": {
            "network_calls_during_ttl": calls["n"] - before,
            "network_quiet_during_ttl": network_quiet_during_ttl,
        },
        "after_ttl_retry": {
            "network_calls_observed": calls["n"] - before2,
            "retry_hit_network": retry_hit_network,
        },
        "fetch_calls_total": calls["n"],
        "transient_distinguished_from_absence": bool(e1 and e1.kind == "negative-transient"),
    }
    print(json.dumps(payload, sort_keys=True))
    if payload["pass"]:
        kind = e1.kind if e1 else "?"
        ttl = e1.ttl if e1 else -1
        print(f"SUCCESS:{UNIT}-probe1 kind={kind} ttl={ttl}s quiet-during-ttl={network_quiet_during_ttl} retry-hits-network={retry_hit_network}")
        return 0
    print(f"FAILED:{UNIT}-probe1 entry={has_negative_entry} quiet={network_quiet_during_ttl} retry={retry_hit_network}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
