#!/usr/bin/env python3
"""Probe 1: over-privileged fixture is refused with zero spawns; twin spawns once."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402
import importlib.util  # noqa: E402

sys.path.insert(0, str(S.SPEC_ROOT))
_spec = importlib.util.spec_from_file_location(
    "imp0136_dispatch_tests",
    S.SPEC_ROOT / "tests" / "test_dispatchpolicy.py",
)
_tests = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_tests)
test_overprivileged_rejected_zero_spawns = _tests.test_overprivileged_rejected_zero_spawns
test_permitted_twin_spawns_once = _tests.test_permitted_twin_spawns_once
test_subset_of_declaration_spawns_once = _tests.test_subset_of_declaration_spawns_once
test_unknown_name_rejected_zero_spawns = _tests.test_unknown_name_rejected_zero_spawns


def main() -> int:
    if not S.DISPATCH_PY.is_file():
        print("FAILED:IMP-0136-probe1 dispatchpolicy.py missing")
        return 1
    if not S.authorize_before_spawn():
        print("FAILED:IMP-0136-probe1 authorize does not precede spawn in dispatch()")
        return 1
    rows = [
        test_overprivileged_rejected_zero_spawns(),
        test_permitted_twin_spawns_once(),
        test_subset_of_declaration_spawns_once(),
        test_unknown_name_rejected_zero_spawns(),
    ]
    over = next(r for r in rows if r["case"] == "overprivileged")
    ok = next(r for r in rows if r["case"] == "permitted_twin")
    if over["spawn_count"] != 0:
        print(f"FAILED:IMP-0136-probe1 overprivileged spawned {over['spawn_count']}")
        return 1
    if ok["spawn_count"] != 1:
        print(f"FAILED:IMP-0136-probe1 permitted twin spawned {ok['spawn_count']}")
        return 1
    payload = {
        "probe": "probe1-least-privilege",
        "unit_id": "IMP-0136",
        "authorize_before_spawn": True,
        "overprivileged_spawns": over["spawn_count"],
        "permitted_twin_spawns": ok["spawn_count"],
        "rows": rows,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "overpriv_spawns=0 permitted_twin_spawns=1 "
        "authorize_before_spawn=True"
    )
    print("SUCCESS:IMP-0136-probe1 over-privileged zero spawns; permitted twin once")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
