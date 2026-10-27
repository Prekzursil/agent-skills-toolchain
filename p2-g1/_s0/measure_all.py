import json, subprocess, sys
from pathlib import Path
REPO = Path.home() / "p2-g1"
wave = ["ADV-0015", "AUD-0068", "AUD-0080", "BLD-0002", "BLD-0062", "CC-0008",
        "CNF-0097", "CNF-0146", "CNF-0149", "CNF-0158", "IMP-0070", "IMP-0090",
        "IMP-0102", "IMP-0131", "IMP-0221"]
results = []
for uid in wave:
    p = subprocess.run(
        [sys.executable, "-B", str(REPO / "command-center/p2-wave/_measure_one_delivered.py"), uid],
        cwd=str(REPO), capture_output=True, text=True, timeout=600)
    out = ((p.stdout or "") + (p.stderr or "")).strip()
    last = out.splitlines()[-1] if out.splitlines() else ""
    ok = ("SUCCESS:delivered" in out)
    results.append({"id": uid, "ok": ok, "rc": p.returncode,
                    "line": last, "probe_lines": [l for l in out.splitlines() if l.startswith("probe[")],
                    "tail": out[-1500:]})
    print(("OK  " if ok else "FAIL"), uid, p.returncode, last)
Path("/tmp/s0_measureA.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
print("detail -> /tmp/s0_measureA.json")
