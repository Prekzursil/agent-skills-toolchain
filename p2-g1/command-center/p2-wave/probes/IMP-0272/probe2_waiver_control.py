"""IMP-0272 probe 2: waiver emission is load-bearing (both-states control).

Re-run: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0272/probe2_waiver_control.py
Exit 0 iff, on the live diversity module: the honest single-vendor artifact
(waiver present, independence void) passes check_artifact; stripping the
waiver from that honest artifact FAILS; solving with emit_waiver=False
(suppressed emission) FAILS the same check; a forged waiver claiming
independence intact FAILS; and the feasible artifact passes with no waiver
(silent-on-good).
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools" / "council" / "participants"))
from diversity import check_artifact, solve  # noqa: E402

REQ = {"candidate_seats": [
    {"seat_id": "s1", "vendor": "a", "model": "m1", "reachable": True},
    {"seat_id": "s2", "vendor": "a", "model": "m1", "reachable": True},
], "min_vendors": 2, "min_models": 2}
FEASIBLE_REQ = {"candidate_seats": [
    {"seat_id": "s1", "vendor": "a", "model": "m1", "reachable": True},
    {"seat_id": "s2", "vendor": "b", "model": "m2", "reachable": True},
], "min_vendors": 2, "min_models": 2}

honest = solve(REQ)
stripped = copy.deepcopy(honest)
stripped["waiver"] = None
suppressed = solve(REQ, emit_waiver=False)
forged = copy.deepcopy(honest)
forged["waiver"]["independence_assumption"] = "intact"
good = solve(FEASIBLE_REQ)

r_honest = check_artifact(honest, REQ)
r_stripped = check_artifact(stripped, REQ)
r_suppressed = check_artifact(suppressed, REQ)
r_forged = check_artifact(forged, REQ)
r_good = check_artifact(good, FEASIBLE_REQ)

checks = {
    "honest_waiver_passes": r_honest["ok"] is True,
    "stripped_waiver_fails": r_stripped["ok"] is False and r_stripped["violations"][0]["id"] == "waiver-missing",
    "suppressed_emission_fails": r_suppressed["ok"] is False and r_suppressed["violations"][0]["id"] == "waiver-missing",
    "forged_intact_waiver_fails": r_forged["ok"] is False,
    "good_state_silent": r_good["ok"] is True and not good["waiver"],
}
both_states = {
    "fired_on_bad_state": not (r_stripped["ok"] and r_suppressed["ok"] and r_forged["ok"]),
    "silent_on_good_state": r_honest["ok"] and r_good["ok"],
}
ok = all(checks.values()) and all(both_states.values())
out = {"probe": "probe2-waiver-control", "unit_id": "IMP-0272",
       "honest_violations": r_honest["violations"],
       "stripped_violation": r_stripped["violations"][0]["id"] if r_stripped["violations"] else None,
       "suppressed_violation": r_suppressed["violations"][0]["id"] if r_suppressed["violations"] else None,
       "forged_violations": r_forged["violations"],
       "both_states": both_states,
       "checks": checks, "pass": ok}
print(json.dumps(out, sort_keys=True))
RAW = Path(__file__).resolve().parent / "probe2-waiver-control.raw.json"
RAW.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
if not ok:
    print("FAILED:IMP-0272-probe2 %s" % [k for k, v in checks.items() if not v])
    raise SystemExit(1)
print("SUCCESS:IMP-0272-probe2 suppressed/stripped waiver FAILS the artifact check; honest waiver passes")
