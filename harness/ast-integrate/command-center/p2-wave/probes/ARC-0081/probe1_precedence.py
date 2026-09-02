#!/usr/bin/env python3
"""Probe 1: every decision-table row is asserted by recomputing evaluate_request.

Both-states on deny-overrides: the same grant without the deny must GRANT, proving
the deny is what produced DENY rather than a silent closed-world miss.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from cases import DECISION_CASES  # noqa: E402
from model import evaluate_request, pset, req, stmt  # noqa: E402

ART = REPO / "command-center/phase4/contracts/ARC-0081.json"
SENTINEL = "SUCCESS:ARC-0081"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:ARC-0081-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:ARC-0081-probe1 sentinel absent")
        return 1
    doc = json.loads(text)
    if doc.get("unit_id") != "ARC-0081":
        print("FAILED:ARC-0081-probe1 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:ARC-0081-probe1 self-declared", doc.get("state"))
        return 1
    table = doc.get("decision_table") or []
    if len(table) < 12:
        print(f"FAILED:ARC-0081-probe1 table rows={len(table)} want>=12")
        return 1

    by_id = {c["id"]: c for c in DECISION_CASES}
    fail = 0
    for row in table:
        rid = row.get("id")
        src = by_id.get(rid)
        if src is None:
            print(f"FAILED:ARC-0081-probe1 unknown row {rid}")
            fail += 1
            continue
        live = evaluate_request(src["permissions"], src["request"])
        if live["outcome"] != row.get("computed_outcome"):
            print(
                f"FAILED:ARC-0081-probe1 {rid} live={live['outcome']} "
                f"stored={row.get('computed_outcome')}"
            )
            fail += 1
            continue
        if live["reason"] != row.get("computed_reason"):
            print(
                f"FAILED:ARC-0081-probe1 {rid} reason live={live['reason']} "
                f"stored={row.get('computed_reason')}"
            )
            fail += 1
            continue
        print(
            f"row {rid} outcome={live['outcome']} reason={live['reason']} "
            f"family={row.get('family')}"
        )

    if len(table) != len(DECISION_CASES):
        print(
            f"FAILED:ARC-0081-probe1 stored={len(table)} "
            f"cases={len(DECISION_CASES)} (contract drifted from cases.py)"
        )
        fail += 1

    # Both-states: deny-overrides vs grant-only.
    both = pset("u", stmt("grant", "tool", "Bash"), stmt("deny", "tool", "Bash"))
    grant_only = pset("u", stmt("grant", "tool", "Bash"))
    d1 = evaluate_request(both, req("tool", "Bash"))
    d2 = evaluate_request(grant_only, req("tool", "Bash"))
    both_ok = d1["outcome"] == "DENY" and d1["reason"] == "deny-overrides" and d2["outcome"] == "GRANT"
    print(f"both-states deny-overrides DENY={d1['outcome']} grant-only={d2['outcome']} ok={both_ok}")
    if not both_ok:
        print("FAILED:ARC-0081-probe1 deny-overrides both-states did not discriminate")
        fail += 1

    outcomes = {r["computed_outcome"] for r in table}
    if outcomes != {"GRANT", "DENY"}:
        print(f"FAILED:ARC-0081-probe1 table not two-sided {outcomes}")
        fail += 1

    if fail:
        print(f"FAILED:ARC-0081-probe1 failures={fail}")
        return 1
    print(f"asserted={len(table)}")
    print("SUCCESS:ARC-0081-probe1 precedence table")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
