#!/usr/bin/env python3
"""Probe 2: divergence control (skip C08) plus implementation census."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from census import census  # noqa: E402
from differential import divergence_control  # noqa: E402


def main() -> int:
    div = divergence_control()
    pop = census()
    fail = False
    reasons: list[str] = []

    if not div.get("ok"):
        fail = True
        reasons.append(
            "divergence_control ok=false detected="
            f"{div.get('detected')} honest_agree={div.get('honest_agree_on_c08_row')} "
            f"healthy_complete={div.get('healthy_skip_still_complete')}"
        )
    if not div.get("detected"):
        fail = True
        reasons.append("skipping C08 was not detected by the differential")
    if pop.get("harness_count", 0) < 2:
        fail = True
        reasons.append(
            f"implementation census found {pop.get('harness_count')} "
            "(NOT-CHECKED rather than a trivial pass)"
        )
    if pop.get("status") != "CHECKED":
        fail = True
        reasons.append(f"census status={pop.get('status')}")
    mention = pop.get("mention_control") or {}
    if mention.get("counted_as_implementation"):
        fail = True
        reasons.append("mention-only markdown was counted as an implementation")
    if not mention.get("mentions_predicate_in_prose"):
        fail = True
        reasons.append("mention-only fixture does not mention the predicate")
    roles = set(pop.get("roles") or [])
    if "local-python" not in roles or "monitor-javascript" not in roles:
        fail = True
        reasons.append(f"roles {sorted(roles)} missing local-python or monitor-javascript")

    payload = {
        "probe": "probe2-divergence-and-census",
        "unit_id": "TST-0330",
        "pass": not fail,
        "divergence": {
            "ok": div.get("ok"),
            "detected": div.get("detected"),
            "honest_agree_on_c08_row": div.get("honest_agree_on_c08_row"),
            "healthy_skip_still_complete": div.get("healthy_skip_still_complete"),
            "patched_python_on_c08_row": div.get("patched_python_on_c08_row"),
            "honest_monitor_on_c08_row": div.get("honest_monitor_on_c08_row"),
            "input_verbatim": div.get("input_verbatim"),
        },
        "census": {
            "status": pop.get("status"),
            "harness_count": pop.get("harness_count"),
            "roles": pop.get("roles"),
            "production_count": pop.get("production_count"),
            "production_hits": pop.get("production_hits"),
            "cc0003_on_disk": pop.get("cc0003_on_disk"),
            "cloud_dispatcher_on_disk": pop.get("cloud_dispatcher_on_disk"),
            "mention_control": pop.get("mention_control"),
            "note": pop.get("note"),
        },
        "reasons": reasons,
    }
    print(json.dumps(payload, sort_keys=True))
    if fail:
        print("FAILED:TST-0330-probe2 divergence or census")
        return 1
    print(
        "SUCCESS:TST-0330-probe2 skip-C08 detected; "
        f"implementations={pop['harness_count']} roles={pop['roles']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
