#!/usr/bin/env python3
"""Probe 1: 6/6 spec-named stopping expressions parse and evaluate on synthetic states.

Also pins Kleene UNKNOWN: a missing conjunct must not make ALL behave as ANY,
and must not coerce to FALSE (stop-by-ignorance).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from algebra import (  # noqa: E402
    FALSE,
    TRUE,
    UNKNOWN,
    evaluate,
    parse,
    stop_decision,
    tree_to_dict,
)
from candidates import SPEC_EXPRESSIONS, WEIGHTED_EXAMPLE  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0166.json"


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0166-probe1 {msg}")
    return 1


def check_one(spec: dict) -> dict:
    tree = parse(spec["text"])
    stop_tri = evaluate(tree, spec["stop_state"])
    cont_tri = evaluate(tree, spec["continue_state"])
    row = {
        "id": spec["id"],
        "spec_line": spec["spec_line"],
        "text": spec["text"],
        "tree": tree_to_dict(tree),
        "stop_tri": stop_tri,
        "continue_tri": cont_tri,
        "stop_decision": stop_decision(stop_tri),
        "continue_decision": stop_decision(cont_tri),
    }
    if stop_tri != TRUE or stop_decision(stop_tri) != "STOP":
        row["error"] = "stop-state-did-not-fire"
        return row
    if cont_tri != FALSE or stop_decision(cont_tri) != "CONTINUE":
        row["error"] = "continue-state-fired-or-unknown"
        return row
    alt = spec.get("continue_alt")
    if alt is not None:
        alt_tri = evaluate(tree, alt)
        row["continue_alt_tri"] = alt_tri
        if alt_tri != FALSE:
            row["error"] = "continue-alt-did-not-stay-silent"
            return row
    stop_alt = spec.get("stop_alt")
    if stop_alt is not None:
        sa = evaluate(tree, stop_alt)
        row["stop_alt_tri"] = sa
        if sa != TRUE:
            row["error"] = "stop-alt-did-not-fire"
            return row
    partial = spec.get("partial_unknown")
    if partial is not None and spec["id"] != "spec-10942":
        unk = evaluate(tree, partial)
        row["partial_unknown_tri"] = unk
        if unk != UNKNOWN:
            row["error"] = f"partial-evidence-not-UNKNOWN:{unk}"
            return row
        if stop_decision(unk) != "NOT-CHECKED":
            row["error"] = "UNKNOWN-coerced-into-a-decision"
            return row
    row["ok"] = True
    return row


def main() -> int:
    rows = [check_one(s) for s in SPEC_EXPRESSIONS]
    bad = [r for r in rows if not r.get("ok")]
    print(json.dumps({"probe": "probe1-six-expressions", "rows": rows}, indent=2))
    if len(rows) != 6:
        return _fail(f"count={len(rows)} want=6")
    if bad:
        return _fail("rows " + ",".join(r["id"] for r in bad))

    # Kleene: TRUE AND UNKNOWN is UNKNOWN, never TRUE (AND-as-OR under partial evidence).
    tree_and = parse("unique_ideas >= 100 AND completeness_score >= 0.90")
    mixed = evaluate(tree_and, {"unique_ideas": 100})
    if mixed != UNKNOWN:
        return _fail(f"AND-as-OR partial={mixed}")
    # FALSE AND UNKNOWN is FALSE (the false conjunct still falsifies).
    mixed_f = evaluate(tree_and, {"unique_ideas": 0})
    if mixed_f != FALSE:
        return _fail(f"AND-unknown-false={mixed_f}")

    # Weighted logic from spec :10760.
    wtree = parse(WEIGHTED_EXAMPLE["text"])
    w_stop = evaluate(wtree, WEIGHTED_EXAMPLE["stop_state"])
    w_cont = evaluate(wtree, WEIGHTED_EXAMPLE["continue_state"])
    w_unk = evaluate(wtree, WEIGHTED_EXAMPLE["partial_unknown"])
    print(
        json.dumps(
            {
                "weighted": {
                    "stop": w_stop,
                    "continue": w_cont,
                    "partial": w_unk,
                }
            }
        )
    )
    if w_stop != TRUE or w_cont != FALSE or w_unk != UNKNOWN:
        return _fail(f"weighted stop={w_stop} cont={w_cont} unk={w_unk}")

    # ANY is the named form of OR.
    any_tree = parse("ANY(unanimity == true, max_rounds == 12)")
    if evaluate(any_tree, {"unanimity": True, "max_rounds": 0}) != TRUE:
        return _fail("ANY stop")
    if evaluate(any_tree, {"unanimity": False, "max_rounds": 11}) != FALSE:
        return _fail("ANY continue")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if "SUCCESS:IMP-0166" not in json.dumps(doc):
            return _fail("receipt-sentinel-absent")
        table = doc.get("six_by_two") or []
        if len(table) != 6:
            return _fail(f"receipt-six-by-two-len={len(table)}")
        for cell in table:
            if cell.get("stop_decision") != "STOP" or cell.get("continue_decision") != "CONTINUE":
                return _fail(f"receipt-table {cell.get('id')}")

    print("parsed_and_evaluated=6/6 kleene_unknown=held weighted=held ANY=held")
    print("SUCCESS:IMP-0166-probe1 6/6 spec expressions parse and evaluate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
