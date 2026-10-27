#!/usr/bin/env python3
"""Survey: run the program's own 12-condition gate on each receipt AS-IS."""
import json
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
sys.path.insert(0, str(REPO / "platform" / "lib"))
from receipt_schema_gate import evaluate_full  # noqa: E402

UNITS = [
    "ARC-0055", "ARC-0056", "ARC-0076",
    "AUD-0003", "AUD-0005", "AUD-0008", "AUD-0010", "AUD-0026",
    "AUD-0032", "AUD-0033", "AUD-0042", "AUD-0043",
]

for uid in UNITS:
    p = REPO / "command-center" / "receipts" / f"{uid}.json"
    rec = json.loads(p.read_text(encoding="utf-8"))
    result, extra = evaluate_full(rec, repo_root=REPO, verify_filesystem=True)
    blocking = [(c.n, c.outcome) for c in result.blocking_conditions]
    print(f"{uid}: state={rec.get('state')} complete={result.complete} schema_errors={len(result.schema_errors)} blocking={blocking} extra={extra[:2]}")
