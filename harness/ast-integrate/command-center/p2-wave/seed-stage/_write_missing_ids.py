#!/usr/bin/env python3
"""Leftover remaining_ids = catalog units whose output_path is missing locally."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
WAVE = REPO / "command-center" / "p2-wave"
CATALOG = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
OUT = WAVE / "P2-CLOUD-LEFTOVER_2026-08-24.json"
ids = []
for u in CATALOG.get("work_units") or []:
    rel = str(u.get("output_path") or "").replace("\\", "/")
    if not rel or not (REPO / rel).is_file():
        ids.append(u["id"])
payload = {
    "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "catalog": 2007,
    "remaining_ids": ids,
    "note": "Missing catalog output_path locally. Re-deliver and harvest receipts.",
}
OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print(len(ids))
