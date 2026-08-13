"""V2: dump the operative fields for the 7 units my two-field classifier disputes."""

import json
from pathlib import Path

rows = json.load(open(Path(__file__).parent / "v1_rows_HEAD.json", encoding="utf-8"))
by = {r["id"]: r for r in rows}
SAT10 = [
    "AUD-0006",
    "AUD-0020",
    "AUD-0021",
    "AUD-0030",
    "AUD-0041",
    "AUD-0051",
    "CC-0002",
    "IMP-0440",
    "TST-0334",
    "TST-0350",
]
DISP = [r["id"] for r in rows if not r["cross_either"] and r["id"] not in SAT10]
print("DISPUTED (my=ANY_INDEP, builder=RAIL_BLOCKED):", DISP)
for uid in DISP:
    r = by[uid]
    print("\n" + "=" * 90)
    print(uid, "state=", r["state"])
    print("--- catalog reviewer_requirement ---")
    print(repr(r["req"])[:1400])
    print("--- receipt failure.blocked_on ---")
    print(repr(r["bo"])[:1400])
print("\n\n### now the 10 satisfiable, operative fields verbatim ###")
for uid in SAT10:
    r = by[uid]
    print("\n" + "=" * 90)
    print(uid)
    print("REQ:", repr(r["req"])[:900])
    print("BO :", repr(r["bo"])[:900])
