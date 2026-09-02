#!/usr/bin/env python3
from pathlib import Path
REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
IDS = [ln.strip() for ln in (REPO/"command-center/p2-wave/ovh-monitor/g1-shards/shard-03.txt").read_text().splitlines() if ln.strip()]
for uid in IDS:
    pdir = REPO/"command-center/p2-wave/probes"/uid
    names = []
    for n in ("emit_artifact.py","emit.py","emit_receipt.py","emit_report.py","emit_census.py","write_receipts.py","emit_migration.py"):
        if (pdir/n).is_file():
            names.append(n)
    print(f"{uid}\t{','.join(names) if names else '-'}")
