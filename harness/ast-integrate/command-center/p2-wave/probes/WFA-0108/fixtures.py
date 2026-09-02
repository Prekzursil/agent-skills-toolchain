"""Executable fusion corpus for WFA-0108.

WFA-0059 (mechanism incidence matrix) and WFA-0094 (semantic differ) are not
on this worktree. The matrix here is extracted from each workflow's stage
*definition* (declared mechanism ids), not from prose self-description — the
WFA-0059 extraction rule, applied to a closed fixture set so the detector is
live rather than BLOCKED on a missing upstream artifact.

Each mechanism writes a distinctive token. Reachability is a graph walk from
the workflow entry; a declared id that is not on any reachable stage is the
named failure 'mechanism id present in the record, behaviour not reachable'.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

UNIT = "WFA-0108"
NAMED_FAILURE = "workflow fusion loses a source capability"
FAILURE_CLASS_ID = "FC-11332"
SPEC_ANCHOR = "_USER-PROMPTS.md:11332"
SEVERITY_P1 = "P1"

MECH_REVIEW = "mech.review-gate"
MECH_SEARCH = "mech.search-tool"
MECH_BUDGET = "mech.budget-stop"
MECH_RETRY = "mech.retry-recovery"
MECH_LICENSE = "mech.license-scan"

TOKENS = {
    MECH_REVIEW: "REVIEW-TOKEN",
    MECH_SEARCH: "SEARCH-TOKEN",
    MECH_BUDGET: "BUDGET-TOKEN",
    MECH_RETRY: "RETRY-TOKEN",
    MECH_LICENSE: "LICENSE-TOKEN",
}

EXTRACTION_RULE = (
    "definition-derived: credit a mechanism only when a stage object names it; "
    "prose self-description is ignored (WFA-0059 use-versus-mention control)"
)


def _stage(sid: str, mechanism_id: str, successors: list[str] | None = None) -> dict[str, Any]:
    return {
        "id": sid,
        "mechanism_id": mechanism_id,
        "successors": list(successors or []),
    }


def _wf(
    wid: str,
    *,
    entry: str,
    stages: list[dict[str, Any]],
    declared: list[str],
    role: str,
) -> dict[str, Any]:
    return {
        "id": wid,
        "role": role,
        "entry": entry,
        "stages": {s["id"]: deepcopy(s) for s in stages},
        "declared_mechanisms": list(declared),
    }


def _handlers() -> dict[str, Any]:
    def stamp(mech: str):
        token = TOKENS[mech]

        def run(case: dict[str, Any]) -> dict[str, Any]:
            out = dict(case)
            marks = list(out.get("marks") or [])
            if token not in marks:
                marks.append(token)
            out["marks"] = marks
            out[f"ran:{mech}"] = True
            if mech == MECH_REVIEW:
                out["blocked"] = bool(out.get("risk") == "high" and not out.get("approved"))
            if mech == MECH_SEARCH:
                out["hits"] = ["fixture://search"]
            if mech == MECH_BUDGET:
                out["stopped"] = int(out.get("tokens") or 0) > int(out.get("budget") or 100)
            if mech == MECH_RETRY:
                out["attempts"] = int(out.get("attempts") or 0) + 1
                out["recovered"] = True
            if mech == MECH_LICENSE:
                out["license_ok"] = True
            return out

        return run

    return {mech: stamp(mech) for mech in TOKENS}


HANDLERS = _handlers()

SRC_ALPHA = _wf(
    "src-alpha",
    entry="s-review",
    stages=[
        _stage("s-review", MECH_REVIEW, ["s-search"]),
        _stage("s-search", MECH_SEARCH, []),
    ],
    declared=[MECH_REVIEW, MECH_SEARCH],
    role="source",
)

SRC_BETA = _wf(
    "src-beta",
    entry="s-budget",
    stages=[
        _stage("s-budget", MECH_BUDGET, ["s-retry"]),
        _stage("s-retry", MECH_RETRY, []),
    ],
    declared=[MECH_BUDGET, MECH_RETRY],
    role="source",
)

SRC_GAMMA = _wf(
    "src-gamma",
    entry="s-license",
    stages=[_stage("s-license", MECH_LICENSE, [])],
    declared=[MECH_LICENSE],
    role="source",
)

# Lossless union: every source mechanism declared AND wired from entry.
FUSION_KEEP = _wf(
    "fusion-keep",
    entry="f-review",
    stages=[
        _stage("f-review", MECH_REVIEW, ["f-search"]),
        _stage("f-search", MECH_SEARCH, ["f-budget"]),
        _stage("f-budget", MECH_BUDGET, ["f-retry"]),
        _stage("f-retry", MECH_RETRY, ["f-license"]),
        _stage("f-license", MECH_LICENSE, []),
    ],
    declared=[MECH_REVIEW, MECH_SEARCH, MECH_BUDGET, MECH_RETRY, MECH_LICENSE],
    role="fusion",
)

# Planted lossy fusion: retry-recovery dropped from the incidence record AND
# from the pipeline. Both signals must name mech.retry-recovery.
FUSION_LOSS = _wf(
    "fusion-lossy-planted",
    entry="f-review",
    stages=[
        _stage("f-review", MECH_REVIEW, ["f-search"]),
        _stage("f-search", MECH_SEARCH, ["f-budget"]),
        _stage("f-budget", MECH_BUDGET, []),
    ],
    declared=[MECH_REVIEW, MECH_SEARCH, MECH_BUDGET],
    role="fusion",
)

# Disconnected: retry-recovery remains in the declared incidence set (so
# signal A is silent) but the stage is not reachable from entry (signal B).
FUSION_DISC = _wf(
    "fusion-disconnected",
    entry="f-review",
    stages=[
        _stage("f-review", MECH_REVIEW, ["f-search"]),
        _stage("f-search", MECH_SEARCH, ["f-budget"]),
        _stage("f-budget", MECH_BUDGET, []),
        _stage("f-retry-orphan", MECH_RETRY, []),
    ],
    declared=[MECH_REVIEW, MECH_SEARCH, MECH_BUDGET, MECH_RETRY],
    role="fusion",
)

# Phantom declaration the other way: license-scan is reachable in the fused
# pipeline but omitted from the incidence record. Signal A fires, B does not.
FUSION_PHANTOM = _wf(
    "fusion-phantom-declaration",
    entry="f-review",
    stages=[
        _stage("f-review", MECH_REVIEW, ["f-search"]),
        _stage("f-search", MECH_SEARCH, ["f-license"]),
        _stage("f-license", MECH_LICENSE, []),
    ],
    declared=[MECH_REVIEW, MECH_SEARCH],
    role="fusion",
)

FUSIONS = [
    {
        "id": "fusion-keep",
        "kind": "lossless",
        "source_ids": ["src-alpha", "src-beta", "src-gamma"],
        "workflow": FUSION_KEEP,
        "planted_loss": [],
        "expect_signal_a_missing": [],
        "expect_signal_b_missing": [],
        "expect_divergence": False,
        "expect_may_certify": True,
    },
    {
        "id": "fusion-lossy-planted",
        "kind": "planted-lossy",
        "source_ids": ["src-alpha", "src-beta"],
        "workflow": FUSION_LOSS,
        "planted_loss": [MECH_RETRY],
        "expect_signal_a_missing": [MECH_RETRY],
        "expect_signal_b_missing": [MECH_RETRY],
        "expect_divergence": False,
        "expect_may_certify": False,
    },
    {
        "id": "fusion-disconnected",
        "kind": "disconnected-behaviour",
        "source_ids": ["src-alpha", "src-beta"],
        "workflow": FUSION_DISC,
        "planted_loss": [MECH_RETRY],
        "expect_signal_a_missing": [],
        "expect_signal_b_missing": [MECH_RETRY],
        "expect_divergence": True,
        "expect_may_certify": False,
    },
    {
        "id": "fusion-phantom-declaration",
        "kind": "phantom-declaration",
        "source_ids": ["src-alpha", "src-gamma"],
        "workflow": FUSION_PHANTOM,
        "planted_loss": [],
        "expect_signal_a_missing": [MECH_LICENSE],
        "expect_signal_b_missing": [],
        "expect_divergence": True,
        "expect_may_certify": False,
    },
]

SOURCES = {
    "src-alpha": SRC_ALPHA,
    "src-beta": SRC_BETA,
    "src-gamma": SRC_GAMMA,
}

SEED_CASES = {
    MECH_REVIEW: {"risk": "high", "approved": False},
    MECH_SEARCH: {"query": "fusion-capability"},
    MECH_BUDGET: {"tokens": 250, "budget": 100},
    MECH_RETRY: {"attempts": 0, "failed": True},
    MECH_LICENSE: {"path": "fixture://license"},
}


def all_workflows() -> dict[str, dict[str, Any]]:
    out = dict(SOURCES)
    for spec in FUSIONS:
        out[spec["id"]] = spec["workflow"]
    return out
