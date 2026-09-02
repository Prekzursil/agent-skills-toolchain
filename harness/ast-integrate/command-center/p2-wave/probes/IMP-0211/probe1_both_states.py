#!/usr/bin/env python3
"""Named probe 1: planted incumbent blocks BUILD; uncovered goal permits BUILD.

Both-states control. A guard that always ADOPTs or always BUILDs fails.
Generator emit without consult is refused; emit after ADOPT is blocked;
emit after BUILD is allowed. The planted citation must name the incumbent
run_id and a mean recomputed from per-case rows (not the decoy summary).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from scenario import PLANTED_ID, PLANTED_RUN, goals, registry  # noqa: E402
from workflow_foundry.anti_rebuild_guard import (  # noqa: E402
    ADOPT,
    BUILD,
    KIND_ABSENT_COVERAGE,
    KIND_INCUMBENT_AT_OR_ABOVE_BAR,
    consult,
)
from workflow_foundry.generator_gate import (  # noqa: E402
    ConsultRequired,
    GeneratorSession,
    RebuildBlocked,
)

ART = REPO / "command-center/receipts/IMP-0211.json"
UNIT = "IMP-0211"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    g = goals()
    reg = registry()
    covered = consult(g["planted_covered"], reg).as_dict()
    uncovered = consult(g["uncovered"], reg).as_dict()

    if covered["action"] != ADOPT or covered["blocks_build"] is not True:
        return fail(f"planted did not block BUILD: {covered}")
    cit = covered["citation"]
    if cit.get("kind") != KIND_INCUMBENT_AT_OR_ABOVE_BAR:
        return fail(f"planted kind {cit.get('kind')}")
    if cit.get("incumbent_id") != PLANTED_ID:
        return fail(f"planted cited {cit.get('incumbent_id')} want {PLANTED_ID}")
    bench = cit.get("benchmark") or {}
    if bench.get("run_id") != PLANTED_RUN:
        return fail(f"planted run_id {bench.get('run_id')} want {PLANTED_RUN}")
    mean = float(bench["mean_score"])
    if abs(mean - 0.9) > 1e-12:
        return fail(f"planted mean {mean} not recomputed 0.9 (decoy summary is 0.11)")
    if mean < float(bench["quality_bar"]):
        return fail("planted mean below bar")
    if PLANTED_ID not in covered["searched_incumbent_ids"]:
        return fail("planted incumbent was not in the searched set")

    if uncovered["action"] != BUILD or uncovered["blocks_build"] is not False:
        return fail(f"uncovered did not permit BUILD: {uncovered}")
    uc = uncovered["citation"]
    if uc.get("kind") != KIND_ABSENT_COVERAGE:
        return fail(f"uncovered kind {uc.get('kind')}")
    gap = uc.get("capability_gap") or []
    if "quantum-anneal" not in gap:
        return fail(f"uncovered gap missing quantum-anneal: {gap}")
    if uc.get("incumbent_id") is not None:
        return fail("absent coverage named an incumbent")
    if covered["action"] == uncovered["action"]:
        return fail("constant-function: both goals same action")

    sess = GeneratorSession(reg)
    try:
        sess.emit({"id": "wf.should-not-emit"})
        return fail("emit without consult was allowed")
    except ConsultRequired:
        pass

    sess.consult(g["planted_covered"])
    try:
        sess.emit({"id": "wf.rebuild.scout"})
        return fail("emit after ADOPT was allowed (rebuild of planted incumbent)")
    except RebuildBlocked as exc:
        if exc.verdict["citation"]["incumbent_id"] != PLANTED_ID:
            return fail("RebuildBlocked did not cite planted incumbent")

    sess2 = GeneratorSession(reg)
    out = sess2.adopt_or_emit(g["uncovered"], {"id": "wf.new.quantum"})
    if not out.get("emitted"):
        return fail("uncovered goal did not emit")
    if out["guard"]["action"] != BUILD:
        return fail("uncovered emit guard was not BUILD")

    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("receipt artifact missing")
    receipt = json.loads(ART.read_text(encoding="utf-8"))
    blob = json.dumps(receipt)
    if "SUCCESS:IMP-0211" not in blob:
        return fail("receipt sentinel absent")
    st = str(receipt.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"receipt self-declared {receipt.get('state')}")
    rec_planted = (receipt.get("both_states") or {}).get("planted_incumbent") or {}
    if rec_planted.get("action") != ADOPT:
        return fail("receipt both_states planted action drifted")
    rec_uncovered = (receipt.get("both_states") or {}).get("uncovered_goal") or {}
    if rec_uncovered.get("action") != BUILD:
        return fail("receipt both_states uncovered action drifted")

    report = {
        "probe": "probe1-both-states",
        "unit_id": UNIT,
        "planted_blocks_build": True,
        "uncovered_permits_build": True,
        "planted_incumbent_id": PLANTED_ID,
        "planted_run_id": bench.get("run_id"),
        "planted_mean": mean,
        "uncovered_kind": uc.get("kind"),
        "constant_function": False,
        "consult_required": True,
        "pass": True,
    }
    print(json.dumps(report, sort_keys=True))
    print("SUCCESS:IMP-0211-probe1 planted incumbent blocks BUILD; uncovered permits BUILD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
