"""Scout-shaped fixtures. IMP-0209 is not delivered; these are the forge's input interface."""
from __future__ import annotations

from ir import clone


GOAL = "scan repo and emit candidates.json"


def _stage(
    sid: str,
    kind: str,
    inputs: list[str],
    outputs: list[str],
    tool: str,
    capability: str,
    timeout: int = 30,
) -> dict:
    return {
        "id": sid,
        "kind": kind,
        "inputs": inputs,
        "outputs": outputs,
        "tool": tool,
        "capability": capability,
        "timeout_seconds": timeout,
    }


def incumbent_workflow() -> dict:
    return {
        "id": "wf.incumbent.scan-emit",
        "kind": "workflow",
        "goal": GOAL,
        "stages": [
            _stage(
                "scan",
                "static-scan",
                ["repo"],
                ["candidates.json"],
                "repo-scan",
                "read-local",
            ),
            _stage(
                "emit",
                "emit",
                ["candidates.json"],
                ["receipt.json"],
                "receipt-emit",
                "write-local",
                15,
            ),
        ],
        "stopping": {"max_stages": 2, "on_error": "halt"},
        "initial_inputs": ["repo"],
    }


def slow_transform_workflow() -> dict:
    return {
        "id": "wf.alt.slow-transform",
        "kind": "workflow",
        "goal": GOAL,
        "stages": [
            _stage(
                "scan",
                "static-scan",
                ["repo"],
                ["candidates.json"],
                "repo-scan",
                "read-local",
            ),
            _stage(
                "rank",
                "transform",
                ["candidates.json"],
                ["ranked.json"],
                "json-transform",
                "transform-json",
                90,
            ),
            _stage(
                "emit",
                "emit",
                ["ranked.json"],
                ["receipt.json"],
                "receipt-emit",
                "write-local",
                15,
            ),
        ],
        "stopping": {"max_stages": 3, "on_error": "halt"},
        "initial_inputs": ["repo"],
    }


def fast_transform_workflow() -> dict:
    wf = slow_transform_workflow()
    wf = clone(wf)
    wf["id"] = "wf.alt.fast-transform"
    for st in wf["stages"]:
        if st["id"] == "rank":
            st["id"] = "rank-fast"
            st["timeout_seconds"] = 5
            st["tool"] = "json-write"
    return wf


def pretty_cycle_workflow() -> dict:
    """Looks complete (id, stages, stopping, tools) but dataflow is cyclic."""
    return {
        "id": "wf.pretty.cycle",
        "kind": "workflow",
        "goal": GOAL,
        "stages": [
            _stage(
                "scan",
                "static-scan",
                ["receipt.json"],
                ["candidates.json"],
                "repo-scan",
                "read-local",
            ),
            _stage(
                "emit",
                "emit",
                ["candidates.json"],
                ["receipt.json"],
                "receipt-emit",
                "write-local",
            ),
        ],
        "stopping": {"max_stages": 2, "on_error": "halt"},
        "initial_inputs": ["repo"],
    }


def pretty_unemulatable_workflow() -> dict:
    """Schema+static valid; simulation must refuse live-network by name."""
    wf = incumbent_workflow()
    wf = clone(wf)
    wf["id"] = "wf.pretty.unemulatable"
    wf["stages"][0]["capability"] = "live-network"
    return wf


def pretty_no_stopping() -> dict:
    wf = incumbent_workflow()
    wf = clone(wf)
    wf["id"] = "wf.pretty.no-stopping"
    del wf["stopping"]
    return wf


def mismatch_donor_stage() -> dict:
    """Same slot id, different io — splice must refuse CONTRACT_MISMATCH."""
    return _stage(
        "rank",
        "transform",
        ["other.json"],
        ["ranked.json"],
        "json-transform",
        "transform-json",
        5,
    )


def good_scout() -> dict:
    return {
        "source": "IMP-0209-interface-fixture",
        "goal": GOAL,
        "candidates": [
            {
                "id": "local.incumbent.scan-emit",
                "score": 0.96,
                "verdict": "adopt",
                "license": "Apache-2.0",
                "provenance": "fixture:planted-incumbent",
                "workflow": incumbent_workflow(),
            },
            {
                "id": "local.alt.slow-transform",
                "score": 0.61,
                "verdict": "adapt",
                "workflow": slow_transform_workflow(),
            },
            {
                "id": "local.alt.fast-transform",
                "score": 0.64,
                "verdict": "adapt",
                "workflow": fast_transform_workflow(),
            },
        ],
    }


def broken_scout_cycle(*, only: bool = True) -> dict:
    cands = [
        {
            "id": "local.pretty.cycle",
            "score": 0.99,
            "verdict": "adopt",
            "workflow": pretty_cycle_workflow(),
        }
    ]
    return {"source": "broken-fixture", "candidates": cands}


def broken_scout_unemulatable() -> dict:
    return {
        "source": "broken-fixture",
        "candidates": [
            {
                "id": "local.pretty.unemulatable",
                "score": 0.99,
                "verdict": "adopt",
                "workflow": pretty_unemulatable_workflow(),
            }
        ],
    }


def broken_scout_schema() -> dict:
    return {
        "source": "broken-fixture",
        "candidates": [
            {
                "id": "local.pretty.no-stopping",
                "score": 0.99,
                "verdict": "adopt",
                "workflow": pretty_no_stopping(),
            }
        ],
    }
