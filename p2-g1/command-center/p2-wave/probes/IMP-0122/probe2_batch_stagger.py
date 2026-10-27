#!/usr/bin/env python3
"""IMP-0122 probe2: server-side first-arrival histogram for a 50-item batch.
Staggered arm: span > 2s, burst_fraction < 0.2, occupied_bins >= 20.
Unstaggered control: burst_fraction == 1.0, span == 0, max_count == 50.
Client-side intent is not the signal; arrivals are recorded by ScriptedTransport."""
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
    spec = importlib.util.spec_from_file_location("imp0122_rlc2", hits[0])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    RLC = load_rlc()

    def ok(_url: str) -> dict:
        return {"status": 200, "headers": {}, "body": b"ok"}

    # staggered arm
    clock = RLC.FakeClock()
    t = RLC.ScriptedTransport(clock, handler=ok)
    c = RLC.RegistryClient(t, clock=clock, batch_stagger_interval=0.05)
    urls = [f"https://registry.example/batch/{i}" for i in range(50)]
    c.batch_get(urls, stagger=True)
    stag = RLC.burst_histogram(t.first_arrivals())

    # unstaggered control (same server, fresh clock)
    clock2 = RLC.FakeClock()
    t2 = RLC.ScriptedTransport(clock2, handler=ok)
    c2 = RLC.RegistryClient(t2, clock=clock2, batch_stagger_interval=0.05)
    c2.batch_get(urls, stagger=False)
    burst = RLC.burst_histogram(t2.first_arrivals())

    result = {
        "unit_id": "IMP-0122",
        "probe": "probe2-batch-stagger",
        "staggered": stag,
        "burst_control": burst,
        "staggered_spread": stag["span"] >= 2.0 and stag["burst_fraction"] < 0.2
                            and stag["occupied_bins"] >= 20,
        "control_is_burst": burst["burst_fraction"] == 1.0 and burst["span"] == 0.0
                            and burst["max_count"] == 50,
        "pass": (stag["span"] >= 2.0 and stag["burst_fraction"] < 0.2
                 and stag["occupied_bins"] >= 20
                 and burst["burst_fraction"] == 1.0 and burst["span"] == 0.0
                 and burst["max_count"] == 50),
    }
    print("RESULT:" + json.dumps(result))
    tail = ("SUCCESS:IMP-0122-probe2 50-batch arrivals staggered server-side; "
            "unstaggered control is a burst (both-states)"
            if result["pass"] else
            "FAILED:IMP-0122-probe2 stagger/burst contract broken")
    print(tail)
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
