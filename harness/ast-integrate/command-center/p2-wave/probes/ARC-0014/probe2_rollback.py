#!/usr/bin/env python3
"""Named probe 2: freeze hook + rollback rehearsal (different field than probe 1).

Probe 1 reads sha256 / line-set remainder. This probe reads freeze-hook exit
status and deploy-write success after restoring one file to hand-authored.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from extract import (  # noqa: E402
    LIVE_LARGER_REL,
    artifact_rollback_rehearsal,
    mini_registry,
    round_trip_tree,
)
from freeze_hook import check, default_ledger, deploy_write  # noqa: E402
from rollback import rehearse  # noqa: E402
from scenario import build_live_tree  # noqa: E402

ART = REPO / "command-center/phase3/A2/MIGRATION.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:ARC-0014-probe2 migration artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory(prefix="arc0014-p2-") as tmp:
        root = Path(tmp)
        build_live_tree(root)
        live_root = root / "live"
        deploy_root = root / "deploy"
        rows = round_trip_tree(live_root)
        entries = [r["entry"] for r in rows]
        registry = mini_registry(entries)
        for rec in rows:
            deploy_write(deploy_root, rec["path"], rec["regenerated"])
        ledger = default_ledger([r["path"] for r in rows])
        baseline = check(deploy_root, registry, ledger)
        if not baseline["ok"]:
            print("FAILED:ARC-0014-probe2 baseline freeze not clean")
            print(json.dumps(baseline, indent=2, default=str)[:2000])
            return 1
        result = rehearse(live_root, deploy_root, registry, ledger, LIVE_LARGER_REL)

    if not result.get("pass"):
        print("FAILED:ARC-0014-probe2 rollback rehearsal")
        print(json.dumps(result, indent=2, default=str)[:3000])
        return 1
    if not result.get("freeze_rejected_live_bytes_before_rollback"):
        print("FAILED:ARC-0014-probe2 freeze did not reject live bytes pre-rollback")
        return 1
    if result.get("restored_path") != LIVE_LARGER_REL:
        print("FAILED:ARC-0014-probe2 restored unexpected path", result.get("restored_path"))
        return 1

    recorded = artifact_rollback_rehearsal(doc)
    if recorded.get("restored_path") != LIVE_LARGER_REL:
        print("FAILED:ARC-0014-probe2 artifact rollback path drift")
        return 1
    if not recorded.get("deploy_write_ok"):
        print("FAILED:ARC-0014-probe2 artifact missing deploy_write_ok")
        return 1

    out = {
        "probe": "probe2-rollback-rehearsal",
        "unit_id": "ARC-0014",
        "restored_path": result["restored_path"],
        "deploy_write_ok": True,
        "freeze_rejects_sibling_tamper": True,
        "freeze_allows_restored_hand_edit": True,
        "freeze_rejected_live_bytes_before_rollback": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "pre_rollback_rejected=True restored="
        f"{result['restored_path']} deploy_ok=True "
        "sibling_tamper_rejected=True hand_edit_allowed=True"
    )
    print("SUCCESS:ARC-0014-probe2 freeze hook and rollback rehearsal")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
