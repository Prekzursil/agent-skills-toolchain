#!/usr/bin/env python3
"""Probe 1: 7-vote unbacked majority loses to 2-vote backed minority.

Both-states: the same 7-2 split with every ballot backed must follow the
ordinary tally (majority wins). A gate that inverts both states is a
round-counter, not an evidence gate.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.vote import evidence_gate as G  # noqa: E402

ART = REPO / "command-center/receipts/TST-0262.json"
OUT = HERE / "probe1-minority-wins.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0262-probe1 {msg}")
    return 1


def main() -> int:
    report = G.run_required_controls()
    fails = G.assertions(report)
    if fails:
        return fail("; ".join(fails))

    rec1 = report["minority_vs_unbacked_majority"]
    rec2 = report["both_states_all_backed"]

    raw_maj = int(rec1["raw_tally"][G.MAJORITY_CHOICE])
    raw_min = int(rec1["raw_tally"][G.MINORITY_CHOICE])
    count_maj = int(rec1["counting_tally"].get(G.MAJORITY_CHOICE, 0))
    count_min = int(rec1["counting_tally"][G.MINORITY_CHOICE])

    if rec1["outcome"] != G.MINORITY_CHOICE:
        return fail(f"outcome={rec1['outcome']}")
    if rec2["outcome"] != G.MAJORITY_CHOICE:
        return fail(f"both-states inverted tally outcome={rec2['outcome']}")
    if raw_maj != 7 or raw_min != 2:
        return fail(f"raw numbers {raw_maj} vs {raw_min}")
    if count_maj != 0 or count_min != 2:
        return fail(f"counting numbers {count_maj} vs {count_min}")
    if rec1["annotated_only_winner"]["outcome"] != G.MAJORITY_CHOICE:
        return fail("annotation-only contrast lost the majority")
    if rec1["annotated_only_winner"]["outcome"] == rec1["outcome"]:
        return fail("gate still counts unbacked ballots")

    why = rec1["why_text"]
    if str(raw_maj) not in why and "unbacked" not in why.lower():
        return fail("decision record missing unbacked-majority why")
    if G.MINORITY_CHOICE not in why and "outvoted" not in why.lower():
        return fail("decision record missing minority/outvoted why")

    payload = {
        "probe": "probe1-minority-wins",
        "unit_id": "TST-0262",
        "pass": True,
        "raw_majority_votes": raw_maj,
        "raw_minority_votes": raw_min,
        "counting_majority_votes": count_maj,
        "backed_minority_votes": count_min,
        "gated_outcome": rec1["outcome"],
        "raw_outcome": rec1["raw_winner"]["outcome"],
        "both_states_outcome": rec2["outcome"],
        "gate_outranks_popularity": rec1["gate_outranks_popularity"],
        "why_text": why,
        "decision_record": {
            "election_id": rec1["election_id"],
            "raw_tally": rec1["raw_tally"],
            "counting_tally": rec1["counting_tally"],
            "outcome": rec1["outcome"],
            "binding": rec1["binding"],
            "why": rec1["why"],
        },
    }

    if ART.is_file():
        receipt = json.loads(ART.read_text(encoding="utf-8"))
        text = ART.read_text(encoding="utf-8")
        if "SUCCESS:TST-0262" not in text:
            return fail("receipt sentinel-absent")
        if str(receipt.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            return fail(f"receipt self-declared {receipt.get('state')}")
        if receipt.get("unit_id") != "TST-0262":
            return fail("receipt unit_id")
        live_raw = receipt.get("raw_majority_votes")
        live_backed = receipt.get("backed_minority_votes")
        if live_raw != raw_maj or live_backed != count_min:
            return fail(
                f"receipt numbers drift raw={live_raw} backed={live_backed} "
                f"live={raw_maj}/{count_min}"
            )
        if receipt.get("gated_outcome") != rec1["outcome"]:
            return fail("receipt gated_outcome disagrees with live")
        if receipt.get("both_states_outcome") != rec2["outcome"]:
            return fail("receipt both_states_outcome disagrees with live")
        payload["receipt_matches_live"] = True
    else:
        payload["receipt_matches_live"] = False

    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    print(
        f"raw={raw_maj}vs{raw_min} counting={count_maj}vs{count_min} "
        f"outcome={rec1['outcome']} both_states={rec2['outcome']}"
    )
    print("SUCCESS:TST-0262-probe1 unbacked majority loses to backed minority")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
