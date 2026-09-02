#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TOOLS))
from plugin.doctor.efficacy import run_all_remediations, run_noop_overclaim  # noqa: E402
from plugin.doctor.io import taxonomy_codes  # noqa: E402


def test_remediation_actually_fixes_the_fixture() -> None:
    sweep = run_all_remediations(taxonomy_codes())
    assert sweep["pass"], sweep
    oc = run_noop_overclaim("PLUGIN.HEALTH.HOOKS_UNLOADED")
    assert oc["overclaim_caught"]


def main() -> int:
    test_remediation_actually_fixes_the_fixture()
    print("test_remediation_actually_fixes_the_fixture ... ok")
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
