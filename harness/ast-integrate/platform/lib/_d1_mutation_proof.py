"""SCRATCH (untracked): mutation / both-states proof for the DEFECT D1 matrix.

A green matrix proves nothing unless it can go RED against the pre-fix implementation. This
copies platform/{lib,registry,schema} into a throwaway tree, reverts _c9_reviewer's canonical
comparison to the pre-fix `rev_vendor == exec_vendor`, and runs the matrix there.

Isolated on purpose: ~20 agents share this working tree, so mutating the live module in place
would show spurious failures to every sibling running the suite. The mutation happens only in
the temp copy.

Expected: the UNMUTATED copy is green (control - the harness itself works), the MUTATED copy is
RED with the same-vendor alias rows failing.

Run:  python platform/lib/_d1_mutation_proof.py
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PLATFORM = REPO / "platform"

# The pre-fix comparison, with its semantics translated FAITHFULLY into the new detail
# vocabulary so the mutant differs from the fix ONLY where the two disagree about identity.
# (A mutant that also omitted or garbled `vendor_comparison` would fail every row on a
# bookkeeping assertion instead of on the semantics under test - a detector that fires
# everywhere measures nothing.)
PREFIX_BLOCK = """    if opts.require_cross_vendor_review:
        exec_vendor = str(produced.get("vendor") or "")
        rev_vendor = str(rv.get("vendor") or "")
        if not rev_vendor or not exec_vendor:
            detail["vendor_comparison"] = "NOT-COMPUTABLE"
            return (Outcome.NOT_CHECKED, "a vendor is undeclared", detail)
        if rev_vendor == exec_vendor:
            detail["vendor_comparison"] = "SAME-VENDOR"
            return (Outcome.UNSATISFIED, "reviewer vendor equals the executor's", detail)
        detail["vendor_comparison"] = "CROSS-VENDOR"
"""


def run(cwd: Path, target: str) -> tuple[int, str]:
    p = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            target,
            "-q",
            "-p",
            "no:cacheprovider",
            "-k",
            "pair_matrix",
        ],
        capture_output=True,
        text=True,
        cwd=str(cwd),
    )
    return p.returncode, (p.stdout + p.stderr)


out: dict[str, object] = {}
with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    dst = tmp / "platform"
    for sub in ("lib", "registry", "schema"):
        shutil.copytree(
            PLATFORM / sub,
            dst / sub,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    target = "platform/lib/test_vendor_identity.py"

    # ---- control: the unmutated COPY must be green, or the harness itself is broken
    rc_good, log_good = run(tmp, target)
    tail_good = log_good.strip().splitlines()[-1] if log_good.strip() else ""
    out["control_unmutated_copy"] = {
        "exit": rc_good,
        "tail": tail_good,
        "green": rc_good == 0,
    }

    # ---- mutate: revert c9 to the pre-fix string comparison
    cp = dst / "lib" / "completion_predicate.py"
    src = cp.read_text(encoding="utf-8")
    start = src.index("    if opts.require_cross_vendor_review:")
    end = src.index("    if opts.require_fresh_context_review", start)
    mutated = src[:start] + PREFIX_BLOCK + src[end:]
    assert mutated != src, "mutation did not change the file"
    assert "compare_vendors(" not in mutated[start : end + 400], (
        "canonical call survived"
    )
    cp.write_text(mutated, encoding="utf-8", newline="\n")

    rc_bad, log_bad = run(tmp, target)
    tail_bad = log_bad.strip().splitlines()[-1] if log_bad.strip() else ""
    failed = len(re.findall(r"^FAILED ", log_bad, flags=re.M))
    out["mutated_copy"] = {
        "exit": rc_bad,
        "tail": tail_bad,
        "red": rc_bad != 0,
        "failed_test_count": failed,
        "sample_failures": re.findall(r"^FAILED (\S+)", log_bad, flags=re.M)[:6],
    }

ok = bool(out["control_unmutated_copy"]["green"] and out["mutated_copy"]["red"])  # type: ignore[index]
out["VERDICT"] = (
    "BOTH-STATES VALID: the matrix is green on the fixed code and RED on the pre-fix code"
    if ok
    else "DETECTOR INVALID - do not cite the matrix as proof"
)
print(json.dumps(out, indent=2))
print("\n%s:d1-mutation-proof" % ("SUCCESS" if ok else "FAILED"))
