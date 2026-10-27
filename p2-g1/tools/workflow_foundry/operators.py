"""Operator registry for foundry replay (IMP-0194)."""
from __future__ import annotations

from workflow_foundry.replay_log import _apply

OPS = {"upper", "join", "digest"}


def apply_op(tool: str, values: list) -> str:
    return _apply(tool, values)
