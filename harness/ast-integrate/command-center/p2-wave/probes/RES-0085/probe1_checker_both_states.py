#!/usr/bin/env python3
"""Probe 1: both-state unanswered-rebuttal / unsupported-claim checkers.

Known-good fixtures must stay silent. Known-broken fixtures must fire.
A checker silent on both states, or that fires on both, fails.
Toulmin unanswered-rebuttal and Dung unsupported-claim must raise Uncheckable.
Control: at least one format is uncheckable or too costly to emit.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

CASES = HERE / "fixtures" / "cases"


def load(name: str) -> dict:
    return json.loads((CASES / name).read_text(encoding="utf-8"))


def fail(msg: str) -> int:
    print(f"FAILED:RES-0085-probe1 {msg}")
    return 1


def main() -> int:
    ibis_ok = load("ibis_answered.json")
    ibis_ur = load("ibis_unanswered.json")
    ibis_us = load("ibis_unsupported.json")
    r_ok = E.check_ibis(ibis_ok)
    r_ur = E.check_ibis(ibis_ur)
    r_us = E.check_ibis(ibis_us)
    print(
        json.dumps(
            {
                "ibis_answered_fires": r_ok["fires"],
                "ibis_unanswered_ids": [x["id"] for x in r_ur["unanswered_rebuttals"]],
                "ibis_unsupported_ids": r_us["unsupported_claims"],
            }
        )
    )
    if r_ok["fires"] or r_ok["unanswered_rebuttals"] or r_ok["unsupported_claims"]:
        return fail("IBIS answered fixture fired (false positive)")
    if not r_ur["unanswered_rebuttals"]:
        return fail("IBIS unanswered fixture silent")
    ids_ur = {x["id"] for x in r_ur["unanswered_rebuttals"]}
    if "a-con->p1" not in ids_ur:
        return fail(f"IBIS unanswered missed a-con->p1 got={ids_ur}")
    if r_ur["fires"] == r_ok["fires"]:
        return fail("IBIS unanswered-rebuttal silent in both states")
    if "p-bare" not in r_us["unsupported_claims"]:
        return fail(f"IBIS unsupported missed p-bare got={r_us['unsupported_claims']}")
    if r_us["fires"] == r_ok["fires"]:
        return fail("IBIS unsupported silent in both states")

    t_ok = E.check_toulmin(load("toulmin_supported.json"))
    t_bad = E.check_toulmin(load("toulmin_unsupported.json"))
    if t_ok["unsupported_claims"]:
        return fail("Toulmin supported fixture fired unsupported")
    if not t_bad["unsupported_claims"]:
        return fail("Toulmin unsupported fixture silent")
    if t_ok["fires"] == t_bad["fires"]:
        return fail("Toulmin unsupported-claim silent in both states")
    try:
        E.toulmin_unanswered_rebuttals(load("toulmin_supported.json"))
        return fail("Toulmin unanswered-rebuttal did not raise Uncheckable")
    except E.Uncheckable as exc:
        print(f"toulmin_unanswered_rebuttal uncheckable ok: {exc.format_id}")
    if t_ok["unanswered_rebuttal_status"] != E.UNCHECKABLE:
        return fail("Toulmin unanswered status not uncheckable")

    d_ok = E.check_dung(load("dung_answered.json"))
    d_bad = E.check_dung(load("dung_unanswered.json"))
    if d_ok["unanswered_rebuttals"]:
        return fail("Dung answered fixture fired unanswered")
    if not d_bad["unanswered_rebuttals"]:
        return fail("Dung unanswered fixture silent")
    if d_ok["fires"] == d_bad["fires"]:
        return fail("Dung unanswered-rebuttal silent in both states")
    ids_d = {x["id"] for x in d_bad["unanswered_rebuttals"]}
    if "b->a" not in ids_d:
        return fail(f"Dung unanswered missed b->a got={ids_d}")
    try:
        E.dung_unsupported(load("dung_answered.json"))
        return fail("Dung unsupported-claim did not raise Uncheckable")
    except E.Uncheckable:
        print("dung_unsupported uncheckable ok")
    if d_ok["emit_cost"] != E.TOO_COSTLY:
        return fail("Dung emit_cost was not too_costly_to_emit")

    rows = E.format_comparison()
    control = [
        r
        for r in rows
        if r["checkability_unanswered_rebuttal"] == E.UNCHECKABLE
        or r["emit_cost"] == E.TOO_COSTLY
    ]
    if not control:
        return fail("control failed: no format marked uncheckable or too costly")
    checkable_ur = [
        r for r in rows if r["checkability_unanswered_rebuttal"] == E.CHECKABLE
    ]
    if len(checkable_ur) < 2:
        return fail("expected IBIS and Dung unanswered-rebuttal checkable")
    for r in checkable_ur:
        text = r["unanswered_rebuttal_check"]
        if "def " not in text or "return" not in text:
            return fail(f"{r['id']} missing written unanswered-rebuttal check")
    rec = [r["id"] for r in rows if r.get("recommended_for_council")]
    if rec != ["ibis"]:
        return fail(f"recommended_for_council={rec} want [ibis]")

    print("control_uncheckable_or_costly=" + ",".join(x["id"] for x in control))
    print("SUCCESS:RES-0085-probe1 both-state checkers and uncheckable control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
