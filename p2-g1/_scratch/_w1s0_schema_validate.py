"""Validate the 12 wave-1 shard-0 artifacts against their catalog output_schema."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
MY = [
    "ADV-0006", "ADV-0019", "ADV-0027", "ADV-0028", "ADV-0029", "ADV-0033",
    "ADV-0037", "ADV-0038", "ADV-0060", "ADV-0096", "ADV-0124", "ADV-0127",
]


def main() -> int:
    cat = json.loads(
        (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    by = {u["id"]: u for u in cat["work_units"]}
    schema_cache: dict[str, dict] = {}
    bad = 0
    for uid in MY:
        u = by[uid]
        schema_rel = u["output_schema"]
        if schema_rel not in schema_cache:
            schema_cache[schema_rel] = json.loads(
                (REPO / schema_rel).read_text(encoding="utf-8")
            )
        schema = schema_cache[schema_rel]
        try:
            doc = json.loads(
                (REPO / u["output_path"]).read_text(encoding="utf-8")
            )
        except Exception as exc:
            print(f"FAILED:schema-validate {uid} unparseable {type(exc).__name__}")
            bad += 1
            continue
        try:
            jsonschema.validate(doc, schema)
            print(f"SUCCESS:schema-validate {uid} against {schema_rel}")
        except jsonschema.ValidationError as exc:
            bad += 1
            print(
                f"FAILED:schema-validate {uid} against {schema_rel}: "
                f"{exc.message[:300]} at {list(exc.absolute_path)[:8]}"
            )
    print(f"validation summary bad={bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
