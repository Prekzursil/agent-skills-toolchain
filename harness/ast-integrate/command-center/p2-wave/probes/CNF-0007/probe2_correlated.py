#!/usr/bin/env python3
"""Probe 2: same-vendor is correlated-confirmation; recompute the rate.

Re-derives labels from catalog + plants. Does not rewrite the matrix artifact.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import matrix as M  # noqa: E402
import validate as V  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0007-crossvendor-matrix.json"


def main() -> int:
    if not ART.is_file():
        print("FAILED:CNF-0007-probe2 matrix missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    schema_errs = V.validate_doc(doc)
    if schema_errs:
        print("FAILED:CNF-0007-probe2 schema-invalid")
        for err in schema_errs[:20]:
            print(" ", err)
        return 1

    built = M.build()
    body = M.payload(doc)
    live_rows = {
        r["claim_id"]: r
        for r in (body.get("assignments") or [])
        if isinstance(r, dict) and r.get("claim_id")
    }
    recomputed = {r["claim_id"]: r for r in built["assignments"]}
    if set(live_rows) != set(recomputed):
        missing = sorted(set(recomputed) - set(live_rows))[:8]
        extra = sorted(set(live_rows) - set(recomputed))[:8]
        print(f"FAILED:CNF-0007-probe2 assignment id set drift missing={missing} extra={extra}")
        return 1

    mismatches = []
    same_as_independent = []
    for cid, row in recomputed.items():
        live = live_rows[cid]
        if live.get("independence_class") != row["independence_class"]:
            mismatches.append(cid)
        if live.get("vendor_pair_cross") != row["vendor_pair_cross"]:
            mismatches.append(cid)
        if (
            live.get("implementer_vendor") == live.get("confirmer_vendor")
            and live.get("independence_class") == "independent"
        ):
            same_as_independent.append(cid)
    if mismatches:
        print(f"FAILED:CNF-0007-probe2 label drift {mismatches[:12]}")
        return 1
    if same_as_independent:
        print(f"FAILED:CNF-0007-probe2 same-vendor labelled independent {same_as_independent}")
        return 1

    same = recomputed["PLANT-P0-SAME-VENDOR"]
    cross = recomputed["PLANT-P0-CROSS-VENDOR"]
    print(
        f"plant same class={same['independence_class']} cross={same['vendor_pair_cross']}"
    )
    print(
        f"plant cross class={cross['independence_class']} cross={cross['vendor_pair_cross']}"
    )
    if same["independence_class"] != "correlated-confirmation":
        print("FAILED:CNF-0007-probe2 same-vendor plant not correlated-confirmation")
        return 1
    if cross["independence_class"] != "independent":
        print("FAILED:CNF-0007-probe2 cross-vendor plant not independent")
        return 1

    meas = body.get("measured") or {}
    want = built["measured"]
    for key in (
        "n_catalog_frame",
        "n_catalog_cross_vendor",
        "catalog_cross_vendor_rate",
        "n_labelled_p0_p1",
        "n_labelled_cross_vendor",
        "n_labelled_correlated",
        "labelled_cross_vendor_rate",
    ):
        if meas.get(key) != want[key]:
            print(f"FAILED:CNF-0007-probe2 measured[{key}] {meas.get(key)} != {want[key]}")
            return 1
    print(
        f"catalog_rate={meas['catalog_cross_vendor_rate']} "
        f"n={meas['n_catalog_frame']} "
        f"labelled_rate={meas['labelled_cross_vendor_rate']} "
        f"labelled_n={meas['n_labelled_p0_p1']} "
        f"correlated={meas['n_labelled_correlated']}"
    )

    mutant = copy.deepcopy(doc)
    mutant_rows = M.payload(mutant).get("assignments") or []
    for row in mutant_rows:
        if row.get("claim_id") == "PLANT-P0-SAME-VENDOR":
            row["independence_class"] = "independent"
            row["vendor_pair_cross"] = True
            break
    else:
        print("FAILED:CNF-0007-probe2 plant row missing for mutant")
        return 1
    caught = False
    for row in mutant_rows:
        if (
            row.get("implementer_vendor") == row.get("confirmer_vendor")
            and row.get("independence_class") == "independent"
        ):
            caught = True
            break
    print(f"mutant_same_vendor_independent_caught={caught}")
    if not caught:
        print("FAILED:CNF-0007-probe2 detector inert on same-vendor independent mutant")
        return 1

    print("SUCCESS:CNF-0007-probe2 correlated-confirmation labels and rate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
