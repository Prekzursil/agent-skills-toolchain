#!/usr/bin/env python3
"""Probe 2: cost-aware Pareto frontier vs a quality-only mutant.

Live: a worse-and-more-expensive candidate is labeled dominated, and the
2%-at-6x-tokens candidate is not collapsed into the 2%-for-free candidate.

Mutant: COST_AWARE_FRONTIER flipped False in memory. The domination pass
returns empty, so D is no longer identified as dominated. The live file is
not written.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import ModuleType

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from bench.cost import (  # noqa: E402
    COST_AWARE_FRONTIER,
    identify_dominated,
    objective_rank,
    pareto_frontier,
    quality_cost_delta,
)
from fixtures import records  # noqa: E402

UNIT = "TST-0304"
COST_PY = REPO / "tools/bench/cost.py"
MARKER = "COST_AWARE_FRONTIER = True  # TST-0304-COST-AWARE-FRONTIER"
MUTANT_LINE = "COST_AWARE_FRONTIER = False  # TST-0304-COST-AWARE-FRONTIER"
ART = REPO / "command-center/receipts/TST-0304.json"
SENTINEL = "SUCCESS:TST-0304"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def load_mutant() -> ModuleType:
    src = COST_PY.read_text(encoding="utf-8")
    if src.count(MARKER) != 1:
        raise RuntimeError(f"marker count={src.count(MARKER)}")
    mutant_src = src.replace(MARKER, MUTANT_LINE, 1)
    if MARKER in mutant_src:
        raise RuntimeError("mutant still contains live frontier flag")
    if MUTANT_LINE not in mutant_src:
        raise RuntimeError("mutant flag not inserted")
    mod = ModuleType("bench_cost_mutant")
    sys.modules["bench_cost_mutant"] = mod
    exec(compile(mutant_src, "<TST-0304-mutant>", "exec"), mod.__dict__)
    return mod


def main() -> int:
    if COST_AWARE_FRONTIER is not True:
        return fail("live COST_AWARE_FRONTIER is not True")
    src = COST_PY.read_text(encoding="utf-8")
    if src.count(MARKER) != 1:
        return fail(f"live marker count={src.count(MARKER)}")

    recs = records()
    by_id = {r.candidate_id: r for r in recs}
    live_dom = identify_dominated(recs)
    live_front = [r.candidate_id for r in pareto_frontier(recs)]
    live_ids = {row["candidate_id"]: row for row in live_dom}

    if live_front != ["B"]:
        return fail(f"live frontier {live_front} want ['B']")
    if "D" not in live_ids:
        return fail("live frontier did not mark D as dominated")
    if live_ids["D"]["kind"] != "worse_and_more_expensive":
        return fail(f"D kind {live_ids['D']['kind']}")
    if "A" not in live_ids["D"]["dominated_by"] or "B" not in live_ids["D"]["dominated_by"]:
        return fail(f"D dominators {live_ids['D']['dominated_by']}")
    if "C" not in live_ids:
        return fail("live frontier hid the 6x-token 2% candidate instead of dominating it")
    if live_ids["C"]["kind"] != "equal_quality_more_expensive":
        return fail(f"C kind {live_ids['C']['kind']}")

    delta_free = quality_cost_delta(by_id["A"], by_id["B"])
    delta_costly = quality_cost_delta(by_id["A"], by_id["C"])
    if abs(float(delta_costly["tokens_ratio"]) - 6.0) > 1e-12:
        return fail("C is not the 6x-token candidate")
    if abs(float(delta_free["tokens_ratio"]) - 1.0) > 1e-12:
        return fail("B is not the 1x-token candidate")
    ranked = objective_rank(recs)
    if not ranked or not ranked[0]["efficiency_is_last"]:
        return fail("resource efficiency is not last in the objective order")
    if ranked[0]["candidate_id"] != "B":
        return fail(f"objective rank head {ranked[0]['candidate_id']}")

    mutant = load_mutant()
    if mutant.COST_AWARE_FRONTIER is not False:
        return fail("mutant flag did not flip")
    mut_dom = mutant.identify_dominated(recs)
    mut_front = [r.candidate_id for r in mutant.pareto_frontier(recs)]
    if mut_dom:
        return fail(f"cost-blind mutant still labeled dominated {mut_dom}")
    mut_ids = {r.candidate_id for r in recs}
    if set(mut_front) != mut_ids:
        return fail(f"cost-blind mutant frontier {mut_front} did not keep every candidate")
    if any(row["candidate_id"] == "D" for row in mut_dom):
        return fail("mutant still identified D")

    if COST_PY.read_text(encoding="utf-8").count(MARKER) != 1:
        return fail("live cost.py was rewritten; mutant must be in-memory only")
    if COST_AWARE_FRONTIER is not True:
        return fail("live flag mutated in-process")

    payload = {
        "pass": True,
        "probe": "probe2-frontier",
        "unit_id": UNIT,
        "live_frontier": live_front,
        "live_dominated": live_dom,
        "mutant_frontier": mut_front,
        "mutant_dominated": mut_dom,
        "delta_free": delta_free,
        "delta_costly": delta_costly,
        "objective_rank": ranked,
        "live_flag": True,
        "mutant_flag": False,
        "source_unchanged": True,
    }
    print(json.dumps(payload, sort_keys=True, ensure_ascii=True, default=str))

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        if SENTINEL not in text:
            return fail("completion_sentinel absent from artifact")
        doc = json.loads(text)
        if str(doc.get("state") or "").upper() in NOT_DELIVERING:
            return fail(f"self-declared {doc.get('state')}")
        measured = doc.get("measured") or {}
        if measured.get("frontier") != ["B"]:
            return fail("receipt frontier drift")
        if "D" not in (measured.get("dominated_ids") or []):
            return fail("receipt missing dominated D")

    print(
        f"frontier={live_front} dominated={sorted(live_ids)} "
        f"mutant_dominated={len(mut_dom)} D_kind={live_ids['D']['kind']}"
    )
    print(
        f"SUCCESS:{UNIT}-probe2 cost-aware frontier identifies dominated D; "
        "quality-only mutant does not"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
