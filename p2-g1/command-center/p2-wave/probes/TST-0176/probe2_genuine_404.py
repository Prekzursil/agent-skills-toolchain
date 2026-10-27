#!/usr/bin/env python3
"""TST-0176 probe2 -- genuine 404 stays negatively cached for its FULL ttl;
regression seed: an EMPTY cache reporting OK is detected (measured on this estate).

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

    def genuine_404():
        calls["n"] += 1
        raise NC.NotFoundError("404 package missing (fixture)")

    try:
        c.get("pkg/gone", genuine_404)
    except NC.NotFoundError:
        pass
    e = c.entry("pkg/gone")
    kind_genuine = bool(e and e.kind == "negative-genuine")
    ttl_full = bool(e and e.ttl == c.genuine_negative_ttl)

    before = calls["n"]
    time.sleep(2 * c.transient_negative_ttl + 0.05)
    try:
        c.get("pkg/gone", genuine_404)
    except NC.NotFoundError:
        pass
    still_cached = calls["n"] == before  # a transient-ttl expiry would have refetched

    # regression seed: broken semantics report an EMPTY/OK result on failure
    bcalls = {"n": 0}

    def broken_fetch():
        bcalls["n"] += 1
        raise NC.TransientFetchError("blip")

    broken = NC.broken_get(NC.NegativeCache(), "pkg/y", broken_fetch)
    empty_ok_defect_present = broken is None and bcalls["n"] == 1

    payload = {
        "probe": "probe2-genuine-404",
        "unit_id": UNIT,
        "pass": kind_genuine and ttl_full and still_cached and empty_ok_defect_present,
        "genuine_entry": {
            "kind": e.kind if e else None,
            "ttl": e.ttl if e else None,
            "full_ttl_s": c.genuine_negative_ttl,
        },
        "stays_cached_across_transient_window": still_cached,
        "regression_seed": {
            "seed": "an EMPTY cache reporting OK, measured on this estate (fixture-local fetch)",
            "broken_semantics_result": broken,
            "fetch_happened": bcalls["n"] == 1,
            "empty_ok_defect_present": empty_ok_defect_present,
            "note": "the detector proves it can see the empty-OK shape before declaring the real cache correct",
        },
        "fetch_calls_total": calls["n"],
    }
    print(json.dumps(payload, sort_keys=True))
    if payload["pass"]:
        print(f"SUCCESS:{UNIT}-probe2 genuine-404-ttl={e.ttl}s still_cached={still_cached} empty-OK-seed-detected={empty_ok_defect_present}")
        return 0
    print(f"FAILED:{UNIT}-probe2 kind={kind_genuine} ttl={ttl_full} cached={still_cached} seed={empty_ok_defect_present}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
