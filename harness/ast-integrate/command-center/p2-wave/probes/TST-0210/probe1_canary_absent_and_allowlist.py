#!/usr/bin/env python3
"""Probe 1: planted canary is absent in a live adapter child; allowlist matches keys.

Two independent signals:
  (a) child's dumped environment keys (canary absent)
  (b) static allowlist in tools/lib/security.mjs compared to the observed set
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from harness import (  # noqa: E402
    ADAPTER_PATH,
    CANARY_KEY,
    SECURITY_MJS,
    dump_keys_via_adapter,
    load_env_mod,
    planted_canary,
)


def main() -> int:
    env_mod = load_env_mod()
    declared = env_mod.load_declared_allowlist(SECURITY_MJS)
    adapter_src = ADAPTER_PATH.read_text(encoding="utf-8")
    static = env_mod.adapter_run_calls_pass_env(adapter_src)
    problems: list[str] = []
    if CANARY_KEY in declared:
        problems.append("canary is in the declared allowlist; detector would be vacuous")
    if not static.get("perform_found"):
        problems.append("ClaudeAdapter._perform not found for env= walk")
    if not static.get("bash_env"):
        problems.append("Bash subprocess.run does not pass env=")
    if not static.get("powershell_env"):
        problems.append("PowerShell subprocess.run does not pass env=")

    with planted_canary():
        if os_canary_missing():
            problems.append("failed to plant canary in parent")
        observed, dispatched = dump_keys_via_adapter()

    extras = env_mod.extras_vs_allowlist(observed, declared)
    canary_present = CANARY_KEY in observed
    if canary_present:
        problems.append("canary key present in child dump")
    if extras:
        problems.append(f"child keys outside allowlist: {extras[:20]}")
    if not observed:
        problems.append("child dump produced zero keys (dump may be fake-empty)")

    payload = {
        "probe": "probe1-canary-absent-and-allowlist",
        "unit_id": "TST-0210",
        "pass": not problems,
        "problems": problems,
        "canary_key": CANARY_KEY,
        "canary_present_in_child": canary_present,
        "declared_allowlist_size": len(declared),
        "observed_key_count": len(observed),
        "observed_keys": observed,
        "extras_vs_allowlist": extras,
        "static_adapter_env": static,
        "adapter_state": dispatched.get("state"),
        "signals": {
            "a_child_dump_canary_absent": not canary_present,
            "b_static_allowlist_covers_observed": extras == [],
        },
    }
    print(json.dumps(payload, indent=1, sort_keys=True))
    if problems:
        print("FAILED:TST-0210-probe1 " + "; ".join(problems))
        return 1
    print(
        "SUCCESS:TST-0210-probe1 canary_absent="
        f"{not canary_present} extras={len(extras)} keys={len(observed)}"
    )
    return 0


def os_canary_missing() -> bool:
    import os

    return os.environ.get(CANARY_KEY) is None


if __name__ == "__main__":
    raise SystemExit(main())
