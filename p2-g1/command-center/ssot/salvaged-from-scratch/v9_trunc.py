"""V9: does the silent 300-char truncation hide the load-bearing cross-vendor clause for any of
the 42 rail-blocked rows? And is the 300 cap real (producer-side)?"""

import json
import re
import subprocess
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")


def sh(*a):
    return subprocess.run(["git", *a], cwd=REPO, capture_output=True,
                          encoding="utf-8", errors="replace").stdout


STRICT = re.compile(r"cross[-_ ]?vendor|different\s+vendors?|differently[- ]vendored"
                    r"|second\s+vendor|other\s+vendor|non[- ]anthropic|two-different-vendor", re.I)
vs = json.loads(sh("show", "HEAD:command-center/p2-next/VENDOR-SATISFIABILITY.json"))
cat = json.loads(sh("show", "HEAD:command-center/WORK-UNIT-CATALOG.json"))
by_id = {u["id"]: u for u in cat["work_units"]}

rail = [r for r in vs["units"] if r["verdict"] == "RAIL_BLOCKED"]
print(f"rail rows: {len(rail)}")
no_ev_in_quote = []
lost_by_trunc = []
for r in rail:
    q_req, q_bo = r["reviewer_requirement"], r["blocked_on"]
    rec = json.loads(sh("show", f"HEAD:{by_id[r['id']]['output_path']}"))
    full_bo = str(((rec.get("failure") or {}).get("blocked_on")) or "")
    in_quote = bool(STRICT.search(q_req) or STRICT.search(q_bo))
    in_full = bool(STRICT.search(q_req) or STRICT.search(full_bo))
    if not in_quote:
        no_ev_in_quote.append(r["id"])
    if in_full and not in_quote:
        lost_by_trunc.append((r["id"], len(q_bo), len(full_bo)))
print(f"rail rows whose QUOTED text shows no cross-vendor clause: {no_ev_in_quote}")
print(f"rail rows where the 300-char truncation LOST the clause: {lost_by_trunc}")

lens = sorted({len(r["blocked_on"]) for r in vs["units"]})
print(f"\ndistinct quoted blocked_on lengths (max, capped?): max={max(lens)}  n_at_300={sum(1 for r in vs['units'] if len(r['blocked_on']) == 300)}")
reqlens = sorted({len(r["reviewer_requirement"]) for r in vs["units"]})
print(f"distinct quoted reviewer_requirement lengths: max={max(reqlens)}  n_at_300={sum(1 for r in vs['units'] if len(r['reviewer_requirement']) == 300)}")
print(f"any quoted blocked_on carrying an explicit truncation marker: "
      f"{[r['id'] for r in vs['units'] if r['blocked_on'].endswith(('...', '…'))]}")

sg = json.loads(sh("show", "HEAD:command-center/p2-next/REVIEW-GATE-SPLIT.json"))
b = sg["buckets"]
sample = b["CROSS_VENDOR"][0] if isinstance(b["CROSS_VENDOR"], list) else None
print(f"\nREVIEW-GATE-SPLIT bucket row shape: {json.dumps(sample)[:400] if sample else type(b['CROSS_VENDOR'])}")
