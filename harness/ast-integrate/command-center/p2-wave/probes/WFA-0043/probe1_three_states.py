#!/usr/bin/env python3
"""Probe 1: the three cell states stay distinct; per-family totals are present."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

ART = E.REPO / E.OUT_REL
UNIT = "WFA-0043"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    text = ART.read_text(encoding="utf-8")
    if E.SENTINEL not in text:
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    live = E.run_census()
    live_tot = live["tally"]["totals"]
    art_tot = doc.get("totals") or {}
    for key in E.STATES:
        if int(art_tot.get(key, -1)) != int(live_tot.get(key, -2)):
            return fail(f"totals-drift {key} artifact={art_tot.get(key)} live={live_tot.get(key)}")
    if not E.three_states_ok(art_tot, 2840):
        return fail("three-states-not-ok")
    if "filled" in art_tot or "unfilled" in art_tot:
        return fail("artifact collapsed into filled/unfilled")
    collapsed = E.collapse_mutant_totals(live_tot)
    if collapsed["filled"] == art_tot.get("EVIDENCED") and live_tot["HONEST-NULL"] > 0:
        return fail("evidenced-equals-collapsed-filled")
    # The answer is the triple, not the collapsed fill rate.
    if doc.get("filled_versus_unfilled_refused") is not True:
        return fail("collapse-not-refused")
    if doc.get("three_states_never_collapsed") is not True:
        return fail("three-states-flag-false")

    families = {p["family"]: p for p in doc.get("per_family") or []}
    g = families.get("G-skill")
    if not g or int(g.get("n_candidates") or 0) != 96:
        return fail(f"g-skill family missing or not 96: {g}")
    fam_cand = sum(int(p.get("n_candidates") or 0) for p in families.values())
    if fam_cand != 284:
        return fail(f"per-family n_candidates sum {fam_cand} != 284")
    fam_cells = sum(int(p.get("n_cells") or 0) for p in families.values())
    if fam_cells != 2840:
        return fail(f"per-family n_cells sum {fam_cells} != 2840")

    dims = doc.get("per_dimension") or []
    if len(dims) != 10:
        return fail(f"expected 10 dimensions got {len(dims)}")
    if len(doc.get("rows") or []) != 284:
        return fail(f"expected 284 rows got {len(doc.get('rows') or [])}")

    ctrl = doc.get("control_fixture") or {}
    if ctrl.get("has_all_three_states") is not True:
        return fail(f"control fixture missing a state: {ctrl.get('states_seen')}")
    for key in E.STATES:
        if int((ctrl.get("totals") or {}).get(key, 0)) <= 0:
            return fail(f"control fixture has zero {key}")

    tests = {t.get("id"): t for t in doc.get("tests") or [] if isinstance(t, dict)}
    if tests.get("WFA-0043-THREE-STATES", {}).get("result") != "PASS":
        return fail("embedded three-states test not PASS")
    if tests.get("WFA-0043-PER-FAMILY", {}).get("result") != "PASS":
        return fail("embedded per-family test not PASS")

    payload = {
        "pass": True,
        "probe": "probe1-three-states",
        "unit_id": UNIT,
        "totals": art_tot,
        "g_skill_candidates": g["n_candidates"],
        "collapse_preview": collapsed,
        "control_states": ctrl.get("states_seen"),
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"three_states=True g_skill=96/284 cells=2840 "
        f"E={art_tot['EVIDENCED']} H={art_tot['HONEST-NULL']} N={art_tot['EMPTY']}"
    )
    print(f"SUCCESS:{UNIT}-probe1 three states and per-family totals")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
