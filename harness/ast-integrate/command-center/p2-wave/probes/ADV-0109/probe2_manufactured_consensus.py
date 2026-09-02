#!/usr/bin/env python3
"""Probe 2: reverse manufactured-consensus scan.

Starts from agreement/convergence claims in the synthesis text, then
checks whether unresolved contradiction pairs remain in the raw inputs.
Does not iterate pair classification as its pass condition (that is probe 1).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import account as A  # noqa: E402

ART = REPO / A.OUT_REL
SENTINEL = A.COMPLETION_SENTINEL


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:ADV-0109-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:ADV-0109-probe2 unparseable {exc}")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ADV-0109-probe2 self-declared {doc.get('state')}")
        return 1
    if SENTINEL not in text:
        print("FAILED:ADV-0109-probe2 sentinel-absent")
        return 1

    cases = A.load_cases()
    live = A.classify_all(cases)
    by_id = {r["id"]: r for r in live["rows"]}

    manufactured = by_id["SYN-MANUFACTURED"]
    if not manufactured["agreement_spans"]:
        print("FAILED:ADV-0109-probe2 planted manufactured case has no agreement spans")
        return 1
    if not manufactured["manufactured_consensus"]:
        print("FAILED:ADV-0109-probe2 planted manufactured consensus not caught")
        return 1
    if not manufactured["unresolved_pair_ids"]:
        print("FAILED:ADV-0109-probe2 manufactured case has no unresolved pairs")
        return 1

    honest = by_id["SYN-HONEST-AGREE"]
    if not honest["agreement_spans"]:
        print("FAILED:ADV-0109-probe2 honest-agree case lost its agreement spans")
        return 1
    if honest["manufactured_consensus"]:
        print("FAILED:ADV-0109-probe2 honest agreement fired (false positive)")
        return 1
    if honest["pair_count"] != 0:
        print("FAILED:ADV-0109-probe2 honest-agree fixture is not pair-empty")
        return 1

    both = by_id["SYN-BOTH-AS-AGREE"]
    if not both["manufactured_consensus"]:
        print("FAILED:ADV-0109-probe2 both-as-agree manufactured consensus missed")
        return 1
    if both["pairs"][0]["a_present"] is not True or both["pairs"][0]["b_present"] is not True:
        print("FAILED:ADV-0109-probe2 both-as-agree did not mention both claims")
        return 1

    represented = by_id["SYN-REPRESENTED"]
    if represented["manufactured_consensus"]:
        print("FAILED:ADV-0109-probe2 represented dissent case fired manufactured")
        return 1

    resolved = by_id["SYN-RESOLVED"]
    if resolved["manufactured_consensus"]:
        print("FAILED:ADV-0109-probe2 resolved-with-reason case fired manufactured")
        return 1

    art_flags = {
        r["id"]: r.get("manufactured_consensus")
        for r in (doc.get("reverse_accounting") or {}).get("rows") or []
    }
    live_flags = {r["id"]: r["manufactured_consensus"] for r in live["rows"]}
    if art_flags != live_flags:
        print("FAILED:ADV-0109-probe2 artifact/live manufactured drift", art_flags, live_flags)
        return 1

    payload = {
        "probe": "probe2-manufactured-consensus",
        "planted_manufactured_spans": manufactured["agreement_spans"],
        "planted_manufactured": True,
        "honest_agree_spans": honest["agreement_spans"],
        "honest_agree_false_positive": False,
        "both_as_agree_manufactured": True,
        "represented_silent": True,
        "resolved_silent": True,
        "flags": live_flags,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "planted_manufactured=True honest_agree_fp=False "
        f"spans_planted={manufactured['agreement_spans']} "
        f"spans_honest={honest['agreement_spans']}"
    )
    print(
        "SUCCESS:ADV-0109-probe2 reverse agreement scan, planted manufactured "
        "consensus caught, honest-agreement negative control silent"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
