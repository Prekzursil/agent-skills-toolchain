#!/usr/bin/env python3
"""Probe 1: reservation both-states + latency with/without the batch sweep.

Signal (a): interactive wait-to-admit distribution with the sweep on vs off.
Both-states: disabling the reservation makes interactive wait degrade
under the same saturating sweep.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center" / "lib"))

from b07_scheduler import (  # noqa: E402
    HOLD_S,
    WAIT_BUDGET_S,
    LaneConfig,
    active_config,
    run_arm,
)

OUT = HERE / "probe1-reservation-both-states.raw.json"
ART = REPO / "command-center" / "receipts" / "TST-0140.json"
SENTINEL = "SUCCESS:TST-0140"
N = 6


def fail(payload: dict, msg: str) -> int:
    payload["pass"] = False
    payload["error"] = msg
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    print(f"FAILED:TST-0140-probe1 {msg}")
    return 1


def check_receipt() -> str | None:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return "artifact missing"
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    state = str(doc.get("state") or "").upper()
    if state in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"self-declared:{doc.get('state')}"
    if SENTINEL not in text:
        return "sentinel-absent"
    return None


def main() -> int:
    payload: dict = {
        "probe": "probe1-reservation-both-states",
        "unit_id": "TST-0140",
        "pass": False,
    }
    err = check_receipt()
    if err:
        return fail(payload, err)

    reserved = active_config()
    unreserved = LaneConfig(
        capacity=reserved.capacity,
        interactive_reserved=reserved.interactive_reserved,
        reservation_enabled=False,
    )
    if not reserved.is_measurable_reservation():
        return fail(payload, "active config is not a measurable reservation")
    if unreserved.is_measurable_reservation():
        return fail(payload, "disabled clone still counts as a reservation")

    no_sweep = run_arm(reserved, sweep=False, n=N, hold_s=HOLD_S)
    sweep_on = run_arm(reserved, sweep=True, n=N, hold_s=HOLD_S)
    sweep_off = run_arm(unreserved, sweep=True, n=N, hold_s=HOLD_S)

    p50_base = float(no_sweep["latency"]["p50"])
    p50_on = float(sweep_on["latency"]["p50"])
    p50_off = float(sweep_off["latency"]["p50"])

    payload.update(
        {
            "wait_budget_s": WAIT_BUDGET_S,
            "hold_s": HOLD_S,
            "no_sweep": {
                "p50": p50_base,
                "p95": no_sweep["latency"]["p95"],
                "within_budget": no_sweep["within_budget"],
                "samples": no_sweep["latency"]["samples"],
            },
            "sweep_reserved": {
                "p50": p50_on,
                "p95": sweep_on["latency"]["p95"],
                "within_budget": sweep_on["within_budget"],
                "headroom_deferral_count": sweep_on["headroom_deferral_count"],
                "samples": sweep_on["latency"]["samples"],
            },
            "sweep_unreserved": {
                "p50": p50_off,
                "p95": sweep_off["latency"]["p95"],
                "within_budget": sweep_off["within_budget"],
                "headroom_deferral_count": sweep_off["headroom_deferral_count"],
                "samples": sweep_off["latency"]["samples"],
            },
            "both_states_control": (
                "disabling reservation degrades interactive wait under the same sweep"
            ),
        }
    )

    if not no_sweep["within_budget"]:
        return fail(payload, "no-sweep interactive wait exceeded budget")
    if not sweep_on["within_budget"]:
        return fail(payload, "reserved sweep interactive wait exceeded budget")
    if abs(p50_on - p50_base) > WAIT_BUDGET_S:
        return fail(payload, "sweep inflated reserved interactive p50 vs no-sweep")
    if sweep_off["within_budget"]:
        return fail(payload, "unreserved sweep stayed in budget; control is insensitive")
    if p50_off < HOLD_S * 0.6:
        return fail(payload, f"unreserved p50 {p50_off} not held for ~{HOLD_S}s")
    if not (p50_off > p50_on * 3):
        return fail(
            payload,
            f"unreserved p50 {p50_off} not > 3x reserved p50 {p50_on}",
        )
    if sweep_on["headroom_deferral_count"] != N:
        return fail(
            payload,
            f"reserved sweep headroom deferrals {sweep_on['headroom_deferral_count']} != {N}",
        )
    if sweep_off["headroom_deferral_count"] != 0:
        return fail(payload, "unreserved sweep emitted interactive-headroom deferrals")

    payload["pass"] = True
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    print(
        f"no_sweep_p50={p50_base:.6f} reserved_p50={p50_on:.6f} "
        f"unreserved_p50={p50_off:.6f} headroom={sweep_on['headroom_deferral_count']}"
    )
    print(
        "SUCCESS:TST-0140-probe1 reservation keeps interactive in budget; "
        "disabling it degrades wait under the sweep"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
