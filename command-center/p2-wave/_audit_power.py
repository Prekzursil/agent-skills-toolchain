"""AUDIT: reconcile 'IMP-0433 unblocks 13' -- which denominator gives 13 vs my 12?"""

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


blocked, gated = [], []
for u in units:
    if dv(u["id"]):
        continue
    if u.get("owner_approval_required"):
        gated.append(u)
        continue
    if not all(
        BK.fullmatch(d) or (d in by and dv(d)) for d in (u.get("dependencies") or [])
    ):
        blocked.append(u)

T = "IMP-0433"
all_dep = [u["id"] for u in units if T in (u.get("dependencies") or [])]
blk_dep = [u["id"] for u in blocked if T in (u.get("dependencies") or [])]
gat_dep = [u["id"] for u in gated if T in (u.get("dependencies") or [])]
print(f"  units naming {T} as a dependency (ALL)          : {len(all_dep)}")
print(f"  ... of which BLOCKED (my unblocking-power basis) : {len(blk_dep)}")
print(f"  ... of which OWNER-GATED                          : {len(gat_dep)}")
print(
    f"  blocked+gated                                     : {len(blk_dep) + len(gat_dep)}"
)
print(f"  all dependents: {all_dep}")
