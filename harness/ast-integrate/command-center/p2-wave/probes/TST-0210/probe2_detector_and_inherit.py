#!/usr/bin/env python3
"""Probe 2: detector (canary on allowlist appears) and inherit-all negative control.

Detector: add the canary to the allowlist and confirm it DOES appear — the child
dump is live, not a hardcoded empty dict.
Negative: full inheritance must fail the canary-absent test.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from harness import (  # noqa: E402
    CANARY_KEY,
    dump_keys_via_adapter,
    dump_keys_with_env,
    load_env_mod,
    planted_canary,
)


def main() -> int:
    env_mod = load_env_mod()
    problems: list[str] = []

    with planted_canary():
        parent_has = CANARY_KEY in os.environ
        default_keys = dump_keys_with_env(env_mod.child_env())
        detector_env = env_mod.filter_env(os.environ, extra_allow=[CANARY_KEY])
        detector_keys = dump_keys_with_env(detector_env)
        inherit_keys = dump_keys_with_env(dict(os.environ))
        adapter_keys, _dispatched = dump_keys_via_adapter()

    if not parent_has:
        problems.append("canary was not in parent env")
    if CANARY_KEY in default_keys:
        problems.append("filtered spawn still leaked canary")
    if CANARY_KEY not in detector_keys:
        problems.append("detector failed: canary on allowlist did not appear in child")
    if CANARY_KEY not in inherit_keys:
        problems.append("inherit-all child missing canary; dump is not a real env")
    inherit_fails_canary_test = CANARY_KEY in inherit_keys
    if not inherit_fails_canary_test:
        problems.append("full inheritance did not fail the canary-absent test")
    if CANARY_KEY in adapter_keys:
        problems.append("adapter child leaked canary during detector probe")
    inherit_extras = env_mod.extras_vs_allowlist(
        inherit_keys, env_mod.load_declared_allowlist()
    )
    if not inherit_extras:
        problems.append(
            "inherit-all observed set is a subset of the allowlist; control is vacuous"
        )

    payload = {
        "probe": "probe2-detector-and-inherit",
        "unit_id": "TST-0210",
        "pass": not problems,
        "problems": problems,
        "parent_has_canary": parent_has,
        "filtered_canary_present": CANARY_KEY in default_keys,
        "detector_canary_present": CANARY_KEY in detector_keys,
        "inherit_canary_present": CANARY_KEY in inherit_keys,
        "adapter_canary_present": CANARY_KEY in adapter_keys,
        "inherit_fails_canary_absent_test": inherit_fails_canary_test,
        "inherit_extras_count": len(inherit_extras),
        "detector_key_count": len(detector_keys),
        "inherit_key_count": len(inherit_keys),
        "filtered_key_count": len(default_keys),
    }
    print(json.dumps(payload, indent=1, sort_keys=True))
    if problems:
        print("FAILED:TST-0210-probe2 " + "; ".join(problems))
        return 1
    print(
        "SUCCESS:TST-0210-probe2 detector_appeared="
        f"{CANARY_KEY in detector_keys} inherit_fails={inherit_fails_canary_test}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
