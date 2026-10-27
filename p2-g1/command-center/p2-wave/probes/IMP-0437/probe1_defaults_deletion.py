"""Defaults-block deletion must turn the armed gate red (IMP-0437).

Before: the same deletion exits 0 against the disarmed surface.
After: identical deletion exits nonzero with V-FIELDS from validate.py.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import vfields_ci as vc  # noqa: E402


def main() -> int:
    mini = vc.mini_catalog()

    with tempfile.TemporaryDirectory() as td:
        armed_intact = vc.run_validate(
            vc.write_sandbox(Path(td) / "armed", mini), flags=["--require-complete"])
        assert armed_intact["exit_code"] == 0, armed_intact["output"][-300:]

        armed_deleted = vc.run_validate(
            vc.write_sandbox(Path(td) / "deleted", mini, drop_defaults=True),
            flags=["--require-complete"])
        assert armed_deleted["exit_code"] != 0, "defaults deletion must fail when armed"
        assert armed_deleted["vfields"], "failure must be V-FIELDS"
        assert vc.workflow_arms_require_complete(), "CI must invoke --require-complete"

        disarmed_deleted = vc.run_validate(
            vc.write_sandbox(Path(td) / "disarmed", mini, drop_defaults=True),
            flags=["--no-require-complete"])
        assert disarmed_deleted["exit_code"] == 0, (
            "disarmed control must stay silent: " + disarmed_deleted["output"][-200:])

    print(json.dumps({
        "probe": "probe1-defaults-deletion",
        "unit_id": "IMP-0437",
        "before_disarmed_deletion_exit": disarmed_deleted["exit_code"],
        "after_armed_intact_exit": armed_intact["exit_code"],
        "after_armed_deletion_exit": armed_deleted["exit_code"],
        "vfields_fired": armed_deleted["vfields"],
        "ci_arms_flag": True,
        "ci_step_command": "python tools/command-center/validate.py --require-complete",
        "sentinel": "SENTINEL:IMP-0437:FIELD-COMPLETENESS-ARMED",
    }, indent=2))
    print("SUCCESS:IMP-0437-probe1 defaults deletion exits 0 disarmed, nonzero armed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
