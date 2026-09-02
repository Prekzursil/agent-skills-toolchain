#!/usr/bin/env python3
"""Probe 2: independent-reproduction control; adversarial default is REFUTED."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center/research/RES-0028.json"
NOT_PROMOTING = {"E3", "E4"}


def fail(msg: str) -> int:
    print(f"FAILED:RES-0028-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    verdict = str(doc.get("independent_reproduction_verdict") or "").upper().replace("_", "-")
    print(f"independent_reproduction_verdict={verdict}")
    if verdict != "NOT-REPRODUCED":
        return fail("explicit NOT-REPRODUCED verdict missing")
    if "not-reproduced" not in text.lower():
        return fail("artifact text lacks not-reproduced")

    claims = list(doc.get("claims") or [])
    acc = next((c for c in claims if c.get("claim_id") == "RES-0028-M2-ACCURACY-VS-MORE-FILES"), None)
    if acc is None:
        return fail("accuracy-vs-more-files claim omitted (silent skip)")
    ir = acc.get("independent_reproduction") or {}
    print(
        f"accuracy_tier={acc.get('evidence_tier')} "
        f"promotable={acc.get('promotable_to_tier1')} "
        f"independent_party_found={ir.get('independent_party_found')} "
        f"effect_size={acc.get('effect_size')!r} baseline={acc.get('baseline')!r}"
    )
    if ir.get("verdict") != "NOT-REPRODUCED":
        return fail("accuracy claim missing NOT-REPRODUCED")
    if ir.get("independent_party_found") is True or (ir.get("parties") or []):
        return fail("claimed an independent reproducer without evidence in this extract")
    if acc.get("promotable_to_tier1") is True:
        return fail("accuracy claim promoted to Tier 1")
    if str(acc.get("evidence_tier") or "") not in NOT_PROMOTING:
        return fail("accuracy claim must stay E3/E4 without baseline+effect size")
    if acc.get("effect_size") not in (None, "", "unknown"):
        return fail("accuracy effect_size present without a cited isolated measurement")
    if acc.get("baseline") not in (None, "", "unknown"):
        return fail("accuracy baseline present without a cited isolated measurement")
    if acc.get("doi") or acc.get("arxiv_id"):
        return fail("accuracy claim cites a DOI/arXiv that this extract did not capture")
    if acc.get("headline_without_baseline") is not True:
        return fail("E3 headline-without-baseline flag missing")

    # Adversarial: any surviving claim that promotes without DOI+baseline+effect is a fail.
    for c in claims:
        if c.get("promotable_to_tier1") is True:
            if not (c.get("doi") or c.get("arxiv_id")):
                return fail(f"{c.get('claim_id')} promoted without DOI/arXiv")
            if c.get("effect_size") in (None, "") or c.get("baseline") in (None, ""):
                return fail(f"{c.get('claim_id')} promoted without baseline and effect size")
        if str(c.get("evidence_tier") or "") == "E1":
            return fail(f"{c.get('claim_id')} graded E1 without a paper")

    reviewer = doc.get("reviewer") or {}
    if reviewer.get("independent") is not True:
        return fail("reviewer is not independent")
    if str(reviewer.get("default_if_insufficient") or "") != "REFUTED":
        return fail("reviewer did not default to REFUTED")
    if "RES-0028-M2-ACCURACY-VS-MORE-FILES" not in " ".join(reviewer.get("refuted_claims") or []):
        return fail("reviewer did not refute the unmeasured accuracy claim")
    tests = {t["id"]: t for t in (doc.get("tests") or [])}
    t2 = tests.get("T2") or {}
    if t2.get("independent_party_has_reproduced_the_improvement") is not False:
        return fail("T2 control did not state independent party has not reproduced")
    if t2.get("observed") != "NOT-REPRODUCED":
        return fail("T2 observed verdict is not NOT-REPRODUCED")
    print("independent_party_has_reproduced_the_improvement=False")
    print("accuracy_claim_held_at_E3=True overclaim_killed=True")
    print("SUCCESS:RES-0028-probe2 independent reproduction control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
