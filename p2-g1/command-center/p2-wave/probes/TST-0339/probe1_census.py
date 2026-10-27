#!/usr/bin/env python3
"""TST-0339 probe1: live census recount vs receipt.

The deterministic live recount surface is fixtures/estate (the receipt own
census.estate scope). The estate-wide recorded census (2026-08-25 snapshot)
is spot-checked on its first 10 no_test_calls anchors; drift is disclosed,
not smoothed.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROBE_DIR))
from census import census  # noqa: E402

RECEIPT = REPO / "command-center" / "receipts" / "TST-0339.json"
FIXTURES = PROBE_DIR / "fixtures" / "estate"
SENTINEL = "SUCCESS:TST-0339-probe1"


def fail(msg):
    print("FAILED:TST-0339-probe1 " + msg)
    return 1


def anchor_still_matches(anchor, function, param):
    path_str, _, line_s = anchor.rpartition(":")
    path = REPO / path_str
    if not path.is_file():
        return False
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return False
    want = int(line_s)
    bare = function.rsplit(".", 1)[-1]
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == bare:
            span = range(node.lineno, (node.end_lineno or node.lineno) + 2)
            if want in span:
                args = node.args
                pos = args.posonlyargs + args.args
                nd = len(args.defaults)
                for arg in pos[len(pos) - nd:]:
                    if arg.arg == param:
                        return True
    return False


def main():
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    est = receipt["census"]["estate"]
    recount = census([FIXTURES])
    checks = [
        ("fixture-n-defaults", recount["n_defaults"] == est["n_defaults"] == 2),
        ("fixture-n-exercised", recount["n_exercised"] == est["n_exercised"] == 1),
        ("fixture-n-unexercised", recount["n_unexercised"] == est["n_unexercised"] == 1),
        ("fixture-n-no-calls", recount["n_no_test_calls"] == est["n_no_test_calls"] == 0),
        ("fixture-n-unresolved", recount["n_unresolved"] == est["n_unresolved"] == 0),
        ("sentinel-in-receipt", receipt["completion_sentinel"] == "SUCCESS:TST-0339"),
        ("receipt-answer-has-sentinel", "SUCCESS:TST-0339" in receipt["answer"]),
    ]
    planted = est["planted"]
    unex = {r["file"].split("/fixtures/")[-1] + ":" + str(r["line"]): r for r in recount["unexercised"]}
    ex = {r["file"].split("/fixtures/")[-1] + ":" + str(r["line"]): r for r in recount["exercised_rows"]}
    for p in [p for p in planted if p["status"] == "unexercised"]:
        key = p["anchor"].split("/fixtures/")[-1]
        row = unex.get(key)
        checks += [
            ("planted-unexercised-" + key, row is not None),
            ("planted-unexercised-supplying", bool(row) and row["calls_supplying"] == p["calls_supplying"] == 3),
            ("planted-unexercised-omitting", bool(row) and row["calls_omitting"] == p["calls_omitting"] == 0),
            ("planted-unexercised-name", bool(row) and row["param"] == p["param"] == "min_bytes"),
        ]
    for p in [p for p in planted if p["status"] == "exercised"]:
        key = p["anchor"].split("/fixtures/")[-1]
        row = ex.get(key)
        checks += [
            ("planted-exercised-" + key, row is not None),
            ("planted-exercised-omits", bool(row) and row["calls_omitting"] >= 1),
        ]
    both = receipt["both_states"]
    checks += [
        ("both-states-recorded", both["unexercised_default_change_stays_green"] is True
            and both["exercised_default_change_goes_red"] is True),
    ]
    ntc = receipt["census"]["no_test_calls"]
    sample = ntc[:10]
    hits = sum(1 for r in sample if anchor_still_matches(r["anchor"], r["function"], r["param"]))
    files_present = sum(1 for r in ntc if (REPO / r["anchor"].rpartition(":")[0]).is_file())
    # The census is a dated 2026-08-25 snapshot of a tree that keeps moving.
    # The falsifiable core that must verify live: the anchors are real (not
    # fabricated), i.e. a non-zero fraction still AST-match, and the anchor
    # files still exist. Total drift is DISCLOSED, never smoothed.
    checks.append(("snapshot-anchors-not-fabricated", hits >= 3 and files_present >= len(ntc) // 2))
    for name, ok in checks:
        print(("  ok " if ok else "  RED ") + name)
        if not ok:
            return fail("check " + name + " RED")
    print(json.dumps({
        "probe": "probe1-census", "unit_id": "TST-0339", "pass": True,
        "fixture_recount": {k: recount[k] for k in ("n_defaults", "n_exercised", "n_unexercised", "n_no_test_calls", "n_unresolved")},
        "recorded_estate_snapshot": {k: receipt["census"][k] for k in ("n_defaults", "n_exercised", "n_unexercised", "n_no_test_calls", "n_unresolved")},
        "anchor_spotcheck_hits": hits, "anchor_spotcheck_n": len(sample), "anchor_files_present": files_present, "anchor_files_total": len(ntc),
    }))
    print(SENTINEL + " fixture estate recounts to the receipt exactly; estate snapshot anchors spot-checked with drift disclosed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
