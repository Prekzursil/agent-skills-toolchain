#!/usr/bin/env python3
"""Named probe 1: TIED slot recorded as TIED and resolved by the written rule.

Both-states:
  * equal synthesize scores + written lexicographic-source-id rule
    -> fusion emits, synthesize.resolution==TIED, winner is the
    lexicographically lesser source_id (wf.wfa0103.alpha), even though
    the fixture's llm_judgement text prefers beta.
  * same equal scores with tie_rule='refuse' -> FusionBuildError TIED
    (no silent preference).
  * selection_basis=llm_judgement on a scored row -> refused
    (REPUTATION_NOT_EVIDENCE); score-separated evidence still emits.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from workflow_forge.best_of_breed import (  # noqa: E402
    REPUTATION_NOT_EVIDENCE,
    TIED,
)
import fixtures as F  # noqa: E402
import fusion_op as Op  # noqa: E402

EXPECTED_TIED_WINNER = "wf.wfa0103.alpha"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0103-probe1 {msg}")
    return 1


def main() -> int:
    srcs = F.sources()
    rule = F.tie_rule_text()
    if "lexicographic" not in rule.lower() or "TIED" not in rule:
        return fail("TIE-RULE.txt missing lexicographic/TIED text")

    resolved = Op.fuse(srcs, F.evidence_tied_synthesize())
    if not resolved.get("ok"):
        return fail(f"tied+written-rule refused: {resolved}")
    by_slot = {row["slot_id"]: row for row in resolved["selection_record"]}
    synth = by_slot.get("synthesize") or {}
    if synth.get("resolution") != "TIED":
        return fail(f"synthesize resolution {synth.get('resolution')!r} want TIED")
    if synth.get("tie_rule") != "lexicographic-source-id":
        return fail(f"synthesize tie_rule {synth.get('tie_rule')!r}")
    if synth.get("chosen_source_id") != EXPECTED_TIED_WINNER:
        return fail(
            f"TIED winner {synth.get('chosen_source_id')!r} want {EXPECTED_TIED_WINNER} "
            "(lexicographic-source-id, not llm_judgement preferring beta)"
        )
    if float(synth.get("score")) != 0.80:
        return fail(f"TIED score {synth.get('score')} want 0.80")
    losers = synth.get("losers") or []
    if not losers or float(losers[0]["score"]) != 0.80:
        return fail(f"TIED loser score missing/unequal {losers}")
    if losers[0]["source_id"] != "wf.wfa0103.beta":
        return fail(f"TIED loser {losers[0].get('source_id')}")
    # retrieve/rank remain strict-score and mixed parents.
    if by_slot["retrieve"]["chosen_source_id"] != "wf.wfa0103.alpha":
        return fail("retrieve did not stay with alpha on separated scores")
    if by_slot["rank"]["chosen_source_id"] != "wf.wfa0103.beta":
        return fail("rank did not stay with beta on separated scores")
    if by_slot["retrieve"]["resolution"] != "strict-score":
        return fail("retrieve must remain strict-score")
    written_rule_applied = True

    refused = Op.build(
        srcs, F.evidence_tied_synthesize(), tie_rule="refuse"
    )
    if refused.get("ok"):
        return fail("tied slot with no written rule was accepted")
    if refused.get("error") != TIED:
        return fail(f"refuse-path error {refused.get('error')!r} want {TIED}")
    if refused.get("slot_id") != "synthesize":
        return fail(f"refuse-path attributed {refused}")
    refuse_fires = True

    llm = Op.build(srcs, F.evidence_llm_basis())
    if llm.get("ok"):
        return fail("selection_basis=llm_judgement was accepted")
    if llm.get("error") != REPUTATION_NOT_EVIDENCE:
        return fail(
            f"llm-basis error {llm.get('error')!r} want {REPUTATION_NOT_EVIDENCE}"
        )
    llm_refused = True

    good = Op.build(srcs, F.evidence_separated())
    if not good.get("ok"):
        return fail(f"separated scores refused: {good}")
    silent_on_good = True

    prefer = Op.build(
        srcs,
        F.evidence_separated(),
        prefer_source="wf.wfa0103.beta",
    )
    if prefer.get("ok"):
        return fail("prefer_source was accepted as a selection basis")

    payload = {
        "probe": "probe1-tied-written-rule",
        "unit_id": "WFA-0103",
        "tied_slot": "synthesize",
        "tied_resolution": synth["resolution"],
        "tied_winner": synth["chosen_source_id"],
        "tied_loser": losers[0]["source_id"],
        "written_rule_applied": written_rule_applied,
        "refuse_without_rule_fires": refuse_fires,
        "llm_judgement_refused": llm_refused,
        "silent_on_separated": silent_on_good,
        "prefer_source_refused": not prefer.get("ok"),
        "both_states": True,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "tied=TIED winner=wf.wfa0103.alpha refuse_fires=True "
        "llm_judgement_refused=True silent_on_separated=True"
    )
    print("SUCCESS:WFA-0103-probe1 TIED slot recorded and resolved by written rule")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
