#!/usr/bin/env python3
"""IMP-0039 probe2: independent reviewer probe — both states, one instrument.

Reviewer obligations (receipt reviewer block + negative controls):
  * healthy config -> FIRED (sentinel + inventory);
  * broken config (unknown top-level $schema key, the Codex zero-load
    precedent) -> NOT-FIRED: inventory empty, trigger_count 0, sentinel absent,
    and every hook file still on disk;
  * a filesystem-only checker is FOOLED by the broken fixture (says FIRED)
    while the real probe is not — the probe cannot pass on file existence.
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


def observe(config: str, work: Path) -> dict:
    root = work / config
    shutil.copytree(FIXTURES / config, root)
    report = run_probe(root)
    client = client_document(root)
    fs_only = filesystem_only_verdict(root)
    files = sorted(
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file()
    )
    return {
        "verdict": report.verdict,
        "sentinel_observed": report.sentinel_observed,
        "trigger_count": report.trigger_count,
        "inventory_loaded": report.inventory_loaded,
        "inventory_reason": client["reason"],
        "extra_keys": report.extra_keys,
        "filesystem_would_say": fs_only,
        "files_on_disk": files,
    }


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="imp0039-p2-"))
    try:
        healthy = observe("healthy", work)
        broken = observe("broken", work)

        checks = {
            "healthy_fired": healthy["verdict"] == "FIRED"
            and healthy["sentinel_observed"] is True
            and healthy["inventory_loaded"] == ["hook.pre-tool"],
            "healthy_fs_only_agrees": healthy["filesystem_would_say"] == "FIRED",
            "broken_not_fired": broken["verdict"] == "NOT-FIRED",
            "broken_inventory_empty": broken["inventory_loaded"] == [],
            "broken_triggers_zero": broken["trigger_count"] == 0,
            "broken_extra_key": broken["extra_keys"] == ["$schema"],
            "broken_files_still_on_disk": any(
                f == "scripts/emit_sentinel.py" for f in broken["files_on_disk"]
            ) and any(f == "hooks.json" for f in broken["files_on_disk"]),
            "fs_only_fooled": broken["filesystem_would_say"] == "FIRED",
            "probe_discriminates": (healthy["verdict"] == "FIRED")
            != (broken["verdict"] == "FIRED"),
        }
        out = {
            "unit_id": "IMP-0039",
            "probe": "probe2-both-states",
            "healthy": healthy,
            "broken": broken,
            "checks": checks,
            "pass": all(checks.values()),
        }
        print(json.dumps(out, sort_keys=True))
        print(
            f"broken extra_keys={broken['extra_keys']} inventory=[] "
            f"trigger_count=0 fs_only_says={broken['filesystem_would_say']} "
            f"real={broken['verdict']}"
        )
        if not all(checks.values()):
            print(f"FAILED:IMP-0039-probe2 {[k for k, v in checks.items() if not v]}")
            return 1
        print("SUCCESS:IMP-0039-probe2 both states; filesystem-only control fires")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
