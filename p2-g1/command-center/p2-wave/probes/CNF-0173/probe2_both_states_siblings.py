#!/usr/bin/env python3
"""Probe 2: both-states, sensitivity sweep, role-collapse, novelty.

Mechanically different from probe 1: does not re-assert seawall firing as
the primary check; it checks the four catalog tests_required rows and that
source_probe != verifier_probe.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402
import scenarios as S  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0173.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0173-probe2 {msg}")
    return 1


def test_row(doc: dict, tid: str) -> dict | None:
    for row in doc.get("tests") or []:
        if isinstance(row, dict) and row.get("id") == tid:
            return row
    return None


def main() -> int:
    harbor = H.evaluate_oracle(S.harbor_after_briefs())
    slow = H.evaluate_oracle(S.role_clone_slow())
    ideas = H.evaluate_oracle(S.hundred_echo_ideas())
    reviewer = H.evaluate_oracle(S.reviewer_ferry_snap())
    seawall = H.evaluate_oracle(S.seawall_clone_panel())

    if harbor["instant_unanimity"]["fired"]:
        return fail("genuine harbor consensus tripped instant_unanimity (false positive)")
    if not seawall["instant_unanimity"]["fired"]:
        return fail("seawall control did not fire; both-states is one-sided")

    sweep_fire = []
    sweep_silent = []
    for vr in range(1, 6):
        ev = H.evaluate_oracle(S.clone_at_vote_round(vr, 0))
        fired = bool(ev["instant_unanimity"]["fired"])
        (sweep_fire if fired else sweep_silent).append(vr)
    if sweep_fire != [1]:
        return fail(f"sensitivity knee expected fire only at r=1, got {sweep_fire}")
    if 2 not in sweep_silent:
        return fail("sensitivity sweep never went silent")
    # Distinct briefs at round 1 must silence instant unanimity.
    with_briefs = H.evaluate_oracle(S.clone_at_vote_round(1, 3))
    if with_briefs["instant_unanimity"]["fired"]:
        return fail("round-1 unanimity after 3 distinct briefs still fired")

    if not slow["role_collapse"]["fired"]:
        return fail("slow identical-argument panel did not trip role_collapse")
    if slow["instant_unanimity"]["fired"]:
        return fail("slow panel tripped instant_unanimity; controls are not separate")

    nov = ideas["novelty"]
    if not nov["fired"]:
        return fail("100-echo idea list did not trip novelty")
    if int(nov.get("unique_after_dedup") or 0) >= 100:
        return fail("novelty unique_after_dedup still >= 100")

    if not reviewer["instant_unanimity"]["fired"]:
        return fail("reviewer ferry-snap scenario did not generalise on the oracle")

    if not ART.is_file():
        return fail("receipt missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    src = (doc.get("source_probe") or {}).get("fingerprint") or ""
    ver = (doc.get("verifier_probe") or {}).get("fingerprint") or ""
    if not src or not ver:
        return fail("missing probe fingerprints")
    if src == ver:
        return fail("same-probe-rerun: source_probe == verifier_probe")
    for tid in (
        "both-states-genuine-consensus-silent",
        "trigger-sensitivity-sweep",
        "role-collapse-distinct-from-fast-unanimity",
        "idea-count-gaming-novelty",
    ):
        row = test_row(doc, tid)
        if row is None:
            return fail(f"artifact missing test {tid}")
        if row.get("result") != "PASS":
            return fail(f"artifact test {tid} result={row.get('result')}")

    print(
        json.dumps(
            {
                "probe": "probe2-both-states-siblings",
                "unit_id": "CNF-0173",
                "harbor_instant_fired": harbor["instant_unanimity"]["fired"],
                "sweep_fire_rounds": sweep_fire,
                "role_collapse_slow": slow["role_collapse"]["fired"],
                "slow_instant": slow["instant_unanimity"]["fired"],
                "novelty_unique": nov.get("unique_after_dedup"),
                "reviewer_instant_fired": reviewer["instant_unanimity"]["fired"],
                "source_ne_verifier": src != ver,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CNF-0173-probe2 both-states sensitivity role-collapse novelty")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
