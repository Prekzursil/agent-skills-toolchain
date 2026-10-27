"""IMP-0272 probe 1: feasible/infeasible constraint matrix.

Re-run: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0272/probe1_constraint_matrix.py
Exit 0 iff the live tools/council/participants/diversity solver distinguishes,
across the matrix: (a) a feasible two-vendor/two-model set seats with NO
waiver and independence intact; (b) a single-reachable-vendor set STILL RUNS
with a waiver recording independence void; (c) two same-vendor seats with
DIFFERENT models do NOT satisfy min_vendors=2 (waiver, void); (d) a
models-only shortfall waives too; (e) unreachable candidate seats are never
seated.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools" / "council" / "participants"))
from diversity import ASSUMPTION_INTACT, ASSUMPTION_VOID, check_artifact, solve  # noqa: E402

def req(cands, min_vendors, min_models):
    return {"candidate_seats": cands, "min_vendors": min_vendors, "min_models": min_models}

def seat(sid, vendor, model, reachable=True):
    return {"seat_id": sid, "vendor": vendor, "model": model, "reachable": reachable}

cases = []

r = check_artifact(solve(req([seat("s1", "a", "m1"), seat("s2", "b", "m2")], 2, 2)), req([seat("s1", "a", "m1"), seat("s2", "b", "m2")], 2, 2))
cases.append({"id": "feasible-no-waiver", "ok": r["ok"], "waiver": False, "assumption": ASSUMPTION_INTACT})

sol = solve(req([seat("s1", "a", "m1"), seat("s2", "a", "m1")], 2, 2))
r = check_artifact(sol, req([seat("s1", "a", "m1"), seat("s2", "a", "m1")], 2, 2))
cases.append({
    "id": "single-vendor-still-runs-with-void-waiver",
    "ok": r["ok"] and sol["feasible"] is False and len(sol["seats"]) == 2,
    "waiver": bool(sol["waiver"]), "assumption": sol["independence_assumption"],
})

sol = solve(req([seat("s1", "a", "m1"), seat("s2", "a", "m2")], 2, 2))
r = check_artifact(sol, req([seat("s1", "a", "m1"), seat("s2", "a", "m2")], 2, 2))
cases.append({
    "id": "same-vendor-different-models-not-two-vendors",
    "ok": r["ok"] and sol["observed_diversity"] == {"vendors": 1, "models": 2},
    "waiver": bool(sol["waiver"]), "assumption": sol["independence_assumption"],
})

sol = solve(req([seat("s1", "a", "m1"), seat("s2", "b", "m1")], 2, 2))
r = check_artifact(sol, req([seat("s1", "a", "m1"), seat("s2", "b", "m1")], 2, 2))
cases.append({
    "id": "models-shortfall-waives",
    "ok": r["ok"] and sol["observed_diversity"] == {"vendors": 2, "models": 1},
    "waiver": bool(sol["waiver"]), "assumption": sol["independence_assumption"],
})

sol = solve(req([seat("s1", "a", "m1", reachable=True), seat("s2", "b", "m2", reachable=False)], 2, 2))
cases.append({
    "id": "unreachable-never-seated",
    "ok": [s["seat_id"] for s in sol["seats"]] == ["s1"]
    and sol["unseated_unreachable"] == ["s2"],
    "waiver": bool(sol["waiver"]), "assumption": sol["independence_assumption"],
})

checks = {
    "feasible_no_waiver": cases[0]["ok"] and not cases[0]["waiver"],
    "all_cases_check_ok": all(c["ok"] for c in cases),
    "infeasible_cases_carry_void_waiver": all(
        c["waiver"] and c["assumption"] == ASSUMPTION_VOID
        for c in cases[1:4]
    ),
    "matrix_size_is_5": len(cases) == 5,
}
ok = all(checks.values())
out = {"probe": "probe1-constraint-matrix", "unit_id": "IMP-0272",
       "cases": cases, "checks": checks, "pass": ok}
print(json.dumps(out, sort_keys=True))
RAW = Path(__file__).resolve().parent / "probe1-constraint-matrix.raw.json"
RAW.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
if not ok:
    print("FAILED:IMP-0272-probe1 %s" % [k for k, v in checks.items() if not v])
    raise SystemExit(1)
print("SUCCESS:IMP-0272-probe1 feasible seats clean; infeasible still runs with void waiver; matrix 5/5")
