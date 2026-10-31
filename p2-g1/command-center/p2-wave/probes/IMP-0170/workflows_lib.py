"""Fixture workflow, rename mutants and gate mutants for the IMP-0170 probes."""
from __future__ import annotations

import copy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

TAGS = [
    "alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta",
    "iota", "kappa", "lambda", "mu", "nu", "xi", "omicron", "pi",
    "rho", "sigma", "tau", "upsilon",
]


def base_workflow() -> dict:
    return {
        "id": "wf.research-pipeline.v1",
        "params": {"budget": 12},
        "stages": [
            {
                "id": "ingest_sources",
                "kind": "ingest",
                "title": "Ingest sources",
                "roles": ["reader"],
                "tools": [{"class": "fs-read", "instance_id": "tool-7"}],
                "gate": {"all": [{"var": "rows_gt_0"}, {"var": "schema_ok"}]},
            },
            {
                "id": "plan_batches",
                "kind": "plan",
                "title": "Plan batches",
                "roles": ["planner"],
                "tools": [],
                "gate": {"all": [{"ref": "ingest_sources"}, {"var": "timeout_lte_30"}]},
            },
            {
                "id": "refine_claims",
                "kind": "refine",
                "title": "Refine claims",
                "roles": ["analyst"],
                "tools": [{"class": "llm-call", "instance_id": "tool-12"}],
                "gate": {"not": [{"var": "underclaim"}]},
            },
            {
                "id": "act_publish",
                "kind": "act",
                "title": "Publish",
                "roles": ["writer", "reviewer"],
                "tools": [{"class": "fs-write", "instance_id": "tool-9"}],
                "gate": {"gte": [{"var": "coverage"}, 0.9]},
            },
            {
                "id": "verify_digest",
                "kind": "gate",
                "title": "Verify digest",
                "roles": ["auditor"],
                "tools": [],
                "gate": {"all": [{"ref": "act_publish"}, {"var": "digest_match"}]},
            },
            {
                "id": "stop_on_budget",
                "kind": "stopping_rule",
                "title": "Stop on budget",
                "roles": ["controller"],
                "tools": [],
                "gate": {"lte": [{"var": "spend"}, {"var": "budget"}]},
            },
        ],
        "edges": [
            ["ingest_sources", "plan_batches"],
            ["plan_batches", "refine_claims"],
            ["refine_claims", "act_publish"],
            ["act_publish", "verify_digest"],
            ["verify_digest", "stop_on_budget"],
        ],
    }


def rename_mutant(base: dict, tag: str) -> dict:
    """Rename workflow id, stage ids, tool instance ids and titles. Nothing else."""
    m = copy.deepcopy(base)
    m["id"] = tag + "." + m["id"]
    remap = {}
    for i, st in enumerate(m["stages"]):
        old = st["id"]
        new = tag + "-stage-" + str(i)
        remap[old] = new
        st["id"] = new
        st["title"] = tag + " " + str(st.get("title") or "")
        for t in st.get("tools") or []:
            if isinstance(t, dict) and t.get("instance_id"):
                t["instance_id"] = tag + "-tool-" + str(t["instance_id"])
    m["edges"] = [[remap.get(s, s), remap.get(d, d)] for s, d in m["edges"]]

    def walk(node):
        if isinstance(node, dict):
            return {k: walk(v) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(x) for x in node]
        if isinstance(node, str) and node in remap:
            return remap[node]
        return node

    for st in m["stages"]:
        st["gate"] = walk(st.get("gate"))
    return m


MUTATIONS = [
    ("ingest_all_to_any", 0, {"any": [{"var": "rows_gt_0"}, {"var": "schema_ok"}]}),
    ("plan_any_to_all", 1, {"any": [{"ref": "ingest_sources"}, {"var": "timeout_lte_30"}]}),
    ("plan_drop_timeout", 1, {"all": [{"ref": "ingest_sources"}]}),
    ("plan_timeout_31", 1, {"all": [{"ref": "ingest_sources"}, {"var": "timeout_lte_31"}]}),
    ("refine_atom_underclaim", 2, {"not": [{"var": "underclaim_v2"}]}),
    ("refine_drop_not", 2, {"var": "underclaim"}),
    ("act_coverage_0_8", 3, {"gte": [{"var": "coverage"}, 0.8]}),
    ("act_coverage_0_95", 3, {"gte": [{"var": "coverage"}, 0.95]}),
    ("act_add_budget_guard", 3, {"all": [{"gte": [{"var": "coverage"}, 0.9]}, {"var": "budget_ok"}]}),
    ("verify_ref_plan", 4, {"all": [{"ref": "plan_batches"}, {"var": "digest_match"}]}),
    ("verify_drop_ref", 4, {"var": "digest_match"}),
    ("verify_or_digest", 4, {"any": [{"ref": "act_publish"}, {"var": "digest_match"}]}),
    ("stop_spend_budget_swap", 5, {"lte": [{"var": "budget"}, {"var": "spend"}]}),
    ("stop_lt_strict", 5, {"lt": [{"var": "spend"}, {"var": "budget"}]}),
    ("stop_drop", 5, None),
    ("ingest_gate_null", 0, None),
    ("plan_ref_self", 1, {"all": [{"ref": "plan_batches"}, {"var": "timeout_lte_30"}]}),
    ("refine_not_not", 2, {"not": [{"not": [{"var": "underclaim"}]}]}),
    ("act_gte_to_gt", 3, {"gt": [{"var": "coverage"}, 0.9]}),
    ("verify_add_second_ref", 4, {"all": [{"ref": "act_publish"}, {"ref": "refine_claims"}, {"var": "digest_match"}]}),
]


def gate_mutant(base: dict, _name: str, idx: int, new_gate) -> dict:
    m = copy.deepcopy(base)
    m["stages"][idx]["gate"] = copy.deepcopy(new_gate)
    return m
