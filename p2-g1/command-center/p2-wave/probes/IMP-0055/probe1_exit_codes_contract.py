#!/usr/bin/env python3
"""IMP-0055 probe1 (source): every failure class exits its exact integer from
the plugin CLI; exit 0 only on verified success; no assigned code collides
with shell-reserved codes."""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from plugin.exit_codes import (  # noqa: E402
    BLOCKED_NEEDS_OWNER, INTERNAL_ERROR, PERMISSION_DENIED, PRECONDITION_FAILED,
    SUCCESS, USAGE_ERROR, VALIDATION_FAILED, cli_argv, is_shell_reserved,
    observe_argv, verify_contract,
)


def obs(argv, expected):
    o = observe_argv(argv, via="native")
    assert o.present and o.exit_code == expected, (argv, o.exit_code, expected, o.stdout[-200:])


def main() -> int:
    obs(cli_argv("not-a-verb"), USAGE_ERROR)
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        missing = str(Path(td) / "nope.json")
        obs(cli_argv("preflight", "--require-file", missing), PRECONDITION_FAILED)
        obs(cli_argv("check", "--file", str(Path(td) / "missing.json")), VALIDATION_FAILED)
        obs(cli_argv("owner-gate", "--candidate", "not-installed-pkg"), BLOCKED_NEEDS_OWNER)
        obs(cli_argv("internal"), INTERNAL_ERROR)
        obs(cli_argv("write", "--path", "/sys/imp0055-denied", "--body", "x"), PERMISSION_DENIED)
        obs(cli_argv("write", "--path", "/sys/imp0055-denied", "--body", "x"), PERMISSION_DENIED)
        obs(cli_argv("verify"), SUCCESS)
    contract = verify_contract()
    checks = {
        "codes_unique": contract["unique"] is True,
        "no_reserved_collisions": contract["reserved_collisions"] == [],
        "success_is_zero": contract["by_name"]["SUCCESS"] == 0,
        "usage_nonzero": contract["by_name"]["USAGE_ERROR"] != 0,
    }
    print(json.dumps({"by_name": contract["by_name"], "checks": checks}))
    if not all(checks.values()):
        print("FAILED:IMP-0055-probe1 contract broken")
        return 1
    print("SUCCESS:IMP-0055-probe1 one integer per failure class; zero only on verified success")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
