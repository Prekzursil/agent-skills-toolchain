#!/usr/bin/env python3
"""Probe 2 (independent reviewer): DUPLICATE-OF and injection neutralize both-states."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from common import OUT_REL, SENTINEL, load_json  # noqa: E402
from grading import apply_rule  # noqa: E402
from neutralize import neutralize  # noqa: E402
from sweep import load_rule, run_sweep  # noqa: E402

ART = REPO / OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0026-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    # Re-derive the sweep; do not trust artifact booleans.
    live = run_sweep()
    art_by_id = {m["id"]: m for m in doc.get("mechanisms") or []}
    live_by_id = {m["id"]: m for m in live["mechanisms"]}
    if set(art_by_id) != set(live_by_id):
        return fail("artifact mechanism ids drifted from live re-derive")
    for mid, row in live_by_id.items():
        art = art_by_id[mid]
        if art.get("disposition") != row["disposition"] or art.get("trust_grade") != row["trust_grade"]:
            return fail(
                f"{mid} artifact disposition/grade {art.get('disposition')}/{art.get('trust_grade')} "
                f"!= live {row['disposition']}/{row['trust_grade']}"
            )

    in_vendor = apply_rule(
        injection_detected=False,
        verbatim_quote="PreToolUse hooks in production",
        authority="PRACTITIONER",
        production_claim_value="EXPLICIT",
        corroboration="DUAL",
        in_vendor=True,
    )
    not_vendor = apply_rule(
        injection_detected=False,
        verbatim_quote="PreToolUse hooks in production",
        authority="PRACTITIONER",
        production_claim_value="EXPLICIT",
        corroboration="DUAL",
        in_vendor=False,
    )
    print(
        f"KNOWN-BAD vendor-present: disposition={in_vendor['disposition']} "
        f"promoted={in_vendor['promoted_to_finding']}"
    )
    print(
        f"KNOWN-GOOD vendor-absent: disposition={not_vendor['disposition']} "
        f"promoted={not_vendor['promoted_to_finding']}"
    )
    if in_vendor["disposition"] != "DUPLICATE-OF" or in_vendor["promoted_to_finding"]:
        return fail("vendor-present was re-counted")
    if not_vendor["disposition"] != "FINDING":
        return fail("vendor-absent identical features were not FINDING")

    hooks = live_by_id.get("M-session-lifecycle-hooks")
    if not hooks or hooks["disposition"] != "DUPLICATE-OF":
        return fail(f"hooks row not DUPLICATE-OF: {hooks}")
    if hooks["id"] in (live["counts"].get("novel_findings") or []):
        return fail("hooks counted as novel finding")

    rule = load_rule()
    planted = (HERE / "fixtures" / "planted_injection.body").read_text(encoding="utf-8")
    neu = neutralize(planted, rule.get("injection_patterns"))
    print(
        f"INJECTION neutralize detected={neu['injection_detected']} "
        f"nlog={len(neu['log'])}"
    )
    if not neu["injection_detected"] or len(neu["log"]) < 1:
        return fail("planted injection was not logged")
    if "ignore previous instructions" in neu["neutralized"].casefold():
        return fail("instruction survived neutralization")
    # Mutant: grading the RAW planted page without neutralize would still REJECT
    # because apply_rule sees injection_detected independently; the control that
    # must fire is "neutralize skipped AND injection_detected forced false".
    followed = apply_rule(
        injection_detected=False,
        verbatim_quote="quantum-raft-orchestrator",
        authority="PRACTITIONER",
        production_claim_value="EXPLICIT",
        corroboration="DUAL",
        in_vendor=False,
    )
    honest = apply_rule(
        injection_detected=True,
        verbatim_quote="quantum-raft-orchestrator",
        authority="PRACTITIONER",
        production_claim_value="EXPLICIT",
        corroboration="DUAL",
        in_vendor=False,
    )
    print(
        f"MUTANT skip-neutralize-and-hide-flag: disposition={followed['disposition']}"
    )
    print(f"HONEST injection_detected: disposition={honest['disposition']}")
    if followed["disposition"] == "FINDING" and honest["disposition"] == "REJECTED":
        pass
    else:
        return fail("injection both-states did not discriminate")
    live_planted = live_by_id["M-planted-quantum-raft"]
    if live_planted["disposition"] != "REJECTED":
        return fail("live planted not REJECTED")

    print(
        json.dumps(
            {
                "probe": "probe2-duplicate-and-injection",
                "unit_id": "WFA-0026",
                "duplicate_of_not_recounted": True,
                "vendor_absent_is_finding": True,
                "injection_logged": True,
                "injection_both_states": True,
                "reviewer_reran_both_states": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:WFA-0026-probe2 duplicate-of injection both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
