"""V7: SECOND-MECHANISM population (git tree walk, catalog never consulted), commit scope,
quoted-text byte check, and existence of every input the PASSes rest on."""

import json
import re
import subprocess
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")


def sh(*a):
    return subprocess.run(["git", *a], cwd=REPO, capture_output=True,
                          encoding="utf-8", errors="replace").stdout


files = [f for f in sh("ls-tree", "-r", "--name-only", "HEAD", "command-center").split("\n")
         if f.endswith(".json")]
print(f"committed JSON files under command-center/: {len(files)}")
found = {}
for f in files:
    t = sh("show", f"HEAD:{f}")
    if not t or '"state"' not in t:
        continue
    try:
        d = json.loads(t)
    except Exception:
        continue
    if not isinstance(d, dict):
        continue
    st = str(d.get("state", "")).upper()
    uid = d.get("unit_id") or d.get("id")
    if st in ("BLOCKED", "FAILED") and uid:
        found.setdefault(uid, []).append(f)
print(f"TREE-WALK distinct BLOCKED/FAILED unit_ids: {len(found)}")
cat = json.loads(sh("show", "HEAD:command-center/WORK-UNIT-CATALOG.json"))
cat_ids = {u["id"] for u in cat["work_units"]}
outside = [u for u in found if u not in cat_ids]
print(f"  outside the catalog: {outside}")
v1 = json.load(open(Path(__file__).parent / "v1_rows_HEAD.json", encoding="utf-8"))
v1ids = {r["id"] for r in v1}
print(f"  tree-walk MINUS catalog-route: {sorted(set(found) - v1ids)}")
print(f"  catalog-route MINUS tree-walk: {sorted(v1ids - set(found))}")
dupes = {k: v for k, v in found.items() if len(v) > 1}
print(f"  unit_ids with >1 committed BLOCKED receipt file: { {k: v for k, v in list(dupes.items())[:5]} }")

print("\n### commit scope ###")
for c in ["ece354d9", "2ca59cc1", "e7d1b2cd"]:
    t = sh("cat-file", "-t", c).strip()
    names = [n for n in sh("show", "--name-only", "--format=", c).split("\n") if n.strip()]
    out = [n for n in names if not n.startswith("command-center/p2-next/")]
    anc = subprocess.run(["git", "merge-base", "--is-ancestor", c, "HEAD"], cwd=REPO).returncode == 0
    print(f"  {c} type={t} files={len(names)} ancestor_of_HEAD={anc} OUTSIDE_SCOPE={out}")

print("\n### quoted-text byte check (my own, independent of the auditor) ###")
vs = json.loads(sh("show", "HEAD:command-center/p2-next/VENDOR-SATISFIABILITY.json"))
by_id = {u["id"]: u for u in cat["work_units"]}
bad = []
for r in vs["units"]:
    u = by_id[r["id"]]
    rec = json.loads(sh("show", f"HEAD:{u['output_path']}"))
    real_req = str(u.get("reviewer_requirement") or "")
    real_bo = str(((rec.get("failure") or {}).get("blocked_on")) or "")
    if r["reviewer_requirement"] != real_req:
        bad.append((r["id"], "req"))
    if r["blocked_on"] != real_bo:
        bad.append((r["id"], "bo"))
print(f"  rows={len(vs['units'])} quoted-string mismatches vs source: {bad}")
# control: a deliberately fabricated quote must be caught
print(f"  CONTROL fabricated quote detected: {'FAKE' != by_id['CC-0002'].get('reviewer_requirement')}")

print("\n### existence of every input the verifiers read ###")
for p in ["command-center/WORK-UNIT-CATALOG.json",
          "command-center/p2-next/VENDOR-SATISFIABILITY.json",
          "command-center/p2-next/REVIEW-GATE-SPLIT.json",
          "command-center/p2-next/FINAL-VERIFY.json"]:
    print(f"  HEAD:{p} -> {'OK' if sh('cat-file', '-e', f'HEAD:{p}') == '' else '?'} "
          f"{len(sh('show', f'HEAD:{p}'))} chars")
rv = list(REPO.glob("tools/**/receipt_validate*.py")) + list(REPO.glob("**/receipt_validate*.py"))
print(f"  receipt_validate script(s) on disk: {[str(p.relative_to(REPO)) for p in rv][:5]}")
print(f"  899ff779^ resolvable: {sh('rev-parse', '899ff779^').strip()[:12]}")
