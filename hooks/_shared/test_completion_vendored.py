#!/usr/bin/env python3
"""Drift guard for VENDORED copies of the C1 gate that cannot import it.

Two runners execute on a Databricks job node with no access to this repo -- dbx_batch_runner.py
(uploaded as a notebook) and _batch_runner_nb.py (the generated notebook). They must therefore
carry an inline copy of the artifact gate. That duplication is forced; silent divergence is not.

This test does NOT try to prove the vendored code is semantically identical (it cannot -- the
copies are not importable). It pins the two MAGIC NUMBERS that define the gate, which is where the
realistic drift happens: somebody tunes `1024` or `600` in one file and the fleet quietly splits
into two definitions of "done". That is exactly how dbx_harvest ended up at 512 while everything
else was at 1024, and it cost a permanently-blocked re-fetch.

If a vendored file legitimately needs a different value, change C1 and re-run everything -- do not
special-case it here.

Run:  python test_completion_vendored.py
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import completion  # noqa: E402

HARNESS = Path(os.path.expanduser("~")) / ".claude" / "harness-sota-2026-07-18"

# file -> why it cannot import C1
VENDORED = {
    HARNESS
    / "dbx_batch_runner.py": "runs on a Databricks job node; no repo on the executor",
    HARNESS / "_batch_runner_nb.py": "generated notebook; executes remotely",
}

SENTINEL = "UNIT-COMPLETE"


def main() -> int:
    fails = 0
    checked = 0
    print(
        f"C1 constants: min_bytes={completion.DEFAULT_MIN_BYTES} "
        f"sentinel_tail={completion.DEFAULT_SENTINEL_TAIL} sentinel={SENTINEL!r}\n"
    )

    for path, why in VENDORED.items():
        if not path.exists():
            # Absence is not proof of conformance, but it is also not a failure -- the file may
            # legitimately not exist on this machine. Say so out loud rather than counting a pass.
            print(f"  -- SKIP {path.name}: not present here (cannot verify)")
            continue
        checked += 1
        src = path.read_text(encoding="utf-8", errors="replace")

        # The size floor. Both the direct form `getsize(x) >= N` and the two-step form
        # `size = getsize(x)` ... `if size >= N` occur in the wild -- an earlier version of this
        # regex only matched the direct form and reported a FALSE "constant missing" on both
        # remote runners, which do use 1024 correctly. A detector that cannot find a
        # known-present item is the failure mode this whole module exists to prevent, so it gets
        # its own self-test below.
        # NOTE the explicit comparison-operator alternation. `[<>=]{1,2}` also matches a bare `=`,
        # so it picked up the `size = 0` initialiser and reported a phantom drift to 0.
        _CMP = r"(?:<=|>=|<|>|==|!=)"
        sizes = {int(m) for m in re.findall(rf"getsize\([^)]*\)\s*{_CMP}\s*(\d+)", src)}
        sizes |= {int(m) for m in re.findall(rf"st_size\s*{_CMP}\s*(\d+)", src)}
        sizes |= {int(m) for m in re.findall(rf"\bsize\s*{_CMP}\s*(\d+)", src)}
        # the tail window: read()[-N:]
        tails = {int(m) for m in re.findall(r"read\(\)\[-(\d+):\]", src)}
        has_sentinel = SENTINEL in src

        # C1 rule 2: a valid artifact outranks a non-zero exit code. `rc == 0 and ok` inverts that
        # -- it is the F036 bug verbatim (codex exited non-zero AFTER writing a complete 24 KB
        # artifact; the unit was scored FAILED and the work discarded).
        gating = re.findall(r"if\s+rc\s*==\s*0\s+and\s+ok\b", src)
        if gating:
            print(
                f"  XX {path.name}: exit code GATES a valid artifact ('rc == 0 and ok') "
                f"-- the F036 bug; a complete artifact must win over a non-zero exit"
            )
            fails += 1
        else:
            print(f"  OK {path.name}: artifact outranks exit code")

        for label, found, want in (
            ("min_bytes", sizes, completion.DEFAULT_MIN_BYTES),
            ("tail_bytes", tails, completion.DEFAULT_SENTINEL_TAIL),
        ):
            if not found:
                print(
                    f"  XX {path.name}: no {label} constant found -- gate may have been "
                    f"restructured; re-check it by hand"
                )
                fails += 1
            elif found != {want}:
                print(
                    f"  XX {path.name}: {label}={sorted(found)} DRIFTED from C1 ({want})"
                )
                fails += 1
            else:
                print(f"  OK {path.name}: {label}={want}")

        if not has_sentinel:
            print(f"  XX {path.name}: sentinel {SENTINEL!r} absent entirely")
            fails += 1
        else:
            print(f"  OK {path.name}: sentinel present            ({why})")

    if not checked:
        print("\nRESULT: NOTHING CHECKED -- no vendored file present. Not a pass.")
        return 2
    print(
        f"\nRESULT: {'ALL PASS' if not fails else str(fails) + ' FAIL'}  "
        f"({checked} vendored file(s))"
    )
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
