"""Local authoring contract mirroring IMP-0230's six required elements.

IMP-0230 is a catalog dependency and is not on disk here. This module
enforces the same six elements so the four IMP-0247 blueprints are not
un-gated skeletons.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

REQUIRED_ELEMENTS: tuple[str, ...] = (
    "typed_workflow",
    "runnable_example",
    "preset",
    "stopping_rules",
    "smoke_test",
    "capability_vector",
)

WORKFLOW_KEYS = ("id", "kind", "discovery_only", "stages", "stopping")
STAGE_KEYS = ("id", "kind", "inputs", "outputs")
STOPPING_KEYS = ("max_stages", "on_error")


def _workflow_errors(wf: Any) -> list[str]:
    errs: list[str] = []
    if not isinstance(wf, dict):
        return ["typed_workflow is not a dict"]
    for k in WORKFLOW_KEYS:
        if k not in wf:
            errs.append(f"typed_workflow missing {k}")
    if wf.get("kind") != "workflow_blueprint":
        errs.append("kind must be workflow_blueprint")
    if not isinstance(wf.get("discovery_only"), bool):
        errs.append("discovery_only must be bool")
    stages = wf.get("stages")
    if not isinstance(stages, list) or not stages:
        errs.append("stages must be a non-empty list")
    else:
        for i, st in enumerate(stages):
            if not isinstance(st, dict):
                errs.append(f"stages[{i}] not a dict")
                continue
            for k in STAGE_KEYS:
                if k not in st:
                    errs.append(f"stages[{i}] missing {k}")
    stopping = wf.get("stopping")
    if not isinstance(stopping, dict):
        errs.append("stopping must be a dict")
    else:
        for k in STOPPING_KEYS:
            if k not in stopping:
                errs.append(f"stopping missing {k}")
        if stopping.get("on_error") not in {"halt", "skip"}:
            errs.append("stopping.on_error must be halt|skip")
        max_st = stopping.get("max_stages")
        if not isinstance(max_st, int) or max_st < 1:
            errs.append("stopping.max_stages must be int >= 1")
    return errs


def check_blueprint(bp: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    for el in REQUIRED_ELEMENTS:
        if el not in bp:
            errs.append(f"missing required element {el}")
    errs.extend(_workflow_errors(bp.get("typed_workflow")))
    if not callable(bp.get("runnable_example")):
        errs.append("runnable_example must be callable")
    preset = bp.get("preset")
    if not isinstance(preset, dict) or not preset:
        errs.append("preset must be a non-empty dict")
    if not callable(bp.get("smoke_test")):
        errs.append("smoke_test must be callable")
    cap = bp.get("capability_vector")
    if not isinstance(cap, (set, frozenset)) or not cap:
        errs.append("capability_vector must be a non-empty set")
    stopping = bp.get("stopping_rules")
    if not isinstance(stopping, dict) or not stopping:
        errs.append("stopping_rules missing")
    if not isinstance(bp.get("id"), str) or not bp.get("id"):
        errs.append("blueprint id missing")
    return errs


def check_all(blueprints: Iterable[Mapping[str, Any]]) -> dict[str, list[str]]:
    return {str(bp.get("id")): check_blueprint(bp) for bp in blueprints}


def omissions_fail_distinctly(bp: Mapping[str, Any]) -> dict[str, str]:
    tokens: dict[str, str] = {}
    for el in REQUIRED_ELEMENTS:
        mutant = dict(bp)
        mutant.pop(el, None)
        if el == "typed_workflow":
            mutant["typed_workflow"] = {}
        if el == "stopping_rules":
            mutant["stopping_rules"] = None
        errs = check_blueprint(mutant)
        tokens[el] = "" if not errs else next(
            (e for e in errs if el in e or el.split("_")[0] in e),
            errs[0],
        )
    return tokens
