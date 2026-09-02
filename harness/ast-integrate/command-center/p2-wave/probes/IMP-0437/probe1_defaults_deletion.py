#!/usr/bin/env python3
"""Named probe 1: deleting the entire defaults block turns the armed CI line red.

Control: the same mutation under --no-require-complete still exits 0.
The unmutated catalog under --require-complete exits 0 (no false positive).
Also asserts .github/workflows/quality.yml passes --require-complete.
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
    print(f"FAILED:IMP-0437-probe1 {msg}")
    return 1


def main() -> int:
    if not vci.workflow_path().is_file():
        return fail(f"missing CI workflow at {vci.WORKFLOW_REL}")
    if not vci.workflow_arms_require_complete():
        return fail(
            f"{vci.WORKFLOW_REL} does not invoke {vci.VALIDATE_REL} "
            f"with {vci.REQUIRE_COMPLETE_FLAG}"
        )

    catalog = vci.real_catalog()
    with tempfile.TemporaryDirectory(prefix="imp0437-p1-") as raw:
        tmp = Path(raw)
        good = vci.write_sandbox(tmp / "good", catalog)
        armed_good = vci.run_validate(good, [vci.REQUIRE_COMPLETE_FLAG])
        if armed_good["exit_code"] != 0 or armed_good["vfields"]:
            return fail(
                "unmutated catalog not silent under --require-complete: "
                f"exit={armed_good['exit_code']} out={armed_good['output'][-800:]}"
            )

        dropped = vci.write_sandbox(tmp / "dropped", catalog, drop_defaults=True)
        disarmed = vci.run_validate(dropped, [vci.DISARM_FLAG])
        if disarmed["exit_code"] != 0 or disarmed["vfields"]:
            return fail(
                "defaults deletion still red when disarmed "
                f"(other checks leaking): exit={disarmed['exit_code']} "
                f"out={disarmed['output'][-800:]}"
            )

        armed_bad = vci.run_validate(dropped, [vci.REQUIRE_COMPLETE_FLAG])
        if armed_bad["exit_code"] == 0 or not armed_bad["vfields"]:
            return fail(
                "defaults deletion did not trip V-FIELDS when armed: "
                f"exit={armed_bad['exit_code']} out={armed_bad['output'][-800:]}"
            )

        bare = vci.run_validate(dropped, [])
        if bare["exit_code"] == 0 or not bare["vfields"]:
            return fail(
                "bare CLI (historical CI line) still silent after defaults deletion: "
                f"exit={bare['exit_code']} out={bare['output'][-800:]}"
            )

    payload = {
        "probe": "probe1-defaults-deletion",
        "unit_id": "IMP-0437",
        "ci_workflow": vci.WORKFLOW_REL,
        "ci_flag": vci.REQUIRE_COMPLETE_FLAG,
        "unmutated_armed_exit": armed_good["exit_code"],
        "defaults_deleted_disarmed_exit": disarmed["exit_code"],
        "defaults_deleted_armed_exit": armed_bad["exit_code"],
        "defaults_deleted_bare_exit": bare["exit_code"],
        "vfields_on_armed_mutation": True,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "unmutated_armed=0 "
        f"deleted_disarmed={disarmed['exit_code']} "
        f"deleted_armed={armed_bad['exit_code']} "
        f"deleted_bare={bare['exit_code']} V-FIELDS=True"
    )
    print("SUCCESS:IMP-0437-probe1 defaults-deletion both-states under CI invocation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
