#!/usr/bin/env python3
"""Probe 1: no document is accepted by one production path and rejected by the other."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

import matrix as M  # noqa: E402

OUT = REPO / "command-center/receipts/TST-0058.json"


def main() -> int:
    live = M.production_matrix()
    t1 = M.test_no_document_is_accepted_by_one_path_and_rejected_by_the_other(live)
    t2 = M.test_the_adversarial_documents_are_rejected_by_both(live)
    report = {
        "probe": "probe1-agreement-matrix",
        "unit_id": "TST-0058",
        "real_count": live["real_count"],
        "adversarial_count": live["adversarial_count"],
        "disagreement_count": live["disagreement_count"],
        "real_both_accept": live["real_both_accept"],
        "adversarial_both_reject": live["adversarial_both_reject"],
        "tests": [t1, t2],
        "pass": t1["ok"] and t2["ok"],
    }
    print(json.dumps(report, sort_keys=True))
    print(
        f"real={live['real_count']} adv={live['adversarial_count']} "
        f"disagree={live['disagreement_count']} "
        f"real_both_accept={live['real_both_accept']} "
        f"adv_both_reject={live['adversarial_both_reject']}"
    )
    if not t1["ok"]:
        print("FAILED:TST-0058-probe1 accept/reject disagreement on production pair")
        if live["disagreements"]:
            print(json.dumps(live["disagreements"][:5], indent=1, sort_keys=True))
        return 1
    if live["real_count"] < 50:
        print(f"FAILED:TST-0058-probe1 real corpus {live['real_count']} < 50")
        return 1
    if not OUT.is_file():
        print("FAILED:TST-0058-probe1 receipt missing")
        return 1
    text = OUT.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:TST-0058" not in text:
        print("FAILED:TST-0058-probe1 sentinel absent in receipt")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:TST-0058-probe1 receipt state={doc.get('state')}")
        return 1
    ev = doc.get("evidence") or {}
    if int(ev.get("real_count") or 0) != live["real_count"]:
        print(
            "FAILED:TST-0058-probe1 receipt real_count "
            f"{ev.get('real_count')} != live {live['real_count']}"
        )
        return 1
    if "disagreement_count" not in ev or ev.get("disagreement_count") != 0:
        print(
            "FAILED:TST-0058-probe1 receipt disagreement_count="
            f"{ev.get('disagreement_count')!r}"
        )
        return 1
    print(
        "SUCCESS:TST-0058-probe1 no accept/reject split on "
        f"{live['real_count']}+{live['adversarial_count']} documents"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
