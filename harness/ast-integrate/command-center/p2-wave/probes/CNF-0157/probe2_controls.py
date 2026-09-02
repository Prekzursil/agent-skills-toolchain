#!/usr/bin/env python3
"""Probe 2: known-broken, loud-degradation, both-states, reviewer cells.

Mechanically different from probe 1: re-executes adapter-fixture controls
directly via adapters.exercise_claim rather than re-reading PATH discovery.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import adapters as A  # noqa: E402
import honesty as H  # noqa: E402
import matrix as M  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0157.json"
REVIEW_A = ("claude-code", "plugin")
REVIEW_B = ("mcp-generic", "hook")


def main() -> int:
    if not ART.is_file():
        print("FAILED:CNF-0157-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    ok, why = H.check(doc)
    print(f"honesty_ok={ok} {why}")
    if not ok:
        print("FAILED:CNF-0157-probe2 honesty")
        return 1

    kb = M.known_broken_control()
    loud = M.loud_degradation_test()
    both = M.both_states_test()
    router = M.skill_router_control()
    print(f"known_broken={kb['pass']} red={kb['red_cell_ids']}")
    print(f"loud={loud['pass']} err={loud['forced_error'][:80]}")
    print(f"both_states={both['pass']} green={both['enabled_green_clients']}")
    print(f"router_11330={router['pass']}")
    if not (kb["pass"] and loud["pass"] and both["pass"] and router["pass"]):
        print("FAILED:CNF-0157-probe2 control re-run")
        return 1

    rec = doc.get("tests") or {}
    if rec.get("known_broken", {}).get("pass") is not True:
        print("FAILED:CNF-0157-probe2 artifact known_broken not pass")
        return 1
    if rec.get("loud_degradation", {}).get("disabled_client", None):
        print("FAILED:CNF-0157-probe2 unexpected field")
        return 1
    if rec.get("loud_degradation", {}).get("pass") is not True:
        print("FAILED:CNF-0157-probe2 artifact loud_degradation not pass")
        return 1

    # Independent reviewer path: call adapters.exercise_claim directly.
    a = A.exercise_claim(*REVIEW_A, work=HERE)
    b = A.exercise_claim(*REVIEW_B, work=HERE)
    print(f"reviewer {REVIEW_A[0]}/{REVIEW_A[1]}={a['verdict']}")
    print(f"reviewer {REVIEW_B[0]}/{REVIEW_B[1]}={b['verdict']}")
    if a["verdict"] != A.VERDICT_REPRODUCES:
        print("FAILED:CNF-0157-probe2 reviewer cell A not REPRODUCES")
        return 1
    if b["verdict"] != A.VERDICT_LOUD:
        print("FAILED:CNF-0157-probe2 reviewer cell B not LOUD-DEGRADE")
        return 1
    if not b.get("capability_named_in_error"):
        print("FAILED:CNF-0157-probe2 reviewer loud error did not name capability")
        return 1

    by_id = {c["id"]: c for c in doc["cells"]}
    want_a = by_id.get("adapter-fixture:claude-code:plugin") or {}
    want_b = by_id.get("adapter-fixture:mcp-generic:hook") or {}
    if want_a.get("verdict") != a["verdict"] or want_b.get("verdict") != b["verdict"]:
        print("FAILED:CNF-0157-probe2 reviewer cells disagree with artifact")
        return 1

    # Mutant: disable the wrong adapter; known-broken must fail.
    wrong = M.fixture_cells(disabled=("codex-cli",))
    red_clients = {c["client_id"] for c in wrong if c["verdict"] == A.VERDICT_RED}
    print(f"wrong_disable_red_clients={sorted(red_clients)}")
    if red_clients == {"claude-code"}:
        print("FAILED:CNF-0157-probe2 wrong disable still looked like the control")
        return 1
    if "codex-cli" not in red_clients:
        print("FAILED:CNF-0157-probe2 disabling codex did not turn it red")
        return 1

    if "SUCCESS:CNF-0157" not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNF-0157-probe2 sentinel absent")
        return 1
    print("SUCCESS:CNF-0157-probe2 known-broken loud both-states reviewer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
