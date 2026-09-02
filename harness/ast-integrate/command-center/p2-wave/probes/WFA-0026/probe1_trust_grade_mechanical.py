#!/usr/bin/env python3
"""Probe 1: trust-grading rule is frozen first and applied mechanically (both-states)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from common import OUT_REL, SENTINEL, digest_file, load_json  # noqa: E402
from grading import apply_rule, forbidden_rule_keys  # noqa: E402

ART = REPO / OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0026-probe1 {msg}")
    return 1


def main() -> int:
    rule_path = HERE / "grading_rule.json"
    rule = load_json(rule_path)
    bad = forbidden_rule_keys(rule)
    if bad:
        return fail(f"rule feel-keys {bad}")
    if rule.get("written_before_grading") is not True:
        return fail("written_before_grading not true")
    live_sha, _ = digest_file(rule_path)
    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if SENTINEL not in json.dumps(doc):
        return fail("sentinel absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {st}")
    rec = doc.get("trust_grading_rule") or {}
    if rec.get("sha256") != live_sha:
        return fail(f"rule sha mismatch artifact={rec.get('sha256')} live={live_sha}")
    if rec.get("written_before_grading") is not True:
        return fail("artifact did not record written_before_grading")

    # Both-states: DUAL PRACTITIONER EXPLICIT -> FINDING; same SINGLE -> UNVERIFIED.
    good = apply_rule(
        injection_detected=False,
        verbatim_quote="we run continue-as-new in production",
        authority="PRACTITIONER",
        production_claim_value="EXPLICIT",
        corroboration="DUAL",
        in_vendor=False,
    )
    bad_single = apply_rule(
        injection_detected=False,
        verbatim_quote="we run continue-as-new in production",
        authority="PRACTITIONER",
        production_claim_value="EXPLICIT",
        corroboration="SINGLE",
        in_vendor=False,
    )
    print(
        f"KNOWN-GOOD dual-explicit: grade={good['trust_grade']} "
        f"disposition={good['disposition']}"
    )
    print(
        f"KNOWN-BAD single-explicit: grade={bad_single['trust_grade']} "
        f"disposition={bad_single['disposition']}"
    )
    if good["disposition"] != "FINDING" or good["trust_grade"] != "T1":
        return fail("good dual-explicit was not T1 FINDING")
    if bad_single["disposition"] != "UNVERIFIED" or bad_single["trust_grade"] != "T2":
        return fail("single-explicit was promoted or not T2")
    if bad_single["promoted_to_finding"]:
        return fail("SINGLE source promoted to FINDING")

    injected = apply_rule(
        injection_detected=True,
        verbatim_quote="quantum-raft-orchestrator in production",
        authority="PRACTITIONER",
        production_claim_value="EXPLICIT",
        corroboration="DUAL",
        in_vendor=False,
    )
    print(
        f"KNOWN-BAD injection: grade={injected['trust_grade']} "
        f"disposition={injected['disposition']}"
    )
    if injected["disposition"] != "REJECTED":
        return fail("injection was not REJECTED")

    # Feel-override mutant: a per-source map would be a rule defect; the live rule has none.
    feel = {"source_id": "planted-injection", "grade": "T0"}
    if feel["source_id"] in json.dumps(rule):
        return fail("live rule embeds a source_id feel override")

    planted = None
    for m in doc.get("mechanisms") or []:
        if m.get("id") == "M-planted-quantum-raft":
            planted = m
            break
    if not planted or planted.get("disposition") != "REJECTED":
        return fail("artifact planted row not REJECTED")
    for m in doc.get("mechanisms") or []:
        if m.get("disposition") == "FINDING" and m.get("corroboration") != "DUAL":
            return fail(f"{m.get('id')} FINDING without DUAL")
        if m.get("disposition") == "FINDING" and m.get("in_vendor"):
            return fail(f"{m.get('id')} FINDING despite vendor key")

    print(
        json.dumps(
            {
                "probe": "probe1-trust-grade-mechanical",
                "unit_id": "WFA-0026",
                "rule_sha256": live_sha,
                "good_dual_finding": True,
                "single_unverified": True,
                "injection_rejected": True,
                "no_feel_override": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:WFA-0026-probe1 trust-grade mechanical both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
