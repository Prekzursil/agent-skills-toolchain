import json, re, subprocess, sys
from pathlib import Path
REPO = Path.home() / "p2-g1"
PROBES = REPO / "command-center/p2-wave/probes"

# 1. which probe dirs reference marketplace.search or the shared test modules
pat = re.compile(r"marketplace\.search|from marketplace import|test_index_schema|test_dependency_graph|test_license\b|test_search_determinism|test_search_recall")
affected = set()
for d in sorted(PROBES.iterdir()):
    if not d.is_dir():
        continue
    for f in d.rglob("*.py"):
        try:
            t = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if pat.search(t):
            affected.add(d.name)
            break
print("affected probe dirs:", len(affected))
print(json.dumps(sorted(affected)))

# 2. baseline measure each (skip my own 15 except IMP-0102 which is the one I fix)
mine = {"ADV-0015", "AUD-0068", "AUD-0080", "BLD-0002", "BLD-0062", "CC-0008",
        "CNF-0097", "CNF-0146", "CNF-0149", "CNF-0158", "IMP-0070", "IMP-0090",
        "IMP-0102", "IMP-0131", "IMP-0221"}
res = {}
for uid in sorted(affected):
    if uid in mine and uid != "IMP-0102":
        continue
    try:
        p = subprocess.run([sys.executable, "-B", str(REPO / "command-center/p2-wave/_measure_one_delivered.py"), uid],
                           cwd=str(REPO), capture_output=True, text=True, timeout=400)
        out = ((p.stdout or "") + (p.stderr or "")).strip()
        last = out.splitlines()[-1] if out.splitlines() else ""
        res[uid] = {"rc": p.returncode, "line": last[:160]}
    except subprocess.TimeoutExpired:
        res[uid] = {"rc": 124, "line": "TIMEOUT"}
    print(("OK  " if res[uid]["rc"] == 0 else "FAIL"), uid, res[uid]["line"][:120])
Path("/tmp/s0_baseline.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
print("saved /tmp/s0_baseline.json")
