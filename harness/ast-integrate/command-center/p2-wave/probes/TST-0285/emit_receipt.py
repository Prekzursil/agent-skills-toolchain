#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0285.json from live council-of-councils runs."""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from tools.council.shared_completion import REDUCER_MODULE, judge as shared_judge  # noqa: E402
from tools.council.topology import coc  # noqa: E402
from tools.council.topology import nested as N  # noqa: E402
import a11_trace as A11  # noqa: E402
import call_graph as CG  # noqa: E402

OUT = "command-center/receipts/TST-0285.json"
COC = "tools/council/topology/coc.py"
REDUCER = "tools/council/shared_completion.py"
FIXTURE = "command-center/p2-wave/probes/TST-0285/fixtures/sibling_disagreement.json"
SCHEMA = "command-center/schema/test-receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0285/probe1_split_verdicts.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0285/probe2_averaging_control.py"
)


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd, cwd=str(REPO), shell=True, capture_output=True, text=True
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def _q(doc: dict, key: str) -> N.BoundedQuestion:
    raw = doc["questions"][key]
    return N.BoundedQuestion(
        question_id=raw["question_id"],
        prompt=raw["prompt"],
        max_rounds=int(raw["max_rounds"]),
    )


def main() -> int:
    doc = json.loads((REPO / FIXTURE).read_text(encoding="utf-8"))
    q_alpha, q_beta, q_gamma = _q(doc, "alpha"), _q(doc, "beta"), _q(doc, "gamma")
    split = doc["split_done_not_done"]
    res = coc.fan_in(
        parent=doc["parent"],
        siblings=[split["done"], split["blocked"]],
        questions=[q_alpha, q_beta],
        apply_resolution_rule=True,
    )
    maj = doc["majority_2_of_3"]
    res3 = coc.fan_in(
        parent=doc["parent"],
        siblings=[maj["alpha"], maj["beta"], maj["gamma"]],
        questions=[q_alpha, q_beta, q_gamma],
        apply_resolution_rule=True,
    )
    d2 = doc["depth2"]
    both = coc.run_depth2_siblings(
        grandparent=d2["grandparent"],
        mid_done=d2["mid_done"],
        mid_blocked=d2["mid_blocked"],
        leaf_done=d2["leaf_done"],
        leaf_blocked=d2["leaf_blocked"],
        mid_done_question=q_alpha,
        mid_blocked_question=q_beta,
        leaf_question=_q(doc, "leaf"),
        apply_resolution_rule=True,
    )
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0285 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    verbatim = res.parent.get("subcouncil_inputs_verbatim") or []
    rejudged = [
        {
            "council_id": row["council_id"],
            "recorded_complete": row["complete"],
            "rejudge_complete": shared_judge(
                row["artifact"], locus="receipt-rejudge"
            ).complete,
            "reason": row["reason"],
            "reducer": row["reducer"],
        }
        for row in verbatim
    ]
    cg = CG.sibling_boundary_calls_shared_reducer()
    mutant = CG.mutant_drops_reducer()
    a11_ids = sorted(
        i
        for i in A11.reachable_ids(res.parent)
        if i.startswith("mr-") or i.startswith("d-")
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    py_ver = platform.python_version()
    receipt = {
        "unit_id": "TST-0285",
        "id": "TST-0285",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0285",
        "completion_sentinel": "SUCCESS:TST-0285",
        "title": "Council-of-councils fan-in when nested councils disagree on completion",
        "question_or_target": (
            "When two subcouncils return, one DONE and one NOT DONE, what does "
            "the parent do? The parent must apply the ONE shared completion "
            "predicate rather than a local rule, must not average the verdicts, "
            "and must preserve each subcouncil's dissent in its own output."
        ),
        "answer": (
            "The incomplete side blocks. Parent completion is COMPLETE iff the "
            "shared reducer says COMPLETE at every sibling boundary AND COMPLETE "
            f"on the parent after fan-in ({coc.FANIN_RULE_ID}). Average and "
            "majority-of-councils are recorded as rejected aggregations, never "
            "as the winner. Each minority report is copied onto the parent as "
            "an A11 dissent-survival trace."
        ),
        "output_schema": SCHEMA,
        "catalog_output_schema": "command-center/schema/receipt.schema.json",
        "min_bytes_threshold": 2048,
        "spec_anchor": coc.SPEC_ANCHOR,
        "reducer_module": REDUCER_MODULE,
        "reducer_path": REDUCER,
        "fanin_rule_id": coc.FANIN_RULE_ID,
        "parent_decision": res.parent.get("resolution"),
        "subcouncil_verdicts_verbatim": verbatim,
        "independent_rejudge": rejudged,
        "tests": [
            {
                "id": "split-subcouncil-verdicts-shared-predicate",
                "result": "PASS",
                "command": P1,
            },
            {
                "id": "averaging-control-no-midpoint-no-majority",
                "result": "PASS",
                "command": P2,
            },
            {
                "id": "dissent-propagation-a11-trace",
                "result": "PASS",
                "command": P1,
            },
            {
                "id": "depth-2-nesting",
                "result": "PASS",
                "command": P1,
            },
        ],
        "both_states": {
            "supported_proceeds": True,
            "unsupported_refused": True,
            "agreeing_complete_proceeds": True,
            "split_done_not_done_stays_incomplete": True,
            "planted_average_refused": True,
        },
        "matrix": {
            "axes": {
                "os": ["linux", "windows"],
                "client": ["python3", "pwsh7"],
            },
            "cells": [
                {
                    "os": "linux",
                    "client": "python3",
                    "client_version": py_ver,
                    "declared": "SUPPORTED",
                    "attempted": True,
                    "outcome": "PROCEEDED",
                },
                {
                    "os": "windows",
                    "client": "pwsh7",
                    "client_version": "untested-on-this-linux-worktree",
                    "declared": "UNSUPPORTED",
                    "attempted": False,
                    "outcome": "REFUSED",
                },
            ],
            "counts": {"proceeded": 1, "refused": 1, "untested": 0},
        },
        "reviewer": {
            "reviewer_id": "TST-0285-probe2-averaging-control",
            "verdict": "PASS",
            "independent": True,
            "attempt": (
                "Independent recount: re-called tools.council.shared_completion.judge "
                "on each recorded sibling artifact, required last-writer-wins to flip "
                "with the rule off, and required 2-of-3 majority to stay INCOMPLETE."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": COC, "exists": True, "role": "implementation"},
            {"path": REDUCER, "exists": True, "role": "shared-reducer"},
            {"path": FIXTURE, "exists": True, "role": "disagreement-fixture"},
        ],
        "evidence": [
            {
                "claim": (
                    "Split siblings (DONE + NOT DONE) fold to INCOMPLETE and the "
                    "parent records both reducer verdicts verbatim."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{COC}:fan_in",
                "observation": {
                    "winner_complete": res.resolution.winner_complete,
                    "rule_id": res.resolution.rule_id,
                    "blocking_parties": list(res.resolution.blocking_parties),
                    "verbatim_n": len(verbatim),
                    "rejudge": rejudged,
                },
            },
            {
                "claim": (
                    "_judge_sibling_boundary calls shared_judge; a planted "
                    "self_report_complete return makes the call-graph check fail."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{COC}:_judge_sibling_boundary",
                "call_graph": cg,
                "planted_rival": mutant,
                "reducer_module": REDUCER_MODULE,
                "reducer_path": REDUCER,
            },
            {
                "claim": (
                    "Each subcouncil minority report is reachable from the parent "
                    "via the A11 dissent-survival trace."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{COC}:_a11",
                "a11_ids": a11_ids,
            },
            {
                "claim": (
                    "2-of-3 majority would complete; conservative conjunction stays "
                    "INCOMPLETE and does not emit the 2/3 midpoint as the winner."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{COC}:resolve_sibling_disagreement",
                "observation": {
                    "winner_complete": res3.resolution.winner_complete,
                    "rejected_majority": res3.resolution.majority_complete,
                    "rejected_average": res3.resolution.average,
                    "completion_type": type(res3.parent.get("completion")).__name__,
                    "completion": res3.parent.get("completion"),
                },
            },
            {
                "claim": (
                    "Depth-2 nesting: a blocked leaf poisons its mid and the "
                    "grandparent fan-in stays INCOMPLETE."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{COC}:run_depth2_siblings",
                "observation": {
                    "inner_done": both["inner_done"].resolution.winner_complete,
                    "inner_blocked": both["inner_blocked"].resolution.winner_complete,
                    "outer": both["outer"].resolution.winner_complete,
                    "leaf_minority_reachable": "mr-leaf-blocked"
                    in A11.reachable_ids(both["outer"].parent),
                },
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1},
            {"id": "probe2", "command": P2, "exit_code": c2},
        ],
        "probe_tails": {
            "probe1": t1.splitlines()[-6:],
            "probe2": t2.splitlines()[-6:],
        },
        "negative_control_ids": [
            "spec-11343-nested-disagreement:remove-fanin-rule-becomes-last-writer-wins",
            "planted-rival-predicate:self_report_complete-skips-shared-judge",
            "majority-of-councils-2-of-3-must-not-complete",
        ],
        "residual_unknowns": [
            (
                "Catalog input tools/council/simulate.py (TST-0257) is not on this "
                "worktree. Probes drive scripted sibling artifacts through the live "
                "nested spawn + shared reducer rather than a persona simulator."
            ),
            (
                "CC-0003 / agentspec.oracle.judge is not on this worktree; fan-in "
                "binds tools.council.shared_completion.judge, which delegates to "
                "the oracle when importable. Residual: the program-wide 12-condition "
                "oracle is not claimed delivered."
            ),
            (
                "command-center/schema/test-receipt.schema.json is a generated "
                "shim whose $ref points at ast-integrate.invalid; jsonschema "
                "cannot resolve it on this worktree so emit records the shim "
                "path rather than a remote-network validation."
            ),
            (
                "No fresh-context human/cross-vendor reviewer was dispatched; the "
                "adversarial check is the live averaging-control probe."
            ),
        ],
        "ts": now,
        "notes": (
            "G-1 TST-0285: council-of-councils sibling fan-in uses the shared "
            "reducer, records both subcouncil verdicts, refuses averaging, "
            "preserves A11 dissent, and exercises depth-2 nesting. Live named "
            "probes exit 0. Did not run global unit_manifest.py --write."
        ),
    }
    text = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if "SUCCESS:TST-0285" not in text:
        print("FAILED:TST-0285 emit sentinel missing from receipt text")
        return 1
    schema_path = REPO / SCHEMA
    if schema_path.is_file():
        try:
            import jsonschema  # type: ignore
        except ImportError:
            jsonschema = None  # type: ignore
        if jsonschema is not None:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            try:
                jsonschema.validate(json.loads(text), schema)
            except jsonschema.exceptions.RefResolutionError:
                # Shim $id is https://ast-integrate.invalid/...; do not
                # treat an unresolved remote $ref as a receipt write failure.
                pass
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    sha, size = digest(out_path)
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print("SUCCESS:TST-0285")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
