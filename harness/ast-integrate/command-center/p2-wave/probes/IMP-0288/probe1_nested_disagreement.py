#!/usr/bin/env python3
"""Probe 1: 2-level nesting with a deliberate completion disagreement.

Asserts:
  * child completion is the shared reducer at the child boundary
  * parent/child disagreement is resolved by the named rule (not averaging)
  * the incomplete side blocks; both verdicts and the child's minority report survive
  * AST call-graph: _judge_at_child_boundary calls shared_judge; planted rival fires
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from tools.council.topology import nested as N  # noqa: E402
from tools.council.shared_completion import judge as shared_judge  # noqa: E402
import call_graph as CG  # noqa: E402

FIXTURE = HERE / "fixtures" / "disagreement.json"


def _q(doc: dict, key: str) -> N.BoundedQuestion:
    raw = doc["questions"][key]
    return N.BoundedQuestion(
        question_id=raw["question_id"],
        prompt=raw["prompt"],
        max_rounds=int(raw["max_rounds"]),
    )


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0288-probe1 {msg}")
    return 1


def main() -> int:
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    leaf_q = _q(doc, "leaf")
    mid_q = _q(doc, "mid")

    # --- Case A: parent reducer-COMPLETE, child reducer-INCOMPLETE ---
    a = doc["parent_complete_child_incomplete"]
    kr_a = N.InMemoryKernel()
    res_a = N.run_nested(
        parent=a["parent"],
        question=leaf_q,
        child_artifact=a["child"],
        kernel=kr_a,
        apply_resolution_rule=True,
    )
    child_v = res_a.spawn.child_verdict
    parent_v = res_a.resolution.parent
    if child_v.complete:
        return _fail(f"case-a child should be incomplete reason={child_v.reason}")
    if not parent_v.complete:
        return _fail(f"case-a parent should be complete reason={parent_v.reason}")
    if res_a.resolution.agreed:
        return _fail("case-a expected disagreement")
    if res_a.resolution.rule_id != N.RESOLUTION_RULE_ID:
        return _fail(f"case-a rule_id={res_a.resolution.rule_id}")
    if res_a.resolution.incidental:
        return _fail("case-a incidental resolution")
    if res_a.resolution.winner_complete:
        return _fail("case-a averaging: parent DONE + child NOT-DONE became DONE")
    if res_a.resolution.blocking_party != "child":
        return _fail(f"case-a blocking_party={res_a.resolution.blocking_party}")
    dissent_ids = [
        d.get("id") if isinstance(d, dict) else None for d in res_a.parent.get("dissent") or []
    ]
    if "mr-child-blocked" not in dissent_ids:
        return _fail(f"case-a minority report lost dissent={dissent_ids}")
    if not res_a.parent.get("child_evidence_cited"):
        return _fail("case-a parent overruled child without citing evidence")
    if N.uses_self_report_as_winner(res_a):
        return _fail("case-a folded completion followed self_report_complete")
    boundary = N.reducer_invocations(kr_a.events)
    if len(boundary) < 1:
        return _fail("case-a no CHILD_BOUNDARY_JUDGE event")
    if boundary[0].get("locus") != "child-boundary":
        return _fail(f"case-a locus={boundary[0].get('locus')}")

    # Child self-report is COMPLETE but reducer is not — judge, not the bit.
    judged = shared_judge(a["child"], locus="probe1-rejudge")
    if judged.complete:
        return _fail("rejudge child unexpectedly complete")
    if a["child"].get("self_report_complete") is not True:
        return _fail("fixture self_report_complete should be true (use-vs-reducer)")

    # --- Case B: parent INCOMPLETE, child COMPLETE — parent remaining work blocks ---
    b = doc["parent_incomplete_child_complete"]
    res_b = N.run_nested(
        parent=b["parent"],
        question=leaf_q,
        child_artifact=b["child"],
        apply_resolution_rule=True,
    )
    if res_b.spawn.child_verdict.complete is not True:
        return _fail("case-b child should be complete")
    if res_b.resolution.parent.complete:
        return _fail("case-b parent should be incomplete")
    if res_b.resolution.winner_complete:
        return _fail("case-b child DONE must not complete an incomplete parent")
    if res_b.resolution.blocking_party != "parent":
        return _fail(f"case-b blocking_party={res_b.resolution.blocking_party}")
    if res_b.resolution.rule_id != N.RESOLUTION_RULE_ID:
        return _fail("case-b missing rule id")

    # --- Agreeing complete: no spurious escalation ---
    c = doc["agreeing_complete"]
    res_c = N.run_nested(
        parent=c["parent"],
        question=leaf_q,
        child_artifact=c["child"],
        apply_resolution_rule=True,
    )
    if not res_c.resolution.agreed or not res_c.resolution.winner_complete:
        return _fail("agreeing pair must fold to complete without escalation")
    if res_c.resolution.blocking_party is not None:
        return _fail("agreeing pair must not name a blocking_party")

    # --- Depth-2: grandparent COMPLETE, mid COMPLETE, leaf BLOCKED ---
    d2 = doc["depth2"]
    kr2 = N.InMemoryKernel()
    both = N.run_depth2(
        grandparent=d2["grandparent"],
        mid=d2["mid"],
        leaf=d2["leaf"],
        mid_question=mid_q,
        leaf_question=leaf_q,
        kernel=kr2,
        apply_resolution_rule=True,
    )
    inner, outer = both["inner"], both["outer"]
    if inner.resolution.winner_complete:
        return _fail("depth2 inner must be incomplete (leaf blocked)")
    if outer.resolution.winner_complete:
        return _fail("depth2 outer must be incomplete (mid folded incomplete)")
    if inner.resolution.rule_id != N.RESOLUTION_RULE_ID:
        return _fail("depth2 inner missing rule id")
    if outer.resolution.rule_id != N.RESOLUTION_RULE_ID:
        return _fail("depth2 outer missing rule id")
    kinds = [e.get("kind") for e in kr2.events]
    if kinds.count("CHILD_BOUNDARY_JUDGE") < 2:
        return _fail(f"depth2 expected >=2 child-boundary judges, kinds={kinds}")
    if kinds.count("RESOLUTION") < 2:
        return _fail(f"depth2 expected >=2 RESOLUTION events, kinds={kinds}")
    dissent_ids_2 = [
        x.get("id") if isinstance(x, dict) else None
        for x in (inner.parent.get("dissent") or [])
    ]
    if "mr-leaf-blocked" not in dissent_ids_2:
        return _fail("depth2 leaf minority report not in mid dissent")

    # Unbounded child is refused.
    bad_child = dict(a["child"])
    bad_child["question_id"] = "q.unbounded.other"
    try:
        N.spawn_subcouncil(
            parent=a["parent"], question=leaf_q, child_artifact=bad_child
        )
    except N.UnboundedChildError:
        pass
    else:
        return _fail("unbounded child was not refused")

    cg = CG.child_boundary_calls_shared_reducer()
    if not cg["ok"]:
        return _fail(f"call-graph {cg}")
    named = CG.resolution_rule_is_named()
    if not named["ok"]:
        return _fail(f"rule-id ast {named}")
    mutant = CG.mutant_drops_reducer()
    if not mutant["ok"]:
        return _fail(f"planted-rival {mutant}")

    summary = {
        "probe": "probe1-nested-disagreement",
        "unit_id": "IMP-0288",
        "pass": True,
        "rule_id": N.RESOLUTION_RULE_ID,
        "case_a": {
            "parent_complete": parent_v.complete,
            "child_complete": child_v.complete,
            "winner_complete": res_a.resolution.winner_complete,
            "blocking_party": res_a.resolution.blocking_party,
            "rule_id": res_a.resolution.rule_id,
            "dissent_ids": dissent_ids,
            "child_boundary_reducer": boundary[0].get("reducer"),
        },
        "case_b": {
            "blocking_party": res_b.resolution.blocking_party,
            "winner_complete": res_b.resolution.winner_complete,
        },
        "agreeing_complete": res_c.resolution.winner_complete,
        "depth2": {
            "inner_complete": inner.resolution.winner_complete,
            "outer_complete": outer.resolution.winner_complete,
            "child_boundary_judges": kinds.count("CHILD_BOUNDARY_JUDGE"),
        },
        "call_graph": cg,
        "planted_rival": mutant,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        "case_a parent=COMPLETE child=INCOMPLETE winner=INCOMPLETE "
        f"rule={res_a.resolution.rule_id} blocking={res_a.resolution.blocking_party}"
    )
    print(
        "depth2 inner_complete="
        f"{inner.resolution.winner_complete} outer_complete={outer.resolution.winner_complete}"
    )
    print("SUCCESS:IMP-0288-probe1 2-level nested disagreement + call-graph")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
