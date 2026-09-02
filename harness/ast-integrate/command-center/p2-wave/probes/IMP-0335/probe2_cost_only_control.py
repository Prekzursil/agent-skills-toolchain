#!/usr/bin/env python3
"""Probe 2: outer-ring-removed negative control and promotion-trigger audit.

Independent of probe1's membership narrative. Re-runs the 15-council corpus
with the outer ring stripped. Unchanged decision sets are classified
cost-only. The citation metric is not replaced by the vanity
any-observer-note rate. Every promotion event is re-checked against its
declared trigger. Both-states: a full inner refuses empty-seat promotion;
an open seat accepts it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

import suite as S  # noqa: E402


def main() -> int:
    fails: list[str] = []
    fails.extend(S.check_promotion_both_states())
    corpus_fails, measured = S.check_corpus()
    fails.extend(corpus_fails)
    nc = measured["negative_control"]
    if measured["classification"] == "contributes" and nc["unchanged_runs"]:
        fails.append("classification hid cost-only instances")
    if measured["observer_contribution_rate"] == measured["vanity_note_presence_rate"]:
        fails.append("published rate equals vanity; metric was tuned")
    receipt = REPO / "command-center/receipts/IMP-0335.json"
    if receipt.is_file():
        doc = json.loads(receipt.read_text(encoding="utf-8"))
        if str(doc.get("reviewer_verdict") or "").upper() != "PASS":
            fails.append(f"reviewer_verdict {doc.get('reviewer_verdict')}")
    print(
        "cost_only_instances="
        f"{nc['cost_only_instances']} "
        f"changed={len(nc['changed_runs'])} "
        f"classification={measured['classification']} "
        f"published_rate={measured['observer_contribution_rate']} "
        f"vanity={measured['vanity_note_presence_rate']} "
        f"audit_ok={measured['promotion_audit']['all_match_declared_trigger']}"
    )
    if fails:
        print("FAILED:IMP-0335-probe2 " + "; ".join(fails))
        return 1
    print(
        "SUCCESS:IMP-0335-probe2 outer-ring-removed control; "
        "cost-only reported not retuned; promotion audit matches triggers"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
