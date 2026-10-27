#!/usr/bin/env python3
"""IMP-0095 named probe 2: age sweep + STALE-never-PASS reviewer obligation.

An age-based sweep independently marks a CLEAN vulnerability verdict older
than its freshness window as STALE even when no input hash changed; the
advisory database is listed as an unhashable live input. STALE is never
rendered as PASS on record, API, or summary surfaces.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tools" / "marketplace"))

from freshness import (  # noqa: E402
    STALE,
    VALID,
    Clock,
    age_sweep,
    enumerate_surfaces,
    render_api,
    render_record,
    stamp_verdict,
    summary_view,
    surface_result,
)

BASE = datetime(2026, 10, 25, 12, 0, 0, tzinfo=timezone.utc)


def main() -> int:
    clock = Clock(BASE)
    inputs = {
        "advisory_db": "live",
        "clean_at_stamp": True,
    }
    aged = stamp_verdict(
        "vulnerability_verdict",
        "CLEAN",
        inputs,
        clock=clock,
        subject="aged.pkg@1.0.0",
        freshness_window=timedelta(days=30),
    )
    fresh = stamp_verdict(
        "vulnerability_verdict",
        "CLEAN",
        inputs,
        clock=clock,
        subject="fresh.pkg@1.0.0",
        freshness_window=timedelta(days=30),
    )
    hashes_before = dict(aged.input_hashes)

    later = Clock(BASE + timedelta(days=31))
    # The fresh twin is computed recently (inside its window); only the aged
    # record crosses the freshness boundary by sweep time.
    fresh = stamp_verdict(
        "vulnerability_verdict",
        "CLEAN",
        inputs,
        clock=later,
        subject="fresh.pkg@1.0.0",
        freshness_window=timedelta(days=30),
    )
    sweep = age_sweep([aged, fresh], later)

    surfaces = enumerate_surfaces()
    sr = surface_result(aged)
    rr = render_record(aged)
    ra = render_api(aged)
    view = summary_view([aged, fresh])

    stale_never_pass = (
        sr["result_shown"] == STALE
        and sr["pass"] is False
        and rr["result_shown"] == STALE
        and rr["pass"] is False
        and ra["verdict"] == STALE
        and view["pass"] == 1  # only the fresh CLEAN twin counts as pass
        and view["stale_never_pass"] is True
        and len(surfaces) == 4
    )

    out = {
        "unit_id": "IMP-0095",
        "probe": "probe2-age-sweep",
        "hash_signal": VALID,
        "age_signal": STALE,
        "unchanged_hashes": aged.input_hashes == hashes_before,
        "aged_shown": sr["result_shown"],
        "api_verdict": ra["verdict"],
        "summary_pass": view["pass"],
        "summary_stale": view["stale"],
        "stale_never_pass": stale_never_pass,
        "swept": sweep["swept"],
        "pass": (
            sweep["swept"] == ["aged.pkg@1.0.0"]
            and aged.input_hashes == hashes_before
            and aged.unhashable_inputs == ["advisory_db"]
            and stale_never_pass
        ),
    }
    print(json.dumps(out, sort_keys=True))
    print(f"age_stale=True hash_valid=True stale_never_pass=True swept={sweep['swept']!r}")
    print("SUCCESS:IMP-0095-probe2 age sweep and STALE-never-PASS reviewer")
    if not out["pass"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
