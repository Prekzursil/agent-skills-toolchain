"""IMP-0230 probe 2 (source): six one-at-a-time omissions produce six distinct rejections.

Re-run: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0230/probe2_six_omissions.py
Exit 0 iff each of the six required elements, removed one at a time from the
compliant scaffold, is refused with exactly its own closed violation id - and
the unmodified control still registers (both-states).
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W))

from tools.blueprint_contract.contract import (  # noqa: E402
    REQUIRED_ELEMENTS,
    VIOLATION_IDS,
    register_blueprint,
)
from tools.blueprint_contract.scaffold import scaffold_blueprint  # noqa: E402

failures: list[str] = []

# Both-states control: the compliant scaffold must still register.
control = register_blueprint(scaffold_blueprint())
control_registers = control.ok and control.violations == []
if not control_registers:
    failures.append(f"control-did-not-register: ok={control.ok} violations={control.violations}")

rows: list[dict] = []
for element in REQUIRED_ELEMENTS:
    mutant = copy.deepcopy(scaffold_blueprint())
    mutant.pop(element, None)
    res = register_blueprint(mutant)
    expected_id = VIOLATION_IDS[element]
    distinct_hit = res.violations == [expected_id]
    if not distinct_hit:
        failures.append(
            f"{element}: expected exactly [{expected_id}], got {res.violations}"
        )
    rows.append({
        "omitted": element,
        "ok": res.ok,
        "expected_id": expected_id,
        "violation_ids": res.violations,
        "distinct_hit": distinct_hit,
    })

ids = [r["expected_id"] for r in rows]
out = {
    "control_registers": control_registers,
    "distinct_violation_ids": len({i for r in rows for i in r["violation_ids"]}),
    "ids": ids,
    "omissions": len(rows),
    "pass": not failures,
    "probe": "probe2-six-omissions",
    "rows": rows,
}
print("RESULT:" + json.dumps(out, sort_keys=True))
if failures:
    for f in failures:
        print(f"  FAIL {f}")
    print(f"FAILED:IMP-0230-probe2 {len(failures)} omission assertion(s) failed")
    raise SystemExit(1)
print("SUCCESS:IMP-0230-probe2 six one-at-a-time omissions produce six distinct rejections")
