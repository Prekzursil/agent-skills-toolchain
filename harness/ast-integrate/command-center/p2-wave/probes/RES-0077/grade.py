"""Mechanical grading and E-tier gates for RES-0077."""
from __future__ import annotations

import copy
from typing import Any

from catalog import (
    BIASES,
    GRADES,
    GRADING_RULE_TEXT,
    MECHANISMS,
    REVIEWER_A_SOURCES,
    REVIEWER_B_SOURCES,
    WIDELY_CITED_OUTSIDE_MEASURED,
    corrections_index,
    table_rows,
)

ALLOWED_GRADES = set(GRADES)


def empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def apply_row_gates(row: dict) -> dict:
    """Attach promotable / illegal-grade flags. Does not trust a pre-written E-tier."""
    out = copy.deepcopy(row)
    missing_effect = empty(out.get("effect_size"))
    missing_baseline = empty(out.get("baseline"))
    missing_source = empty(out.get("source")) or empty(out.get("locator"))
    if missing_effect or missing_baseline or missing_source:
        out["evidence_tier"] = "E3"
        out["promotable"] = False
        out["headline_without_baseline"] = True
    else:
        out["headline_without_baseline"] = False
        if out.get("evidence_tier") not in {"E1", "E2", "E3", "E4"}:
            out["evidence_tier"] = "E1"
        out["promotable"] = out["evidence_tier"] in {"E1", "E2"}
    grade = out.get("grade")
    out["illegal_measured_effective"] = False
    if grade == "measured-effective":
        if not out["promotable"]:
            out["illegal_measured_effective"] = True
        if empty(out.get("correction_effect_size")):
            out["illegal_measured_effective"] = True
            out["promotable"] = False
    out["illegal_grade_value"] = bool(grade not in ALLOWED_GRADES and grade is not None)
    return out


def apply_mechanism_gates(mech: dict) -> dict:
    out = copy.deepcopy(mech)
    if (
        empty(out.get("effect_size"))
        or empty(out.get("baseline"))
        or empty(out.get("source"))
        or empty(out.get("locator"))
    ):
        out["evidence_tier"] = "E3"
        out["promotable"] = False
        out["headline_without_baseline"] = True
    else:
        out["headline_without_baseline"] = False
        out["promotable"] = out.get("evidence_tier") in {"E1", "E2"}
    return out


def live_table() -> list[dict]:
    return [apply_row_gates(r) for r in table_rows()]


def live_mechanisms() -> list[dict]:
    return [apply_mechanism_gates(m) for m in MECHANISMS]


def grade_errors(rows: list[dict] | None = None) -> list[str]:
    rows = rows if rows is not None else live_table()
    errs: list[str] = []
    if not GRADING_RULE_TEXT or "measured-effective" not in GRADING_RULE_TEXT:
        errs.append("grading_rule_missing")
    seen_bias = set()
    seen_grade = set()
    for r in rows:
        g = apply_row_gates(r)
        seen_bias.add(g.get("bias"))
        seen_grade.add(g.get("grade"))
        if g.get("illegal_grade_value"):
            errs.append(f"{g.get('id')}:bad-grade")
        if g.get("illegal_measured_effective"):
            errs.append(
                f"{g.get('id')}:measured-effective-without-correction-delta-or-baseline"
            )
        if empty(g.get("effect_size")):
            errs.append(f"{g.get('id')}:missing-effect")
        if empty(g.get("baseline")):
            errs.append(f"{g.get('id')}:missing-baseline")
        if empty(g.get("citation")) and empty(g.get("arxiv")):
            errs.append(f"{g.get('id')}:missing-citation")
        if g.get("grade") not in ALLOWED_GRADES:
            errs.append(f"{g.get('id')}:grade-not-in-enum")
    missing_bias = [b for b in BIASES if b not in seen_bias]
    if missing_bias:
        errs.append(f"missing-biases:{missing_bias}")
    if not (seen_grade - {"measured-effective"}):
        errs.append("control-failed-all-grades-measured-effective")
    return errs


def widely_cited_outside_measured(rows: list[dict] | None = None) -> dict:
    rows = rows if rows is not None else live_table()
    hits = []
    for r in rows:
        g = apply_row_gates(r)
        if g.get("correction_id") in WIDELY_CITED_OUTSIDE_MEASURED:
            hits.append(
                {
                    "id": g.get("id"),
                    "correction_id": g.get("correction_id"),
                    "grade": g.get("grade"),
                    "widely_cited": True,
                }
            )
    ok = bool(hits) and all(h["grade"] != "measured-effective" for h in hits)
    return {"ok": ok, "rows": hits}


