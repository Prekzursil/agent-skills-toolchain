#!/usr/bin/env python3
"""Probe 2: both-states negative-scope detector + receipt honesty + distinct control.

Mechanically different from probe 1 (which plants a lexical paraphrase).

  1. BOTH-STATES: the same capability WITH a do-NOT-use-for clause must be
     absent from the zero-negative-scope set; stripping that clause must put
     it in the set. A detector that returns the same answer for both fails.
  2. Receipt numbers must match a live re-lint of the unplanted fixture.
  3. Distinct-rewrite control: rename + replace the description with a
     disjoint calendar blurb; that pair must NOT appear in the top 5.
     Stops a linter that always promotes the planted ids.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "router"))
import desc_lint as L  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0388.json"
INDEX = HERE / "fixtures/capability-index.json"
MUTANT = HERE / "fixtures/planted-mutant.json"
SENTINEL = "SENTINEL:IMP-0388:DESCRIPTION-LINT-COMPLETE"
DISTINCT = (
    "Creates calendar events with timezone attendees and recurrence rules "
    "for a named mailbox."
)


def _find(caps: list[dict], cid: str) -> dict:
    for cap in caps:
        if L.cap_id(cap) == cid:
            return cap
    raise KeyError(cid)


def both_states(caps: list[dict]) -> dict:
    """Pick a capability that currently HAS negative scope; strip it; compare."""
    with_neg = next(c for c in caps if L.has_negative_scope(c))
    cid = L.cap_id(with_neg)
    good = copy.deepcopy(caps)
    good_ids = set(L.zero_negative_scope(good)["ids"])
    bad = copy.deepcopy(caps)
    target = _find(bad, cid)
    target["description"] = (
        "Validates credentials against a store and rejects expired rows. "
        "Use when the user asks to check a key."
    )
    for key in ("negative_scope", "do_not_use_for", "do_not_use", "not_for"):
        target.pop(key, None)
    bad_ids = set(L.zero_negative_scope(bad)["ids"])
    good_in = cid in good_ids
    bad_in = cid in bad_ids
    return {
        "capability_id": cid,
        "with_clause_in_zero_set": good_in,
        "without_clause_in_zero_set": bad_in,
        "discriminates": (not good_in) and bad_in,
        "same_answer_both_states": good_in == bad_in,
    }


def main() -> int:
    caps, loaded = L.load_index(INDEX)
    live = L.lint(caps, top_n=20)
    states = both_states(caps)
    spec = json.loads(MUTANT.read_text(encoding="utf-8"))
    distinct_caps = L.apply_rename_paraphrase(
        caps,
        source_id=spec["source_id"],
        sibling_id=spec["sibling_id"],
        new_id=spec["new_id"],
        paraphrase=DISTINCT,
    )
    distinct_rank = L.lint(distinct_caps, top_n=20)["confusability"]["top_20"]
    distinct_hit = L.pair_in_top(
        distinct_rank, spec["new_id"], spec["sibling_id"], k=5
    )

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:IMP-0388-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        print("FAILED:IMP-0388-probe2 sentinel absent")
        return 1
    if doc.get("unit_id") != "IMP-0388":
        print("FAILED:IMP-0388-probe2 unit_id", doc.get("unit_id"))
        return 1

    rec_zeros = doc.get("zero_negative_scope") or {}
    live_zeros = live["zero_negative_scope"]
    rec_most = (doc.get("confusability") or {}).get("most_confusable_pair") or {}
    live_most = live["confusability"]["most_confusable_pair"]

    payload = {
        "probe": "probe2-negative-scope-both-states",
        "index": loaded,
        "both_states": states,
        "distinct_rewrite_in_top_5": distinct_hit is not None,
        "receipt_zero_count": rec_zeros.get("count"),
        "live_zero_count": live_zeros["count"],
        "receipt_most": [rec_most.get("id_a"), rec_most.get("id_b")],
        "live_most": [live_most["id_a"], live_most["id_b"]],
        "live_most_score": live_most["token_overlap_score"],
    }
    print(json.dumps(payload, sort_keys=True))

    if not states["discriminates"] or states["same_answer_both_states"]:
        print("FAILED:IMP-0388-probe2 negative-scope detector silent on both states")
        return 1
    if rec_zeros.get("count") != live_zeros["count"]:
        print(
            "FAILED:IMP-0388-probe2 zero-count mismatch "
            f"receipt={rec_zeros.get('count')} live={live_zeros['count']}"
        )
        return 1
    if list(rec_zeros.get("ids") or []) != live_zeros["ids"]:
        print("FAILED:IMP-0388-probe2 zero-scope id list mismatch")
        return 1
    rec_pair = frozenset({rec_most.get("id_a"), rec_most.get("id_b")})
    live_pair = frozenset({live_most["id_a"], live_most["id_b"]})
    if rec_pair != live_pair:
        print("FAILED:IMP-0388-probe2 most-confusable pair mismatch")
        return 1
    rec_score = rec_most.get("token_overlap_score")
    if rec_score != live_most["token_overlap_score"]:
        print("FAILED:IMP-0388-probe2 token_overlap_score mismatch")
        return 1
    rec_top = (doc.get("confusability") or {}).get("top_20") or []
    if len(rec_top) < 20:
        print(f"FAILED:IMP-0388-probe2 top_20 length {len(rec_top)}")
        return 1
    for i, (a, b) in enumerate(zip(rec_top[:20], live["confusability"]["top_20"][:20])):
        if (a.get("id_a"), a.get("id_b"), a.get("token_overlap_score")) != (
            b["id_a"],
            b["id_b"],
            b["token_overlap_score"],
        ):
            print(f"FAILED:IMP-0388-probe2 top_20 row {i} mismatch")
            return 1
        if not a.get("description_a") or not a.get("description_b"):
            print(f"FAILED:IMP-0388-probe2 top_20 row {i} missing quoted descriptions")
            return 1
    if distinct_hit is not None:
        print("FAILED:IMP-0388-probe2 distinct rewrite wrongly in top 5")
        return 1
    if rec_zeros.get("count") != len(rec_zeros.get("ids") or []):
        print("FAILED:IMP-0388-probe2 count != len(ids)")
        return 1
    print(
        f"both_states_ok={states['discriminates']} "
        f"zeros={live_zeros['count']} "
        f"most={live_most['id_a']}|{live_most['id_b']} "
        f"distinct_control=held"
    )
    print("SUCCESS:IMP-0388-probe2 negative-scope both-states and receipt honesty")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
