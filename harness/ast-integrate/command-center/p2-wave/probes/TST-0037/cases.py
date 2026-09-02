"""Conformance fixtures: one negative (and a good twin) per contract rule."""
from __future__ import annotations

from copy import deepcopy
from typing import Any


def _unit(nid: str, run: str) -> dict[str, Any]:
    return {"id": nid, "type": "unit", "body": {"run": run}}


def good_fanout_barrier() -> dict[str, Any]:
    return {
        "spec_version": 1,
        "id": "wf-fanout-barrier",
        "entry": "start",
        "nodes": [
            _unit("start", "begin"),
            {"id": "fo", "type": "fanout", "members": ["w1", "w2"]},
            _unit("w1", "a"),
            _unit("w2", "b"),
            {"id": "bar", "type": "barrier", "awaits": ["w1", "w2"]},
            _unit("done", "end"),
        ],
        "edges": [
            ["start", "fo"],
            ["fo", "w1"],
            ["fo", "w2"],
            ["w1", "bar"],
            ["w2", "bar"],
            ["bar", "done"],
        ],
    }


def neg_fanout_empty() -> dict[str, Any]:
    return {
        "spec_version": 1,
        "id": "wf-fanout-empty",
        "entry": "start",
        "nodes": [
            _unit("start", "begin"),
            {"id": "fo", "type": "fanout", "members": []},
        ],
        "edges": [["start", "fo"]],
    }


def neg_fanout_unknown() -> dict[str, Any]:
    return {
        "spec_version": 1,
        "id": "wf-fanout-unknown",
        "entry": "start",
        "nodes": [
            _unit("start", "begin"),
            {"id": "fo", "type": "fanout", "members": ["ghost"]},
        ],
        "edges": [["start", "fo"]],
    }


def neg_barrier_empty() -> dict[str, Any]:
    return {
        "spec_version": 1,
        "id": "wf-barrier-empty",
        "entry": "start",
        "nodes": [
            _unit("start", "begin"),
            {"id": "bar", "type": "barrier", "awaits": []},
        ],
        "edges": [["start", "bar"]],
    }


def neg_barrier_unknown() -> dict[str, Any]:
    return {
        "spec_version": 1,
        "id": "wf-barrier-unknown",
        "entry": "start",
        "nodes": [
            _unit("start", "begin"),
            {"id": "bar", "type": "barrier", "awaits": ["ghost"]},
        ],
        "edges": [["start", "bar"]],
    }


def _with_typed_node(nid: str, node: dict[str, Any]) -> dict[str, Any]:
    return {
        "spec_version": 1,
        "id": f"wf-{nid}",
        "entry": "start",
        "nodes": [_unit("start", "begin"), node],
        "edges": [["start", nid]],
    }


def good_loop() -> dict[str, Any]:
    return _with_typed_node(
        "lp",
        {
            "id": "lp",
            "type": "loop-with-convergence",
            "body": "start",
            "convergence_expr": "stable",
            "max_iterations": 3,
            "on_bound_reached": "fail",
        },
    )


def neg_loop_unbounded() -> dict[str, Any]:
    return _with_typed_node(
        "lp",
        {"id": "lp", "type": "loop-with-convergence", "body": "start"},
    )


def good_checkpoint() -> dict[str, Any]:
    return _with_typed_node(
        "hc",
        {
            "id": "hc",
            "type": "human-checkpoint",
            "prompt_ref": "approve",
            "allowed_responses": ["go", "stop"],
            "default_if_unanswered": "stop",
            "pause_token": "tok-1",
        },
    )


def neg_checkpoint_no_prompt() -> dict[str, Any]:
    doc = good_checkpoint()
    for node in doc["nodes"]:
        if node.get("id") == "hc":
            node.pop("prompt_ref", None)
    return doc


