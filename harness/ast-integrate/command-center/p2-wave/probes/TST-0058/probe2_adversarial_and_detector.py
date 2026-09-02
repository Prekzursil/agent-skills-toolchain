#!/usr/bin/env python3
"""Probe 2: adversarial docs rejected by both; detector fires on unaligned JSONC."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

from tools.json_ingest import jsonc_loads, strict_loads  # noqa: E402

import corpus as C  # noqa: E402
import matrix as M  # noqa: E402


def main() -> int:
    prod = M.production_matrix()
    t2 = M.test_the_adversarial_documents_are_rejected_by_both(prod)
    ctrl = M.control_matrix()
    identical_disagree = 0
    for rel in C.require_corpus()["adversarial_paths"]:
        text = (REPO / rel).read_text(encoding="utf-8")
        a = strict_loads(text)
        b = strict_loads(text)
        if a.accepted != b.accepted:
            identical_disagree += 1

    jsonc_fail = [
        r
        for r in ctrl["rows"]
        if r.get("jsonc") != "accept" or r.get("strict") != "reject"
    ]
    report = {
        "probe": "probe2-adversarial-and-detector",
        "unit_id": "TST-0058",
        "adversarial_both_reject": prod["adversarial_both_reject"],
        "adversarial_count": prod["adversarial_count"],
        "test_adversarial": t2,
        "control_planted_divergence_count": ctrl["planted_divergence_count"],
        "control_jsonc_accept_count": ctrl["jsonc_accept_count"],
        "control_strict_reject_count": ctrl["strict_reject_count"],
        "identical_pair_disagreements": identical_disagree,
        "jsonc_fail_rows": jsonc_fail[:6],
        "pass": (
            t2["ok"]
            and ctrl["planted_divergence_count"] == ctrl["adversarial_count"]
            and ctrl["jsonc_accept_count"] == ctrl["adversarial_count"]
            and identical_disagree == 0
            and prod["disagreement_count"] == 0
        ),
    }
    print(json.dumps(report, sort_keys=True))
    print(
        f"adv_both_reject={prod['adversarial_both_reject']}/{prod['adversarial_count']} "
        f"planted={ctrl['planted_divergence_count']} "
        f"jsonc_accept={ctrl['jsonc_accept_count']} "
        f"identical_disagree={identical_disagree}"
    )
    if not t2["ok"]:
        print("FAILED:TST-0058-probe2 adversarial documents not rejected by both")
        return 1
    if ctrl["jsonc_accept_count"] != ctrl["adversarial_count"]:
        print("FAILED:TST-0058-probe2 jsonc control parser did not accept adversarial corpus")
        print(json.dumps(jsonc_fail[:4], indent=1, sort_keys=True))
        return 1
    if ctrl["planted_divergence_count"] != ctrl["adversarial_count"]:
        print(
            "FAILED:TST-0058-probe2 detector silent on unaligned jsonc vs strict "
            "(constant-green)"
        )
        return 1
    if identical_disagree != 0:
        print("FAILED:TST-0058-probe2 identical strict/strict pair reported disagreement")
        return 1
    if prod["disagreement_count"] != 0:
        print("FAILED:TST-0058-probe2 production pair is not silent")
        return 1
    print(
        "SUCCESS:TST-0058-probe2 adversarial rejected by both; "
        "unaligned jsonc detector fires; aligned pair silent"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
