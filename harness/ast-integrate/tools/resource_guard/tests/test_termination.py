#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE.parent))

from resource_guard.termination import (  # noqa: E402
    ACTION_REAP,
    ACTION_SPARE,
    REASON_ALLOWLIST,
    evaluate,
    load_ceiling_world,
)


def main() -> int:
    world = load_ceiling_world()
    run = evaluate(world)
    assert 8812 not in run.kill_set
    assert run.decision_for(8812).action == ACTION_SPARE
    assert run.decision_for(8812).reason == REASON_ALLOWLIST
    assert 9001 in run.kill_set
    assert run.decision_for(9001).action == ACTION_REAP
    print("SUCCESS:resource_guard.termination self-test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
