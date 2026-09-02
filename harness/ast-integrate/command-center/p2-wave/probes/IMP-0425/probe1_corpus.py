#!/usr/bin/env python3
"""Probe 1: historical receipts rejected; matched genuine results accepted.

Runs the role-aware fan-in gate over a corpus of at least three known
receipt-shaped payloads (all must be FAILED / unable to satisfy the barrier)
and a matched set of genuine results that discuss the same phrases as
subject matter (all must be ACCEPTED). A gate that rejects both is the
use-vs-mention defect.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import suite as S  # noqa: E402


def main() -> int:
    report = S.run_corpus()
    print(
        "historical_all_rejected="
        f"{report['historical_all_rejected']} "
        "genuine_all_accepted="
        f"{report['genuine_all_accepted']} "
        "naive_foil_rejects_genuine="
        f"{report['naive_foil_rejects_genuine']} "
        "use_vs_mention_ok="
        f"{report['use_vs_mention_ok']} "
        "receipt_cannot_satisfy_barrier="
        f"{report['receipt_cannot_satisfy_barrier']}"
    )
    for r in report["historical"]:
        print(
            f"receipt[{r['id']}] decision={r['got_decision']} "
            f"role={r['got_role']} barrier={r['barrier_satisfied']} ok={r['ok']}"
        )
    for r in report["genuine"]:
        print(
            f"genuine[{r['id']}] decision={r['got_decision']} "
            f"role={r['got_role']} naive={r['naive_decision']} ok={r['ok']}"
        )
    if not report["historical_all_rejected"]:
        print("FAILED:IMP-0425-probe1 a known receipt was not rejected")
        return 1
    if not report["genuine_all_accepted"]:
        print("FAILED:IMP-0425-probe1 a genuine result that discusses receipts was rejected")
        return 1
    if not report["naive_foil_rejects_genuine"]:
        print("FAILED:IMP-0425-probe1 naive substring foil did not reject genuine mentions")
        return 1
    if not report["use_vs_mention_ok"]:
        print("FAILED:IMP-0425-probe1 use-vs-mention control failed")
        return 1
    if not report["receipt_cannot_satisfy_barrier"]:
        print("FAILED:IMP-0425-probe1 a receipt could satisfy the barrier")
        return 1
    art_ok, why = S.artifact_ok()
    if not art_ok:
        print(f"FAILED:IMP-0425-probe1 artifact {why}")
        return 1
    print("SUCCESS:IMP-0425-probe1 corpus receipts rejected, genuine mentions accepted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