def good_subworkflow() -> dict[str, Any]:
    doc = _with_typed_node(
        "sw",
        {
            "id": "sw",
            "type": "subworkflow",
            "workflow_ref": "child",
            "param_bindings": {},
            "id_namespace": "child",
        },
    )
    doc["workflows"] = {
        "child": {
            "spec_version": 1,
            "id": "child",
            "entry": "c0",
            "nodes": [_unit("c0", "inner")],
            "edges": [],
        }
    }
    return doc


def neg_subworkflow_cycle() -> dict[str, Any]:
    doc = good_subworkflow()
    for node in doc["nodes"]:
        if node.get("id") == "sw":
            node["workflow_ref"] = "wf-sw"
    return doc


def good_retry() -> dict[str, Any]:
    return _with_typed_node(
        "rt",
        {
            "id": "rt",
            "type": "retry",
            "target": "start",
            "max_attempts": 2,
            "on_failure_classes": ["rate-limited"],
        },
    )


def neg_retry_unbounded() -> dict[str, Any]:
    doc = good_retry()
    for node in doc["nodes"]:
        if node.get("id") == "rt":
            node["max_attempts"] = 0
    return doc


def good_resume() -> dict[str, Any]:
    return {
        "spec_version": 1,
        "id": "wf-rs",
        "entry": "start",
        "nodes": [
            _unit("start", "begin"),
            {
                "id": "hc",
                "type": "human-checkpoint",
                "prompt_ref": "approve",
                "allowed_responses": ["go"],
                "pause_token": "tok-1",
            },
            {
                "id": "rs",
                "type": "resume",
                "from_token": "tok-1",
                "checkpoint_ref": "hc",
            },
        ],
        "edges": [["start", "hc"], ["hc", "rs"]],
    }


def neg_resume_no_token() -> dict[str, Any]:
    doc = good_resume()
    for node in doc["nodes"]:
        if node.get("id") == "rs":
            node["from_token"] = ""
    return doc


