r"""Dump the FULL catalog row for named units, so the build is to the row and not a paraphrase."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"


def main() -> int:
    doc = json.loads(CATALOG.read_text(encoding="utf-8"))
    by_id = {u["id"]: u for u in doc["work_units"]}
    for uid in sys.argv[1:]:
        u = by_id.get(uid)
        print("=" * 100)
        if not u:
            print(f"{uid}: NOT IN CATALOG")
            continue
        print(json.dumps(u, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
