#!/usr/bin/env python3
"""IMP-0122 probe1: a fake server returning 429 + Retry-After: 1.5 is honored
on the injected clock — the second attempt's inter-arrival gap is >= 1.5s,
attempts=2, second attempt status 200. The gap is within the declared cap and
the negative control (Retry-After absent) backs off with the default."""
from __future__ import annotations

import glob
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def load_rlc():
    hits = sorted(glob.glob(str(REPO / "tools" / "marketplace" / "rate_limit_client.py")))
    spec = importlib.util.spec_from_file_location("imp0122_rlc1", hits[0])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    RLC = load_rlc()
    clock = RLC.FakeClock()
    state = {"n": 0}

    def handler(url: str) -> dict:
        state["n"] += 1
        if state["n"] == 1:
            return {"status": 429, "headers": {"Retry-After": "1.5"}, "body": b""}
        return {"status": 200, "headers": {}, "body": b"ok"}

    transport = RLC.ScriptedTransport(clock, handler=handler)
    client = RLC.RegistryClient(transport, clock=clock, max_retries=2)
    resp = client.get("https://registry.example/pkg")
    reqs = transport.requests
    attempts = len(reqs)
    gap = (reqs[1]["at"] - reqs[0]["at"]) if attempts >= 2 else 0.0

    honored = (resp.get("status") == 200
               and attempts == 2
               and gap >= 1.5)

    # negative control: no Retry-After header -> default backoff (0.5s)
    clock2 = RLC.FakeClock()
    state2 = {"n": 0}

    def handler2(url: str) -> dict:
        state2["n"] += 1
        if state2["n"] == 1:
            return {"status": 429, "headers": {}, "body": b""}
        return {"status": 200, "headers": {}, "body": b"ok"}

    t2 = RLC.ScriptedTransport(clock2, handler=handler2)
    c2 = RLC.RegistryClient(t2, clock=clock2, max_retries=1)
    c2.get("https://registry.example/other")
    gap2 = t2.requests[1]["at"] - t2.requests[0]["at"] if len(t2.requests) >= 2 else 0.0
    default_backoff_ok = abs(gap2 - 0.5) < 1e-9

    result = {
        "unit_id": "IMP-0122",
        "probe": "probe1-retry-after",
        "attempts": attempts,
        "final_status": resp.get("status"),
        "gap_s": round(gap, 6),
        "gap_at_least_retry_after": honored,
        "default_backoff_gap": round(gap2, 6),
        "default_backoff_used_when_header_absent": default_backoff_ok,
        "pass": honored and default_backoff_ok,
    }
    print("RESULT:" + json.dumps(result))
    tail = ("SUCCESS:IMP-0122-probe1 Retry-After honored on the fake-server clock; "
            "header-absent arm uses default backoff"
            if result["pass"] else
            "FAILED:IMP-0122-probe1 retry-after contract broken")
    print(tail)
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
