#!/usr/bin/env python3
"""Probe 1: per-vendor identical-output rate is MEASURED, not assumed.

Recomputes the rate from the recorded outputs (max frequency / n) and
requires that classify() agree with those numbers. A seed-ignoring vendor
must not be published as PINNED. A no-seed vendor must be NOT-PINNABLE
even if its outputs are stable.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.determinism import (  # noqa: E402
    NOT_PINNABLE,
    PINNED,
    default_council,
    estate_vendors,
    identical_output_rate,
    record_council,
)

RAW = HERE / "probe1-vendor-rates.raw.json"


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0260-probe1 {msg}")
    return 1


def recompute_rate(outputs: list[str]) -> float:
    if not outputs:
        raise ValueError("no outputs")
    counts = Counter(outputs)
    return max(counts.values()) / float(len(outputs))


def main() -> int:
    report = record_council()
    seats = report["seats"]
    if len(seats) != len(default_council()):
        return _fail(f"seat count {len(seats)} != roster")

    vendors = estate_vendors()
    for spec in default_council():
        if spec.vendor not in vendors:
            return _fail(f"roster vendor {spec.vendor} missing from estate_vendors")

    rows = []
    pinned = 0
    for rec in seats:
        outputs = rec["outputs"]
        live = identical_output_rate(outputs) if outputs else None
        independent = recompute_rate(outputs) if outputs else None
        if live != rec["identical_output_rate"]:
            return _fail(
                f"{rec['seat_id']} stored rate {rec['identical_output_rate']} "
                f"!= live {live}"
            )
        if independent != rec["identical_output_rate"]:
            return _fail(
                f"{rec['seat_id']} stored rate {rec['identical_output_rate']} "
                f"!= independent {independent}"
            )
        if rec["pin_status"] == PINNED:
            pinned += 1
            if not rec["seed_exposed"]:
                return _fail(f"{rec['seat_id']} PINNED without seed_exposed")
            if rec["identical_output_rate"] != 1.0:
                return _fail(
                    f"{rec['seat_id']} PINNED with rate={rec['identical_output_rate']}"
                )
            if rec["sampling"]["seed"] is None:
                return _fail(f"{rec['seat_id']} PINNED with seed=null")
        if rec["vendor"] == "local-echo-seed-ignored":
            if rec["pin_status"] != NOT_PINNABLE:
                return _fail("seed-ignoring vendor claimed deterministic")
            if rec["pin_reason"] != "seed-ignored":
                return _fail(f"seed-ignoring reason={rec['pin_reason']}")
            if rec["identical_output_rate"] >= 1.0:
                return _fail("seed-ignoring vendor produced identical outputs")
            if rec["sampling"]["seed"] is None:
                return _fail("seed-ignoring vendor did not record the pinned seed")
        if rec["vendor"] == "local-echo-unseeded":
            if rec["pin_status"] != NOT_PINNABLE:
                return _fail("unseeded vendor claimed deterministic")
            if rec["pin_reason"] != "seed-not-exposed":
                return _fail(f"unseeded reason={rec['pin_reason']}")
            if rec["sampling"]["seed"] is not None:
                return _fail("unseeded vendor recorded a fake seed")
            if rec["identical_output_rate"] != 1.0:
                return _fail("unseeded vendor should be stable-but-unpinnable")
        rows.append(
            {
                "seat_id": rec["seat_id"],
                "vendor": rec["vendor"],
                "seed_exposed": rec["seed_exposed"],
                "seed": rec["sampling"]["seed"],
                "identical_output_rate": rec["identical_output_rate"],
                "pin_status": rec["pin_status"],
                "pin_reason": rec["pin_reason"],
                "distinct_outputs": rec["distinct_outputs"],
            }
        )
        print(
            f"vendor={rec['vendor']} seat={rec['seat_id']} "
            f"rate={rec['identical_output_rate']} "
            f"status={rec['pin_status']} reason={rec['pin_reason']} "
            f"seed={rec['sampling']['seed']}"
        )

    frac = pinned / float(len(seats))
    if frac != report["council_reproducible_fraction"]:
        return _fail(
            f"fraction {frac} != report {report['council_reproducible_fraction']}"
        )
    if pinned < 1 or pinned >= len(seats):
        return _fail(f"expected mixed PINNED/NOT-PINNABLE, pinned={pinned}/{len(seats)}")
    if report["live_http_measured"] is not False:
        return _fail("must not claim live HTTP was measured")

    again = record_council()
    for a, b in zip(seats, again["seats"]):
        if a["vendor"] == "local-echo-seeded" and a["outputs"] != b["outputs"]:
            return _fail("seed-honouring vendor not stable across record_council calls")
        if a["pin_status"] != b["pin_status"] or a["pin_reason"] != b["pin_reason"]:
            return _fail(f"classification drifted for {a['seat_id']}")

    doc = {
        "council_reproducible_fraction": frac,
        "live_http_measured": False,
        "measurement_surface": report["measurement_surface"],
        "pass": True,
        "per_vendor": report["per_vendor"],
        "pinned_seat_count": pinned,
        "probe": "probe1-vendor-rates",
        "rows": rows,
        "seat_count": len(seats),
        "unit_id": "IMP-0260",
    }
    RAW.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(doc, sort_keys=True))
    print(
        f"fraction={frac} pinned={pinned}/{len(seats)} "
        f"surface={report['measurement_surface']}"
    )
    print("SUCCESS:IMP-0260-probe1 per-vendor rates measured not assumed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
