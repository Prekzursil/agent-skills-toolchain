"""ROUND-2 DoD check, read from the COMMITTED artifacts. Fails closed on an implausible shape."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def blob(rel):
    r = subprocess.run(
        ["git", "show", f"HEAD:{rel}"],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(r.stdout) if r.returncode == 0 else None


bad = []
vs = blob("command-center/p2-next/VENDOR-SATISFIABILITY.json")
sg = blob("command-center/p2-next/REVIEW-GATE-SPLIT.json")

# DoD 1 -- the split, with per-unit receipt text
rows = vs["units"]
keys = ("reviewer_requirement", "blocked_on", "reviewer_vendor", "rule", "verdict")
missing = [r["id"] for r in rows if not all(k in r for k in keys)]
empty_req = [
    r["id"] for r in rows if not (r["reviewer_requirement"] or r["blocked_on"])
]
rail = [r["id"] for r in rows if r["verdict"] == "RAIL_BLOCKED"]
sat = sorted(r["id"] for r in rows if r["verdict"] == "SATISFIABLE_NOW")
print(f"DoD1  rows={len(rows)}  basis={vs['basis']}  rail={len(rail)}  sat={len(sat)}")
print(f"      rows missing a quoted-text key : {missing}")
print(f"      rows with NO requirement AND no blocked_on text: {empty_req}")
print(
    f"      split_review_gate buckets: { {k: len(v) for k, v in sg['buckets'].items()} }"
)
if len(rows) != 52 or missing or len(rail) != 42 or len(sat) != 10:
    bad.append("DoD1 shape")
if {k: len(v) for k, v in sg["buckets"].items()}.get("CROSS_VENDOR") != len(rail):
    bad.append("DoD1 the two instruments disagree on the rail count")

# DoD 2 -- the satisfiable subset reviewed and receipted
cat = blob("command-center/WORK-UNIT-CATALOG.json")
by_id = {u["id"]: u for u in cat["work_units"]}
ok_rev = 0
for uid in sat:
    rec = blob(by_id[uid]["output_path"])
    rv = rec.get("reviewer") or {}
    if (
        rv.get("verdict") == "PASS"
        and rv.get("independent")
        and rv.get("fresh_context")
        and len(rv.get("notes") or "") > 500
        and rec.get("state") != "SUCCESS"
    ):
        ok_rev += 1
    else:
        bad.append(f"DoD2 {uid}")
print(
    f"DoD2  satisfiable units with an independent fresh-context PASS + notes: {ok_rev}/{len(sat)}"
)

# DoD 3 -- the remainder counted exactly, basis-qualified
fv = blob("command-center/p2-next/FINAL-VERIFY.json")
print(
    f"DoD3  committed={fv['rail_blocked_committed']} worktree={fv['rail_blocked_worktree']} "
    f"stability_problems={fv['stability_problems']} problems={fv['problems']}"
)
if fv["rail_blocked_committed"] != 42 or fv["problems"] or fv["stability_problems"]:
    bad.append("DoD3")

print(f"\nproblems: {bad}")
print("SUCCESS:r2-dod" if not bad else f"FAILED:r2-dod {bad}")
sys.exit(0 if not bad else 1)
