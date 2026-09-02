#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TOOLS))
from plugin.exit_codes import (  # noqa: E402
    BLOCKED_NEEDS_OWNER,
    INTERNAL_ERROR,
    PERMISSION_DENIED,
    PRECONDITION_FAILED,
    SUCCESS,
    USAGE_ERROR,
    VALIDATION_FAILED,
    BY_NAME,
    cli_argv,
    is_shell_reserved,
    observe_argv,
)


def _run(argv, expected) -> None:
    obs = observe_argv(argv, via="native")
    assert obs.present and obs.exit_code == expected, (obs.exit_code, expected, obs.stdout)


def test_usage_error() -> None:
    _run(cli_argv("not-a-verb"), USAGE_ERROR)


def test_precondition_failed() -> None:
    with tempfile.TemporaryDirectory() as td:
        missing = str(Path(td) / "nope.json")
        _run(cli_argv("preflight", "--require-file", missing), PRECONDITION_FAILED)


def test_validation_failed() -> None:
    with tempfile.TemporaryDirectory() as td:
        bad = Path(td) / "bad.json"
        bad.write_text("{}", encoding="utf-8")
        _run(cli_argv("check", "--file", str(bad)), VALIDATION_FAILED)


def test_permission_denied() -> None:
    _run(cli_argv("write", "--path", "/sys/imp0055-denied", "--body", "x"), PERMISSION_DENIED)


def test_blocked_needs_owner() -> None:
    _run(
        cli_argv("owner-gate", "--installed", "fs:read", "--candidate", "fs:read", "--candidate", "net:connect"),
        BLOCKED_NEEDS_OWNER,
    )


def test_internal_error() -> None:
    _run(cli_argv("internal"), INTERNAL_ERROR)


def test_negative_control_failed_prints_report_never_exits_zero() -> None:
    with tempfile.TemporaryDirectory() as td:
        bad = Path(td) / "bad.json"
        bad.write_text("{}", encoding="utf-8")
        obs = observe_argv(cli_argv("check", "--file", str(bad)), via="native")
        assert obs.exit_code != 0
        assert obs.stdout.strip()
        json.loads(obs.stdout.strip().splitlines()[-1])


def test_no_collision_with_shell_reserved_values() -> None:
    for name, code in BY_NAME.items():
        assert not is_shell_reserved(code), name


def test_posix_shell_observes_the_same_integers() -> None:
    native = observe_argv(cli_argv("not-a-verb"), via="native")
    bash = observe_argv(cli_argv("not-a-verb"), via="bash")
    if bash.present:
        assert bash.exit_code == native.exit_code == USAGE_ERROR


def test_success_is_zero_only_when_verified() -> None:
    ok = observe_argv(cli_argv("verify"), via="native")
    bad = observe_argv(cli_argv("not-a-verb"), via="native")
    assert ok.exit_code == SUCCESS == 0
    assert bad.exit_code != 0


def main() -> int:
    tests = [
        test_usage_error,
        test_precondition_failed,
        test_validation_failed,
        test_permission_denied,
        test_blocked_needs_owner,
        test_internal_error,
        test_negative_control_failed_prints_report_never_exits_zero,
        test_no_collision_with_shell_reserved_values,
        test_posix_shell_observes_the_same_integers,
        test_success_is_zero_only_when_verified,
    ]
    for fn in tests:
        fn()
        print(f"{fn.__name__} ... ok")
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
