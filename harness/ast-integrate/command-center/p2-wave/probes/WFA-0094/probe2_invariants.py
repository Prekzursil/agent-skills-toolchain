#!/usr/bin/env python3
"""Probe 2: self-diff empty, ABSENT vs PRESENT-BUT-DIFFERENT, set compare, reviewer."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import differ as D  # noqa: E402
import fixtures as F  # noqa: E402
import reviewer as R  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0094-semantic-diff-engine.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0094-probe2 {msg}")
    return 1


def main() -> int:
    n = 0
    for ir in F.corpus():
        n += 1
        sd = D.self_diff(ir)
        od = D.order_invariant(ir)
        print(f"corpus id={ir['id']} self_empty={sd['empty']} order_empty={od['empty']}")
        if not D.empty_report(sd):
            return fail(f"self-diff nonempty id={ir['id']} sig={D.signature(sd)}")
        if not D.empty_report(od):
            return fail(f"order-shuffle nonempty id={ir['id']} sig={D.signature(od)}")
    print(f"corpus_n={n} all_self_empty=True all_order_empty=True")

    left, changed = F.present_but_different_pair()
    ch = D.diff_irs(left, changed)
    gate = next(d for d in ch["dimensions"] if d["dimension"] == "gate")
    print(
        f"present_but_different gate.changed={len(gate['changed'])} "
        f"left_only={len(gate['left_only'])} right_only={len(gate['right_only'])} "
        f"kind={gate['changed'][0]['kind'] if gate['changed'] else None}"
    )
    if (
        len(gate["changed"]) != 1
        or gate["changed"][0]["kind"] != D.KIND_CHANGED
        or gate["left_only"]
        or gate["right_only"]
    ):
        return fail("PRESENT-BUT-DIFFERENT was collapsed into ABSENT")

    left, missing = F.absent_tool_pair()
    ab = D.diff_irs(left, missing)
    tool = next(d for d in ab["dimensions"] if d["dimension"] == "tool")
    print(
        f"absent_tool left_only={len(tool['left_only'])} "
        f"changed={len(tool['changed'])} "
        f"kind={tool['left_only'][0]['kind'] if tool['left_only'] else None}"
    )
    if (
        len(tool["left_only"]) != 1
        or tool["left_only"][0]["id"] != "t-read"
        or tool["left_only"][0]["kind"] != D.KIND_ABSENT
        or tool["changed"]
    ):
        return fail("ABSENT was collapsed into PRESENT-BUT-DIFFERENT")

    rev = R.review()
    print(
        f"reviewer verdict={rev['verdict']} both_states_rerun={rev['both_states_rerun']} "
        f"gold_ok={rev['known_diff_gold_signature_match']} "
        f"self_ok={rev['known_empty_self_diff']}"
    )
    if rev["verdict"] != "PASS" or not rev["both_states_rerun"]:
        return fail(f"reviewer {rev['verdict']}")

    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("sentinel") != "SUCCESS:WFA-0094":
        return fail("artifact sentinel")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared:{doc.get('state')}")
    if doc.get("evidence_b", {}).get("all_self_empty") is not True:
        return fail("artifact evidence_b not empty")
    print("SUCCESS:WFA-0094-probe2 self-diff absent-vs-changed sets reviewer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
