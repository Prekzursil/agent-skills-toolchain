"""Dump complete schema error lists for the 9 failing units to a text file."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
FAILING = [
    "ADV-0006", "ADV-0019", "ADV-0029", "ADV-0033", "ADV-0037", "ADV-0060",
    "ADV-0096", "ADV-0124", "ADV-0127",
]


def main() -> int:
    cat = json.loads(
        (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    by = {u["id"]: u for u in cat["work_units"]}
    out: list[str] = []
    for uid in FAILING:
        u = by[uid]
        schema = json.loads((REPO / u["output_schema"]).read_text(encoding="utf-8"))
        doc = json.loads((REPO / u["output_path"]).read_text(encoding="utf-8"))
        out.append(f"===== {uid} =====")
        n = 0
        for exc in jsonschema.Draft202012Validator(schema).iter_errors(doc):
            path = "/".join(str(p) for p in exc.absolute_path)
            out.append(f"[{path}] {exc.message[:400]}")
            n += 1
        out.append(f"-- total {n}")
    (REPO / "_scratch/w1s0_errors.txt").write_text("\n".join(out), encoding="utf-8")
    print(f"wrote {n and ''}{len(out)} lines")
    return 0


if __name__ == "__main__":
    sys.exit(main())
