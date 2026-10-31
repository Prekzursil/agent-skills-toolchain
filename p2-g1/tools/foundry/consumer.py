"""Foundry consumer: the downstream reader behind condition 12.

Reads a certified workflow blueprint and dispatches its stages. An action the
foundry cannot dispatch is a hard refusal, never a silent skip — this is the
executable meaning of "downstream consumers can read it".
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.foundry.completion_predicate import FOUNDRY_ACTIONS


class UndispatchableAction(RuntimeError):
    """A blueprint stage names an action the foundry cannot execute."""


def load_blueprint(path: str | Path) -> dict[str, Any]:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError("blueprint is not a JSON object")
    return doc


def dispatch_stage(stage: dict[str, Any]) -> dict[str, Any]:
    action = str(stage.get("action") or "")
    if action not in FOUNDRY_ACTIONS:
        raise UndispatchableAction(
            f"stage {stage.get('id')!r} action {action!r} is not a foundry action"
        )
    # Dispatch is a read-side capability check here: the consumer proves it can
    # interpret the stage; execution engines live in tools/foundry/runtime.py.
    return {"stage": stage.get("id"), "action": action, "dispatched": True}


def consume(path: str | Path) -> dict[str, Any]:
    """Read a blueprint and dispatch every stage. Raises on any refusal."""
    doc = load_blueprint(path)
    stages = doc.get("stages")
    if not isinstance(stages, list) or not stages:
        raise ValueError("blueprint has no dispatchable stages")
    results = [dispatch_stage(s) for s in stages if isinstance(s, dict)]
    return {"blueprint": doc.get("id"), "stages": results, "read_ok": True}


__all__ = ["FOUNDRY_ACTIONS", "UndispatchableAction", "consume", "dispatch_stage", "load_blueprint"]
