"""ROUND2 R1: read the IMP-0433 catalog row VERBATIM and the declared schema file.

The audit CONFIRMED: IMP-0433's declared output_schema accepts garbage (0 errors on a garbage
doc) => the round-1 sentence "executable-proven against its declared contract" is an overclaim
for that unit. Before fixing anything, read the row and the schema for real.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CAT = json.loads(
    (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
)
by = {u["id"]: u for u in CAT["work_units"]}

uid = sys.argv[1] if len(sys.argv) > 1 else "IMP-0433"
row = by[uid]
print(f"===== CATALOG ROW {uid} =====")
print(json.dumps(row, indent=2, ensure_ascii=False))

sch = row.get("output_schema", "")
print()
print(f"===== declared output_schema = {sch!r} =====")
for tok in [t.strip() for t in sch.replace("+", "\n").splitlines() if t.strip()]:
    base = tok.split("#")[0]
    p = REPO / base
    print(
        f"  token={tok!r} base={base!r} exists={p.exists()} size={p.stat().st_size if p.exists() else 0}"
    )
    if p.exists() and p.stat().st_size < 4000:
        print("  ---- content ----")
        print(p.read_text(encoding="utf-8"))
        print("  ---- end ----")
