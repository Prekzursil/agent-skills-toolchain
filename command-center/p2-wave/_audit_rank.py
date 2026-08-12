"""AUDIT: independently rank READY units by OQ-2 (ascending phase, then unblocking power).

Unblocking power = how many currently-blocked units name this unit as a dependency.
"""

import importlib.util as il
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CAT = json.loads(
    (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
)
units = CAT["work_units"]
by = {u["id"]: u for u in units}

s = il.spec_from_file_location("ru", REPO / "command-center/ready_units.py")
ru = il.module_from_spec(s)
s.loader.exec_module(ru)
res = ru._load_resolver()
BK = re.compile(r"B\d+")
cache = {}


def dv(uid):
    if uid not in cache:
        u = by.get(uid)
        cache[uid] = False if u is None else ru.artifact_delivered(u, res)[0]
    return cache[uid]


ready, blocked = [], []
for u in units:
    if dv(u["id"]) or u.get("owner_approval_required"):
        continue
    if all(
        BK.fullmatch(d) or (d in by and dv(d)) for d in (u.get("dependencies") or [])
    ):
        ready.append(u)
    else:
        blocked.append(u)

power = {}
for b in blocked:
    for d in b.get("dependencies") or []:
        if d in by:
            power[d] = power.get(d, 0) + 1


def phase_key(p):
    """Numeric-aware phase sort: '10' must come AFTER '2', and '2A' after '2'."""
    m = re.match(r"^(\d+)([A-Za-z]*)$", str(p or ""))
    return (int(m.group(1)), m.group(2)) if m else (999, str(p))


print(
    "  phase comparator control: ['0','2','2A','10'] sorted ->",
    sorted(["0", "2", "2A", "10"], key=phase_key),
)

ranked = sorted(
    ready, key=lambda u: (phase_key(u.get("phase")), -power.get(u["id"], 0), u["id"])
)
print()
print(f"  {'rank':<5} {'unit':<10} {'phase':<6} {'unblocks':<9} built-by-builder?")
built = {"IMP-0433", "AUD-0041", "AUD-0051", "AUD-0030", "AUD-0020"}
for i, u in enumerate(ranked[:10], 1):
    mark = (
        "YES"
        if u["id"] in built
        else ("SKIPPED (blocker recorded)" if u["id"] == "AUD-0001" else "no")
    )
    print(
        f"  {i:<5} {u['id']:<10} {str(u.get('phase')):<6} {power.get(u['id'], 0):<9} {mark}"
    )
