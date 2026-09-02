"""Independent both-states re-run of the WFA-0094 controls.

Does not author the differ. Re-imports differ/fixtures and asserts:
  known-diff state: gold pair matches the hand-written signature
  known-empty state: self-diff and order-shuffle are empty on the whole corpus
"""
from __future__ import annotations

from typing import Any

import differ as D
import fixtures as F


def review() -> dict[str, Any]:
    gold = D.diff_irs(F.gold_left(), F.gold_right())
    got = D.signature(gold)
    want = sorted(F.GOLD_SIGNATURE)
    gold_ok = got == want

    self_empty = True
    order_empty = True
    n = 0
    for ir in F.corpus():
        n += 1
        if not D.empty_report(D.self_diff(ir)):
            self_empty = False
        if not D.empty_report(D.order_invariant(ir)):
            order_empty = False

    left, changed = F.present_but_different_pair()
    ch = D.diff_irs(left, changed)
    gate = next(d for d in ch["dimensions"] if d["dimension"] == "gate")
    changed_ok = (
        len(gate["changed"]) == 1
        and gate["changed"][0]["kind"] == D.KIND_CHANGED
        and not gate["left_only"]
        and not gate["right_only"]
    )

    left, missing = F.absent_tool_pair()
    ab = D.diff_irs(left, missing)
    tool = next(d for d in ab["dimensions"] if d["dimension"] == "tool")
    absent_ok = (
        len(tool["left_only"]) == 1
        and tool["left_only"][0]["kind"] == D.KIND_ABSENT
        and tool["left_only"][0]["id"] == "t-read"
        and not tool["changed"]
    )

    both_states = gold_ok and self_empty
    verdict = (
        "PASS"
        if both_states and order_empty and changed_ok and absent_ok
        else "FAIL"
    )
    return {
        "reviewer_id": "WFA-0094-both-states-rerun",
        "independent": True,
        "verdict": verdict,
        "both_states_rerun": True,
        "known_diff_gold_signature_match": gold_ok,
        "known_empty_self_diff": self_empty,
        "order_shuffle_empty": order_empty,
        "present_but_different_not_collapsed": changed_ok,
        "absent_not_collapsed_into_changed": absent_ok,
        "corpus_n": n,
        "gold_got": got,
        "gold_want": want,
    }
