#!/usr/bin/env python3
"""Enumerate every schema error for the five open shard-5 wave-2 artifacts.
output_path/output_schema are read from the catalog itself (no hand-typed paths)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "platform" / "lib"))

from schema_resolver import validator_for  # noqa: E402

IDS = ["AUD-0095", "BLD-0004", "BLD-0005", "BLD-0013", "BLD-0014"]


def main() -> int:
    cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    units = {u["id"]: u for u in cat.get("work_units", []) if isinstance(u, dict)}
    for uid in IDS:
        u = units[uid]
        art_rel = str(u["output_path"]).replace("\\", "/")
        sch_rel = str(u["output_schema"]).replace("\\", "/")
        doc = json.loads((REPO / art_rel).read_text(encoding="utf-8"))
        try:
            v = validator_for(sch_rel)
        except Exception as exc:  # noqa: BLE001
            print(f"=== {uid}: validator FAILED {type(exc).__name__}: {exc}")
            continue
        errs = sorted(f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
                      for e in v.iter_errors(doc))
        print(f"=== {uid}: {len(errs)} error(s)")
        for e in errs[:16]:
            print("   ", e[:260])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