def partition_ok(rows: list[dict] | None = None) -> dict:
    rows = rows if rows is not None else live_table()
    if REVIEWER_A_SOURCES & REVIEWER_B_SOURCES:
        return {
            "ok": False,
            "reason": "reviewer-source-sets-overlap",
            "overlap": sorted(REVIEWER_A_SOURCES & REVIEWER_B_SOURCES),
        }
    a, b, neither = [], [], []
    for r in rows:
        src = r.get("source")
        if src in REVIEWER_A_SOURCES:
            a.append(r["id"])
        elif src in REVIEWER_B_SOURCES:
            b.append(r["id"])
        else:
            neither.append({"id": r.get("id"), "source": src})
    return {
        "ok": (not neither) and bool(a) and bool(b),
        "reviewer_a_rows": a,
        "reviewer_b_rows": b,
        "unassigned": neither,
        "unassigned": neither,
        "disjoint": True,
    }


def both_states_headline_without_baseline() -> dict:
    """Known-broken: strip baseline from a measured-effective row; must refuse promotion."""
    rows = live_table()
    good = next(r for r in rows if r["grade"] == "measured-effective")
    broken = copy.deepcopy(good)
    broken["baseline"] = ""
    broken["correction_effect_size"] = None
    gated_good = apply_row_gates(good)
    gated_bad = apply_row_gates(broken)
    silent_on_good = (
        gated_good["promotable"]
        and not gated_good["illegal_measured_effective"]
        and not gated_good["headline_without_baseline"]
    )
    fires_on_bad = (
        gated_bad["evidence_tier"] == "E3"
        and not gated_bad["promotable"]
        and gated_bad["headline_without_baseline"]
        and gated_bad["illegal_measured_effective"]
    )
    return {
        "ok": silent_on_good and fires_on_bad,
        "silent_on_good": silent_on_good,
        "silent_on_good": silent_on_good,
        "fires_on_bad": fires_on_bad,
        "fires_on_bad": fires_on_bad,
        "good_id": good["id"],
        "good_tier": gated_good["evidence_tier"],
        "bad_tier": gated_bad["evidence_tier"],
        "bad_illegal_measured_effective": gated_bad["illegal_measured_effective"],
    }


def both_states_all_measured_effective_control() -> dict:
    """Known-broken: if every correction is measured-effective, the required control fails."""
    live = live_table()
    live_ctrl = widely_cited_outside_measured(live)
    poisoned = copy.deepcopy(live)
    for r in poisoned:
        r["grade"] = "measured-effective"
        if empty(r.get("correction_effect_size")):
            r["correction_effect_size"] = "fabricated-delta"
    poisoned_ctrl = widely_cited_outside_measured(poisoned)
    return {
        "ok": live_ctrl["ok"] and (not poisoned_ctrl["ok"]),
        "live_ok": live_ctrl["ok"],
        "live_ok": live_ctrl["ok"],
        "poisoned_ok": poisoned_ctrl["ok"],
        "live_hits": live_ctrl["rows"],
    }


def summary() -> dict:
    rows = live_table()
    mechs = live_mechanisms()
    return {
        "grading_rule": GRADING_RULE_TEXT,
        "n_table_rows": len(rows),
        "n_mechanisms": len(mechs),
        "promotable_mechanisms": [m["id"] for m in mechs if m["promotable"]],
        "grades": sorted({r["grade"] for r in rows}),
        "errors": grade_errors(rows),
        "widely_cited_control": widely_cited_outside_measured(rows),
        "partition": partition_ok(rows),
        "corrections": corrections_index(),
        "headline_control": both_states_headline_without_baseline(),
        "all_effective_control": both_states_all_measured_effective_control(),
    }


def emit_ready() -> tuple[bool, dict]:
    s = summary()
    ok = (
        not s["errors"]
        and s["widely_cited_control"]["ok"]
        and s["partition"]["ok"]
        and s["headline_control"]["ok"]
        and s["all_effective_control"]["ok"]
        and len(s["promotable_mechanisms"]) >= 4
    )
    return ok, s


# Aliases used by emit.py and the named probes.
live_mechanisms = live_mechanisms
partition_ok = partition_ok
both_states_headline_without_baseline = both_states_headline_without_baseline
both_states_all_measured_effective_control = both_states_all_measured_effective_control
