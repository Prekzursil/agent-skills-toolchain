#!/usr/bin/env python3
"""Probe 2: both-states on the P1 safety rule the disposition gate consumes.

Known-good: every gate / permission_bound / stop_rule loss is P1 and blocks ADOPT.
Planted-bad: downgrade one stop_rule to P3/ACCEPTABLE; the check FIRES.
Recount derives P1 ids from safety_class only (ignores severity).
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import ledger as L  # noqa: E402
import recount as R  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0055-adapter-lossy-field-ledger.json"
SENTINEL = "SUCCESS:WFA-0055"
PLANT_ID = "LOSS-0050-llm-judge-termination"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0055-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared:{doc.get('state')}")

    rows = L.declared_rows()
    art_rows = (doc.get("ledger") or {}).get("losses") or []
    if len(art_rows) != len(rows):
        return fail(f"artifact n_losses={len(art_rows)} live={len(rows)}")

    good_viol = L.safety_violations(rows)
    if good_viol:
        return fail(f"known-good safety violations {good_viol}")
    s_ids = R.p1_ids_from_safety(rows)
    v_ids = R.p1_ids_from_severity(rows)
    if s_ids != v_ids:
        return fail(f"recount P1 disagree safety={s_ids} severity={v_ids}")
    if PLANT_ID not in s_ids:
        return fail(f"{PLANT_ID} not in P1 set")

    gate = (doc.get("disposition_gate") or {}).get("per_adapter") or {}
    live_gate = L.gate_all_adapters(rows)
    for uid, g in live_gate.items():
        art_g = gate.get(uid) or {}
        if bool(art_g.get("allowed")) != bool(g["allowed"]):
            return fail(f"gate allowed mismatch {uid}")
        if g["n_p1_blocking"] and g["allowed"]:
            return fail(f"P1 blocking but adopt allowed {uid}")

    # Frequency must not downgrade P1: a rare stop_rule stays P1.
    rare = copy.deepcopy(rows)
    for row in rare:
        if row.get("loss_id") == PLANT_ID:
            row["frequency"] = "once-in-corpus"
            annotated = L.annotate(
                {
                    k: row[k]
                    for k in (
                        "loss_id",
                        "adapter_id",
                        "native_field",
                        "source_construct",
                        "worked_example",
                        "ir_gap",
                        "downstream_consequence",
                        "safety_class",
                        "frequency",
                        "transferability",
                        "degrade",
                        "acceptability",
                    )
                    if k in row
                }
            )
            if annotated["severity"] != "P1" or not annotated["blocks_adopt"]:
                return fail("frequency downgraded P1")

    planted = copy.deepcopy(rows)
    found = False
    for row in planted:
        if row.get("loss_id") == PLANT_ID:
            row["severity"] = "P3"
            row["blocks_adopt"] = False
            row["acceptability"] = "ACCEPTABLE"
            found = True
    if not found:
        return fail(f"{PLANT_ID} missing")
    bad_viol = L.safety_violations(planted)
    planted_gate = L.evaluate_adopt("WFA-0050", None, planted)
    fired = PLANT_ID in bad_viol
    # Independent signal: safety-class P1 set still contains the plant, severity set does not.
    s_bad = R.p1_ids_from_safety(planted)
    v_bad = R.p1_ids_from_severity(planted)
    disagree = PLANT_ID in s_bad and PLANT_ID not in v_bad
    if not fired or not disagree:
        return fail(f"plant not caught viol={bad_viol} disagree={disagree}")

    negative = (
        "On the planted-bad ledger (LOSS-0050-llm-judge-termination, a stop_rule, "
        "downgraded to severity=P3 and blocks_adopt=false), safety_violations FIRES "
        f"and recount P1 sets disagree (safety has the id, severity does not). "
        f"viol={bad_viol} allowed_after_plant={planted_gate['allowed']}."
    )
    out = {
        "pass": True,
        "probe": "probe2-safety-p1",
        "unit_id": "WFA-0055",
        "silent_on_good": True,
        "fired_on_bad": True,
        "frequency_cannot_downgrade_p1": True,
        "n_p1": len(s_ids),
        "p1_ids": s_ids,
        "plant_id": PLANT_ID,
        "negative_control": negative,
    }
    print(json.dumps(out, sort_keys=True))
    print(f"known-good silent violations=0 n_p1={len(s_ids)}")
    print(f"planted-bad fired=True {negative}")
    print("SUCCESS:WFA-0055-probe2 safety-P1 both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
