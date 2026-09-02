#!/usr/bin/env python3
"""Probe 2: independent reviewer — 200 generated Retry-After values.

Recomputes expected waits from the raw header (does not trust probe1
summaries). Requires honor client inside the instructed window, ignore
client outside it when expected != ignore backoff, and client/server
clock gaps to reconcile.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from harness import (  # noqa: E402
    EPOCH,
    FALLBACK,
    IGNORE_BACKOFF,
    PROPERTY_N,
    generate_property_headers,
    honor_criteria,
    reconcile,
    result_to_dict,
    run_four_cases,
    run_property,
    wait_seconds,
)

PKG = HERE.parents[3] / "tools" / "command-center"
sys.path.insert(0, str(PKG))
from retry_after import parse_retry_after  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:TST-0136-probe2 {msg}")
    return 1


def main() -> int:
    headers = generate_property_headers()
    if len(headers) != PROPERTY_N:
        return fail(f"generated {len(headers)} want {PROPERTY_N}")

    honor = run_property(honor=True)
    ignore = run_property(honor=False)
    if len(honor) != PROPERTY_N or len(ignore) != PROPERTY_N:
        return fail("property run length mismatch")

    # Independent recompute: expected wait from raw header at t=0.
    recompute_fail = []
    for spec, row in zip(headers, honor):
        expected = wait_seconds(spec["header"], now=EPOCH, fallback=FALLBACK)
        if abs(expected - row.expected_wait) > 1e-9:
            # Honor runner uses first-attempt now; for FakeClock that is EPOCH.
            recompute_fail.append(
                {
                    "id": spec["id"],
                    "independent": expected,
                    "row": row.expected_wait,
                    "header": spec["header"][:60],
                }
            )
    if recompute_fail:
        return fail(f"independent expected mismatch n={len(recompute_fail)} {recompute_fail[:3]}")

    honor_fail = [r.case_id for r in honor if not honor_criteria(r)]
    if honor_fail:
        return fail(f"honor property failed {honor_fail[:8]} n={len(honor_fail)}")

    ignore_should_fail = []
    ignore_accidentally_pass = []
    for spec, row in zip(headers, ignore):
        expected = wait_seconds(spec["header"], now=EPOCH, fallback=FALLBACK)
        if abs(expected - IGNORE_BACKOFF) <= 1e-9:
            continue
        ignore_should_fail.append(spec["id"])
        if honor_criteria(row):
            ignore_accidentally_pass.append(spec["id"])
    if ignore_accidentally_pass:
        return fail(f"ignore passed honor window {ignore_accidentally_pass[:8]}")
    if len(ignore_should_fail) < 150:
        return fail(f"ignore-must-fail population too small {len(ignore_should_fail)}")

    rec = reconcile(honor, live=False)
    if not rec["ok"]:
        return fail(f"clock reconciliation {rec}")

    kinds = {}
    for spec in headers:
        kinds[spec["kind"]] = kinds.get(spec["kind"], 0) + 1
    for required in ("delta-seconds", "http-date", "http-date-past", "malformed"):
        if kinds.get(required, 0) < 1:
            return fail(f"property set missing {required}")

    # Four-case ignore control re-run in this reviewer process.
    four_ignore = run_four_cases(live=False, honor=False)
    four_honor = run_four_cases(live=False, honor=True)
    if any(honor_criteria(r) for r in four_ignore):
        return fail("reviewer four-case ignore did not fail all")
    if any(not honor_criteria(r) for r in four_honor):
        return fail("reviewer four-case honor did not pass all")

    parsed_kinds = [parse_retry_after(s["header"], now=EPOCH).kind for s in headers[:12]]

    payload = {
        "probe": "probe2-property-200",
        "unit_id": "TST-0136",
        "n": PROPERTY_N,
        "kind_counts": kinds,
        "honor_pass": len(honor) - len(honor_fail),
        "ignore_must_fail": len(ignore_should_fail),
        "ignore_accidental_pass": len(ignore_accidentally_pass),
        "reconcile": {k: rec[k] for k in ("pairs", "skew_fail", "gap_fail", "ok")},
        "sample": [result_to_dict(r) for r in honor[:8]],
        "seed_parse_kinds": parsed_kinds,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"n={PROPERTY_N} honor_pass={payload['honor_pass']} "
        f"ignore_fail_pop={len(ignore_should_fail)} reconcile_ok={rec['ok']}"
    )
    print("SUCCESS:TST-0136-probe2 property-200 clock-reconciliation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
