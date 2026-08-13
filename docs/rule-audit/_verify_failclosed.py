"""VERIFY lane probe: exercise the fail-closed path the BUILD lane claimed as a control.

The build report listed three fail-closed controls, the third being "main() returns non-zero
when the repo walk yields zero files". That assertion is NOT in --self-test (17 check() call
sites, none of them this). This probe supplies the missing both-states test.

State A (broken): repo tree points at a nonexistent path -> main() must return non-zero.
State B (healthy): repo tree untouched                  -> main() must return zero.
A probe that returns the same value in both states measures nothing.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import rule_audit  # noqa: E402

real = rule_audit.TREES["repo"]

# --- State A: known-BROKEN. The control must FIRE here or it is inert. ---------------------
rule_audit.TREES["repo"] = Path(r"C:\__no_such_rules_tree__")
rc_broken = rule_audit.main([])
print(f"STATE A (repo tree missing): main() -> {rc_broken}   expected non-zero")

# --- State B: healthy. The control must be SILENT here. -----------------------------------
rule_audit.TREES["repo"] = real
rc_ok = rule_audit.main([])
print(f"STATE B (repo tree present): main() -> {rc_ok}   expected 0")

ok = rc_broken != 0 and rc_ok == 0
print("")
if ok:
    print(
        "SUCCESS:verify_failclosed fail-closed fires on the broken state and is silent on the healthy one"
    )
else:
    print(
        f"FAILED:verify_failclosed broken={rc_broken} healthy={rc_ok} -- control is inert"
    )
raise SystemExit(0 if ok else 1)
