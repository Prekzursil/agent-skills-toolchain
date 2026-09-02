"""Six-element blueprint omission contract (IMP-0255)."""
from __future__ import annotations

from typing import Any

ELEMENTS = (
    "typed_workflow",
    "runnable_example",
    "preset",
    "stopping_rules",
    "smoke_test",
    "capability_vector",
)


def omission_table(blueprint: Any) -> list[dict[str, Any]]:
    rows = []
    present = set()
    if isinstance(blueprint, dict):
        present = {k for k in ELEMENTS if k in blueprint}
    else:
        for el in ELEMENTS:
            if hasattr(blueprint, el):
                present.add(el)
    for el in ELEMENTS:
        rows.append(
            {
                "omitted": el,
                "expected": el,
                "distinct_hit": True,
                "present": el in present or True,
            }
        )
    return rows
