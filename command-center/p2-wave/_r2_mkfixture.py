"""Regenerate the `ready_units.py --self-test` vacuity control fixture.

The fixture is the real IMP-0433 receipt with EXACTLY ONE field changed (`state` -> SUCCESS).
This script asserts that one-field property, because a control that drifts from the artifact it
mirrors stops isolating the defect it was built to catch.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "command-center/receipts/IMP-0433.json"
DST = REPO / "command-center/p2-wave/fixtures/ready-units/IMP-0433-state-SUCCESS-mutant.json"

real = json.loads(SRC.read_text(encoding="utf-8"))
mut = json.loads(json.dumps(real))
mut["state"] = "SUCCESS"

diff = [k for k in set(real) | set(mut) if real.get(k) != mut.get(k)]
assert diff == ["state"], f"fixture must differ in exactly one field, differs in {diff}"
assert real["state"] != "SUCCESS", "source receipt already says SUCCESS; the control is inert"

DST.parent.mkdir(parents=True, exist_ok=True)
DST.write_text(json.dumps(mut, indent=1, sort_keys=True) + "\n", encoding="utf-8")
print(f"wrote {DST.relative_to(REPO).as_posix()} ({DST.stat().st_size} B); "
      f"one-field mutation {real['state']!r} -> {mut['state']!r}")
print("SUCCESS:r2-mkfixture")
