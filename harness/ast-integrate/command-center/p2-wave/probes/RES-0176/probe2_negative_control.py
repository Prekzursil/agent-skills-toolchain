#!/usr/bin/env python3
"""Probe 2: adversarial reviewer — both-states transfer + E3 one-rail.

Defaults to REFUTED unless:
  * live claims are E2 against captured bytes
  * conversational_group_chat is NOT transferable with GroupChatManager named
  * a mutant that marks that abstraction transferable is rejected
  * a one-rail claim grades E3 / not citable
  * a fabricated quote is not citable
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from lib import (  # noqa: E402
    ARTIFACT,
    grade_claim,
    load_harvest_index,
    transfer_verdict_errors,
)


def fail(msg: str) -> int:
    print(f"FAILED:RES-0176-probe2 {msg}")
    return 1


def main() -> int:
    doc = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    idx = load_harvest_index()
    claims = [c for c in (doc.get("claims") or []) if isinstance(c, dict)]
    if len(claims) < 3:
        return fail("too-few-claims")

    for c in claims:
        g = grade_claim(c, idx)
        if not g["citable_as_measured_fact"]:
            return fail(f"good-state-not-citable:{c.get('claim_id')} {g['problems']}")
    print("both_states good=True (all claims E2 against live bytes)")

    sample = copy.deepcopy(claims[0])
    sample["source_lineage"] = (sample.get("source_lineage") or [])[:1]
    g1 = grade_claim(sample, idx)
    print(f"one_rail tier={g1['tier']} citable={g1['citable_as_measured_fact']}")
    if g1["tier"] != "E3" or g1["citable_as_measured_fact"]:
        return fail("one-rail-must-be-e3")

    broken = copy.deepcopy(claims[0])
    for r in broken.get("source_lineage") or []:
        r["quote"] = "THIS-QUOTE-IS-NOT-IN-ANY-SNAPSHOT-BYTES-RES-0176"
    g2 = grade_claim(broken, idx)
    print(
        f"fabricated_quote citable={g2['citable_as_measured_fact']} "
        f"problems={g2['problems']}"
    )
    if g2["citable_as_measured_fact"] or not g2["problems"]:
        return fail("fabricated-quote-silent")

    verdicts = copy.deepcopy(doc.get("transfer_verdicts") or [])
    good_errs = transfer_verdict_errors(verdicts)
    print(f"good_verdicts errors={good_errs}")
    if good_errs:
        return fail(f"good-verdicts-red:{good_errs}")

    mutant = copy.deepcopy(verdicts)
    flipped = False
    for v in mutant:
        if v.get("abstraction") == "conversational_group_chat":
            v["transferable"] = True
            flipped = True
    if not flipped:
        return fail("groupchat-verdict-missing")
    bad_errs = transfer_verdict_errors(mutant)
    print(f"mutant_transferable_true errors={bad_errs}")
    if "negative-control-absent-no-nontransferable" not in bad_errs:
        return fail("mutant-transferable-silent")

    stripped = copy.deepcopy(verdicts)
    for v in stripped:
        if v.get("abstraction") == "conversational_group_chat":
            v["runtime_service"] = ""
    strip_errs = transfer_verdict_errors(stripped)
    print(f"mutant_unnamed_runtime errors={strip_errs}")
    if not any("runtime-service-unnamed" in e for e in strip_errs):
        return fail("unnamed-runtime-silent")

    nc = doc.get("negative_control") or {}
    if nc.get("transferable") is not False:
        return fail("artifact-negative-control-not-false")
    if "GroupChatManager" not in str(nc.get("runtime_service") or ""):
        return fail("artifact-runtime-service-missing")

    print(
        "fired_on_bad=True silent_on_good=True "
        "groupchat_not_transferable=True named_runtime=GroupChatManager"
    )
    print(
        "SUCCESS:RES-0176-probe2 reviewer both-states, E3 one-rail, "
        "non-transferable group chat"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
