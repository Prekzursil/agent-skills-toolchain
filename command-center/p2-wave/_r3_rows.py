"""Dump the FULL catalog rows for the units this round intends to build, so the build is against
the row rather than a paraphrase of it."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
catalog = json.loads(
    (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
)
by_id = {u["id"]: u for u in catalog["work_units"]}
for uid in sys.argv[1:]:
    print("=" * 100)
    print(json.dumps(by_id[uid], indent=1, sort_keys=True))
