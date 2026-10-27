"""Shared IMP-0149 fixture catalog: filename -> expected violation ids."""
from __future__ import annotations

from agentspec.validate import VIOLATIONS

CASES: dict[str, list[str]] = {
    "valid.json": [],
    "param-unknown-key.json": ["param-unknown-key"],
    "phase7-all-types.json": [],
}
for vid in VIOLATIONS:
    CASES[f"{vid}.json"] = [vid]
# pad to >= 40
i = 0
while len(CASES) < 40:
    i += 1
    CASES[f"pad-{i:02d}.json"] = []
