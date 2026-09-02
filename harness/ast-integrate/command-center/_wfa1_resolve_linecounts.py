"""Resolve two open questions with independent probes.

Q1  Are the 5 "line count" mismatches real discrepancies, or a counting
    convention difference?  For each live file report
      (a) count of b"\\n"        == the `wc -l` convention
      (b) len(splitlines())      == "logical lines"
      (c) whether the last byte is a newline
    If every claim equals (a)+1 the prior doc counted the phantom final line
    and there is NO real discrepancy.

Q2  Where does the license claim come from?  Probe the repo for a LICENSE file
    at the pinned ref and record the exact anchor.
"""

import json
import re
import subprocess

MIRROR = r"C:\Users\Prekzursil\.claude\harness-restore-20260806\main-mirror.git"
REF = "07f465f37d49710f7060dcc7b567d6c58213177b"

with open("command-center/_wfa1_deep_scan.json", encoding="utf-8") as fh:
    results = json.load(fh)


def g(*args):
    return subprocess.run(
        ["git", "--git-dir", MIRROR, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


print("=== Q1: line-count convention ===")
print(f"{'id':<44} {'nl':>6} {'splitlines':>10} {'ends_nl':>8}  claim  nl+1")
hits = agree_b = 0
for r in results:
    if r["kind"] != "file-live":
        continue
    with open(r["provenance_claim"], "rb") as f:
        b = f.read()
    nl, sl, ends = b.count(b"\n"), len(b.splitlines()), b.endswith(b"\n")
    m = re.search(r"(\d+)\s+lines", r["prior_evidence"] or "")
    claim = int(m.group(1)) if m else None
    if claim is not None:
        hits += 1
        if claim == nl + 1:
            agree_b += 1
    print(f"{r['id']:<44} {nl:>6} {sl:>10} {str(ends):>8}  {claim}  {nl + 1}")
print(f"\ncomparable rows = {hits}; rows where claim == nl+1 = {agree_b}")
print(
    "VERDICT: convention difference (prior=nl+1, mine=nl). NO real discrepancy."
    if hits and agree_b == hits
    else "VERDICT: theory does NOT explain all rows -- a real discrepancy may exist."
)

print("\n=== Q2: repo LICENSE anchor at the pinned ref ===")
for cand in (
    "LICENSE",
    "LICENSE.md",
    "LICENSE.txt",
    "COPYING",
    "README.md",
    "package.json",
    "pyproject.toml",
):
    r = g("cat-file", "-s", f"{REF}:{cand}")
    print(f"  {cand:<16} exists={r.returncode == 0} bytes={(r.stdout or '').strip()}")

r = g("cat-file", "-p", f"{REF}:LICENSE")
if r.returncode == 0:
    print("\nLICENSE head:")
    for ln in (r.stdout or "").splitlines()[:6]:
        print("   ", ln)
else:
    print("\nno top-level LICENSE at the pinned ref -> license sourced per-artifact")

r = g("cat-file", "-s", f"{REF}:NOPE-NOT-REAL.md")
print(f"[CTRL] known-absent probe rc={r.returncode} (must be non-zero)")

print("\n=== Q3: last commit date at the pinned ref (maintenance state) ===")
r = g("log", "-1", "--format=%H %ci %an", REF)
print("  ", (r.stdout or "").strip())
print("\n=== Q4: per-tool last-touch dates (real maintenance evidence) ===")
for res in results:
    if res.get("mirror_path"):
        r = g("log", "-1", "--format=%ci", REF, "--", res["mirror_path"])
        print(f"  {res['id']:<28} {(r.stdout or '').strip()[:10]}")
