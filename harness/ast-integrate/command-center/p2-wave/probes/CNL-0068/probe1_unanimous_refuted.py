#!/usr/bin/env python3
"""Probe 1: unanimous YES + failing bound test must not record YES.

Both-states: the same check is silent on a unanimous YES whose bound test passes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import override as O  # noqa: E402

ACCEPTING = O.ACCEPTING


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0068-probe1 {msg}")
    return 1


def main() -> int:
    planted = O.fixture_result("unanimous_refuted.json")
    good = O.fixture_result("known_good.json")
    print(json.dumps({"fixture": "unanimous_refuted", "result": planted}, sort_keys=True))
    print(json.dumps({"fixture": "known_good", "result": good}, sort_keys=True))

    if not planted["tally"]["unanimous_yes"]:
        return fail("planted fixture is not unanimous YES")
    if planted["tentative_outcome"] not in ACCEPTING:
        return fail(f"planted tentative={planted['tentative_outcome']}")
    if planted["outcome"] in ACCEPTING:
        return fail(
            f"unanimous YES survived a failing bound test: outcome={planted['outcome']}"
        )
    if planted["outcome"] != "REFUTED":
        return fail(f"expected REFUTED, got {planted['outcome']}")
    if planted["reason"] != "executable-test-override":
        return fail(f"reason={planted['reason']}")
    if planted["binding_yes"] is True:
        return fail("binding_yes must be false after override")
    if not planted["overriding_tests"]:
        return fail("no overriding test recorded")

    if not good["tally"]["unanimous_yes"]:
        return fail("known-good fixture is not unanimous YES")
    if good["outcome"] not in ACCEPTING:
        return fail(f"known-good was vetoed: outcome={good['outcome']}")
    if good["overriding_tests"]:
        return fail("known-good recorded an override")

    print(f"planted_fired outcome={planted['outcome']} reason={planted['reason']}")
    print(f"known_good_silent outcome={good['outcome']} reason={good['reason']}")
    print("negative_control_verbatim=" + O.NEGATIVE_CONTROL_VERBATIM)
    print("SUCCESS:CNL-0068-probe1 unanimous-but-refuted both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
