"""Gated mutation modules (TST-0119)."""
from __future__ import annotations

GATED_MODULES = (
    "tools.plugin.strict_json",
    "tools.plugin.case_collision",
)


def gated_names() -> list[str]:
    return list(GATED_MODULES)
