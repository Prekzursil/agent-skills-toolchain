#!/usr/bin/env python3
"""Named probe 2: detector control + create-if-missing (different field than probe 1).

Probe 1 reads tree-sha equality of real operations. This probe requires the
same comparison to fire on a deliberately non-idempotent append, and requires
create-if-missing not to truncate an existing non-empty file.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from harness import (  # noqa: E402
    measure_control,
    measure_create_if_missing,
    measure_force_create_hazard,
    report_payload,
)

ART = REPO / "command-center/confirmation/CNF-0036-repeat-application.json"


def main() -> int:
    control = measure_control()
    create = measure_create_if_missing()
    force = measure_force_create_hazard()
    derived = {
        "probe": "probe2-detector-control",
        "unit_id": "CNF-0036",
        "control_detected": control["detected"],
        "control_hash_sets_equal": control["hash_sets_equal"],
        "create_if_missing_pass": create["pass"],
        "create_truncated": create["truncated"],
        "force_create_truncates": force["truncated_existing"],
        "derived_pass": bool(
            control["detected"]
            and not control["hash_sets_equal"]
            and create["pass"]
            and not create["truncated"]
            and force["pass_as_data_loss_probe"]
        ),
    }
    print(json.dumps(derived, sort_keys=True))
    if not control["detected"] or control["hash_sets_equal"]:
        print("FAILED:CNF-0036-probe2 non-idempotent control not detected")
        return 1
    if not create["pass"] or create["truncated"] or create["wrote"]:
        print("FAILED:CNF-0036-probe2 create-if-missing truncated or wrote")
        return 1
    if not force["pass_as_data_loss_probe"]:
        print("FAILED:CNF-0036-probe2 force-create hazard not observed")
        return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0036-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    payload = report_payload(doc)
    art_ctl = payload.get("control") or {}
    if not art_ctl.get("detected") or art_ctl.get("hash_sets_equal"):
        print("FAILED:CNF-0036-probe2 artifact did not record control detection")
        return 1
    art_cim = payload.get("create_if_missing") or {}
    if not art_cim.get("pass") or art_cim.get("truncated"):
        print("FAILED:CNF-0036-probe2 artifact create-if-missing failed")
        return 1
    print("SUCCESS:CNF-0036-probe2 detector control and create-if-missing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
