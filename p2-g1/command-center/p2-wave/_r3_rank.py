"""Round-3 pick list, under the FIXED predicate, in the recorded owner order (OQ-2):
ascending phase, then unblocking power.

Two exclusions, both stated rather than silently applied:
  * ADV-* -- their output_path is under command-center/adversarial/, which this wave's floor
    forbids this lane from touching. They currently occupy the entire READY head, so the
    exclusion is load-bearing and is reported as a BLOCKER, not as a skip;
  * units whose artifact already exists on disk -- taken by an earlier round or a sibling.

The phase comparator carries its own control: phase is a STRING in the catalog, so a
lexicographic sort puts '10' before '2'. The control asserts the numeric order.
"""

from __future__ import annotations

import importlib.util
import json
import re
from collections import Counter
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
spec = importlib.util.spec_from_file_location(
    "ru", REPO / "command-center/ready_units.py"
)
ru = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ru)
resolver = ru._load_resolver()

catalog = json.loads(
    (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
)
units = catalog["work_units"]
by_id = {u["id"]: u for u in units}
ready = set(
    json.loads((REPO / "command-center/READY-UNITS.json").read_text(encoding="utf-8"))[
        "ready_units"
    ]
)
print(f"READY (from the tool's own output): {len(ready)}")


def phase_key(p) -> tuple[int, str]:
    m = re.match(r"(\d+)", str(p))
    return (int(m.group(1)) if m else 999, str(p))


ctl = sorted(["10", "2", "0", "2A"], key=phase_key)
assert ctl == ["0", "2", "2A", "10"], f"phase comparator BROKEN: {ctl}"
print(f"CONTROL phase comparator: ['10','2','0','2A'] -> {ctl} OK")

# unblocking power = how many units name this one as a dependency
power: Counter = Counter()
for u in units:
    for d in u.get("dependencies") or []:
        power[d] += 1

rows = []
for uid in ready:
    u = by_id[uid]
    p = u.get("output_path") or ""
    taken = bool(p) and (REPO / p).exists()
    adv = uid.startswith("ADV-") or p.startswith("command-center/adversarial/")
    rows.append(
        {
            "id": uid,
            "phase": u.get("phase"),
            "power": power[uid],
            "substrate": u.get("execution_substrate"),
            "taken": taken,
            "adversarial": adv,
            "path": p,
            "schema": u.get("output_schema"),
            "title": (u.get("title") or "")[:70],
        }
    )

excl_adv = [r for r in rows if r["adversarial"]]
excl_taken = [r for r in rows if r["taken"] and not r["adversarial"]]
cands = [r for r in rows if not r["adversarial"] and not r["taken"]]
print(f"  excluded, adversarial/ (wave scope): {len(excl_adv)}")
print(
    f"  excluded, artifact already exists  : {len(excl_taken)} -> {[r['id'] for r in excl_taken][:12]}"
)
print(f"  candidates                         : {len(cands)}")
print(
    f"  candidate substrate histogram      : {dict(Counter(r['substrate'] for r in cands))}"
)

cands.sort(key=lambda r: (phase_key(r["phase"]), -r["power"], r["id"]))
print("\nrank  unit      phase power substrate         output_path")
for i, r in enumerate(cands[:14], 1):
    print(
        f"{i:4d}  {r['id']:9s} {str(r['phase']):5s} {r['power']:5d} {str(r['substrate']):17s} {r['path']}"
    )
    print(f"      {r['title']}")

print("\nSUCCESS:r3-rank")
