#!/usr/bin/env python3
"""Probe 1: planted controls DETECTED, genuine zero FPs, both-states, mention≠use."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import emit as E  # noqa: E402
import scanner as S  # noqa: E402

ART = REPO / "command-center/receipts/TST-0348.json"
SENTINEL = "SUCCESS:TST-0348"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0348-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")

    control = S.scan_roots([S.fixture_root(HERE)], REPO)
    report = E.control_report(control)
    if not report["planted_all_detected"]:
        print(json.dumps(report["planted"], indent=2))
        return fail("planted controls not all DETECTED")
    if not report["genuine_zero_false_positives"]:
        print(json.dumps(report["genuine"], indent=2))
        return fail("genuine false positives")

    inversion = E.both_states()
    if not inversion["inversion_holds"]:
        print(json.dumps(inversion, indent=2))
        return fail("both-states inversion")

    mention_src = (S.fixture_root(HERE) / "planted_no_assertion.py").read_text(
        encoding="utf-8"
    )
    tree_mentions = 0
    tree_uses = 0
    import ast

    tree = ast.parse(mention_src)
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and "assert" in node.value
        ):
            tree_mentions += 1
        if isinstance(node, ast.Assert):
            tree_uses += 1
    if tree_mentions < 1:
        return fail("mention control has no string mentioning assert")
    if tree_uses != 0:
        return fail("mention-only fixture had an Assert node")

    rec_planted = doc.get("controls", {}).get("planted") or []
    if len(rec_planted) != len(E.PLANTED_EXPECT):
        return fail("receipt planted row count drifted")
    if doc.get("controls", {}).get("planted_all_detected") is not True:
        return fail("receipt planted_all_detected")
    if doc.get("both_states", {}).get("inversion_holds") is not True:
        return fail("receipt both_states")

    live = S.scan_roots(S.live_roots(REPO), REPO)
    sample = [r for r in live if not r["vacuous"]][:8]
    if not sample:
        return fail("no live genuine tests to sample")
    for rec in sample:
        if rec["assertion_sites"] < 1:
            return fail(f"live sample {rec['test']} has no assertion-use")

    print(
        json.dumps(
            {
                "planted_detected": [p["test"] for p in report["planted"]],
                "genuine_clean": [g["test"] for g in report["genuine"]],
                "mention_strings": tree_mentions,
                "assert_nodes_in_mention_fixture": tree_uses,
                "both_states": inversion,
                "live_sample": len(sample),
            },
            indent=2,
            sort_keys=True,
        )
    )
    print("SUCCESS:TST-0348-probe1 planted DETECTED genuine zero-FP both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
