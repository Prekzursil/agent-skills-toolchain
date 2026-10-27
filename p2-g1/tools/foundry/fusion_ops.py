"""Fusion operators (IMP-0254)."""
from __future__ import annotations

from typing import Any

from tools.foundry import counters


class FusionRefused(RuntimeError):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


def concat(payload: dict[str, Any]) -> dict[str, Any]:
    counters.inc("fusion.apply_operator")
    a = dict(payload.get("parent_a") or {})
    b = dict(payload.get("parent_b") or {})
    sa = list(a.get("stages") or [])
    sb = list(b.get("stages") or [])
    if sa and sb:
        a_out = str(sa[-1].get("output_type") or "")
        b_in = str(sb[0].get("input_type") or "")
        if a_out and b_in and a_out != b_in:
            raise FusionRefused("contract-mismatch", f"{a_out} != {b_in}")
        # second parent starting at Goal while first ended at Doc is a mismatch
        if str(sb[0].get("input_type") or "") == "Goal" and str(sa[-1].get("output_type") or "") != "Goal":
            raise FusionRefused("contract-mismatch", "second parent restarts at Goal")
    stages = sa + sb
    return {
        "operator": payload.get("operator") or "concat",
        "id": f"fused:{a.get('id')}+{b.get('id')}",
        "stages": stages,
    }
