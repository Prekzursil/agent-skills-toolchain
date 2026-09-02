#!/usr/bin/env python3
"""Probe 2 (control / independent reviewer): named uncacheable class + dual rails.

A live-web step with no captured body is uncacheable. A URL-only mutant key
collides two different bodies. Single-rail claims are E3 and must not be
cited as measured fact. Defaults to REFUTED when a claim lacks two rails.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from rails import RAILS, verify_all  # noqa: E402
from spec import UNCACHEABLE_LIVE_WEB  # noqa: E402
from suite import uncacheable_control  # noqa: E402

ART = REPO / "command-center/research/RES-0070.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
REQUIRED_RAIL_FIELDS = ("kind", "permalink", "fetch_timestamp", "http_status", "sha256")


def grade_claim(claim: dict) -> str:
    rails = [r for r in (claim.get("rails") or []) if isinstance(r, dict)]
    kinds = {r.get("kind") for r in rails}
    complete = []
    for r in rails:
        if all(r.get(k) not in (None, "", 0) for k in REQUIRED_RAIL_FIELDS):
            if r.get("http_status") == 200 and isinstance(r.get("sha256"), str) and len(r["sha256"]) == 64:
                complete.append(r)
    if len(complete) >= 2 and "structured-api" in kinds and "prose-source" in kinds:
        return "E2"
    if len(complete) == 1:
        return "E3"
    return "E4"


def main() -> int:
    ctrl = uncacheable_control()
    print(json.dumps({k: ctrl[k] for k in sorted(ctrl) if k != "pass"}))
    if not ctrl["pass"]:
        print("FAILED:RES-0070-probe2 uncacheable control")
        return 1
    if ctrl["named_uncacheable_class"] != UNCACHEABLE_LIVE_WEB:
        print("FAILED:RES-0070-probe2 missing named class")
        return 1

    rails = verify_all()
    bad = [r for r in rails if not r.get("ok")]
    if bad:
        print("FAILED:RES-0070-probe2 rails", json.dumps(bad)[:2000])
        return 1
    print(f"rails_ok={len(rails)}")

    # Detector control: a claim with one rail is E3, not measured fact.
    single = {
        "claim_id": "MUTANT-SINGLE-RAIL",
        "rails": [
            {
                "kind": "prose-source",
                "permalink": RAILS["bazel-remote-caching"]["permalink"],
                "fetch_timestamp": RAILS["bazel-remote-caching"]["fetch_timestamp"],
                "http_status": 200,
                "sha256": RAILS["bazel-remote-caching"]["sha256"],
            }
        ],
    }
    if grade_claim(single) != "E3":
        print("FAILED:RES-0070-probe2 single-rail mutant was not E3")
        return 1
    empty = {"claim_id": "MUTANT-NO-RAIL", "rails": []}
    if grade_claim(empty) != "E4":
        print("FAILED:RES-0070-probe2 empty-rail mutant was not E4")
        return 1
    print("single_rail_E3=True empty_E4=True")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if str(doc.get("state") or "").upper() in NOT_DELIVERING:
            print(f"FAILED:RES-0070-probe2 self-declared {doc.get('state')}")
            return 1
        classes = doc.get("uncacheable_step_classes") or []
        ids = [c.get("id") for c in classes if isinstance(c, dict)]
        if UNCACHEABLE_LIVE_WEB not in ids:
            print("FAILED:RES-0070-probe2 artifact missing uncacheable class")
            return 1
        blob = json.dumps(doc)
        if "named uncacheable step class" not in blob:
            print("FAILED:RES-0070-probe2 named-class phrase absent")
            return 1
        cited = 0
        for claim in doc.get("claims") or []:
            if not isinstance(claim, dict):
                continue
            live_grade = grade_claim(claim)
            recorded = claim.get("evidence_tier")
            if recorded in {"E1", "E2"} and live_grade not in {"E1", "E2"}:
                print("FAILED:RES-0070-probe2 overclaim", claim.get("claim_id"), recorded, live_grade)
                return 1
            if live_grade in {"E3", "E4"} and claim.get("cite_as_measured_fact") is True:
                print("FAILED:RES-0070-probe2 E3/E4 cited as fact", claim.get("claim_id"))
                return 1
            if recorded in {"E1", "E2"}:
                cited += 1
            # Independent reviewer default: insufficient rails => REFUTED as measured fact.
            if live_grade in {"E3", "E4"} and claim.get("verdict") not in {
                "REFUTED-AS-MEASURED-FACT",
                "E3-NOT-FACT",
                "SUPPORTING",
                None,
            }:
                # supporting E3 is allowed if not claimed as measured
                if claim.get("evidence_tier") in {"E1", "E2"}:
                    print("FAILED:RES-0070-probe2 reviewer did not default REFUTED", claim.get("claim_id"))
                    return 1
        if cited < 2:
            print("FAILED:RES-0070-probe2 fewer than two E2 claims")
            return 1
        rev = doc.get("reviewer") or {}
        if rev.get("independent") is not True or rev.get("verdict") not in {"PASS", "CONFIRMED"}:
            print("FAILED:RES-0070-probe2 reviewer")
            return 1
    print("SUCCESS:RES-0070-probe2 uncacheable-class control and dual-rail grader")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
