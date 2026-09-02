#!/usr/bin/env python3
"""Probe 2: moving the permission check after spawn makes zero-spawn go red."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402
import ast  # noqa: E402
import importlib.util  # noqa: E402

sys.path.insert(0, str(S.SPEC_ROOT))
from agentspec.dispatchpolicy import dispatch  # noqa: E402
from agentspec.evals.fake_rail import CountingFakeRail  # noqa: E402
from agentspec.spec import ToolPermissionError  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "imp0136_dispatch_tests",
    S.SPEC_ROOT / "tests" / "test_dispatchpolicy.py",
)
_tests = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_tests)
overprivileged_unit = _tests.overprivileged_unit


def run_overpriv(dispatch_fn) -> tuple[int, str | None]:
    rail = CountingFakeRail()
    unit = overprivileged_unit()
    code = None
    try:
        dispatch_fn(unit, frozenset({"Read", "Write"}), rail)
    except ToolPermissionError as exc:
        code = exc.code
    except Exception as exc:  # pragma: no cover - unexpected
        return rail.spawn_count, f"{type(exc).__name__}:{exc}"
    return rail.spawn_count, code


def load_mutant(src: str):
    tree = S.mutate_check_after_spawn(src)
    ns: dict = {}
    exec(compile(tree, "<IMP-0136-mutant>", "exec"), ns)
    return ns["dispatch"]


def main() -> int:
    src = S.dispatch_source()
    if not S.authorize_before_spawn(src):
        print("FAILED:IMP-0136-probe2 live dispatch() is not check-then-spawn")
        return 1

    live_spawns, live_code = run_overpriv(dispatch)
    if live_spawns != 0 or live_code is None:
        print(
            f"FAILED:IMP-0136-probe2 live overpriv spawns={live_spawns} code={live_code}"
        )
        return 1

    mutant_dispatch = load_mutant(src)
    mutant_src = ast.unparse(S.mutate_check_after_spawn(src))
    if S.authorize_before_spawn(mutant_src):
        print("FAILED:IMP-0136-probe2 mutant still has authorize before spawn")
        return 1

    mutant_spawns, mutant_code = run_overpriv(mutant_dispatch)
    zero_spawn_assertion_holds = mutant_spawns == 0
    if zero_spawn_assertion_holds:
        print(
            "FAILED:IMP-0136-probe2 mutant kept zero spawns; "
            "moving the check after spawn must go red"
        )
        return 1
    if mutant_spawns != 1:
        print(f"FAILED:IMP-0136-probe2 mutant spawn_count={mutant_spawns} expected 1")
        return 1

    relive_spawns, _ = run_overpriv(dispatch)
    if relive_spawns != 0:
        print("FAILED:IMP-0136-probe2 live dispatch drifted after mutant exec")
        return 1
    if not S.DISPATCH_PY.read_text(encoding="utf-8") == src:
        print("FAILED:IMP-0136-probe2 dispatchpolicy.py bytes changed")
        return 1

    payload = {
        "probe": "probe2-mutation-order",
        "unit_id": "IMP-0136",
        "live_overpriv_spawns": live_spawns,
        "live_violation": live_code,
        "mutant_overpriv_spawns": mutant_spawns,
        "mutant_zero_spawn_assertion": "RED",
        "source_unchanged": True,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"live_spawns={live_spawns} mutant_spawns={mutant_spawns} "
        "zero_spawn_on_mutant=RED source_unchanged=True"
    )
    print("SUCCESS:IMP-0136-probe2 mutation: check-after-spawn makes zero-spawn go red")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
