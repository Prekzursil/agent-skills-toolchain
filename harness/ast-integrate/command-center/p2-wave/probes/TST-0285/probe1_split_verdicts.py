#!/usr/bin/env python3
"""Probe 1: split sibling verdicts, shared reducer, A11 dissent, depth-2.

Catalog tests:
  * Split subcouncil verdicts -> parent applies the shared predicate and records both inputs.
  * Dissent propagation: each subcouncil minority report is present in the parent (A11 trace).
  * Depth-2 nesting exercised, not just one level.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from tools.council.shared_completion import REDUCER_MODULE, judge as shared_judge  # noqa: E402
from tools.council.topology import coc  # noqa: E402
from tools.council.topology import nested as N  # noqa: E402
import a11_trace as A11  # noqa: E402
import call_graph as CG  # noqa: E402

FIXTURE = HERE / "fixtures" / "sibling_disagreement.json"
REDUCER_PATH = "tools/council/shared_completion.py"


def _q(doc: dict, key: str) -> N.BoundedQuestion:
    raw = doc["questions"][key]
    return N.BoundedQuestion(
        question_id=raw["question_id"],
        prompt=raw["prompt"],
        max_rounds=int(raw["max_rounds"]),
    )


def _fail(msg: str) -> int:
    print(f"FAILED:TST-0285-probe1 {msg}")
    return 1


def main() -> int:
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    q_alpha, q_beta = _q(doc, "alpha"), _q(doc, "beta")
    split = doc["split_done_not_done"]
    parent = doc["parent"]

    kr = N.InMemoryKernel()
    res = coc.fan_in(
        parent=parent,
        siblings=[split["done"], split["blocked"]],
        questions=[q_alpha, q_beta],
        kernel=kr,
        apply_resolution_rule=True,
    )
    by_id = {s.council_id: s for s in res.siblings}
    done = by_id.get("council.alpha-done")
    blocked = by_id.get("council.beta-blocked")
    if done is None or blocked is None:
        return _fail(f"missing sibling records {list(by_id)}")
    if not done.complete:
        return _fail(f"alpha should be reducer-COMPLETE reason={done.reason}")
    if blocked.complete:
        return _fail(f"beta should be reducer-INCOMPLETE reason={blocked.reason}")
    if res.resolution.agreed:
        return _fail("split fixture must disagree")
    if res.resolution.rule_id != coc.FANIN_RULE_ID:
        return _fail(f"rule_id={res.resolution.rule_id}")
    if res.resolution.incidental:
        return _fail("split resolution must not be incidental")
    if res.resolution.winner_complete:
        return _fail("averaging: DONE + NOT-DONE must not become DONE")
    if res.parent.get("completion") is not False:
        return _fail(f"parent.completion={res.parent.get('completion')!r}")
    if not isinstance(res.parent.get("completion"), bool):
        return _fail("parent must not emit a numeric midpoint completion")
    if "council.beta-blocked" not in res.resolution.blocking_parties:
        return _fail(f"blocking_parties={res.resolution.blocking_parties}")

    verbatim = res.parent.get("subcouncil_inputs_verbatim") or []
    if len(verbatim) != 2:
        return _fail(f"parent did not record both inputs n={len(verbatim)}")
    for row in verbatim:
        live = shared_judge(row["artifact"], locus="probe1-rejudge")
        if bool(live.complete) != bool(row["complete"]):
            return _fail(f"verbatim mismatch {row['council_id']}")
        if str(row.get("reducer")) != REDUCER_MODULE:
            return _fail(f"sibling reducer not shared module: {row.get('reducer')}")
    if res.parent.get("reducer_path") != REDUCER_PATH:
        return _fail(f"parent reducer_path={res.parent.get('reducer_path')}")
    if res.parent.get("reducer_module") != REDUCER_MODULE:
        return _fail(f"parent reducer_module={res.parent.get('reducer_module')}")

    ids = A11.reachable_ids(res.parent)
    for need in ("mr-alpha-done", "mr-beta-blocked", "d-alpha-minor", "d-beta-block"):
        if need not in ids:
            return _fail(f"A11 dissent lost id={need} have={sorted(ids)}")
    sources = {r.get("source_council_id") for r in A11.a11_rows(res.parent)}
    if "council.alpha-done" not in sources or "council.beta-blocked" not in sources:
        return _fail(f"A11 sources={sources}")

    if split["blocked"].get("self_report_complete") is not True:
        return _fail("fixture self_report_complete should be true (use-vs-reducer)")
    if blocked.self_report_complete is not True:
        return _fail("blocked sibling self-report should be true")

    kinds = [e.get("kind") for e in kr.events]
    if kinds.count("CHILD_BOUNDARY_JUDGE") < 2:
        return _fail(f"expected >=2 CHILD_BOUNDARY_JUDGE kinds={kinds}")
    if "COC_FANIN" not in kinds:
        return _fail(f"missing COC_FANIN kinds={kinds}")

    ag = doc["agreeing_complete"]
    res_ok = coc.fan_in(
        parent=parent,
        siblings=[ag["alpha"], ag["beta"]],
        questions=[q_alpha, q_beta],
        apply_resolution_rule=True,
    )
    if not res_ok.resolution.winner_complete or not res_ok.resolution.agreed:
        return _fail("agreeing COMPLETE pair must fold COMPLETE")
    if res_ok.resolution.blocking_parties:
        return _fail("agreeing pair must not name blocking_parties")

    d2 = doc["depth2"]
    kr2 = N.InMemoryKernel()
    both = coc.run_depth2_siblings(
        grandparent=d2["grandparent"],
        mid_done=d2["mid_done"],
        mid_blocked=d2["mid_blocked"],
        leaf_done=d2["leaf_done"],
        leaf_blocked=d2["leaf_blocked"],
        mid_done_question=q_alpha,
        mid_blocked_question=q_beta,
        leaf_question=_q(doc, "leaf"),
        kernel=kr2,
        apply_resolution_rule=True,
    )
    inner_done, inner_blocked, outer = (
        both["inner_done"],
        both["inner_blocked"],
        both["outer"],
    )
    if not inner_done.resolution.winner_complete:
        return _fail("depth2 inner_done must be COMPLETE")
    if inner_blocked.resolution.winner_complete:
        return _fail("depth2 inner_blocked must be INCOMPLETE (leaf blocked)")
    if outer.resolution.winner_complete:
        return _fail("depth2 outer must be INCOMPLETE (sibling split)")
    if outer.resolution.rule_id != coc.FANIN_RULE_ID:
        return _fail("depth2 outer missing fan-in rule id")
    kinds2 = [e.get("kind") for e in kr2.events]
    if kinds2.count("CHILD_BOUNDARY_JUDGE") < 4:
        return _fail(f"depth2 expected >=4 child-boundary judges, kinds={kinds2}")
    if "mr-leaf-blocked" not in A11.reachable_ids(outer.parent):
        return _fail("depth2 leaf minority report not reachable from grandparent")

    cg = CG.sibling_boundary_calls_shared_reducer()
    if not cg["ok"]:
        return _fail(f"call-graph {cg}")
    cited = CG.fan_in_cites_shared_judge()
    if not cited["ok"]:
        return _fail(f"fan_in judges {cited}")
    mutant = CG.mutant_drops_reducer()
    if not mutant["ok"]:
        return _fail(f"planted-rival {mutant}")

    summary = {
        "probe": "probe1-split-verdicts",
        "unit_id": "TST-0285",
        "pass": True,
        "rule_id": coc.FANIN_RULE_ID,
        "reducer_module": REDUCER_MODULE,
        "reducer_path": REDUCER_PATH,
        "split": {
            "alpha_complete": done.complete,
            "beta_complete": blocked.complete,
            "winner_complete": res.resolution.winner_complete,
            "blocking_parties": list(res.resolution.blocking_parties),
            "verbatim_n": len(verbatim),
            "a11_ids": sorted(
                i
                for i in ids
                if i.startswith("mr-") or i.startswith("d-")
            ),
        },
        "agreeing_complete": res_ok.resolution.winner_complete,
        "depth2": {
            "inner_done": inner_done.resolution.winner_complete,
            "inner_blocked": inner_blocked.resolution.winner_complete,
            "outer": outer.resolution.winner_complete,
            "child_boundary_judges": kinds2.count("CHILD_BOUNDARY_JUDGE"),
        },
        "call_graph": cg,
        "planted_rival": mutant,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        "split alpha=COMPLETE beta=INCOMPLETE winner=INCOMPLETE "
        f"rule={res.resolution.rule_id} reducer={REDUCER_PATH}"
    )
    print(
        "depth2 inner_done="
        f"{inner_done.resolution.winner_complete} inner_blocked="
        f"{inner_blocked.resolution.winner_complete} outer="
        f"{outer.resolution.winner_complete}"
    )
    print("SUCCESS:TST-0285-probe1 split-verdicts shared-reducer A11 depth-2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
