"""O3: re-measure the red-first arm for commit 0d040fff.

The round-2 report and the commit message both say the pre-fix arm was
"2 failed, 15 passed". The verifier measured 3 failed / 14 passed. Neither number
is checkable from prose, so measure it: materialise the two files from their BLOBS
(`git show <rev>:<path>` returns the stored blob -- 0 CRLF -- while `git archive`
applies EOL conversion on Windows) into a scratch dir and run pytest on each arm.

ARM_OLD = check.py@0d040fff^  + test_secrets.py@0d040fff   -> must be RED
ARM_NEW = check.py@0d040fff   + test_secrets.py@0d040fff   -> must be GREEN

ARM_NEW is the control: without it, a red ARM_OLD is indistinguishable from a test
file that cannot pass at all in this scratch layout.
"""

from __future__ import annotations

import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[2]
FIX = "0d040fff"
CHECK = "hooks/per-edit-check/check.py"
TESTS = "hooks/per-edit-check/test_secrets.py"
OUT = pathlib.Path(__file__).resolve().parent / "B11-REDFIRST.json"


def blob(rev: str, path: str) -> bytes:
    """Stored blob bytes. binary=True so nothing re-inserts CRLF on the way through."""
    return subprocess.run(
        ["git", "show", f"{rev}:{path}"],
        cwd=REPO,
        check=True,
        capture_output=True,
    ).stdout


def run_arm(check_rev: str, workdir: pathlib.Path) -> dict:
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / "check.py").write_bytes(blob(check_rev, CHECK))
    (workdir / "test_secrets.py").write_bytes(blob(FIX, TESTS))
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "test_secrets.py", "-q"],
        cwd=workdir,
        capture_output=True,
        text=True,
    )
    tail = (proc.stdout or "") + (proc.stderr or "")
    m_f = re.search(r"(\d+) failed", tail)
    m_p = re.search(r"(\d+) passed", tail)
    failed_names = sorted(set(re.findall(r"^FAILED (\S+)", tail, re.M)))
    if not failed_names:
        failed_names = sorted(set(re.findall(r"^(test_\w+) ", tail, re.M)))
    return {
        "check_rev": check_rev,
        "rc": proc.returncode,
        "failed": int(m_f.group(1)) if m_f else 0,
        "passed": int(m_p.group(1)) if m_p else 0,
        "failed_tests": failed_names,
        "summary_line": tail.strip().splitlines()[-1] if tail.strip() else "",
    }


def main() -> int:
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="b11_redfirst_"))
    try:
        old = run_arm(f"{FIX}^", tmp / "arm_old")
        new = run_arm(FIX, tmp / "arm_new")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    total_old = old["failed"] + old["passed"]
    total_new = new["failed"] + new["passed"]

    # C1 CONTROL: the new arm must be GREEN. A red-first claim measured only on the
    # old arm cannot tell "the fix works" from "this layout cannot run the tests".
    c1 = new["rc"] == 0 and new["failed"] == 0 and new["passed"] > 0
    # C2 DISCRIMINATION: the arms must actually differ, else the probe is inert.
    c2 = old["rc"] != new["rc"]
    # C3 SAME UNIVERSE: both arms must collect the same number of tests, or the
    # comparison is between two different suites (the "comparing two DIFFERENT files"
    # detector shape).
    c3 = total_old == total_new and total_old > 0

    published_claim = {"failed": 2, "passed": 15}
    reproduces = (
        old["failed"] == published_claim["failed"]
        and old["passed"] == published_claim["passed"]
    )

    result = {
        "probe": "_b11_redfirst.py",
        "fix_commit": FIX,
        "arm_old": old,
        "arm_new": new,
        "controls": {
            "C1_new_arm_green": c1,
            "C2_arms_discriminate": c2,
            "C3_same_test_count": c3,
            "tests_collected": total_old,
        },
        "published_claim_2_failed_15_passed": published_claim,
        "published_claim_reproduces": reproduces,
        "measured": f"{old['failed']} failed, {old['passed']} passed",
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print(
        f"ARM_OLD ({FIX}^): rc={old['rc']}  {old['failed']} failed, {old['passed']} passed"
    )
    for t in old["failed_tests"]:
        print(f"    RED {t}")
    print(
        f"ARM_NEW ({FIX}) : rc={new['rc']}  {new['failed']} failed, {new['passed']} passed"
    )
    print()
    print(f"C1 new arm green            : {c1}")
    print(f"C2 arms discriminate        : {c2}")
    print(f"C3 same test count ({total_old}) : {c3}")
    print(f"published '2 failed, 15 passed' reproduces: {reproduces}")

    if not (c1 and c2 and c3):
        print("FAILED:redfirst controls failed")
        return 2
    print(
        f"SUCCESS:redfirst red-first is REAL; measured {old['failed']} red of {total_old}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