# Each case: construct, rule, role (good|bad), expected contract ids,
# expected production id subset, production must be clean.
CASES: tuple[dict[str, Any], ...] = (
    {
        "id": "fan-out/good",
        "construct": "fan-out",
        "rule": "fanout-empty",
        "role": "good",
        "builder": good_fanout_barrier,
        "expect_contract": frozenset(),
        "expect_production_empty": True,
        "expect_production_contains": frozenset(),
    },
    {
        "id": "fan-out/empty",
        "construct": "fan-out",
        "rule": "fanout-empty",
        "role": "bad",
        "builder": neg_fanout_empty,
        "expect_contract": frozenset({"fanout-empty"}),
        "expect_production_empty": False,
        "expect_production_contains": frozenset({"fanout-empty"}),
    },
    {
        "id": "fan-out/unknown-member",
        "construct": "fan-out",
        "rule": "fanout-unknown-member",
        "role": "bad",
        "builder": neg_fanout_unknown,
        "expect_contract": frozenset({"fanout-unknown-member"}),
        "expect_production_empty": False,
        "expect_production_contains": frozenset({"fanout-unknown-member"}),
    },
    {
        "id": "barrier/good",
        "construct": "barrier",
        "rule": "barrier-empty-awaits",
        "role": "good",
        "builder": good_fanout_barrier,
        "expect_contract": frozenset(),
        "expect_production_empty": True,
        "expect_production_contains": frozenset(),
    },
    {
        "id": "barrier/empty",
        "construct": "barrier",
        "rule": "barrier-empty-awaits",
        "role": "bad",
        "builder": neg_barrier_empty,
        "expect_contract": frozenset({"barrier-empty-awaits"}),
        "expect_production_empty": False,
        "expect_production_contains": frozenset({"barrier-empty-awaits"}),
    },
    {
        "id": "barrier/unknown-await",
        "construct": "barrier",
        "rule": "barrier-awaits-unknown",
        "role": "bad",
        "builder": neg_barrier_unknown,
        "expect_contract": frozenset({"barrier-awaits-unknown"}),
        "expect_production_empty": False,
        "expect_production_contains": frozenset({"barrier-awaits-unknown"}),
    },
    {
        "id": "loop-with-convergence/good",
        "construct": "loop-with-convergence",
        "rule": "loop-unbounded",
        "role": "good",
        "builder": good_loop,
        "expect_contract": frozenset(),
        "expect_production_empty": False,
        "expect_production_contains": frozenset({"unknown-node-type"}),
        "expect_production_absent": frozenset({"loop-unbounded"}),
    },
    {
        "id": "loop-with-convergence/unbounded",
        "construct": "loop-with-convergence",
        "rule": "loop-unbounded",
        "role": "bad",
        "builder": neg_loop_unbounded,
        "expect_contract": frozenset({"loop-unbounded"}),
        "expect_production_empty": False,
        "expect_production_contains": frozenset({"unknown-node-type"}),
        "expect_production_absent": frozenset({"loop-unbounded"}),
    },
    {
        "id": "human-checkpoint/good",
        "construct": "human-checkpoint",
        "rule": "checkpoint-missing-prompt",
        "role": "good",
        "builder": good_checkpoint,
        "expect_contract": frozenset(),
        "expect_production_empty": False,
        "expect_production_contains": frozenset({"unknown-node-type"}),
    },
    {
        "id": "human-checkpoint/no-prompt",
        "construct": "human-checkpoint",
        "rule": "checkpoint-missing-prompt",
        "role": "bad",
        "builder": neg_checkpoint_no_prompt,
        "expect_contract": frozenset({"checkpoint-missing-prompt"}),
        "expect_production_empty": False,
        "expect_production_contains": frozenset({"unknown-node-type"}),
    },
    {
        "id": "subworkflow/good",
        "construct": "subworkflow",
        "rule": "subworkflow-cycle",
        "role": "good",
        "builder": good_subworkflow,
        "expect_contract": frozenset(),
        "expect_production_empty": False,
        "expect_production_contains": frozenset({"unknown-node-type"}),
    },
    {
        "id": "subworkflow/cycle",
        "construct": "subworkflow",
        "rule": "subworkflow-cycle",
        "role": "bad",
        "builder": neg_subworkflow_cycle,
        "expect_contract": frozenset({"subworkflow-cycle"}),
        "expect_production_empty": False,
        "expect_production_contains": frozenset({"unknown-node-type"}),
        "expect_production_absent": frozenset({"subworkflow-cycle"}),
    },
    {
        "id": "retry/good",
        "construct": "retry",
        "rule": "retry-unbounded",
        "role": "good",
        "builder": good_retry,
        "expect_contract": frozenset(),
        "expect_production_empty": False,
        "expect_production_contains": frozenset({"unknown-node-type"}),
    },
    {
        "id": "retry/unbounded",
        "construct": "retry",
        "rule": "retry-unbounded",
        "role": "bad",
        "builder": neg_retry_unbounded,
        "expect_contract": frozenset({"retry-unbounded"}),
        "expect_production_empty": False,
        "expect_production_contains": frozenset({"unknown-node-type"}),
        "expect_production_absent": frozenset({"retry-unbounded"}),
    },
    {
        "id": "resume/good",
        "construct": "resume",
        "rule": "resume-missing-token",
        "role": "good",
        "builder": good_resume,
        "expect_contract": frozenset(),
        "expect_production_empty": False,
        "expect_production_contains": frozenset({"unknown-node-type"}),
    },
    {
        "id": "resume/no-token",
        "construct": "resume",
        "rule": "resume-missing-token",
        "role": "bad",
        "builder": neg_resume_no_token,
        "expect_contract": frozenset({"resume-missing-token"}),
        "expect_production_empty": False,
        "expect_production_contains": frozenset({"unknown-node-type"}),
        "expect_production_absent": frozenset({"resume-missing-token"}),
    },
)


def materialize() -> list[dict[str, Any]]:
    rows = []
    for spec in CASES:
        row = dict(spec)
        row["doc"] = deepcopy(spec["builder"]())
        rows.append(row)
    return rows
