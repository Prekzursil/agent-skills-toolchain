"""AUDIT: read what the artifacts and lane docs ACTUALLY contain vs what the report claims."""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def load(p):
    return json.loads((REPO / p).read_text(encoding="utf-8"))


print("=" * 72)
print("AUD-0030 report")
print("=" * 72)
r = load("command-center/audit/AUD-0030-import-graph-cycles.json")["report"]
for k in ("kind", "module_count", "edge_count", "cycles", "runtime_only_imports"):
    v = r.get(k)
    print(f"  {k:<22} = {str(v)[:150]}")
print(f"  top_fan_in[:3]         = {r.get('top_fan_in', [])[:3]}")
obs = r.get("observations")
if isinstance(obs, list):
    for o in obs[:6]:
        print(f"    obs: {str(o)[:150]}")

print()
print("=" * 72)
print("AUD-0041 report + probe recording")
print("=" * 72)
a = load("command-center/audit/AUD-0041-ci-step-inventory.json")
r = a["report"]
print(f"  report keys: {sorted(r.keys())}")
for k in ("workflow_files", "job_count", "step_count", "conditional_steps", "conditional_jobs"):
    if k in r:
        print(f"  {k:<22} = {r[k]}")
ev = a.get("evidence", [])
print(f"  evidence entries: {len(ev)}")
for e in ev[:6]:
    print(f"    - anchor={str(e.get('anchor'))[:70]!r} claim={str(e.get('claim'))[:90]!r}")
tests = a.get("tests", [])
print(f"  tests entries: {len(tests)}")
for t in tests[:6]:
    print(f"    - {t.get('id')}: result={t.get('result')} cmd={str(t.get('command'))[:80]!r}")

print()
print("=" * 72)
print("STATE TALLY over artifacts that EXIST (builder: 43 of 44 self-declare not-done)")
print("=" * 72)
CAT = load("command-center/WORK-UNIT-CATALOG.json")
tally = {}
present = 0
for u in CAT["work_units"]:
    op = u.get("output_path")
    if not op:
        continue
    fp = REPO / op
    if not fp.exists() or fp.stat().st_size == 0:
        continue
    present += 1
    if fp.suffix.lower() != ".json":
        tally["<non-json>"] = tally.get("<non-json>", 0) + 1
        continue
    try:
        d = json.loads(fp.read_text(encoding="utf-8"))
    except Exception:
        tally["<unparseable>"] = tally.get("<unparseable>", 0) + 1
        continue
    st = d.get("state") if isinstance(d, dict) else None
    key = st if isinstance(st, str) else "<no-state-field>"
    tally[key] = tally.get(key, 0) + 1
print(f"  artifacts present & non-empty : {present}")
print(f"  state tally                   : {tally}")

print()
print("=" * 72)
print(".gitkeep census (builder: 14 new dirs)")
print("=" * 72)
gk = sorted(p.parent.relative_to(REPO).as_posix()
            for p in (REPO / "command-center").rglob(".gitkeep"))
print(f"  .gitkeep under command-center : {len(gk)}")
for g in gk:
    print(f"     {g}")
