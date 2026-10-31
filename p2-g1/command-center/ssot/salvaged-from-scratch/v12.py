import json, subprocess
from pathlib import Path
REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
def sh(*a):
    return subprocess.run(["git",*a],cwd=REPO,capture_output=True,encoding="utf-8",errors="replace").stdout
cat=json.loads(sh("show","HEAD:command-center/WORK-UNIT-CATALOG.json"))
by={u["id"]:u for u in cat["work_units"]}
sg=json.loads(sh("show","HEAD:command-center/p2-next/REVIEW-GATE-SPLIT.json"))
for b,rows in sg["buckets"].items():
    for r in rows:
        real=str(by[r["id"]].get("reviewer_requirement") or "")
        q=r.get("reviewer_requirement","")
        if q!=real:
            print(f"{r['id']:10s} bucket={b} qlen={len(q)} reallen={len(real)} prefix={real.startswith(q)}")
            print(f"   Q: {q[:150]!r}")
            print(f"   R: {real[:150]!r}")
