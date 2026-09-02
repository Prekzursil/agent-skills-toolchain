"""Fixture IR corpus and gold-pair expected signature for WFA-0094.

The catalog's live 10-workflow round-trip corpus (~/.claude/workflows) is not
on this Linux worktree. These IRs exercise the five named dimensions, including
loop, fan-out, human checkpoint, and retry/resume shapes described in WFA-0044's
question. They are fixture IRs, not claimed extractions of those live files.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from differ import KIND_ABSENT, KIND_CHANGED

ANCHOR = "command-center/p2-wave/probes/WFA-0094/fixtures.py"


def _n(nid: str, extra: dict[str, Any], seq: int = 0) -> dict[str, Any]:
    node = {"id": nid, "source_anchor": f"{ANCHOR}:{nid}", "seq": seq}
    node.update(extra)
    return node


def gold_left() -> dict[str, Any]:
    return {
        "id": "gold-left",
        "source_anchor": f"{ANCHOR}:gold-left",
        "stages": [
            _n("s-intake", {"name": "intake", "kind": "phase"}, 0),
            _n("s-plan", {"name": "plan", "kind": "phase"}, 1),
            _n("s-exec", {"name": "execute", "kind": "phase"}, 2),
        ],
        "roles": [
            _n(
                "r-planner",
                {"name": "planner", "capabilities": ["draft", "revise"]},
                0,
            ),
            _n(
                "r-critic",
                {"name": "critic", "capabilities": ["object", "score"]},
                1,
            ),
        ],
        "gates": [
            _n(
                "g-plan-ok",
                {
                    "name": "plan-approved",
                    "blocking": True,
                    "condition": "plan.approved",
                },
                0,
            ),
        ],
        "tools": [
            _n("t-read", {"name": "Read", "policy": "allow"}, 0),
            _n("t-grep", {"name": "Grep", "policy": "allow"}, 1),
            _n("t-write", {"name": "Write", "policy": "ask"}, 2),
        ],
        "stop_rules": [
            _n(
                "sr-floor",
                {"expression": "min_rounds>=2", "kind": "floor"},
                0,
            ),
        ],
    }


def gold_right() -> dict[str, Any]:
    """Known deltas vs gold_left (ids only; order of roles/tools is permuted).

    stage: s-intake ABSENT on right; s-report ABSENT on left
    role:  same set, reversed listing order (must be empty delta)
    gate:  g-plan-ok PRESENT-BUT-DIFFERENT (condition)
    tool:  t-read ABSENT on right
    stop-rule: sr-coverage ABSENT on left
    """
    return {
        "id": "gold-right",
        "source_anchor": f"{ANCHOR}:gold-right",
        "stages": [
            _n("s-plan", {"name": "plan", "kind": "phase"}, 0),
            _n("s-exec", {"name": "execute", "kind": "phase"}, 1),
            _n("s-report", {"name": "report", "kind": "phase"}, 2),
        ],
        "roles": [
            _n(
                "r-critic",
                {"name": "critic", "capabilities": ["object", "score"]},
                0,
            ),
            _n(
                "r-planner",
                {"name": "planner", "capabilities": ["draft", "revise"]},
                1,
            ),
        ],
        "gates": [
            _n(
                "g-plan-ok",
                {
                    "name": "plan-approved",
                    "blocking": True,
                    "condition": "plan.score>=0.8",
                },
                0,
            ),
        ],
        "tools": [
            _n("t-write", {"name": "Write", "policy": "ask"}, 0),
            _n("t-grep", {"name": "Grep", "policy": "allow"}, 1),
        ],
        "stop_rules": [
            _n(
                "sr-floor",
                {"expression": "min_rounds>=2", "kind": "floor"},
                0,
            ),
            _n(
                "sr-coverage",
                {"expression": "coverage>=0.9", "kind": "threshold"},
                1,
            ),
        ],
    }


# Hand-written. Must not be derived from differ.signature() at fixture-author time.
GOLD_SIGNATURE: list[tuple[str, str, str, str]] = [
    ("gate", KIND_CHANGED, "g-plan-ok", "both"),
    ("stage", KIND_ABSENT, "s-intake", "left"),
    ("stage", KIND_ABSENT, "s-report", "right"),
    ("stop-rule", KIND_ABSENT, "sr-coverage", "right"),
    ("tool", KIND_ABSENT, "t-read", "left"),
]


def _wf(
    wid: str,
    stages: list[dict[str, Any]],
    roles: list[dict[str, Any]],
    gates: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    stops: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "id": wid,
        "source_anchor": f"{ANCHOR}:{wid}",
        "stages": stages,
        "roles": roles,
        "gates": gates,
        "tools": tools,
        "stop_rules": stops,
    }


def corpus() -> list[dict[str, Any]]:
    """Ten fixture IRs standing in for the absent live saved-workflow corpus."""
    plan_gate = _wf(
        "ir-plan-gate",
        [
            _n("s-design", {"name": "design", "kind": "phase"}, 0),
            _n("s-plan", {"name": "plan", "kind": "phase"}, 1),
            _n("s-exec", {"name": "execute", "kind": "phase"}, 2),
        ],
        [
            _n("r-architect", {"name": "architect", "capabilities": ["spec"]}, 0),
            _n("r-implementer", {"name": "implementer", "capabilities": ["edit"]}, 1),
        ],
        [
            _n(
                "g-plan",
                {"name": "plan-gate", "blocking": True, "condition": "plan.ok"},
                0,
            ),
        ],
        [
            _n("t-read", {"name": "Read", "policy": "allow"}, 0),
            _n("t-edit", {"name": "Edit", "policy": "allow"}, 1),
        ],
        [_n("sr-delib", {"expression": "roles_spoken>=2", "kind": "floor"}, 0)],
    )
    design_gate = _wf(
        "ir-design-gate",
        [
            _n("s-design", {"name": "design", "kind": "phase"}, 0),
            _n("s-build", {"name": "build", "kind": "phase"}, 1),
        ],
        [_n("r-architect", {"name": "architect", "capabilities": ["spec", "review"]}, 0)],
        [
            _n(
                "g-design",
                {"name": "design-gate", "blocking": True, "condition": "design.ok"},
                0,
            ),
        ],
        [_n("t-read", {"name": "Read", "policy": "allow"}, 0)],
        [_n("sr-design", {"expression": "design.approved", "kind": "predicate"}, 0)],
    )
    loop_converge = _wf(
        "ir-loop-converge",
        [
            _n("s-draft", {"name": "draft", "kind": "loop-body"}, 0),
            _n(
                "s-critique",
                {
                    "name": "critique",
                    "kind": "loop-body",
                    "convergence": "jaccard>=0.8",
                },
                1,
            ),
            _n("s-exit", {"name": "exit", "kind": "loop-exit"}, 2),
        ],
        [
            _n("r-writer", {"name": "writer", "capabilities": ["draft"]}, 0),
            _n("r-critic", {"name": "critic", "capabilities": ["object"]}, 1),
        ],
        [
            _n(
                "g-converge",
                {
                    "name": "loop-converge",
                    "blocking": True,
                    "condition": "delta==0 OR rounds>=4",
                },
                0,
            ),
        ],
        [_n("t-write", {"name": "Write", "policy": "allow"}, 0)],
        [_n("sr-max-rounds", {"expression": "rounds<=4", "kind": "ceiling"}, 0)],
    )
    fanout = _wf(
        "ir-fanout-barrier",
        [
            _n("s-split", {"name": "split", "kind": "fan-out"}, 0),
            _n("s-a", {"name": "arm-a", "kind": "parallel"}, 1),
            _n("s-b", {"name": "arm-b", "kind": "parallel"}, 2),
            _n("s-join", {"name": "join", "kind": "barrier"}, 3),
        ],
        [_n("r-coord", {"name": "coordinator", "capabilities": ["dispatch", "join"]}, 0)],
        [
            _n(
                "g-barrier",
                {"name": "all-arms-done", "blocking": True, "condition": "pending==0"},
                0,
            ),
        ],
        [
            _n("t-agent", {"name": "Agent", "policy": "allow"}, 0),
            _n("t-wait", {"name": "Wait", "policy": "allow"}, 1),
        ],
        [_n("sr-join", {"expression": "joined==true", "kind": "predicate"}, 0)],
    )
    human = _wf(
        "ir-human-checkpoint",
        [
            _n("s-work", {"name": "work", "kind": "phase"}, 0),
            _n("s-hold", {"name": "human-hold", "kind": "checkpoint"}, 1),
        ],
        [
            _n("r-agent", {"name": "agent", "capabilities": ["propose"]}, 0),
            _n("r-owner", {"name": "owner", "capabilities": ["approve", "reject"]}, 1),
        ],
        [
            _n(
                "g-human",
                {
                    "name": "owner-approval",
                    "blocking": True,
                    "condition": "owner.decision in {approve,reject}",
                },
                0,
            ),
        ],
        [_n("t-ask", {"name": "AskUser", "policy": "require"}, 0)],
        [_n("sr-human", {"expression": "checkpoint.cleared", "kind": "predicate"}, 0)],
    )
    retry = _wf(
        "ir-retry-resume",
        [
            _n(
                "s-call",
                {
                    "name": "tool-call",
                    "kind": "action",
                    "retry": {"max": 3, "backoff": "exp"},
                    "resume": True,
                },
                0,
            ),
        ],
        [_n("r-runner", {"name": "runner", "capabilities": ["retry"]}, 0)],
        [
            _n(
                "g-retry-budget",
                {"name": "retry-budget", "blocking": True, "condition": "attempts<=3"},
                0,
            ),
        ],
        [_n("t-net", {"name": "WebFetch", "policy": "allow"}, 0)],
        [_n("sr-budget", {"expression": "attempts<=3", "kind": "ceiling"}, 0)],
    )
    min_stop = _wf(
        "ir-min-stop",
        [_n("s-only", {"name": "run", "kind": "phase"}, 0)],
        [_n("r-solo", {"name": "solo", "capabilities": ["act"]}, 0)],
        [],
        [_n("t-read", {"name": "Read", "policy": "allow"}, 0)],
        [_n("sr-done", {"expression": "true", "kind": "immediate"}, 0)],
    )
    lineage = _wf(
        "ir-lineage",
        [
            _n(
                "s-adapt",
                {
                    "name": "adapt",
                    "kind": "phase",
                    "lineage": ["src:saved-workflow", "adapter:js"],
                },
                0,
            ),
        ],
        [_n("r-adapter", {"name": "adapter", "capabilities": ["parse"]}, 0)],
        [],
        [_n("t-parse", {"name": "Parse", "policy": "allow"}, 0)],
        [_n("sr-parsed", {"expression": "ir.valid", "kind": "predicate"}, 0)],
    )
    return [
        gold_left(),
        gold_right(),
        plan_gate,
        design_gate,
        deepcopy(plan_gate) | {"id": "ir-plan-gate-clone", "source_anchor": f"{ANCHOR}:ir-plan-gate-clone"},
        loop_converge,
        fanout,
        human,
        retry,
        min_stop,
        lineage,
    ]


def present_but_different_pair() -> tuple[dict[str, Any], dict[str, Any]]:
    left = gold_left()
    right = deepcopy(left)
    right["id"] = "gold-left-gate-mutated"
    right["source_anchor"] = f"{ANCHOR}:gold-left-gate-mutated"
    right["gates"][0]["condition"] = "plan.approved AND review.ok"
    return left, right


def absent_tool_pair() -> tuple[dict[str, Any], dict[str, Any]]:
    left = gold_left()
    right = deepcopy(left)
    right["id"] = "gold-left-minus-read"
    right["source_anchor"] = f"{ANCHOR}:gold-left-minus-read"
    right["tools"] = [t for t in right["tools"] if t["id"] != "t-read"]
    return left, right
