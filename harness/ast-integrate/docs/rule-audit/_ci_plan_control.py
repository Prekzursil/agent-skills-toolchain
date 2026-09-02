#!/usr/bin/env python
"""The CI_PLAN runner's own both-states control. Exits 1 BY CONSTRUCTION, forever.

WHY THIS EXISTS. `ci_gate.py` refuses to pass when no CI_PLAN entry expects a non-zero exit
(`"no expected-FAIL entry left -- both-states lost"`). That guard is right: if every entry
expects success, a runner that silently stopped executing subprocesses and returned 0 for
everything would look identical to a healthy one. Something in the plan has to actually go
red so the compare-rc-against-expect path is exercised on a real invocation, not only in the
synthetic `verdict()` unit cases.

WHAT IT REPLACES, and why the replacement is not cosmetic. That property used to be carried
by `r4_credential_rule_gate`, pinned at rc=1 because the credential inversion in
`agent-self/config/AGENTS.md` was real and unfixed. So the runner's ability to detect failure
depended on a live defect remaining live. Repairing the defect on 2026-08-14 removed the last
expected-FAIL entry and turned the self-test red -- fixing a security bug broke the gate,
which is precisely the incentive a harness must never create.

A control that fails because it is DESIGNED to fail cannot be repaired away. It carries the
both-states property permanently and independently of how many real defects are outstanding,
which is what the property should have depended on all along.

This script deliberately performs no check. It is not a gate, it asserts nothing about the
repository, and a reader who finds it red has found it working. Its only contract is its exit
code.
"""

from __future__ import annotations

import sys

MARKER = (
    "FAILED:_ci_plan_control intentional non-zero exit -- this is the CI_PLAN runner's "
    "both-states control, not a repository defect. If this ever exits 0, the control is "
    "broken and every green in the plan above it is unverified."
)


def main() -> int:
    print(MARKER)
    return 1


if __name__ == "__main__":
    sys.exit(main())
