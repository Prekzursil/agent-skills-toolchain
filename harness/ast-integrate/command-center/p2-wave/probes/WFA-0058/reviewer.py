"""Independent reviewer: re-run mapping both-states and discrimination."""
from __future__ import annotations

from typing import Any

import corpus as C
import discriminate as D
import mapper as M
import namespaces as N
from vocab import DISCRIMINATION_FLOOR, GAP, vocab_ids


def mapping_both_states() -> dict[str, Any]:
    data = C.load_corpus()
    texts = C.distinct_texts(data)
    rows = M.map_all(texts)
    leaks = M.closed_ids(rows)
    multi = M.unique_mapping(rows)
    alias_rows = [r for r in data["rows"] if r["kind"] == "alias"]
    alias_ok = True
    for row in alias_rows:
        got = M.map_one(row["text"])
        if got["vocab_id"] != row["source"] or got["gap"]:
            alias_ok = False
            break
    gap_rows = [r for r in data["rows"] if r["kind"] == "gap"]
    gap_ok = all(M.map_one(r["text"])["vocab_id"] == GAP for r in gap_rows)
    planted = "planted-unknown-mechanism-xyzzy"
    planted_row = M.map_one(planted)
    fallback = M.fallback_mutant(planted)
    invented = M.invent_id_mutant(planted)
    fallback_rejected = fallback == planted and fallback not in vocab_ids()
    invent_rejected = invented == "MX-9001" and invented not in vocab_ids()
    closed_handles_plant = planted_row["vocab_id"] == GAP
    good = (
        not leaks
        and not multi
        and alias_ok
        and gap_ok
        and closed_handles_plant
        and fallback_rejected
        and invent_rejected
    )
    return {
        "known_good": {
            "n": len(rows),
            "closed_leaks": sorted(leaks),
            "multi_mapped": {k: sorted(v) for k, v in multi.items()},
            "aliases_exact": alias_ok,
            "gaps_are_NEW_MECHANISM": gap_ok,
            "fired": False,
            "ok": good,
        },
        "planted_gap": {
            "string": planted,
            "closed_id": planted_row["vocab_id"],
            "fallback_mutant": fallback,
            "invent_id_mutant": invented,
            "fallback_is_free_text": fallback_rejected,
            "invent_not_in_frozen_vocab": invent_rejected,
            "closed_records_gap": closed_handles_plant,
            "fired": True,
            "ok": closed_handles_plant and fallback_rejected and invent_rejected,
        },
        "ok": good,
    }


def review() -> dict[str, Any]:
    both = mapping_both_states()
    blind = D.run_blind()
    merge = D.indistinguishable_pair()
    ns = N.audit()
    ok = (
        both["ok"]
        and blind["passed"]
        and merge["merged_before_freeze"]
        and ns["clean"]
        and ns["planted_M-16_rejected_as_vocab_id"]
        and blind["score"] >= DISCRIMINATION_FLOOR
    )
    return {
        "reviewer_id": "WFA-0058-both-states-discrimination-rerun",
        "independent": True,
        "verdict": "PASS" if ok else "FAIL",
        "both_states_rerun": True,
        "mapping_both_states_ok": both["ok"],
        "discrimination_score": blind["score"],
        "discrimination_passed": blind["passed"],
        "indistinguishable_merged_before_freeze": merge["merged_before_freeze"],
        "namespace_clean": ns["clean"],
        "planted_option_id_rejected": ns["planted_M-16_rejected_as_vocab_id"],
    }
