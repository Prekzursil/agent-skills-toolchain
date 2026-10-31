"""AUDIT (independent): re-derive the builder's headline numbers with MY OWN code.

Never reads the builder's artifacts to get an answer; only compares at the end.
"""

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CAT = json.loads(
    (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
)
units = CAT["work_units"]
by = {u["id"]: u for u in units}

print("=" * 70)
print("A. TWO-SCHEMA (half-enforced) DECLARATIONS")
print("=" * 70)
two = [
    u
    for u in units
    if isinstance(u.get("output_schema"), str) and "+" in u["output_schema"]
]
print(f"  units whose output_schema contains '+' : {len(two)}   (builder claimed 41)")

# READY-UNITS.json stores only COUNTS, so recompute the ready SET here with the same rules
# ready_units.py documents (bucket-satisfied, dep must be delivered, unknown token blocks).
import importlib.util as _il  # noqa: E402

_s = _il.spec_from_file_location("ru", REPO / "command-center/ready_units.py")
_ru = _il.module_from_spec(_s)
_s.loader.exec_module(_ru)
_res = _ru._load_resolver()
_BUCKET = re.compile(r"B\d+")
_cache: dict = {}


def _deliv(uid):
    if uid not in _cache:
        u = by.get(uid)
        _cache[uid] = False if u is None else _ru.artifact_delivered(u, _res)[0]
    return _cache[uid]


ready = set()
for u in units:
    if _deliv(u["id"]) or u.get("owner_approval_required"):
        continue
    bad = False
    for dep in u.get("dependencies") or []:
        if _BUCKET.fullmatch(dep):
            continue
        if dep not in by or not _deliv(dep):
            bad = True
            break
    if not bad:
        ready.add(u["id"])
print(f"  [audit recomputed READY set size: {len(ready)}]")
two_ready = sorted(u["id"] for u in two if u["id"] in ready)
print(
    f"  of which READY now                     : {len(two_ready)} {two_ready}   (builder claimed 5)"
)

print()
print("=" * 70)
print("B. CI WORKFLOW / JOB / STEP INVENTORY  (builder: 7 / 14 / 143)")
print("=" * 70)
import yaml  # noqa: E402

wfdir = REPO / ".github/workflows"
files = (
    sorted([p for p in wfdir.iterdir() if p.suffix in (".yml", ".yaml")])
    if wfdir.is_dir()
    else []
)
njobs = nsteps = 0
for f in files:
    doc = yaml.safe_load(f.read_text(encoding="utf-8"))
    jobs = (doc or {}).get("jobs") or {}
    njobs += len(jobs)
    for jn, j in jobs.items():
        nsteps += len((j or {}).get("steps") or [])
print(f"  workflow files : {len(files)}  {[f.name for f in files]}")
print(f"  jobs           : {njobs}")
print(f"  steps          : {nsteps}")

print()
print("=" * 70)
print("C. PYTHON MODULES UNDER tools/  (builder: 679 modules)")
print("=" * 70)
tools = REPO / "tools"
pys = [p for p in tools.rglob("*.py")] if tools.is_dir() else []
print(f"  .py files under tools/ (rglob, no filter) : {len(pys)}")
print(f"  tools/lib exists                          : {(tools / 'lib').is_dir()}")
print(
    f"  .py files under tools/lib                 : {len(list((tools / 'lib').rglob('*.py'))) if (tools / 'lib').is_dir() else 'n/a'}"
)

print()
print("=" * 70)
print("D. REVIEWER GATE  (builder: 449/449 READY units carry reviewer_requirement)")
print("=" * 70)
have = sum(1 for uid in ready if (by[uid].get("reviewer_requirement") or "").strip())
print(f"  READY units                       : {len(ready)}")
print(f"  with a non-empty reviewer_requirement : {have}")

print()
print("=" * 70)
print("E. HOW MANY UNITS DECLARE A VACUOUS META-SCHEMA?")
print("=" * 70)
meta = [
    u["id"]
    for u in units
    if isinstance(u.get("output_schema"), str)
    and "meta/json-schema-draft" in u["output_schema"]
]
print(f"  units declaring meta/json-schema-draft.json : {len(meta)}")
print(
    f"  of which READY now                          : {len([m for m in meta if m in ready])}"
)
print(f"  sample: {meta[:12]}")
