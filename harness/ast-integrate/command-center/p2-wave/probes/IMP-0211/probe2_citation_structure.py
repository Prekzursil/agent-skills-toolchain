#!/usr/bin/env python3
"""Named probe 2: BUILD citations are structural, not prose.

A BUILD verdict must cite ABSENT_COVERAGE or INFERIOR_BASELINE as a closed
vocabulary kind, with typed fields. Independently recomputes the inferior
incumbent's mean from per-case rows. A mutant that drops `kind` or replaces
it with prose must fail the structural checker. Generator emit is shown
(via AST) to require consult. Guard source must not hard-code fixture ids.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from scenario import INCOMPARABLE_ID, INFERIOR_ID, PLANTED_ID, goals, registry  # noqa: E402
from workflow_foundry.anti_rebuild_guard import (  # noqa: E402
    ADOPT,
    BUILD,
    KIND_ABSENT_COVERAGE,
    KIND_INCOMPARABLE_BASELINE,
    KIND_INFERIOR_BASELINE,
    GuardError,
    assert_build_citation_structural,
    consult,
)

UNIT = "IMP-0211"
GUARD_PY = REPO / "tools/workflow_foundry/anti_rebuild_guard.py"
GATE_PY = REPO / "tools/workflow_foundry/generator_gate.py"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def _emit_requires_consult(src: str) -> bool:
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "GeneratorSession":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "emit":
                    text = ast.dump(item)
                    return (
                        "ConsultRequired" in text
                        and "_consulted" in text
                        and "RebuildBlocked" in text
                    )
    return False


def main() -> int:
    g = goals()
    reg = registry()
    inferior = consult(g["inferior_cover"], reg).as_dict()
    absent = consult(g["uncovered"], reg).as_dict()
    incomparable = consult(g["incomparable_cover"], reg).as_dict()

    try:
        assert_build_citation_structural(inferior)
        assert_build_citation_structural(absent)
    except GuardError as exc:
        return fail(f"live BUILD citation failed structural check: {exc}")

    if inferior["action"] != BUILD or inferior["citation"]["kind"] != KIND_INFERIOR_BASELINE:
        return fail(f"inferior cover was not BUILD/INFERIOR_BASELINE: {inferior}")
    if inferior["citation"]["incumbent_id"] != INFERIOR_ID:
        return fail(f"inferior cited {inferior['citation']['incumbent_id']}")
    bench = inferior["citation"]["benchmark"]
    inc = next(i for i in reg.incumbents if i.workflow_id == INFERIOR_ID)
    recomputed = inc.baseline.mean_score()
    if abs(float(bench["mean_score"]) - recomputed) > 1e-12:
        return fail("inferior mean not recomputed from per-case rows")
    if recomputed >= float(bench["quality_bar"]):
        return fail("inferior mean is not below the bar")
    if abs(recomputed - 0.4) > 1e-12:
        return fail(f"inferior mean {recomputed} expected 0.4 (decoy summary is 0.99)")
    if bench.get("at_or_above_bar") is True:
        return fail("inferior marked at_or_above_bar")

    if absent["citation"]["kind"] != KIND_ABSENT_COVERAGE:
        return fail("uncovered BUILD not ABSENT_COVERAGE")
    if not isinstance(absent["citation"]["capability_gap"], list):
        return fail("capability_gap not a list (not structural)")
    if "quantum-anneal" not in absent["citation"]["capability_gap"]:
        return fail("absent coverage gap missing quantum-anneal")

    if incomparable["action"] != ADOPT:
        return fail(f"incomparable cover must fail-closed ADOPT, got {incomparable['action']}")
    if incomparable["citation"]["kind"] != KIND_INCOMPARABLE_BASELINE:
        return fail(f"incomparable kind {incomparable['citation']['kind']}")
    if incomparable["citation"]["incumbent_id"] != INCOMPARABLE_ID:
        return fail("incomparable did not cite the covering incumbent")
    if incomparable["blocks_build"] is not True:
        return fail("incomparable ADOPT must block BUILD")

    mutant_kind = json.loads(json.dumps(inferior))
    del mutant_kind["citation"]["kind"]
    try:
        assert_build_citation_structural(mutant_kind)
        return fail("structural checker accepted BUILD with kind stripped")
    except GuardError:
        pass

    mutant_prose = json.loads(json.dumps(absent))
    mutant_prose["citation"]["kind"] = "looks new, go ahead and BUILD"
    try:
        assert_build_citation_structural(mutant_prose)
        return fail("structural checker accepted prose kind")
    except GuardError:
        pass

    mutant_empty_gap = {
        "action": BUILD,
        "blocks_build": False,
        "citation": {
            "kind": KIND_ABSENT_COVERAGE,
            "incumbent_id": None,
            "capability_gap": [],
        },
    }
    try:
        assert_build_citation_structural(mutant_empty_gap)
        return fail("empty capability_gap accepted as ABSENT_COVERAGE")
    except GuardError:
        pass

    gate_src = GATE_PY.read_text(encoding="utf-8")
    if not _emit_requires_consult(gate_src):
        return fail("generator_gate.emit does not structurally require consult")

    guard_src = GUARD_PY.read_text(encoding="utf-8")
    for needle in (PLANTED_ID, INFERIOR_ID, "quantum-anneal", "summary_score_ignored"):
        if needle in guard_src:
            return fail(f"guard hard-codes fixture token {needle!r}")

    report = {
        "probe": "probe2-citation-structure",
        "unit_id": UNIT,
        "inferior_kind": KIND_INFERIOR_BASELINE,
        "absent_kind": KIND_ABSENT_COVERAGE,
        "incomparable_kind": KIND_INCOMPARABLE_BASELINE,
        "incomparable_blocks_build": True,
        "mutant_stripped_kind_rejected": True,
        "mutant_prose_kind_rejected": True,
        "emit_requires_consult_ast": True,
        "guard_not_hardcoded_to_fixtures": True,
        "independent_mean": recomputed,
        "pass": True,
    }
    print(json.dumps(report, sort_keys=True))
    print(
        "SUCCESS:IMP-0211-probe2 BUILD cites ABSENT_COVERAGE or INFERIOR_BASELINE structurally"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
