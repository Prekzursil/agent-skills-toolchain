#!/usr/bin/env python3
"""Probe 2: independent blind discrimination + collapsed-taxonomy both-states.

A reader who sees only the class definition and four unlabeled candidate
definitions (1 in-class, 3 out) must pick the in-class one. The scorer is
char-4gram Jaccard in discriminate.py — it does not import assign.score_class.
Coverage numbers are reportable only when accuracy >= floor.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import assign as A  # noqa: E402
import candidates as C  # noqa: E402
import discriminate as D  # noqa: E402
import taxonomy as T  # noqa: E402

REPO = HERE.parents[3]
ART = REPO / "command-center/wfa/WFA-0035-extract-task-fit.json"
DISC_PY = HERE / "discriminate.py"
ASSIGN_PY = HERE / "assign.py"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0035-probe2 {msg}")
    return 1


def _calls_score_class(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = ""
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            if name == "score_class":
                return True
    return False


def main() -> int:
    if _calls_score_class(DISC_PY):
        return fail("discriminate.py calls score_class; scorer is not independent")
    if not _calls_score_class(ASSIGN_PY):
        return fail("assign.py no longer defines the cue scorer this probe contrasts")

    tax = T.build_taxonomy()
    pack = C.load_candidates()
    assigned = A.assign_all(pack["candidates"], tax["classes"])
    disc = D.discrimination_report(assigned["assignments"], tax["classes"])

    print(
        json.dumps(
            {
                "scorer": disc["scorer"],
                "n_trials": disc["n_trials"],
                "live_accuracy": disc["live"]["accuracy"],
                "live_hits": disc["live"]["hits"],
                "floor": disc["floor"],
                "floor_met": disc["live"]["floor_met"],
                "collapsed_accuracy": disc["collapsed"]["accuracy"],
                "collapsed_floor_met": disc["collapsed"]["floor_met"],
                "both_states_ok": disc["both_states_ok"],
            },
            sort_keys=True,
        )
    )

    if disc["n_trials"] < 8:
        return fail(f"too few discrimination trials {disc['n_trials']}")
    if not disc["live"]["floor_met"]:
        return fail(
            f"accuracy {disc['live']['accuracy']} < floor {disc['floor']}"
        )
    if disc["collapsed"]["floor_met"]:
        return fail(
            f"collapsed taxonomy still met floor "
            f"acc={disc['collapsed']['accuracy']}"
        )
    if not disc["both_states_ok"]:
        return fail("both-states failed")
    if not disc["coverage_numbers_reportable"]:
        return fail("coverage numbers not reportable")

    # Independence check: cue scorer vs 4-gram Jaccard disagree on a constructed pair.
    class_a = {
        "id": "synth-a",
        "cues": ["entropy", "prefix", "secret", "zero", "print", "never"],
        "definition": "zero entropy prefix never print secret",
    }
    class_b = {
        "id": "synth-b",
        "cues": ["generic", "workflow"],
        "definition": (
            "generic workflow library task class generic workflow library "
            "task class generic workflow library task class"
        ),
    }
    does = (
        "zero entropy prefix never print secret. generic workflow library "
        "task class generic workflow library task class generic workflow "
        "library task class"
    )
    sa = A.score_class(does, class_a)
    sb = A.score_class(does, class_b)
    ja = D.jaccard(class_a["definition"], does)
    jb = D.jaccard(class_b["definition"], does)
    cue_picks_a = sa > sb
    jac_picks_b = jb > ja
    print(
        f"INDEPENDENCE cueA={sa} cueB={sb} jacA={ja:.3f} jacB={jb:.3f} "
        f"cue_picks_a={cue_picks_a} jac_picks_b={jac_picks_b}"
    )
    if not (cue_picks_a and jac_picks_b):
        return fail("constructed pair did not show scorer disagreement")

    if not ART.is_file():
        return fail("artifact missing")
    art = json.loads(ART.read_text(encoding="utf-8"))
    if not art.get("coverage", {}).get("reported_because_discrimination_floor_met"):
        return fail("artifact reported coverage without floor gate")
    if abs(float(art["discrimination"]["live"]["accuracy"]) - disc["live"]["accuracy"]) > 1e-9:
        return fail("artifact discrimination accuracy != live recompute")

    print(
        f"verbatim known-good: accuracy={disc['live']['accuracy']:.3f} "
        f">= {disc['floor']} on {disc['n_trials']} trials"
    )
    print(
        f"verbatim planted-bad: collapsed-definition accuracy="
        f"{disc['collapsed']['accuracy']:.3f} misses floor"
    )
    print("SUCCESS:WFA-0035-probe2 blind-discrimination both-states floor-gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
