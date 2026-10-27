#!/usr/bin/env python3
"""Both-states tests for the IMP-0437 field-completeness CI arming.

Runnable as a script (emit_receipt.py) and as pytest (quality.yml collects
tools/command-center/tests). Named probes in probes/IMP-0437/ re-run the same
mutations against the live catalog; this file uses the mini fixture so the
pytest lane stays fast.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CC = HERE.parent
if str(CC) not in sys.path:
    sys.path.insert(0, str(CC))

import vfields_ci as vci  # noqa: E402


def test_workflow_invokes_validate_with_require_complete() -> None:
    assert vci.workflow_path().is_file(), f"missing {vci.WORKFLOW_REL}"
    assert vci.workflow_arms_require_complete(), (
        f"{vci.WORKFLOW_REL} does not invoke {vci.VALIDATE_REL} "
        f"with {vci.REQUIRE_COMPLETE_FLAG}"
    )


def test_unmutated_catalog_silent_when_armed() -> None:
    with tempfile.TemporaryDirectory(prefix="vfields-good-") as raw:
        sandbox = vci.write_sandbox(Path(raw) / "good", vci.mini_catalog())
        armed = vci.run_validate(sandbox, [vci.REQUIRE_COMPLETE_FLAG])
        bare = vci.run_validate(sandbox, [])
        assert armed["exit_code"] == 0, armed["output"][-800:]
        assert not armed["vfields"], armed["output"][-800:]
        assert bare["exit_code"] == 0, bare["output"][-800:]
        assert not bare["vfields"], bare["output"][-800:]


def test_defaults_deletion_exits_nonzero_when_armed() -> None:
    with tempfile.TemporaryDirectory(prefix="vfields-armed-") as raw:
        dropped = vci.write_sandbox(
            Path(raw) / "dropped", vci.mini_catalog(), drop_defaults=True
        )
        armed = vci.run_validate(dropped, [vci.REQUIRE_COMPLETE_FLAG])
        bare = vci.run_validate(dropped, [])
        assert armed["exit_code"] != 0, armed["output"][-800:]
        assert armed["vfields"], armed["output"][-800:]
        assert bare["exit_code"] != 0, bare["output"][-800:]
        assert bare["vfields"], bare["output"][-800:]


def test_defaults_deletion_exits_zero_when_disarmed() -> None:
    with tempfile.TemporaryDirectory(prefix="vfields-disarm-") as raw:
        dropped = vci.write_sandbox(
            Path(raw) / "dropped", vci.mini_catalog(), drop_defaults=True
        )
        disarmed = vci.run_validate(dropped, [vci.DISARM_FLAG])
        assert disarmed["exit_code"] == 0, disarmed["output"][-800:]
        assert not disarmed["vfields"], disarmed["output"][-800:]


def test_single_field_deletion_exits_nonzero_when_armed() -> None:
    with tempfile.TemporaryDirectory(prefix="vfields-one-") as raw:
        one = vci.write_sandbox(
            Path(raw) / "one",
            vci.mini_catalog(),
            drop_default_field=vci.SINGLE_FIELD,
        )
        armed = vci.run_validate(one, [vci.REQUIRE_COMPLETE_FLAG])
        disarmed = vci.run_validate(one, [vci.DISARM_FLAG])
        assert armed["exit_code"] != 0, armed["output"][-800:]
        assert armed["vfields"], armed["output"][-800:]
        assert vci.SINGLE_FIELD in armed["output"], armed["output"][-800:]
        assert disarmed["exit_code"] == 0, disarmed["output"][-800:]
        assert not disarmed["vfields"], disarmed["output"][-800:]


def main() -> int:
    tests = (
        test_workflow_invokes_validate_with_require_complete,
        test_unmutated_catalog_silent_when_armed,
        test_defaults_deletion_exits_nonzero_when_armed,
        test_defaults_deletion_exits_zero_when_disarmed,
        test_single_field_deletion_exits_nonzero_when_armed,
    )
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print("SUCCESS:IMP-0437-tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
