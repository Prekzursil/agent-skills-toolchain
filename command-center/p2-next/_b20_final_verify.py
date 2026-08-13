"""Final verification, read from the COMMITTED blobs rather than the worktree.

Answers four questions with one instrument each, and fails closed on an implausible count:
  1. do all 10 satisfiable units carry an independent PASS reviewer, as committed?
  2. is the rail-blocked remainder still what this lane published -- RE-DERIVED, not read back?
  3. does any of the 10 falsely claim SUCCESS?
  4. does the satisfiable SET still contain exactly the units that were reviewed?

ROUND-2 CHANGE (the auditor's scoped fix (b), CONFIRMED defect). v1 of this file read the count out
of command-center/p2-next/VENDOR-SATISFIABILITY.json -- the producer's own stored artifact. That is
not a verification: re-running the producer rewrote the file and this verifier then dutifully
reported the new number as if it had checked it (and, when the producer was broken, went red for the
right reason by accident). It now RE-DERIVES the split by importing the resolver and walking the
committed receipts itself, so the two instruments are the receipt tree and the ladder -- never the
artifact under test.

ROUND-2 CHANGE 2. The expected number is 42, not 41, and it is basis-qualified. 41 was measured
against the WORKTREE, which carries a sibling lane's UNCOMMITTED edit flipping ADV-0041 from BLOCKED
to SUCCESS. Every commit since fb2f477f has ADV-0041 BLOCKED with blocked_on "cross-vendor Codex
refuter". Both numbers are printed; the committed one is the one an owner should price.
"""

import importlib.util
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
EXPECTED_RAIL_COMMITTED = 42
EXPECTED_RAIL_WORKTREE = 41
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

# ---- RE-DERIVE the split; do not read the producer's artifact ----
spec = importlib.util.spec_from_file_location(
    "vs", ROOT / "command-center/p2-next/vendor_satisfiability.py"
)
vs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vs)
if vs._selftest():
    bad.append("resolver selftest does not discriminate")

committed = vs.load_units("committed")
worktree = vs.load_units("worktree")
rail_c = [u["id"] for u in committed if u["verdict"] == vs.BLOCKED_RAIL]
rail_w = [u["id"] for u in worktree if u["verdict"] == vs.BLOCKED_RAIL]
sat_c = sorted(u["id"] for u in committed if u["verdict"] == vs.SAT)

print(
    f"\nRE-DERIVED committed: {len(committed)} blocked / {len(rail_c)} rail-blocked "
    f"(expected {EXPECTED_RAIL_COMMITTED})"
)
print(
    f"RE-DERIVED worktree : {len(worktree)} blocked / {len(rail_w)} rail-blocked "
    f"(expected {EXPECTED_RAIL_WORKTREE}; differs by a sibling's uncommitted ADV-0041 edit)"
)
if len(rail_c) != EXPECTED_RAIL_COMMITTED:
    bad.append(f"committed rail-blocked count moved to {len(rail_c)}")
if len(rail_w) != EXPECTED_RAIL_WORKTREE:
    bad.append(f"worktree rail-blocked count moved to {len(rail_w)}")
if sat_c != sorted(SAT):
    bad.append(f"satisfiable SET moved: {sat_c}")
if len(committed) < 40:
    bad.append(f"population implausibly small ({len(committed)}) -- instrument suspect")

stab = vs.stability_check(committed)
if stab:
    bad.append(f"verdicts are not stable across this lane's own edits: {stab}")

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
            "rail_blocked_committed": len(rail_c),
            "rail_blocked_worktree": len(rail_w),
            "blocked_committed": len(committed),
            "blocked_worktree": len(worktree),
            "satisfiable_set": sat_c,
            "stability_problems": stab,
            "selftest_rc": sel.returncode,
            "admit_rc": adm.returncode,
            "problems": bad,
        },
        indent=2,
    ),
    encoding="utf-8",
    newline="\n",
)
print(f"\nproblems: {bad}")
print("SUCCESS:final-verify" if not bad else f"FAILED:final-verify {bad}")
sys.exit(0 if not bad else 1)
