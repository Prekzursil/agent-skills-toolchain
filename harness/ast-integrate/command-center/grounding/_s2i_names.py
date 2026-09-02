"""Print the exact over-spec and folded-scalar skill names per repo root."""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "_m", Path(__file__).with_name("_s2i_measure.py")
)
assert spec and spec.loader
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

for label, root in m.ROOTS.items():
    rows = []
    for p in sorted(root.glob("*/SKILL.md")):
        r = m.parse(p)
        if "error" not in r:
            rows.append(r)
    over = sorted((r["name"], r["len"]) for r in rows if r["len"] > m.SPEC_MAX)
    folded = sorted(r["name"] for r in rows if r["folded"])
    print(f"== {label}  n={len(rows)}")
    print(f"   over1024 ({len(over)}): {over}")
    print(f"   folded   ({len(folded)}): {folded}")
