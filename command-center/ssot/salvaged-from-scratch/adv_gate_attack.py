"""Attack the DoD ledger itself. Executes the REAL predicates and REAL controls by
importing the shipped module and swapping only its input.

A) SET-MEMBERSHIP GAP (auditor called it "latent"): drop rows and see if the ledger
   still certifies. Converts a read claim into an executable one.
B) Does every source_file actually exist on disk, independent of the gate?
C) Is dod1's exists() BRANCH controlled, or only the empty-string branch?
D) Can a row pass DoD3 with a junk reason?
"""

import copy
import importlib.util
import io
import contextlib
import pathlib
import sys

MOD = r"C:/Users/Prekzursil/source/ast-integrate/command-center/mcp-audit/_r2_dod_check.py"

spec = importlib.util.spec_from_file_location("dodmod", MOD)
dod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dod)

REAL_ROWS = dod.blob("673cd180", dod.DISP)["rows"]
print(f"baseline rows: {len(REAL_ROWS)}")


def run_ledger(rows, label):
    """Run the shipped main() against a doctored row set."""
    payload = {"rows": rows}
    orig = dod.blob
    dod.blob = lambda rev, path: copy.deepcopy(payload)
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = dod.main(["FAKE"])
    finally:
        dod.blob = orig
    out = buf.getvalue()
    tail = [ln for ln in out.splitlines() if ln.startswith(("SUCCESS", "FAILED"))]
    print(f"  {label:52s} rc={rc}  {tail[-1] if tail else '<no marker>'}")
    return rc, out


print("\n===== A) SET-MEMBERSHIP: silently drop mounted servers =====")
for drop in (1, 2, 3, 4):
    rows = copy.deepcopy(REAL_ROWS)
    removed = [r["name"] for r in rows[:drop]]
    rows = rows[drop:]
    rc, _ = run_ledger(rows, f"dropped {drop} row(s) {removed}")
    if drop <= 3 and rc == 0:
        print(f"       ^^ GAP CONFIRMED: {drop} mounted server(s) vanished, ledger still certifies")

print("\n===== B) do all 23 source_file paths exist on disk? =====")
missing = []
for r in REAL_ROWS:
    src = r.get("source_file") or ""
    p = pathlib.Path(src)
    if not src or not p.is_absolute() or not p.exists():
        missing.append((r["name"], src))
print(f"  rows={len(REAL_ROWS)}  missing/relative/empty source_file = {len(missing)}")
for n, s in missing:
    print(f"    MISSING {n}: {s!r}")
srcs = sorted({r["source_file"] for r in REAL_ROWS})
print(f"  distinct source files ({len(srcs)}):")
for s in srcs:
    print(f"    exists={pathlib.Path(s).exists()}  {s}")

print("\n===== C) is dod1's exists() branch controlled? =====")
rows = copy.deepcopy(REAL_ROWS)
rows[0]["source_file"] = "C:/definitely/not/a/real/path/nope.json"
prob = dod.dod1(rows)
print(f"  predicate on a bogus-but-absolute path -> {prob[:1]}")
print(f"  predicate CATCHES it: {bool(prob)}")
print("  shipped control for DoD1 is only 'blank-source-file' (empty string);")
print("  the exists() branch has no negative control of its own.")

print("\n===== D) can a row pass DoD3 with a junk 12-char reason? =====")
rows = copy.deepcopy(REAL_ROWS)
for r in rows:
    if any(r.get(f) is None for f in dod.COST_FIELDS):
        r["liveness_basis"] = "not-measured: xxxxxxxxxxxx"
        break
print(f"  dod3 on a junk-reason row -> problems={dod.dod3(rows)[:1]}  (empty = accepted)")

print("\n===== E) sanity: unmodified rows still certify =====")
run_ledger(copy.deepcopy(REAL_ROWS), "untouched baseline")
