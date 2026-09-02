#!/usr/bin/env python3
"""Probe 2: independent blake2s line-hash differ + refuse-without-decision.

Mechanically different from probe 1's str-set packet differ. Requires set
equality of unique lines. Also the negative control: acting on DIVERGED
without a recorded decision is refused. Recommendation cannot authorise act.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

import fixtures as F  # noqa: E402
from plugin.classifier import DIVERGED, one_directional_repo_extra  # noqa: E402
from plugin.gate import REFUSE_NO_DECISION, act  # noqa: E402
from plugin.independent_differ import unique_line_sets_via_hash  # noqa: E402
from plugin.packet import emit_packet, record_decision  # noqa: E402
from plugin.tests.test_divergence_packet import (  # noqa: E402
    test_packet_contains_both_unique_sets,
    test_recommendation_is_advisory_not_decision,
    test_refuse_act_without_recorded_decision,
)

OUT = HERE / "probe2-independent.raw.json"


def main() -> int:
    F.build_fixtures()
    ledger = F.load_ledger()
    equal = 0
    mismatches: list[dict] = []
    refused = 0
    allowed_after_record = 0
    mutant_fired = 0
    mtime_not_authorship = 0
    size_not_authorship = 0

    for rel in F.PATHS:
        repo_text, live_text, _rp, lp = F.read_pair(rel)
        packet = emit_packet(
            path=rel,
            repo_text=repo_text,
            live_text=live_text,
            repo_root=REPO,
            live_path=lp,
            ledger=ledger,
        )
        ru, lu = unique_line_sets_via_hash(repo_text, live_text)
        pkt_ru, pkt_lu = set(packet["repo_unique_lines"]), set(packet["live_unique_lines"])
        if ru != pkt_ru or lu != pkt_lu:
            mismatches.append(
                {
                    "path": rel,
                    "packet_repo": sorted(pkt_ru),
                    "hash_repo": sorted(ru),
                    "packet_live": sorted(pkt_lu),
                    "hash_live": sorted(lu),
                }
            )
        else:
            equal += 1

        if packet["classification"] == DIVERGED:
            denied = act(packet, "TAKE-LIVE")
            if not (denied["refused"] is True and denied["reason"] == REFUSE_NO_DECISION):
                print("FAILED:IMP-0036-probe2 DIVERGED act not refused")
                return 1
            refused += 1
            recorded = record_decision(packet, "KEEP-BOTH")
            allowed = act(recorded, "KEEP-BOTH")
            if not allowed["ok"]:
                print("FAILED:IMP-0036-probe2 recorded decision not honoured")
                return 1
            allowed_after_record += 1
            mutant = one_directional_repo_extra(repo_text, live_text)
            if mutant == DIVERGED:
                print("FAILED:IMP-0036-probe2 mutant still reports DIVERGED")
                return 1
            mutant_fired += 1
            if packet["mtime_is_authorship_signal"] is False and packet["recommendation"]["action"] == "HOLD-FOR-RECORDED-DECISION":
                mtime_not_authorship += 1
            if packet["size_is_authorship_signal"] is False:
                size_not_authorship += 1

    if mismatches:
        print("FAILED:IMP-0036-probe2 independent differ mismatch")
        print(json.dumps(mismatches[:3], indent=2))
        return 1
    if equal != 28:
        print(f"FAILED:IMP-0036-probe2 equal={equal}")
        return 1
    if refused != 20 or allowed_after_record != 20 or mutant_fired != 20:
        print("FAILED:IMP-0036-probe2 gate counts")
        return 1

    test_packet_contains_both_unique_sets()
    test_refuse_act_without_recorded_decision()
    test_recommendation_is_advisory_not_decision()

    payload = {
        "probe": "probe2-independent-differ",
        "unit_id": "IMP-0036",
        "independent_differ": "blake2s-16 line-hash set difference",
        "packet_differ": "plugin.lines unique_line_sets (str set, first-seen order)",
        "set_equality": equal,
        "mismatches": 0,
        "diverged_refused_without_decision": refused,
        "diverged_allowed_after_record": allowed_after_record,
        "one_directional_mutant_misclassified": mutant_fired,
        "mtime_not_authorship": mtime_not_authorship,
        "size_not_authorship": size_not_authorship,
        "unit_tests": [
            "test_packet_contains_both_unique_sets",
            "test_refuse_act_without_recorded_decision",
            "test_recommendation_is_advisory_not_decision",
        ],
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        "set_equality="
        + str(equal)
        + " refused_without_decision="
        + str(refused)
        + " allowed_after_record="
        + str(allowed_after_record)
        + " mutant_misclassified="
        + str(mutant_fired)
        + " mtime_not_authorship="
        + str(mtime_not_authorship)
        + " size_not_authorship="
        + str(size_not_authorship)
    )
    print("SUCCESS:IMP-0036-probe2 independent differ and refuse-without-decision")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
