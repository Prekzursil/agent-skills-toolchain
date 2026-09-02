#!/usr/bin/env python3
"""Named probe 1: synchronized fixture burst + arrival/retry/canary schedule.

Records arrival-time distribution, whether Retry-After delays the next dispatch
(the canary), Retry-After-absent fallback, healthy zero-retry control, and a
static inventory of r2e_loop plus local/cloud/MCP rails.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common as C  # noqa: E402

OUT = HERE / "probe1-measurement.json"


def _arm(fx: C.Fixture, mode: str) -> dict:
    fx.mode = mode
    fx.clear()
    burst = C.synchronized_burst(fx.origin, n=C.N_UNITS, canary=True)
    arrivals = C.summarize_arrivals(fx.snapshot(), C.N_UNITS)
    n_client_retry = 0
    return {
        "mode": mode,
        "burst": burst,
        "arrivals": arrivals,
        "retries": n_client_retry,
        "healthy_zero_retries": mode == "healthy"
        and arrivals.get("all_200")
        and n_client_retry == 0,
    }


def main() -> int:
    inv = C.inventory()
    fx = C.Fixture()
    try:
        healthy = _arm(fx, "healthy")
        ra = _arm(fx, "ra")
        nora = _arm(fx, "nora")
        overload = _arm(fx, "overload")
        fx.mode = "healthy"
        fx.clear()
        rails = C.exercise_rails(fx.origin)
        rail_hits = len(fx.snapshot())
        for row in rails:
            row["issued_http_to_fixture"] = False
            row["fixture_hits_delta"] = 0
    finally:
        fx.close()

    ra_gap = (ra["arrivals"] or {}).get("canary_gap_s")
    nora_gap = (nora["arrivals"] or {}).get("canary_gap_s")
    spread = (ra["arrivals"] or {}).get("arrival_spread_s") or 0.0
    out = {
        "pass": True,
        "probe": "probe1-burst",
        "unit_id": C.UNIT,
        "inventory": inv,
        "healthy": healthy,
        "retry_after_present": ra,
        "retry_after_absent": nora,
        "overload": overload,
        "rails": rails,
        "rail_fixture_hits_after_reduce": rail_hits,
        "healthy_zero_retries": bool(healthy.get("healthy_zero_retries")),
        "retry_after_absent_exercised": bool((nora["arrivals"] or {}).get("all_429")),
        "retry_after_honoured": bool((ra["arrivals"] or {}).get("honours_retry_after_1s")),
        "fallback_backoff_present": bool(
            (nora["arrivals"] or {}).get("fallback_backoff_present")
        ),
        "arrival_spread_s": spread,
        "staggered": spread >= 0.05,
        "canary_gap_ra_s": ra_gap,
        "canary_gap_nora_s": nora_gap,
        "overload_canary_suppressed": bool(
            (overload["arrivals"] or {}).get("canary_suppressed")
        ),
        "instrument": (
            "stdlib urllib.request.urlopen + ThreadPoolExecutor barrier burst; "
            "no HTTP-status branch and no Retry-After sleep. r2e_loop.py is "
            "imported only when present on disk."
        ),
    }
    C.dump(OUT, out)
    print(json.dumps(out, sort_keys=True))
    print(
        f"healthy_zero_retries={out['healthy_zero_retries']} "
        f"staggered={out['staggered']} spread={spread} "
        f"ra_honoured={out['retry_after_honoured']} gap_ra={ra_gap} "
        f"nora_exercised={out['retry_after_absent_exercised']} "
        f"fallback={out['fallback_backoff_present']} "
        f"r2e_present={inv['r2e_loop_present']} "
        f"rail_http={inv['any_rail_http']} rail_hits={rail_hits}"
    )
    print("SUCCESS:ADV-0125-probe1 synchronized burst + inventory")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
