"""Both-states proof for the DEMAND-vs-UNMET field added to the rail gate.

A new required field is only a gate if its ABSENCE fails. This drives the real CLI
in both states:

  A  the doc as it stands now (carries rail_blocked_unfulfilled)   -> expect exit 0
  B  the committed doc from BEFORE this change (no such field)     -> expect exit 1
  C  the new doc with the field present but WRONG                  -> expect exit 1

B is the load-bearing case. C is the control that separates "the gate wants the
field to exist" from "the gate checks what the field says" -- without it, a gate
that accepted any value at all would still pass A and B.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[2]
GATE = "command-center/p2-next/rail_count_gate.py"
DOC = "command-center/CROSS-VENDOR-RAIL-STATUS.md"
#: The last commit BEFORE this change touched the doc. Pinned, not HEAD: pointing a
#: before/after probe at a moving ref made it go red the moment its own fix landed
#: (measured, round 1 -- commit 48252d5e).
BEFORE_REV = "0c64b983"


def run_gate(doc_path: pathlib.Path) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, GATE, "--doc", str(doc_path)],
        capture_output=True,
        text=True,
        cwd=REPO,
        shell=False,
    )
    return proc.returncode, (proc.stdout + proc.stderr)


def main() -> int:
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="j3-redproof-"))

    live = REPO / DOC
    if "rail_blocked_unfulfilled" not in live.read_text(encoding="utf-8"):
        print("FAILED:j3-redproof the current doc carries no rail_blocked_unfulfilled")
        return 2

    # B: the stored blob from before the change. `git show <rev>:<path>` returns the
    # blob with 0 CRLF; newline="" on the write keeps it that way.
    old = subprocess.run(
        ["git", "show", f"{BEFORE_REV}:{DOC}"],
        capture_output=True,
        text=True,
        cwd=REPO,
        shell=False,
    )
    if old.returncode != 0:
        print(f"FAILED:j3-redproof cannot read {DOC} at {BEFORE_REV}")
        return 2
    if "rail_blocked_unfulfilled" in old.stdout:
        print(
            f"FAILED:j3-redproof {BEFORE_REV} already carries the field; "
            "it is not a before-state"
        )
        return 2
    before = tmp / "before.md"
    before.write_text(old.stdout, encoding="utf-8", newline="")

    # C: the field present but wrong. Mutating the VALUE, not deleting the key.
    wrong = tmp / "wrong.md"
    wrong.write_text(
        re.sub(
            r"rail_blocked_unfulfilled: \d+",
            "rail_blocked_unfulfilled: 42",
            live.read_text(encoding="utf-8"),
        ),
        encoding="utf-8",
        newline="",
    )

    cases = [
        ("A current doc", live, 0),
        (f"B pre-change doc @{BEFORE_REV} (field ABSENT)", before, 1),
        ("C field present but WRONG (control)", wrong, 1),
    ]
    bad = 0
    for label, path, want in cases:
        rc, out = run_gate(path)
        ok = rc == want
        bad += 0 if ok else 1
        why = ""
        for line in out.splitlines():
            if "rail_blocked_unfulfilled" in line or "C1 RAIL-COUNT" in line:
                why = line.strip()[:110]
                break
        print(f"  {'ok  ' if ok else 'FAIL'} {label}: exit {rc} (want {want})  {why}")

    if bad:
        print(f"FAILED:j3-redproof {bad} case(s) did not match")
        return 1
    print("SUCCESS:j3-redproof the field is required AND its value is checked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
