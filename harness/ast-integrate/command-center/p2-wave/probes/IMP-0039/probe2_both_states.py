#!/usr/bin/env python3
"""Named probe 2: both-states + filesystem-only cannot pass.

Reviewer order: known-broken first. A probe silent in both states measures nothing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))

from hook_fire_probe import filesystem_only_verdict, run_probe  # noqa: E402

BROKEN = HERE / "fixtures" / "broken"
HEALTHY = HERE / "fixtures" / "healthy"


def main() -> int:
    broken = run_probe(BROKEN, work_dir=HERE / ".work" / "probe2-broken")
    print("broken", json.dumps(broken.to_dict(), sort_keys=True))
    if broken.verdict != "NOT-FIRED":
        print("FAILED:IMP-0039-probe2 broken config must report NOT-FIRED")
        return 1
    if broken.sentinel_observed:
        print("FAILED:IMP-0039-probe2 broken config emitted a sentinel")
        return 1
    if broken.inventory_loaded:
        print("FAILED:IMP-0039-probe2 broken inventory must be empty")
        return 1
    if "$schema" not in broken.extra_keys:
        print("FAILED:IMP-0039-probe2 expected $schema among extra_keys")
        return 1
    if broken.trigger_count != 0:
        print("FAILED:IMP-0039-probe2 unloaded client must not invoke hooks")
        return 1

    fs_broken = filesystem_only_verdict(BROKEN)
    print(f"filesystem_only_broken={fs_broken}")
    if fs_broken != "FIRED":
        print("FAILED:IMP-0039-probe2 filesystem-only control must be fooled")
        return 1
    if fs_broken == broken.verdict:
        print("FAILED:IMP-0039-probe2 filesystem-only matched the real probe")
        return 1
    if not (BROKEN / "hooks.json").is_file() or not (BROKEN / "scripts" / "emit_sentinel.py").is_file():
        print("FAILED:IMP-0039-probe2 broken fixture missing files (seed violated)")
        return 1

    healthy = run_probe(HEALTHY, work_dir=HERE / ".work" / "probe2-healthy")
    print("healthy", json.dumps(healthy.to_dict(), sort_keys=True))
    if healthy.verdict != "FIRED":
        print("FAILED:IMP-0039-probe2 silent-in-both-states (healthy not FIRED)")
        return 1
    if broken.verdict == healthy.verdict:
        print("FAILED:IMP-0039-probe2 probe did not discriminate states")
        return 1

    print("SUCCESS:IMP-0039-probe2 both-states NOT-FIRED vs FIRED; filesystem-only cannot pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
