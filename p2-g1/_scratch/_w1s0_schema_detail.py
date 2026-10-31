"""Full schema error detail for the failing wave-1 shard-0 artifacts."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
MY = [
    "ADV-0006", "ADV-0019", "ADV-0029", "ADV-0033", "ADV-0037", "ADV-0060",
    "ADV-0096", "ADV-0124", "ADV-0127",
]


def main() -> int:
    cat = json.loads(
        (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    by = {u["id"]: u for u in cat["work_units"]}
    for uid in MY:
        u = by[uid]
        schema = json.loads(
            (REPO / u["output_schema"]).read_text(encoding="utf-8")
        )
        doc = json.loads((REPO / u["output_path"]).read_text(encoding="utf-8"))
        print(f"===== {uid} ({u['output_schema']}) =====")
        errs = sorted(
            jsonschema.Draft202012Validator(schema).iter_errors(doc),
            key=lambda e: str(list(e.absolute_path)),
        )
        shown = 0
        for exc in errs:
            path = "/".join(str(p) for p in exc.absolute_path)
            print(f"  ERR at [{path}]: {exc.message[:260]}")
            shown += 1
            if shown >= 4:
                remaining = sum(1 for _ in jsonschema.Draft202012Validator(schema).iter_errors(doc)) - 4
                if remaining > 0:
                    print(f"  ... +{remaining} more")
                break
    return 0


if __name__ == "__main__":
    sys.exit(main())
