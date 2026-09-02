#!/usr/bin/env python3
"""Named probe 2: both-states independence / fingerprint / third-run controls.

Probe 1 re-derives the live sample rate. This probe plants the known-broken
and known-good cases required by CNF-0002, CNF-0006, and CNF-0118: reviewer
rejected only by rule (b), empty source probe, shell-only difference,
threshold ± epsilon, planted disagreement vs agreement, and a banned
third run of the original probe.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import lib as L  # noqa: E402

ART = L.REPO / L.OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0118-probe2 {msg}")
    return 1


def main() -> int:
    ctr = L.planted_controls()
    indep = ctr["independence"]
    if not indep["rule_a_author_rejected"]:
        return fail("rule (a) did not reject the author as confirmer")
    if not indep["rule_b_reviewer_rejected"]:
        return fail("rule (b) did not reject the implementation reviewer")
    if not indep["authorship_only_would_accept_reviewer"]:
        return fail("authorship-only rule also rejected the reviewer; (b) would be inert")
    if indep["rule_b_inert_if_both_agree"]:
        return fail("rule (b) is inert (authorship-only and (b) agree)")
    if not indep["rule_c_ancestor_rejected"]:
        return fail("rule (c) did not reject the ancestor-artifact author")
    if not indep["fresh_confirmer_accepted"]:
        return fail("fresh confirmer was not accepted")

    fp = ctr["fingerprints"]
    if not fp["identical_rejected"]:
        return fail("identical fingerprint was accepted")
    if not fp["shell_only_accepted"]:
        return fail("shell-only difference was rejected (shell is an independence axis)")
    if not fp["empty_source_rejected"]:
        return fail("empty source probe counted as different")

    dg = ctr["disagreement"]
    if not dg["planted_disagreement_detected"]:
        return fail("planted disagreement not detected")
    if not dg["planted_agreement_not_flagged"]:
        return fail("planted agreement was flagged")
    if not dg["third_original_probe_rejected"]:
        return fail("third original-probe run was accepted")
    if not dg["raw_source_escalation_accepted"]:
        return fail("raw-source escalation was not accepted")
    third = L.resolve_disagreement("third_original_probe")
    if third["accepted"]:
        return fail("resolve_disagreement accepted a third original probe")

    th = ctr["threshold"]
    if not th["minus_epsilon_no_expansion"]:
        return fail("threshold-epsilon triggered expansion")
    if not th["plus_epsilon_expansion"]:
        return fail("threshold+epsilon did not trigger expansion")
    if not th["at_threshold_no_expansion"]:
        return fail("rate equal to threshold triggered expansion")
    if not th["two_simulations_differ"]:
        return fail("±epsilon simulations produced identical expansion flags")

    park = ctr["park"]
    same = park["same_fingerprint_parks"]
    if not same.get("park") or same.get("status") != "BLOCKED" or not same.get("required_fix"):
        return fail("two same-fingerprint structural refutes did not park with required_fix")
    different = park["different_fingerprint_does_not_park"]
    if different.get("park"):
        return fail("different fingerprints parked")

    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    recorded = ((L.domain(doc).get("controls") or {}).get("threshold") or {})
    if recorded.get("two_simulations_differ") is not True:
        return fail("artifact omitted differing threshold simulations")
    if str(doc.get("state") or "").upper() in L.NOT_DELIVERING:
        return fail(f"self-declared {doc.get('state')}")

    payload = {
        "probe": "probe2-independence-controls",
        "unit_id": L.UNIT,
        "rule_b_rejects_reviewer": True,
        "authorship_only_accepts_reviewer": True,
        "empty_source_rejected": True,
        "shell_only_accepted": True,
        "third_original_probe_rejected": True,
        "threshold_epsilons_differ": True,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "rule_b_active=True empty_source_rejected=True "
        "third_run_rejected=True threshold_epsilons_differ=True"
    )
    print("SUCCESS:CNF-0118-probe2 independence fingerprint and third-run controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
