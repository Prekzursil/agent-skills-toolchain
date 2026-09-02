#!/usr/bin/env python3
"""Named probe 2: unsatisfiable-as-written is escalated, not dropped.

Both-states: under PR-ONLY the canary conditions are UNSATISFIABLE-AS-WRITTEN;
under PRIVATE-CANARY the same conditions are NOT-CHECKED (no canary receipt),
never silently SATISFIED. Live artifact must schema-validate and remain compute-only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from catalog_bind import oq9_substitute  # noqa: E402
from conditions import PROMOTION_CONDITIONS  # noqa: E402
from evaluate import FALSE, NOT_CHECKED, SATISFIED, UNSAT, disk_lookup, evaluate, map_lookup  # noqa: E402
from schema_local import iter_errors, release_payload  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0126-release-gate-recompute.json"
UNSAT_IDS = {
    "PG-11125-private-canary-first",
    "PG-11131-canary-succeeds",
}


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0126-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("live artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    payload = release_payload(doc)
    errs = iter_errors(doc)
    if errs:
        print("schema", errs[0].message)
        return fail("live artifact schema-invalid")
    for garbage in ({}, {"totally": "unrelated"}, {"blob": "x" * 2000}):
        if not iter_errors(garbage):
            return fail("schema accepted garbage")

    if payload.get("promotion_verdict") != "NO-GO":
        return fail(f"live verdict {payload.get('promotion_verdict')} want NO-GO")
    if payload.get("scope", {}).get("created_merged_or_published") is not False:
        return fail("created_merged_or_published not false")
    if payload.get("scope", {}).get("actions") != ["compute-state"]:
        return fail("actions are not compute-only")

    live_ids = [r["id"] for r in payload.get("conditions") or []]
    want_ids = [c["id"] for c in PROMOTION_CONDITIONS]
    if live_ids != want_ids:
        return fail(f"live dropped or reordered conditions {live_ids}")
    live_unsat = [
        r["id"]
        for r in payload["conditions"]
        if r.get("computed_state") == UNSAT
    ]
    if set(live_unsat) != UNSAT_IDS:
        return fail(f"live unsat {live_unsat}")
    esc_ids = {e["condition_id"] for e in payload.get("escalations") or []}
    if esc_ids != UNSAT_IDS:
        return fail(f"escalations {esc_ids} do not match unsat")
    for e in payload["escalations"]:
        if e.get("silently_dropped") is not False:
            return fail(f"{e.get('condition_id')} silently_dropped")
        sub = e.get("proposed_substitute") or {}
        if sub.get("owner_question_id") != "OQ-9":
            return fail("substitute is not OQ-9")
        if not str(sub.get("text") or "").strip():
            return fail("substitute text empty")
        if sub.get("substitute_computed_state") == SATISFIED:
            return fail("substitute SATISFIED while REL-0004/0005/0006 are absent")
        if sub.get("substitute_computed_state") not in {NOT_CHECKED, FALSE}:
            return fail(f"substitute state {sub.get('substitute_computed_state')}")

    lookup = disk_lookup(REPO)
    oq9 = oq9_substitute()
    pr_only = evaluate("PR-ONLY", lookup, PROMOTION_CONDITIONS, oq9)
    canary = evaluate("PRIVATE-CANARY", lookup, PROMOTION_CONDITIONS, oq9)

    if pr_only["output_ids"] != want_ids or canary["output_ids"] != want_ids:
        return fail("evaluator dropped conditions")
    if set(pr_only["unsatisfiable_ids"]) != UNSAT_IDS:
        return fail(f"PR-ONLY unsat {pr_only['unsatisfiable_ids']}")
    if canary["unsatisfiable_ids"]:
        return fail(f"PRIVATE-CANARY still unsat {canary['unsatisfiable_ids']}")
    for cid in sorted(UNSAT_IDS):
        row = next(r for r in canary["conditions"] if r["id"] == cid)
        if row["computed_state"] == SATISFIED:
            return fail(f"{cid} under PRIVATE-CANARY silently SATISFIED")
        if row["computed_state"] not in {NOT_CHECKED, FALSE}:
            return fail(f"{cid} under PRIVATE-CANARY is {row['computed_state']}")

    # Substitute SATISFIED must not rewrite the as-written unsat row.
    ok = (HERE / "fixtures" / "ok-receipt.json").read_bytes()
    from conditions import REL_0004, REL_0005, REL_0006, WAVE4  # noqa: E402

    with_sub = evaluate(
        "PR-ONLY",
        map_lookup(
            {
                WAVE4: ok,
                REL_0004: ok,
                REL_0005: ok,
                REL_0006: ok,
            }
        ),
        PROMOTION_CONDITIONS,
        oq9,
    )
    still_unsat = {r["id"] for r in with_sub["conditions"] if r["computed_state"] == UNSAT}
    if still_unsat != UNSAT_IDS:
        return fail("as-written unsat rewritten when substitute receipts present")
    for e in with_sub["escalations"]:
        if e["proposed_substitute"]["substitute_computed_state"] != SATISFIED:
            return fail("substitute receipts did not SATISFY the substitute")
        if e.get("silently_dropped") is not False:
            return fail("escalation dropped after substitute SATISFIED")

    payload = {
        "pr_only_unsat": pr_only["unsatisfiable_ids"],
        "private_canary_unsat": canary["unsatisfiable_ids"],
        "escalations": sorted(esc_ids),
        "silently_dropped": False,
        "compute_only": True,
        "as_written_kept_when_substitute_satisfied": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:CNF-0126-probe2 unsat-escalated-not-dropped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
