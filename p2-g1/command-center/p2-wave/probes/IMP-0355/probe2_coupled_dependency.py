#!/usr/bin/env python3
"""Probe 2: genuinely coupled question — dependency pass must FIRE before split.

Mechanically different from probe 1 (no recompose path). Silent on an
independent fixture from the same pack (both-states).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURES = HERE / "fixtures" / "compounds.json"
MODULE = REPO / "tools" / "council" / "decompose.py"


def load_mod():
    sys.path.insert(0, str(MODULE.parent))
    import decompose as mod  # noqa: E402

    return mod


def main() -> int:
    if not MODULE.is_file():
        print("FAILED:IMP-0355-probe2 missing tools/council/decompose.py")
        return 1
    D = load_mod()
    pack = json.loads(FIXTURES.read_text(encoding="utf-8"))
    coupled = pack["coupled"]
    independent = pack["independent"][0]

    deps = D.detect_dependencies(coupled)
    spl = D.split(coupled, require_independent=True)
    interacting = list(deps.interacting_ids)
    reasons = sorted({e.reason for e in deps.edges})

    print(
        f"coupled id={coupled['id']} fired={deps.fired} "
        f"split_accepted={spl.accepted} n_edges={len(deps.edges)} "
        f"interacting={interacting} reasons={reasons}"
    )

    fail = False
    if not deps.fired:
        print("FAILED:IMP-0355-probe2 dependency pass silent on coupled question")
        fail = True
    if not spl.dependency_pass_fired:
        print("FAILED:IMP-0355-probe2 split did not record dependency_pass_fired")
        fail = True
    if spl.accepted or spl.subquestions:
        print("FAILED:IMP-0355-probe2 coupled question was accepted as independent")
        fail = True
    if "q-p99" not in interacting or "q-retry" not in interacting:
        print(f"FAILED:IMP-0355-probe2 interacting ids incomplete: {interacting}")
        fail = True
    if "needs-bind" not in reasons and "token-bind" not in reasons and "causal-need" not in reasons:
        print(f"FAILED:IMP-0355-probe2 expected bind-coupling, got {reasons}")
        fail = True

    # Strip declared needs: token/causal path must still fire (annotation-not-trusted).
    stripped = {
        "id": coupled["id"] + "-stripped-needs",
        "text": coupled["text"],
        "clauses": [
            {**coupled["clauses"][0]},
            {**coupled["clauses"][1], "needs": []},
        ],
    }
    stripped_deps = D.detect_dependencies(stripped)
    if not stripped_deps.fired:
        print("FAILED:IMP-0355-probe2 silent after needs[] stripped (annotation-only detector)")
        fail = True
    else:
        print(
            f"stripped-needs still fired n_edges={len(stripped_deps.edges)} "
            f"reasons={sorted({e.reason for e in stripped_deps.edges})}"
        )

    good_deps = D.detect_dependencies(
        {
            "id": independent["id"],
            "text": independent["text"],
            "clauses": independent["clauses"],
        }
    )
    good_split = D.split(
        {
            "id": independent["id"],
            "text": independent["text"],
            "clauses": independent["clauses"],
        }
    )
    if good_deps.fired or not good_split.accepted:
        print("FAILED:IMP-0355-probe2 dependency pass fired on independent fixture")
        fail = True
    else:
        print(
            f"independent id={independent['id']} fired={good_deps.fired} "
            f"accepted={good_split.accepted} silent_on_good=True"
        )

    summary = {
        "probe": "probe2-coupled-dependency",
        "unit_id": "IMP-0355",
        "coupled_fired": deps.fired,
        "split_refused": (not spl.accepted) and spl.dependency_pass_fired,
        "interacting_ids": interacting,
        "reasons": reasons,
        "stripped_needs_still_fired": stripped_deps.fired,
        "silent_on_independent": (not good_deps.fired) and good_split.accepted,
        "pass": (not fail),
    }
    print(json.dumps(summary, sort_keys=True))
    if fail:
        print("FAILED:IMP-0355-probe2 coupled dependency pass")
        return 1
    print("SUCCESS:IMP-0355-probe2 coupled question fires dependency pass before split")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
