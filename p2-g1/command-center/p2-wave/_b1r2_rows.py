r"""Dump the FULL catalog row for each unit id given on argv, so the build lane
builds to the row rather than to a paraphrase of it."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"

FIELDS = [
    "id",
    "phase",
    "title",
    "question_or_target",
    "output_path",
    "output_schema",
    "completion_sentinel",
    "evidence_requirement",
    "tests_required",
    "mechanism",
    "inputs",
    "dependencies",
    "failure_classification",
    "reviewer_requirement",
    "execution_substrate",
    "spec_anchor",
    "retry_policy",
    "tool_permissions",
]


def main() -> int:
    doc = json.loads(CATALOG.read_text(encoding="utf-8"))
    by_id = {u["id"]: u for u in doc["work_units"]}
    for uid in sys.argv[1:]:
        u = by_id.get(uid)
        if not u:
            print(f"### {uid}: NOT IN CATALOG")
            continue
        print("=" * 100)
        for f in FIELDS:
            v = u.get(f)
            if v is None:
                continue
            if isinstance(v, list):
                v = " | ".join(str(x) for x in v)
            print(f"{f:>24}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
