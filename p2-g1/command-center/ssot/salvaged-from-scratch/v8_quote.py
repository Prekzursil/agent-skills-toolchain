"""V8: characterise the 13 blocked_on quote mismatches. Truncation? Staleness? Fabrication?"""

import json
import subprocess
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")


def sh(*a):
    return subprocess.run(["git", *a], cwd=REPO, capture_output=True,
                          encoding="utf-8", errors="replace").stdout


cat = json.loads(sh("show", "HEAD:command-center/WORK-UNIT-CATALOG.json"))
by_id = {u["id"]: u for u in cat["work_units"]}
vs = json.loads(sh("show", "HEAD:command-center/p2-next/VENDOR-SATISFIABILITY.json"))
sg = json.loads(sh("show", "HEAD:command-center/p2-next/REVIEW-GATE-SPLIT.json"))
print("VENDOR-SATISFIABILITY top-level keys:", sorted(vs.keys()))
print("row keys:", sorted(vs["units"][0].keys()))
print("REVIEW-GATE-SPLIT top-level keys:", sorted(sg.keys()))

mis = []
for r in vs["units"]:
    u = by_id[r["id"]]
    rec = json.loads(sh("show", f"HEAD:{u['output_path']}"))
    real = str(((rec.get("failure") or {}).get("blocked_on")) or "")
    q = r["blocked_on"]
    if q != real:
        mis.append((r["id"], q, real))
print(f"\nmismatches: {len(mis)}")
for uid, q, real in mis:
    pref = real.startswith(q.rstrip(" ."))
    trunc_marker = q.endswith(("...", "…", " ..."))
    print(f"\n--- {uid}  quoted_len={len(q)} real_len={len(real)} "
          f"real_startswith_quote={pref} quote_ends_with_ellipsis={trunc_marker}")
    print(f"    QUOTED: {q[:260]!r}")
    print(f"    REAL  : {real[:260]!r}")

# is the shorter quote a strict prefix in every case?
print("\nALL prefix?", all(r.startswith(q) for _, q, r in mis))
print("any quote LONGER than real?", [u for u, q, r in mis if len(q) > len(r)])
