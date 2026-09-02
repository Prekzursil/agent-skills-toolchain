#!/usr/bin/env python3
"""Probe 2: validation-time flag, both-states control, load-bearing mutant.

Mechanically different from probe 1: does not list the grid. Calls the validator
API on one known-vulnerable fixture and one known-safe fixture, then disables the
search inside the validator (mutant) and asserts the vulnerable config would be
accepted — proving the flag, not a comment, is what fires.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from tally import ABSTAIN, QUORUM_FAIL, tally  # noqa: E402
from validate_config import (  # noqa: E402
    StrategicAbstentionError,
    flag_strategic_abstention,
    require_safe_config,
)

RECEIPT = REPO / "command-center/receipts/TST-0269.json"
VULN = {"method": "majority", "quorum": {"kind": "count", "min": 3}, "weights": [1, 1, 1]}
SAFE = {"method": "majority", "quorum": None, "weights": [1, 1, 1]}
WEIGHTED_VULN = {
    "method": "majority",
    "quorum": {"kind": "weight", "min": 4},
    "weights": [3, 1, 1],
}


def _hand_quorum_fail() -> None:
    """Independent of enumerator: arithmetic on one planted profile."""
    o_abs = tally(
        ["A", "A", ABSTAIN],
        method="majority",
        weights=[1, 1, 1],
        quorum={"kind": "count", "min": 3},
    )
    o_vote_a = tally(
        ["A", "A", "A"],
        method="majority",
        weights=[1, 1, 1],
        quorum={"kind": "count", "min": 3},
    )
    o_vote_b = tally(
        ["A", "A", "B"],
        method="majority",
        weights=[1, 1, 1],
        quorum={"kind": "count", "min": 3},
    )
    if o_abs != QUORUM_FAIL:
        raise AssertionError(f"hand abstain expected QUORUM_FAIL got {o_abs}")
    if o_vote_a != "A" or o_vote_b != "A":
        raise AssertionError(f"hand votes expected A,A got {o_vote_a},{o_vote_b}")
    if o_abs in {o_vote_a, o_vote_b}:
        raise AssertionError("hand unique-by-abstention failed")
    w_abs = tally(
        [ABSTAIN, "A", "A"],
        method="majority",
        weights=[3, 1, 1],
        quorum={"kind": "weight", "min": 4},
    )
    w_vote = tally(
        ["B", "A", "A"],
        method="majority",
        weights=[3, 1, 1],
        quorum={"kind": "weight", "min": 4},
    )
    if w_abs != QUORUM_FAIL or w_vote == QUORUM_FAIL:
        raise AssertionError(f"weighted hand {w_abs} {w_vote}")


def main() -> int:
    if not RECEIPT.is_file() or RECEIPT.stat().st_size <= 0:
        print("FAILED:TST-0269-probe2 receipt-absent")
        return 1
    text = RECEIPT.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:TST-0269-probe2 self-declared", doc.get("state"))
        return 1
    if "SUCCESS:TST-0269" not in text:
        print("FAILED:TST-0269-probe2 sentinel-absent")
        return 1
    triples = doc.get("strategic_abstention_triples") or []
    if not isinstance(triples, list) or not triples:
        print("FAILED:TST-0269-probe2 triples-absent")
        return 1
    planted_listed = any(
        isinstance(t, dict)
        and t.get("method") == "majority"
        and isinstance(t.get("quorum"), dict)
        and t["quorum"].get("kind") == "count"
        and t["quorum"].get("min") == 3
        and list(t.get("weights") or []) == [1, 1, 1]
        for t in triples
    )
    if not planted_listed:
        print("FAILED:TST-0269-probe2 planted-triple-not-in-receipt")
        return 1

    try:
        _hand_quorum_fail()
    except AssertionError as exc:
        print("FAILED:TST-0269-probe2 hand-recompute", exc)
        return 1

    fired = flag_strategic_abstention(**VULN)
    silent = flag_strategic_abstention(**SAFE)
    weighted = flag_strategic_abstention(**WEIGHTED_VULN)
    if fired.get("ok") is not False or fired.get("flag") != "strategic_abstention_vulnerable":
        print("FAILED:TST-0269-probe2 flag-did-not-fire-on-vulnerable")
        print(json.dumps(fired, indent=2, sort_keys=True))
        return 1
    if silent.get("ok") is not True or silent.get("flag") is not None:
        print("FAILED:TST-0269-probe2 flag-fired-on-safe-negative-control")
        print(json.dumps(silent, indent=2, sort_keys=True))
        return 1
    if weighted.get("ok") is not False:
        print("FAILED:TST-0269-probe2 weighted-quorum-not-flagged")
        print(json.dumps(weighted, indent=2, sort_keys=True))
        return 1

    raised = False
    try:
        require_safe_config(**VULN)
    except StrategicAbstentionError:
        raised = True
    if not raised:
        print("FAILED:TST-0269-probe2 require_safe_config-did-not-raise")
        return 1
    require_safe_config(**SAFE)

    mutant = flag_strategic_abstention(
        **VULN, search=lambda method, quorum, weights: []
    )
    if mutant.get("ok") is not True:
        print("FAILED:TST-0269-probe2 mutant-still-flagged")
        print(json.dumps(mutant, indent=2, sort_keys=True))
        return 1

    summary = {
        "probe": "probe2-validate-flag",
        "unit_id": "TST-0269",
        "fired_on_bad_state": True,
        "silent_on_good_state": True,
        "weighted_quorum_flagged": True,
        "require_raises_on_vulnerable": True,
        "mutant_search_disabled_accepts_vulnerable": True,
        "hand_recompute_ok": True,
        "receipt_lists_planted_triple": True,
        "pass": True,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(
        "fired_bad=True silent_good=True mutant_accepts_vuln=True "
        "weighted_flagged=True"
    )
    print("SUCCESS:TST-0269-probe2 validation-time flag both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
