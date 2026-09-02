#!/usr/bin/env python3
"""Probe 1: seven single-condition-removed negatives plus both-states control.

FIRE: known-good advantage and known-good complement are CERTIFIED.
SILENT/REFUSE: each of the seven single-condition removals is refused.
Stage-count independence: n_stages=1 and n_stages=99 do not change the verdict.
A detector that only ever sees the good packet has not been shown to refuse.
"""
from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import gate as G  # noqa: E402
import packets as P  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0118-certification-gate.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0118-probe1 {msg}")
    return 1


def main() -> int:
    src = inspect.getsource(G.evaluate)
    forbidden = (
        '["n_stages"]',
        "['n_stages']",
        'get("n_stages")',
        "get('n_stages')",
        '["stage_count"]',
        "['stage_count']",
        'get("stage_count")',
        "get('stage_count')",
    )
    if any(tok in src for tok in forbidden):
        return fail("evaluate reads fusion depth; certification must ignore it")

    good = G.evaluate(P.known_good())
    print(
        f"known-good certified={good['certified']} verdict={good['verdict']} "
        f"failed={good['failed']}"
    )
    if not good["certified"] or good["verdict"] != "CERTIFIED":
        return fail(f"known-good not certified {good}")
    if any(c["result"] != "PASS" for c in good["conditions"]):
        return fail("known-good has a failing condition")

    complement = G.evaluate(P.known_good_complement())
    print(
        f"complement certified={complement['certified']} "
        f"reason={complement['conditions'][0]['reason']}"
    )
    if not complement["certified"]:
        return fail("complementarity-delta path was not certified")
    if "complementarity_delta" not in complement["conditions"][0]["reason"]:
        return fail("complement path did not use complementarity_delta")

    inc = G.evaluate(P.inconclusive_inside_floor())
    print(f"inside-floor certified={inc['certified']} verdict={inc['verdict']}")
    if inc["certified"] or inc["verdict"] != "INCONCLUSIVE":
        return fail(f"inside-floor must be INCONCLUSIVE not a pass {inc}")

    refusals = []
    for cid, packet in P.seven_negatives():
        result = G.evaluate(packet)
        print(
            f"neg {cid} certified={result['certified']} verdict={result['verdict']} "
            f"failed={result['failed']}"
        )
        if result["certified"]:
            return fail(f"negative {cid} was certified")
        if cid not in result["failed"]:
            return fail(f"negative {cid} did not fail the removed condition")
        others = [c for c in result["conditions"] if c["id"] != cid]
        if any(c["result"] != "PASS" for c in others):
            return fail(f"negative {cid} also broke a different condition")
        refusals.append(cid)
    if refusals != list(P.CONDITION_IDS):
        return fail(f"refusals={refusals}")

    stages = {}
    for name, packet in P.stage_variants():
        result = G.evaluate(packet)
        stages[name] = (result["certified"], result["verdict"], result["failed"])
        print(f"stage {name} n={packet['n_stages']} certified={result['certified']}")
    if stages["good-s1"][:2] != (True, "CERTIFIED") or stages["good-s99"][:2] != (
        True,
        "CERTIFIED",
    ):
        return fail(f"stage-good mismatch {stages}")
    if stages["lossy-s1"][0] or stages["lossy-s99"][0]:
        return fail(f"stage-lossy certified {stages}")
    if stages["lossy-s1"][2] != stages["lossy-s99"][2]:
        return fail(f"stage-lossy failed-set depends on n_stages {stages}")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if str(doc.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            return fail(f"artifact self-declared {doc.get('state')}")
        if "SUCCESS:WFA-0118" not in ART.read_text(encoding="utf-8"):
            return fail("sentinel absent from artifact")
        if doc.get("certified") is not True or doc.get("verdict") != "CERTIFIED":
            return fail("artifact featured fusion not CERTIFIED")
        negs = doc.get("negative_controls") or []
        if len(negs) != 7:
            return fail(f"artifact negative_controls={len(negs)}")
        art_removed = [n.get("removed_condition") for n in negs]
        if art_removed != list(P.CONDITION_IDS):
            return fail(f"artifact removed set {art_removed}")
        if any(n.get("certified") is not False for n in negs):
            return fail("artifact negative control marked certified")
        if doc.get("fusion_stage_count_ignored") is not True:
            return fail("artifact does not declare stage-count independence")

    payload = {
        "probe": "probe1-seven-negatives",
        "unit_id": "WFA-0118",
        "known_good_certified": True,
        "complement_certified": True,
        "inconclusive_inside_floor": inc["verdict"],
        "negatives_refused": refusals,
        "stage_independence": stages,
        "evaluate_ignores_n_stages": True,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:WFA-0118-probe1 seven negatives refused both-states stage-independent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
