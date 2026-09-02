#!/usr/bin/env python3
"""Named probe 1: recall and injected-token cost as a pair on every configuration.

Recomputes the matrix from repertoire.json + labelled_set.json. Does not trust
a recall figure with no cost figure. Flood must have perfect offer-recall and
a measured cost that fails the budget.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import scenario as S  # noqa: E402
from router import TOKEN_BUDGET, count_tokens, payload_for  # noqa: E402

OUT = HERE / "probe1-pairs.raw.json"
ART = REPO / "command-center/receipts/TST-0318.json"
POLICIES = ("budgeted", "flood", "starve")


def fail(msg: str) -> int:
    print(f"FAILED:TST-0318-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0318" not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if doc.get("unit_id") != "TST-0318":
        return fail(f"unit_id {doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")

    ev = S.evaluate()
    pairs = ev["pairs"]
    claimed = doc.get("configuration_pairs") or {}
    if not claimed:
        return fail("receipt configuration_pairs missing")

    for policy in POLICIES:
        live = pairs[policy]
        row = claimed.get(policy) or {}
        if "recall" not in row or "injected_token_cost_mean" not in row:
            return fail(f"{policy} missing recall/cost pair")
        if abs(float(row["recall"]) - float(live["recall"])) > 1e-12:
            return fail(f"{policy} recall mismatch {row['recall']} vs {live['recall']}")
        if abs(float(row["injected_token_cost_mean"]) - float(live["injected_token_cost_mean"])) > 1e-9:
            return fail(f"{policy} cost mismatch")
        if live["pair_complete"] is not True:
            return fail(f"{policy} pair incomplete")

    flood = pairs["flood"]
    if flood["recall"] != 1.0:
        return fail(f"flood recall {flood['recall']} not perfect")
    if flood["injected_token_cost_max"] <= TOKEN_BUDGET:
        return fail("flood cost did not fail budget")
    live_flood = count_tokens(payload_for(ev["repertoire"]))
    if live_flood != flood["injected_token_cost_max"]:
        return fail("flood cost was not re-measured from descriptions")
    if live_flood == ev["flood_estimate"]:
        return fail("flood cost equals decoy token_cost sum (estimated, not measured)")

    starve = pairs["starve"]
    if starve["recall"] != 0.0 or starve["injected_token_cost_mean"] != 0.0:
        return fail("starve is not the zero-cost zero-recall degenerate")

    budgeted = pairs["budgeted"]
    if not budgeted["budget_ok"]:
        return fail("budgeted exceeded token budget")
    if budgeted["recall"] <= 0.5:
        return fail("budgeted recall collapsed")

    payload = {
        "probe": "probe1-recall-cost-pair",
        "unit_id": "TST-0318",
        "pairs": pairs,
        "flood_measured": live_flood,
        "flood_estimate": ev["flood_estimate"],
        "computed_not_asserted": True,
    }
    OUT.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "budgeted_recall": budgeted["recall"],
                "budgeted_cost_mean": budgeted["injected_token_cost_mean"],
                "flood_recall": flood["recall"],
                "flood_cost": flood["injected_token_cost_max"],
                "starve_recall": starve["recall"],
                "starve_cost": starve["injected_token_cost_mean"],
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:TST-0318-probe1 recall and cost recomputed as a pair")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
