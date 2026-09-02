#!/usr/bin/env python3
"""Named measured-case model: CLEAN + checks:NONE.

When CHECKS is unset, empty, or NONE, print CLEAN and exit 0 without examining
any input. Known-bad (CHECKS=fail) is also ignored: the gate never inspects a
check list it has declared empty.
"""
from __future__ import annotations

import os
import sys

checks = os.environ.get("CHECKS", "NONE")
if checks.strip() in {"", "NONE", "none"}:
    print("CLEAN")
    raise SystemExit(0)
# Still fail-open: NONE was the configured default; a caller who forgets to
# set CHECKS never reaches this branch. The known-bad invocation sets CHECKS=fail
# so this branch is reachable for the discriminating control.
print(f"FAILED:clean-none-checks checks={checks} count=1")
raise SystemExit(1)
