#!/usr/bin/env python3
"""Named probe 2: unit-outcome to response-code join (mechanically different).

Does not compute arrival spreads or canary gaps. Re-runs a 429 burst, maps each
unit's HTTP statuses to a terminal outcome the way a scheduler with no 429
branch can (200 COMPLETE else FAILED), and checks that no unit is FAILED solely
because of a 429. A correct backoff curve with FAILED units is still a defect.
The join gate is a both-states control (FAILED+429 is red; RETRY-PENDING is not).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common as C  # noqa: E402

OUT = HERE / "probe2-measurement.json"


def main() -> int:
    fx = C.Fixture()
    try:
        fx.mode = "ra"
        fx.clear()
        burst = C.synchronized_burst(fx.origin, n=C.N_UNITS, canary=False)
        events = fx.snapshot()
        by_unit: dict[str, list[int]] = {}
        for ev in events:
            uid = str(ev.get("unit_id") or "")
            if not uid.startswith("U"):
                continue
            by_unit.setdefault(uid, []).append(int(ev["status"]))
        client_disp = C.dispositions_from_client(burst["client"])
        joined = []
        for row in client_disp:
            uid = row["unit_id"]
            statuses = by_unit.get(uid) or row["statuses"]
            joined.append(
                {
                    "unit_id": uid,
                    "statuses": statuses,
                    "outcome": row["outcome"],
                    "failed_solely_on_429": row["outcome"] == "FAILED"
                    and bool(statuses)
                    and all(s == 429 for s in statuses),
                }
            )
        missing = [u for u in (r["unit_id"] for r in client_disp) if u not in by_unit]
        nc = C.both_states_join_control()
        live_gate = C.join_gate(joined)
        every_final = len(joined) == C.N_UNITS and not missing
        failed_on_429 = [r["unit_id"] for r in joined if r["failed_solely_on_429"]]
        # Rails: 429 is not a first-class outcome class on the reducer.
        rails = C.exercise_rails(fx.origin)
        rail_sees_429 = []
        for rail in rails:
            folded = rail.get("reduce") or {}
            rail_sees_429.append(
                {
                    "rail": rail["rail"],
                    "verdict": folded.get("verdict"),
                    "has_retry_after": (rail.get("scan") or {}).get("has_retry_after"),
                    "http_ast": (rail.get("scan") or {}).get("http_ast"),
                }
            )
    finally:
        fx.close()

    passed = (
        nc["fired_on_bad_state"]
        and nc["silent_on_good_state"]
        and every_final
        and len(joined) == C.N_UNITS
    )
    out = {
        "pass": passed,
        "probe": "probe2-outcome-join",
        "unit_id": C.UNIT,
        "joined": joined,
        "missing_units": missing,
        "every_unit_has_final_disposition": every_final,
        "failed_solely_on_429": failed_on_429,
        "any_failed_solely_on_429": bool(failed_on_429),
        "live_join_gate": live_gate,
        "negative_control": nc,
        "rails": rail_sees_429,
        "does_not_consult_arrival_spread": True,
        "does_not_consult_canary_gap": True,
    }
    C.dump(OUT, out)
    print(json.dumps(out, sort_keys=True))
    print(
        f"join_n={len(joined)} missing={missing} "
        f"failed_on_429={failed_on_429} live_red={live_gate['red']} "
        f"nc_fired={nc['fired_on_bad_state']} nc_silent={nc['silent_on_good_state']}"
    )
    if not passed:
        print("FAILED:ADV-0125-probe2 join gate inert or incomplete dispositions")
        return 1
    print("SUCCESS:ADV-0125-probe2 outcome-to-status join; both-states gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
