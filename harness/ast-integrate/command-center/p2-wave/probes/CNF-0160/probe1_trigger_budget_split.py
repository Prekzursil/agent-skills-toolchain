#!/usr/bin/env python3
"""Probe 1: trigger control, three-way split → AMBIGUOUS-CLAIM, budget cap."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from recruit import apply_rule, load_ledger, load_thirds  # noqa: E402
from rule import (  # noqa: E402
    AMBIGUOUS_CLAIM,
    CONVERGENT_ANTHROPIC,
    CONVERGENT_CODEX,
    DEFAULT_BUDGET_CAP,
    is_casting_vote,
    resolve_three_way,
)

ART = REPO / "command-center/receipts/CNF-0160.json"
AGREE_IDS = ("C-AGREE-001", "C-AGREE-002")
SETTLED_IDS = ("C-SETTLED-003", "C-SETTLED-004")
SPLIT_ID = "C-IRRED-SPLIT-007"
BUDGET_HELD_IDS = ("C-IRRED-BUDGET-008", "C-IRRED-BUDGET-009")
RECRUITED_IDS = (
    "C-IRRED-CONVERGE-A-005",
    "C-IRRED-CONVERGE-C-006",
    "C-IRRED-SPLIT-007",
)


def naive_majority(a: str, b: str, c: str) -> str | None:
    """What a forbidden majority vote would return. Must not match our resolver."""
    top, n = Counter([a, b, c]).most_common(1)[0]
    if n >= 2:
        return top
    return None


def by_id(run: dict) -> dict:
    return {e["claim_id"]: e for e in run["evaluations"]}


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0160-probe1 receipt missing")
        return 1
    receipt = json.loads(ART.read_text(encoding="utf-8"))
    text = json.dumps(receipt)
    if receipt.get("unit_id") != "CNF-0160":
        print("FAILED:CNF-0160-probe1 unit_id", receipt.get("unit_id"))
        return 1
    if "SUCCESS:CNF-0160" not in text:
        print("FAILED:CNF-0160-probe1 sentinel absent")
        return 1
    if str(receipt.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:CNF-0160-probe1 self-declared", receipt.get("state"))
        return 1

    ledger = load_ledger()
    thirds = load_thirds()
    live = apply_rule(ledger, thirds, rail_available=True, cap=DEFAULT_BUDGET_CAP)
    rows = by_id(live)

    # Trigger control: agreeing vendors must NOT escalate, even with planted thirds.
    for cid in AGREE_IDS:
        ev = rows[cid]
        if ev["trigger_fired"] or ev["recruited"]:
            print(f"FAILED:CNF-0160-probe1 agree {cid} escalated={ev}")
            return 1
        if "vendors-agree" not in ev["inhibit_reasons"]:
            print(f"FAILED:CNF-0160-probe1 agree {cid} missing vendors-agree")
            return 1

    for cid in SETTLED_IDS:
        ev = rows[cid]
        if ev["trigger_fired"] or ev["recruited"]:
            print(f"FAILED:CNF-0160-probe1 settled {cid} escalated")
            return 1
        if "cnf0155-settled-executably" not in ev["inhibit_reasons"]:
            print(f"FAILED:CNF-0160-probe1 settled {cid} missing settled inhibit")
            return 1

    # Three-way split: CONFIRMED / REFUTED / PARTIAL → AMBIGUOUS-CLAIM, not a vote.
    split_direct = resolve_three_way("CONFIRMED", "REFUTED", "PARTIAL")
    majority = naive_majority("CONFIRMED", "REFUTED", "PARTIAL")
    casting = "PARTIAL"
    if split_direct != AMBIGUOUS_CLAIM:
        print("FAILED:CNF-0160-probe1 resolver", split_direct)
        return 1
    if is_casting_vote(split_direct):
        print("FAILED:CNF-0160-probe1 casting vote", split_direct)
        return 1
    if split_direct == majority or split_direct == casting:
        print(
            f"FAILED:CNF-0160-probe1 split collapsed to vote "
            f"ours={split_direct} majority={majority} casting={casting}"
        )
        return 1

    split = rows[SPLIT_ID]
    if not split["recruited"] or split["triangulation_outcome"] != AMBIGUOUS_CLAIM:
        print("FAILED:CNF-0160-probe1 split row", split)
        return 1
    if split["two_way_fallback_used"] or split["casting_vote_used"]:
        print("FAILED:CNF-0160-probe1 split used vote")
        return 1

    conv_a = rows["C-IRRED-CONVERGE-A-005"]
    conv_c = rows["C-IRRED-CONVERGE-C-006"]
    if conv_a["triangulation_outcome"] != CONVERGENT_ANTHROPIC:
        print("FAILED:CNF-0160-probe1 converge-A", conv_a["triangulation_outcome"])
        return 1
    if conv_c["triangulation_outcome"] != CONVERGENT_CODEX:
        print("FAILED:CNF-0160-probe1 converge-C", conv_c["triangulation_outcome"])
        return 1
    if is_casting_vote(conv_a["triangulation_outcome"]) or is_casting_vote(
        conv_c["triangulation_outcome"]
    ):
        print("FAILED:CNF-0160-probe1 convergent collapsed to claim verdict")
        return 1

    # Budget: escalated count stays within cap; 4th/5th IRREDUCIBLE held.
    if live["escalated_count"] != DEFAULT_BUDGET_CAP:
        print(
            f"FAILED:CNF-0160-probe1 escalated={live['escalated_count']} "
            f"cap={DEFAULT_BUDGET_CAP}"
        )
        return 1
    if not live["escalated_within_cap"]:
        print("FAILED:CNF-0160-probe1 over cap")
        return 1
    if live["recruited_claim_ids"] != list(RECRUITED_IDS):
        print("FAILED:CNF-0160-probe1 recruited ids", live["recruited_claim_ids"])
        return 1
    for cid in BUDGET_HELD_IDS:
        ev = rows[cid]
        if ev["recruited"] or ev["trigger_fired"]:
            print(f"FAILED:CNF-0160-probe1 budget held {cid} recruited")
            return 1
        if "budget-exhausted" not in ev["inhibit_reasons"]:
            print(f"FAILED:CNF-0160-probe1 budget held {cid} {ev['inhibit_reasons']}")
            return 1

    if live["two_way_fallback_anywhere"] or live["casting_vote_anywhere"]:
        print("FAILED:CNF-0160-probe1 vote used in run")
        return 1

    # Receipt must match the live re-run (not a narrative).
    rec_eval = {
        e["claim_id"]: e
        for e in (receipt.get("trigger_evaluations") or [])
        if isinstance(e, dict)
    }
    if set(rec_eval) != set(rows):
        print(
            "FAILED:CNF-0160-probe1 receipt eval ids",
            sorted(rec_eval),
            sorted(rows),
        )
        return 1
    for cid, ev in rows.items():
        other = rec_eval[cid]
        if bool(other.get("recruited")) != bool(ev["recruited"]):
            print(f"FAILED:CNF-0160-probe1 receipt recruited drift {cid}")
            return 1
        if other.get("triangulation_outcome") != ev["triangulation_outcome"]:
            print(f"FAILED:CNF-0160-probe1 receipt outcome drift {cid}")
            return 1
        if bool(other.get("trigger_fired")) != bool(ev["trigger_fired"]):
            print(f"FAILED:CNF-0160-probe1 receipt trigger drift {cid}")
            return 1

    if receipt.get("source_probe", {}).get("fingerprint") == receipt.get(
        "verifier_probe", {}
    ).get("fingerprint"):
        print("FAILED:CNF-0160-probe1 same-probe-rerun fingerprints")
        return 1
    if not receipt.get("source_probe", {}).get("fingerprint"):
        print("FAILED:CNF-0160-probe1 empty source_probe")
        return 1

    summary = {
        "probe": "probe1-trigger-budget-split",
        "unit_id": "CNF-0160",
        "agree_not_escalated": True,
        "settled_not_escalated": True,
        "three_way_outcome": split_direct,
        "majority_would_have_returned": majority,
        "casting_would_have_returned": casting,
        "escalated_count": live["escalated_count"],
        "budget_cap": DEFAULT_BUDGET_CAP,
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"agree_held={list(AGREE_IDS)} split={split_direct} "
        f"escalated={live['escalated_count']}/{DEFAULT_BUDGET_CAP}"
    )
    print("SUCCESS:CNF-0160-probe1 trigger control, three-way split, budget")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
