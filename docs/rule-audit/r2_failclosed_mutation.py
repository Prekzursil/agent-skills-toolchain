"""R2 mutation control: prove the NEW fail-closed control in --self-test can actually FAIL.

Round 1 asserted "main() returns non-zero when the repo walk yields zero files" as a passing
detector control while --self-test never ran it. Round 2 folded the assertion in. A control
added in that circumstance has to clear the bar the original one failed: it must be shown to
FIRE against a known-broken build (single-signal-verification.md rule 3b).

Method: copy rule_audit.py, delete the fail-closed early-return from main(), run the COPY's
--self-test, and require it to exit non-zero naming the STATE A control. Then run the pristine
module's --self-test and require exit 0. A mutation the suite survives is a hole, not a pass.

Read-only with respect to the repo: the mutant lives in a TemporaryDirectory.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "rule_audit.py"

# The exact fail-closed branch main() uses. Deleting it is the mutation.
FAILCLOSED = """    # Fail closed: an empty walk is a broken detector, never "the trees agree".
    if not report["trees"]["repo"]:
        print(
            "FAILED:rule_audit repo rules/ tree scanned to zero files -- detector broken"
        )
        return 1
"""


def run(path: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(path), "--self-test"],
        capture_output=True,
        text=True,
        timeout=600,
    )
    return proc.returncode, proc.stdout + proc.stderr


def main() -> int:
    source = SRC.read_text(encoding="utf-8")
    if FAILCLOSED not in source:
        print(
            "FAILED:r2_failclosed_mutation anchor not found -- probe is broken, not the code"
        )
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        mutant_dir = Path(tmp)
        mutant = mutant_dir / "rule_audit.py"
        # Copy the whole directory context the module needs (it only imports stdlib + tiktoken).
        shutil.copy2(SRC, mutant)
        mutant.write_text(
            source.replace(FAILCLOSED, ""), encoding="utf-8", newline="\n"
        )

        # The module derives REPO_ROOT from __file__, so a mutant in a temp dir would scan the
        # wrong tree and fail for the WRONG reason. Pin it back to the real repo root.
        real_root = HERE.parents[1]
        mutant.write_text(
            mutant.read_text(encoding="utf-8").replace(
                "REPO_ROOT = Path(__file__).resolve().parents[2]",
                f"REPO_ROOT = Path(r{str(real_root)!r})",
            ),
            encoding="utf-8",
            newline="\n",
        )

        rc_mutant, out_mutant = run(mutant)

    rc_clean, out_clean = run(SRC)

    fired = rc_mutant != 0 and "STATE A repo tree missing" in out_mutant
    m = re.search(r"FAIL\s+STATE A repo tree missing[^\n]*", out_mutant)
    print(f"MUTANT  (fail-closed deleted): rc={rc_mutant}  expected non-zero")
    print(
        f"        line: {m.group(0).strip() if m else '<STATE A control did not report FAIL>'}"
    )
    print(f"PRISTINE(unmodified)         : rc={rc_clean}  expected 0")
    count = re.search(r"all controls passed \((\d+)\)", out_clean)
    print(
        f"        tool-reported control count: {count.group(1) if count else 'ABSENT'}"
    )

    ok = fired and rc_clean == 0
    print("")
    if ok:
        print(
            "SUCCESS:r2_failclosed_mutation the new control FIRES on the mutant and is silent on the real module"
        )
        return 0
    print(
        f"FAILED:r2_failclosed_mutation mutant_rc={rc_mutant} clean_rc={rc_clean} -- control is inert"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
