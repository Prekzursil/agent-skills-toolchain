#!/usr/bin/env python3
"""Probe 2: DST / timezone-change / backward-step on live close.py paths."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import clock_lib as C  # noqa: E402

NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0127-probe2 {msg}")
    return 1


def main() -> int:
    live = C.behavioral()
    print(
        json.dumps(
            {
                "probe": live["probe"],
                "unit_id": live["unit_id"],
                "stable_utc_ok": live["stable_utc_control"]["ok"],
                "naive_tz_shift": live["timezone_change"]["naive"]["fired"],
                "aware_tz_silent": not live["timezone_change"]["aware"]["fired"],
                "dst_utc_order_ok": live["dst_transition"]["utc_order_preserved"],
                "backward_reorders": live["backward_clock_step"]["reorders"],
                "distinction": live["dst_vs_backward_distinction"],
                "lease_never_expires": live["lease_defer"]["is_open_ignores_until"],
                "retry_clock_independent": live["retry_backoff"]["clock_independent"],
                "negative_control": live["negative_control"],
                "powershell_present": live["powershell"]["present"],
                "mtime_fixture": live["mtime_ttl_fixture_not_production"],
            },
            indent=1,
            sort_keys=True,
            default=str,
        )
    )
    if not live["stable_utc_control"]["ok"]:
        return fail("stable UTC control did not behave normally")
    if not live["timezone_change"]["naive"]["fired"]:
        return fail("naive ISO did not shift under TZ change")
    if live["timezone_change"]["aware"]["fired"]:
        return fail("UTC-aware ISO shifted under TZ change (control broken)")
    if not live["dst_transition"]["utc_order_preserved"]:
        return fail("UTC stamps reversed across DST instant")
    if not live["backward_clock_step"]["reorders"]:
        return fail("backward step did not reorder sort-by-ts vs append")
    if not live["dst_vs_backward_distinction"]["only_one_handled_by_utc_storage_alone"]:
        return fail("failed to distinguish DST from backward step")
    if not live["negative_control"]["ok"]:
        return fail("detector does not discriminate both states")
    if not live["lease_defer"]["is_open_ignores_until"]:
        return fail("expected is_open to ignore defer.until")
    if not live["retry_backoff"]["clock_independent"]:
        return fail("retry backoff unexpectedly clock-dependent")
    art = C.REPO / C.OUT_REL
    if not art.is_file() or art.stat().st_size < 1024:
        return fail("artifact missing")
    text, doc = C.load_artifact()
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        return fail(f"self-declared {doc.get('state')}")
    if C.catalog_sentinel() not in text:
        return fail("sentinel-absent")
    recorded = doc.get("behavioral") or {}
    if recorded.get("backward_clock_step", {}).get("reorders") is not True:
        return fail("artifact missing backward reorder")
    if recorded.get("timezone_change", {}).get("naive", {}).get("fired") is not True:
        return fail("artifact missing naive TZ shift")
    if recorded.get("negative_control", {}).get("ok") is not True:
        return fail("artifact negative control not ok")
    print(
        "stable_utc=True naive_tz_shift=True aware_silent=True "
        "dst_order=True backward_reorders=True detector_both_states=True"
    )
    print("SUCCESS:ADV-0127-probe2 behavioral DST/TZ/backward, UTC-vs-naive detector, artifact matches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
