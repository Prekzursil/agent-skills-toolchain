#!/usr/bin/env python3
"""Named probe 2 (independent reviewer): one-field mutation + re-derive probe1 exits.

Does not import probe1. Rebuilds the sandbox from the live catalog and checks:
- unmutated + armed is silent
- deleting timeout_seconds from defaults trips V-FIELDS when armed
- whole-defaults deletion: disarmed exit 0, armed exit nonzero (same as probe1)
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import vfields_ci as vci  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0437-probe2 {msg}")
    return 1


def main() -> int:
    catalog = vci.real_catalog()
    with tempfile.TemporaryDirectory(prefix="imp0437-p2-") as raw:
        tmp = Path(raw)
        good = vci.write_sandbox(tmp / "good", catalog)
        armed_good = vci.run_validate(good, [vci.REQUIRE_COMPLETE_FLAG])
        if armed_good["exit_code"] != 0 or armed_good["vfields"]:
            return fail(
                "reviewer: unmutated catalog not silent: "
                f"exit={armed_good['exit_code']} out={armed_good['output'][-800:]}"
            )

        one = vci.write_sandbox(
            tmp / "one", catalog, drop_default_field=vci.SINGLE_FIELD
        )
        one_armed = vci.run_validate(one, [vci.REQUIRE_COMPLETE_FLAG])
        if one_armed["exit_code"] == 0 or not one_armed["vfields"]:
            return fail(
                f"reviewer: deleting defaults.{vci.SINGLE_FIELD} did not trip V-FIELDS: "
                f"exit={one_armed['exit_code']} out={one_armed['output'][-800:]}"
            )
        if vci.SINGLE_FIELD not in one_armed["output"]:
            return fail(
                f"reviewer: V-FIELDS did not name {vci.SINGLE_FIELD}: "
                f"{one_armed['output'][-800:]}"
            )
        one_disarmed = vci.run_validate(one, [vci.DISARM_FLAG])
        if one_disarmed["exit_code"] != 0 or one_disarmed["vfields"]:
            return fail(
                "reviewer: single-field mutation red while disarmed "
                f"(leak): exit={one_disarmed['exit_code']} "
                f"out={one_disarmed['output'][-800:]}"
            )

        dropped = vci.write_sandbox(tmp / "dropped", catalog, drop_defaults=True)
        whole_disarmed = vci.run_validate(dropped, [vci.DISARM_FLAG])
        whole_armed = vci.run_validate(dropped, [vci.REQUIRE_COMPLETE_FLAG])
        if whole_disarmed["exit_code"] != 0 or whole_disarmed["vfields"]:
            return fail(
                "reviewer: whole-defaults deletion red while disarmed: "
                f"exit={whole_disarmed['exit_code']} out={whole_disarmed['output'][-800:]}"
            )
        if whole_armed["exit_code"] == 0 or not whole_armed["vfields"]:
            return fail(
                "reviewer: whole-defaults deletion silent when armed: "
                f"exit={whole_armed['exit_code']} out={whole_armed['output'][-800:]}"
            )

    payload = {
        "probe": "probe2-single-field-review",
        "unit_id": "IMP-0437",
        "reviewer_id": "IMP-0437-probe2-single-field-review",
        "single_field": vci.SINGLE_FIELD,
        "unmutated_armed_exit": armed_good["exit_code"],
        "single_field_armed_exit": one_armed["exit_code"],
        "single_field_disarmed_exit": one_disarmed["exit_code"],
        "whole_defaults_disarmed_exit": whole_disarmed["exit_code"],
        "whole_defaults_armed_exit": whole_armed["exit_code"],
        "independent": True,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"single_field={vci.SINGLE_FIELD} "
        f"one_armed={one_armed['exit_code']} one_disarmed={one_disarmed['exit_code']} "
        f"whole_armed={whole_armed['exit_code']} whole_disarmed={whole_disarmed['exit_code']}"
    )
    print("SUCCESS:IMP-0437-probe2 single-field mutation and independent both-states review")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
