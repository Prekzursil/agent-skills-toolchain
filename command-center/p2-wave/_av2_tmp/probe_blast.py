"""Blast radius of the one-key bypass + integrity check on the AUDIT's own plant sweep.

The audit reports it planted an 84-byte `{"$schema": ...}` file at EACH of the 23 vacuous units'
output_paths and observed 23/23 DELIVERED. That is a MUTATING probe against real artifact paths,
including WFA-0001 -- the program's single delivered unit. Because a planted stub is ALSO counted
delivered, the partition count cannot detect an un-restored plant. So check the FILES, not the count.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
spec = importlib.util.spec_from_file_location("ru", REPO / "command-center/ready_units.py")
ru = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ru)
resolver = ru._load_resolver()

catalog = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
units = catalog["work_units"] if isinstance(catalog, dict) else catalog
print(f"catalog units: {len(units)}")

# 1. recompute the vacuity census independently of READY-UNITS.json
decls = {}
for u in units:
    s = u.get("output_schema")
    if isinstance(s, str) and s:
        decls.setdefault(s, []).append(u["id"])
vac = {s: ids for s, ids in decls.items() if not ru.contract_discriminates(resolver, s)}
print(f"distinct declarations: {len(decls)}")
print(f"vacuous declarations : {len(vac)} -> {list(vac)}")
affected = sorted({i for ids in vac.values() for i in ids})
print(f"units declaring one  : {len(affected)}")

# 2. for each affected unit: does its artifact exist, how big, does it carry the magic key,
#    is it tracked+clean in git, and what does the predicate say?
print(
    "\n unit        exists  bytes   $schema/$id  git-status  delivered  reason"
)
planted_suspects = []
for uid in affected:
    u = next(x for x in units if x["id"] == uid)
    rel = u.get("output_path") or ""
    fp = REPO / rel if rel else None
    exists = bool(fp and fp.exists())
    size = fp.stat().st_size if exists else 0
    key = ""
    if exists and fp.suffix.lower() == ".json":
        try:
            d = json.loads(fp.read_text(encoding="utf-8"))
            key = "YES" if isinstance(d, dict) and ("$schema" in d or "$id" in d) else "no"
        except Exception:
            key = "unparseable"
    gs = subprocess.run(
        ["git", "status", "--porcelain", "--", rel],
        cwd=REPO, capture_output=True, text=True,
    ).stdout.strip() or "clean"
    ok, why = ru.artifact_delivered(u, resolver) if rel else (False, "no-output-path")
    print(f" {uid:11s} {str(exists):6s} {size:7d}  {key:11s}  {gs[:10]:10s}  {str(ok):9s} {why[:44]}")
    if exists and size < 200 and key == "YES":
        planted_suspects.append((uid, rel, size))

print(f"\n small-{{$schema}}-only suspects (possible un-restored plant): {planted_suspects}")

# 3. the real WFA-0001 artifact: is it a genuine schema pack or a stub?
w = next((x for x in units if x["id"] == "WFA-0001"), None)
if w:
    fp = REPO / w["output_path"]
    print(f"\nWFA-0001 output_path = {w['output_path']}")
    print(f"  exists={fp.exists()} bytes={fp.stat().st_size if fp.exists() else 0}")
    hh = subprocess.run(
        ["git", "log", "-1", "--format=%h %ad %s", "--date=short", "--", w["output_path"]],
        cwd=REPO, capture_output=True, text=True,
    ).stdout.strip()
    print(f"  last commit touching it: {hh}")
    st = subprocess.run(
        ["git", "status", "--porcelain", "--", w["output_path"]],
        cwd=REPO, capture_output=True, text=True,
    ).stdout.strip()
    print(f"  git status: {st or 'clean (matches committed blob)'}")
