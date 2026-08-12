"""AUDIT: blocker census, probe-file existence, substrate histogram, lane docs."""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PW = REPO / "command-center/p2-wave"

print("=" * 72)
print("P2-BLOCKED-UNITS.json")
print("=" * 72)
b = json.loads((PW / "P2-BLOCKED-UNITS.json").read_text(encoding="utf-8"))
print(f"  top-level keys: {sorted(b.keys())}")
print(json.dumps(b, indent=1)[:1800])

print()
print("=" * 72)
print("PROBE FILES claimed by the artifacts (do they exist and are they non-empty?)")
print("=" * 72)
for d in sorted(PW.rglob("probe*")) + sorted(PW.rglob("control*")):
    if d.is_file():
        print(f"  {d.relative_to(REPO).as_posix():<70} {d.stat().st_size:>9} B")

print()
print("=" * 72)
print("AUD-0041 probe2: is there REAL GitHub Actions API data?")
print("=" * 72)
p2 = PW / "probes/AUD-0041/probe2-actions-api.json"
if p2.is_file():
    d = json.loads(p2.read_text(encoding="utf-8"))
    s = json.dumps(d)
    print(f"  size={p2.stat().st_size} B  top-keys={sorted(d.keys()) if isinstance(d, dict) else type(d)}")
    print(f"  mentions run ids? {'run_id' in s or 'runs/' in s}")
    print(f"  excerpt: {s[:600]}")
else:
    print("  ABSENT")

print()
print("=" * 72)
print("SUBSTRATE HISTOGRAM over READY units (builder: local-parallel 157, local-serialized 151,")
print("                                       worktree-isolated 86, cloud-batch 55)")
print("=" * 72)
import importlib.util as il  # noqa: E402
import re  # noqa: E402
CAT = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
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


ready = []
for u in units:
    if dv(u["id"]) or u.get("owner_approval_required"):
        continue
    if all(BK.fullmatch(d) or (d in by and dv(d)) for d in (u.get("dependencies") or [])):
        ready.append(u)
hist = {}
for u in ready:
    k = u.get("execution_substrate") or "<none>"
    hist[k] = hist.get(k, 0) + 1
print(f"  READY={len(ready)}  histogram={hist}")

print()
print("=" * 72)
print("LANE DOCS")
print("=" * 72)
md = PW / "P2-BUILD-ROUND1.md"
txt = md.read_text(encoding="utf-8", errors="replace")
print(f"  P2-BUILD-ROUND1.md  {md.stat().st_size} B, {len(txt.splitlines())} lines")
secs = [ln for ln in txt.splitlines() if ln.strip().startswith("#")]
print(f"  headings ({len(secs)}):")
for h in secs[:26]:
    print(f"     {h[:100]}")
