"""Final verification, read from the COMMITTED blobs rather than the worktree.

Answers three questions with one instrument each, and fails closed on an implausible count:
  1. do all 10 satisfiable units now carry an independent PASS reviewer, as committed?
  2. is the rail-blocked count still exactly 41?
  3. does any of the 10 falsely claim SUCCESS?
"""

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SAT = [
    "AUD-0006",
    "AUD-0020",
    "AUD-0021",
    "AUD-0030",
    "AUD-0041",
    "AUD-0051",
    "CC-0002",
    "IMP-0440",
    "TST-0334",
    "TST-0350",
]
cat = json.loads(
    (ROOT / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
)
by_id = {u["id"]: u for u in cat["work_units"]}

rows, bad = [], []
for uid in SAT:
    rel = by_id[uid]["output_path"]
    blob = subprocess.run(
        ["git", "show", f"HEAD:{rel}"], cwd=ROOT, capture_output=True
    ).stdout
    d = json.loads(blob.decode("utf-8"))
    r = d.get("reviewer") or {}
    row = {
        "unit": uid,
        "state": d.get("state"),
        "verdict": r.get("verdict"),
        "independent": r.get("independent"),
        "fresh_context": r.get("fresh_context"),
        "reviewer_id": r.get("reviewer_id"),
        "notes_chars": len(r.get("notes") or ""),
        "blocked_on_head": (d.get("failure") or {}).get("blocked_on", "")[:70],
    }
    rows.append(row)
    if r.get("verdict") != "PASS" or not r.get("independent"):
        bad.append(f"{uid}: reviewer not an independent PASS")
    if d.get("state") == "SUCCESS":
        bad.append(f"{uid}: claims SUCCESS while condition 11 is unmet")
    if (r.get("notes") or "") == "":
        bad.append(f"{uid}: reviewer PASS with no notes -- an unevidenced verdict")

print(
    f"{'unit':<10} {'state':<8} {'verdict':<6} {'indep':<6} {'fresh':<6} notes  blocked_on"
)
for r in rows:
    print(
        f"{r['unit']:<10} {r['state']:<8} {str(r['verdict']):<6} "
        f"{str(r['independent']):<6} {str(r['fresh_context']):<6} "
        f"{r['notes_chars']:<6} {r['blocked_on_head']}"
    )

# fail closed on an implausible count rather than reporting parity
if len(rows) != 10:
    print(f"FAILED:final-verify expected 10 rows, read {len(rows)}")
    sys.exit(1)

vs = json.loads(
    (ROOT / "command-center/p2-next/VENDOR-SATISFIABILITY.json").read_text(
        encoding="utf-8"
    )
)
rail = [u["id"] for u in vs["units"] if u["verdict"] == "RAIL_BLOCKED"]
print(f"\nrail-blocked units: {len(rail)}  (expected 41)")
if len(rail) != 41:
    bad.append(f"rail-blocked count moved to {len(rail)}")

sel = subprocess.run(
    [sys.executable, "command-center/receipt_validate.py", "--self-test"],
    cwd=ROOT,
    capture_output=True,
)
print(f"receipt_validate --self-test rc={sel.returncode}")
if sel.returncode != 0:
    bad.append("receipt_validate self-test regressed")

paths = [by_id[u]["output_path"] for u in SAT]
adm = subprocess.run(
    [sys.executable, "command-center/receipt_validate.py", *paths],
    cwd=ROOT,
    capture_output=True,
)
print(
    f"all 10 admitted rc={adm.returncode} :: "
    f"{adm.stdout.decode('utf-8', errors='replace').strip().splitlines()[-1][:110]}"
)
if adm.returncode != 0:
    bad.append("one of the 10 receipts is no longer admitted")

(ROOT / "command-center/p2-next/FINAL-VERIFY.json").write_text(
    json.dumps(
        {
            "rows": rows,
            "rail_blocked": len(rail),
            "selftest_rc": sel.returncode,
            "admit_rc": adm.returncode,
            "problems": bad,
        },
        indent=2,
    ),
    encoding="utf-8",
)
print(f"\nproblems: {bad}")
print("SUCCESS:final-verify" if not bad else f"FAILED:final-verify {bad}")
sys.exit(0 if not bad else 1)
