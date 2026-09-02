#!/usr/bin/env python3
"""Probe 2: confusion matrix before/after + adversarial refuter.

Before = naive payload-text matcher (historical FP rate 1.0).
After  = semantic-role library (historical FP rate 0.0).
Each surviving false positive is emitted as the raw record.
The refuter constructs held-out mentions (must not fire) and held-out uses
(must fire). Both-states: naive fires on those mentions; role does not.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "hooks" / "_shared"))

import corpus as C  # noqa: E402
import use_vs_mention as uvm  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0470.json"
SENTINEL = "SENTINEL:IMP-0470:ROLE-BASED-DETECTION"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def main() -> int:
    hist = C.historical_false_positives()
    before = uvm.confusion_matrix(hist, mode="naive")
    after = uvm.confusion_matrix(hist, mode="role")
    surviving = uvm.surviving_false_positives(hist)
    adv_m = C.adversarial_mentions()
    adv_u = C.adversarial_uses()
    adv_m_role_fires = [
        r["id"] for r in adv_m if uvm.classify_record(r, mode="role")["fires"]
    ]
    adv_u_role_miss = [
        r["id"] for r in adv_u if not uvm.classify_record(r, mode="role")["fires"]
    ]
    adv_m_naive = [
        r["id"] for r in adv_m if uvm.classify_record(r, mode="naive")["fires"]
    ]
    both_states = []
    for rec in adv_m:
        n = uvm.classify_record(rec, mode="naive")["fires"]
        r = uvm.classify_record(rec, mode="role")["fires"]
        both_states.append({"id": rec["id"], "naive_fires": n, "role_fires": r})
        if not n or r:
            print(f"FAILED:IMP-0470-probe2 both-states {rec['id']} naive={n} role={r}")
            return 1

    summary = {
        "probe": "probe2-confusion-refute",
        "historical_n": len(hist),
        "fp_rate_before": before["false_positive_rate"],
        "fp_rate_after": after["false_positive_rate"],
        "before": {k: before[k] for k in ("tp", "fp", "fn", "tn", "labelled")},
        "after": {k: after[k] for k in ("tp", "fp", "fn", "tn", "labelled")},
        "surviving_false_positive_ids": [s["id"] for s in surviving],
        "surviving_false_positives_raw": [s["raw"] for s in surviving],
        "adversarial_mention_still_fires": adv_m_role_fires,
        "adversarial_use_missed": adv_u_role_miss,
        "adversarial_mention_naive_fires": adv_m_naive,
        "both_states": both_states,
    }
    print(json.dumps(summary, sort_keys=True, default=str)[:8000])

    if before["false_positive_rate"] != 1.0:
        print(
            f"FAILED:IMP-0470-probe2 naive historical FP rate "
            f"{before['false_positive_rate']} != 1.0 (control inert)"
        )
        return 1
    if after["false_positive_rate"] != 0.0:
        print(
            f"FAILED:IMP-0470-probe2 role historical FP rate "
            f"{after['false_positive_rate']} != 0.0"
        )
        return 1
    if surviving:
        print("FAILED:IMP-0470-probe2 surviving false positives remain")
        return 1
    if adv_m_role_fires:
        print(f"FAILED:IMP-0470-probe2 refuter mention still fires {adv_m_role_fires}")
        return 1
    if adv_u_role_miss:
        print(f"FAILED:IMP-0470-probe2 refuter use missed {adv_u_role_miss}")
        return 1
    if len(adv_m_naive) != len(adv_m):
        print("FAILED:IMP-0470-probe2 naive did not fire on every adversarial mention")
        return 1

    if not ART.is_file():
        print("FAILED:IMP-0470-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        print(f"FAILED:IMP-0470-probe2 self-declared {doc.get('state')}")
        return 1
    if SENTINEL not in text:
        print("FAILED:IMP-0470-probe2 sentinel-absent")
        return 1
    meas = doc.get("measurement") or {}
    if meas.get("fp_rate_before") != 1.0:
        print(f"FAILED:IMP-0470-probe2 receipt fp_rate_before={meas.get('fp_rate_before')}")
        return 1
    if meas.get("fp_rate_after") != 0.0:
        print(f"FAILED:IMP-0470-probe2 receipt fp_rate_after={meas.get('fp_rate_after')}")
        return 1
    if meas.get("surviving_false_positives") not in ([], None) and meas.get(
        "surviving_false_positives"
    ):
        print("FAILED:IMP-0470-probe2 receipt lists surviving FPs")
        return 1
    raw = meas.get("historical_false_positives_raw") or []
    if len(raw) != len(hist):
        print(
            f"FAILED:IMP-0470-probe2 receipt historical raw count {len(raw)} != {len(hist)}"
        )
        return 1
    rev = doc.get("reviewer") or {}
    if rev.get("verdict") != "PASS" or rev.get("independent") is not True:
        print("FAILED:IMP-0470-probe2 reviewer gate")
        return 1
    print(
        f"fp_rate {before['false_positive_rate']} -> {after['false_positive_rate']} "
        f"surviving={len(surviving)} adv_m_hold={len(adv_m)} adv_u_hold={len(adv_u)}"
    )
    print("SUCCESS:IMP-0470-probe2 confusion-matrix and adversarial refuter")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
