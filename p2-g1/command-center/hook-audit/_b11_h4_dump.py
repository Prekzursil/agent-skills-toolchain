"""Read the H4 rows off the FIELD, not off a sentence about them."""

from __future__ import annotations

import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
d = json.loads((HERE / "H4-TIMING-live.json").read_text(encoding="utf-8"))
rows = d["checks"]
print("ROW KEYS:", sorted(rows[0]))
print()
head = "{:<13} {:<34} {:>9} {:>9} {:>8} {:>7}".format(
    "event", "check", "load_ms", "run_ms", "budget_s", "pct"
)
print(head)
print("-" * len(head))
for x in sorted(rows, key=lambda z: z.get("run_ms") or 0):
    print(
        "{:<13} {:<34} {:>9} {:>9} {:>8} {:>7}".format(
            str(x.get("event")),
            str(x.get("name")),
            str(x.get("load_ms")),
            str(x.get("run_ms")),
            str(x.get("budget_s")),
            str(x.get("pct_of_budget")),
        )
    )
print()
print("n rows =", len(rows))
