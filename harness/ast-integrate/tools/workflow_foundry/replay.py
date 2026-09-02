"""Replay a generated workflow against inputs (IMP-0194)."""
from __future__ import annotations

import hashlib
from typing import Any

from workflow_foundry.replay_log import _apply


def replay_workflow(workflow: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    env = dict(inputs)
    applies = []
    for stage in workflow.get("stages") or []:
        tool = str(stage.get("tool") or stage.get("op") or "")
        args = list(stage.get("args") or [])
        out_name = str(stage.get("output") or stage.get("id"))
        values = [env.get(a, a) for a in args]
        result = _apply(tool, values)
        env[out_name] = result
        applies.append(tool)
    final = env.get("digest") or env.get((workflow.get("stages") or [{}])[-1].get("output"))
    digest = hashlib.sha256(str(final).encode("utf-8")).hexdigest()
    return {
        "applies": applies,
        "outcome": {"digest": digest, "verdict": "PASS", "final": final},
        "env": env,
    }


def outcomes_equal(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return a.get("digest") == b.get("digest") and a.get("verdict") == b.get("verdict")
