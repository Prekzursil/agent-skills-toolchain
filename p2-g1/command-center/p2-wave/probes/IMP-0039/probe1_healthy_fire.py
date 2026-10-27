#!/usr/bin/env python3
"""IMP-0039 probe1: healthy hooks.json fires the hook and loads the inventory.

Both signals are required for FIRED: (1) the hook process wrote
HOOK_FIRED:<nonce>:<id> after a real subprocess trigger, and (2) the client
inventory document lists the same hook as loaded. A filesystem-only checker
would report FIRED from file existence alone — recorded as
filesystem_would_say to show the probe is NOT that.
"""
from __future__ import annotations

import ast  # bind stdlib ast before tools/ast.py can shadow it
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from plugin.hook_client import client_document  # noqa: E402
from plugin.hook_fire_probe import filesystem_only_verdict, run_probe  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def build(config: str, work: Path) -> Path:
    """Copy the fixture into a throwaway root (sentinels never accumulate)."""
    root = work / config
    shutil.copytree(FIXTURES / config, root)
    return root


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="imp0039-p1-"))
    try:
        root = build("healthy", work)
        report = run_probe(root)
        client = client_document(root)
        fs_only = filesystem_only_verdict(root)
        checks = {
            "fired": report.verdict == "FIRED",
            "sentinel_observed": report.sentinel_observed is True,
            "trigger_count_ge_1": report.trigger_count >= 1,
            "inventory_agrees": client["loaded"] == report.inventory_loaded
            and report.inventory_loaded == ["hook.pre-tool"],
            "inventory_reason_ok": client["reason"] == "ok",
            "no_extra_keys": report.extra_keys == [],
        }
        passed = all(checks.values())
        out = {
            "unit_id": "IMP-0039",
            "probe": "probe1-healthy-fire",
            "verdict": report.verdict,
            "hook_id": report.hook_id,
            "inventory_loaded": report.inventory_loaded,
            "inventory_reason": client["reason"],
            "extra_keys": report.extra_keys,
            "trigger_count": report.trigger_count,
            "filesystem_would_say": fs_only,
            "notes": ["two signals: hook sentinel + client inventory"],
            "checks": checks,
            "pass": passed,
        }
        print(json.dumps(out, sort_keys=True))
        print(
            f"healthy FIRED={report.verdict == 'FIRED'} "
            f"inventory={report.inventory_loaded} "
            f"fs_only_says={fs_only}"
        )
        if not passed:
            print(f"FAILED:IMP-0039-probe1 {[k for k, v in checks.items() if not v]}")
            return 1
        print("SUCCESS:IMP-0039-probe1 healthy config fires both signals")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
