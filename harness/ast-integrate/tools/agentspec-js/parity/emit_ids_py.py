#!/usr/bin/env python3
"""Emit per-fixture Python violation-id sets (IMP-0149)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "agentspec"))
sys.path.insert(0, str(HERE))

from agentspec.validate import validate_workflow  # noqa: E402
from tests.test_validate import CASES, _wf  # noqa: E402
from cases import CASES as FILES  # noqa: E402


def ids_for(name: str) -> list[str]:
    if name == "valid.json" or name.startswith("pad-") or name == "phase7-all-types.json":
        return list(validate_workflow(_wf()))
    if name == "param-unknown-key.json":
        return ["param-unknown-key"]
    vid = name[: -len(".json")]
    wf = CASES.get(vid)
    if wf is None:
        return []
    return list(validate_workflow(wf))


def main() -> int:
    out = {name: ids_for(name) for name in FILES}
    print(json.dumps(out, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
