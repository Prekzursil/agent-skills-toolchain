#!/usr/bin/env python3
"""Probe 2: planted import-path break is visible via the console script.

Omits tst0128pkg/extra.py from a scratch install. Source-tree ``python -m``
stays green (the broken detector). The installed console script's collection
set shrinks / import fails — a collection difference is a packaging defect
even if every *collected* test still passed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from parity import planted_break  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:TST-0128-probe2 {msg}")
    return 1


def main() -> int:
    result = planted_break()
    print(json.dumps(result, sort_keys=True, default=str))
    if result["extra_installed"]:
        return fail("planted omit did not drop tst0128pkg/extra.py")
    if not result["source_python_m_still_green"]:
        return fail("source python -m was not green on the planted tree")
    if not result["console_script_sees_break"]:
        return fail("console script did not see the omitted extra module")
    if not result["collection_sets_differ"]:
        return fail("collection sets matched — planted break is invisible")
    if not result["pass"]:
        return fail("planted-break control did not hold")
    print(
        "SUCCESS:TST-0128-probe2 planted-import-path-break "
        f"source={result['source_set']} console={result['console_set']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
