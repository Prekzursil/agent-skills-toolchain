#!/usr/bin/env python3
"""Named probe 2 (ARC-0007): content-preservation union + negative overwrite control.

Different field from probe 1: unique-line union membership and the
REFUSE-ONE-DIRECTIONAL-OVERWRITE boolean, not git committer ISO / mtime.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import procedure as P  # noqa: E402

ART = REPO / "command-center/phase3/A1/MIGRATION.json"
LEDGER = HERE / "fixtures/repo-committer-ledger.json"
REPO_ROOT = HERE / "fixtures/repo"
LIVE_ROOT = HERE / "fixtures/live"
NEG_LINE = "LIVE-ONLY-LINE:synthetic-ARC-0007-negcontrol"


def main() -> int:
    doc = json.loads(ART.read_text(encoding="utf-8"))
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    failed = []
    preserved = 0
    for row in doc.get("sample") or []:
        rel = row["path"]
        rec = P.measure_file(rel, REPO_ROOT, LIVE_ROOT, ledger, None)
        repo_text = P.read_if(REPO_ROOT / rel)
        live_text = P.read_if(LIVE_ROOT / rel)
        result = P.apply_merge(repo_text, live_text)
        ok = result.migrated is not None and P.unique_lines_preserved(
            repo_text, live_text, result.migrated
        )
        if not ok or not rec.unique_lines_preserved:
            failed.append(rel)
        else:
            preserved += 1
    neg = P.negative_control_refuse_overwrite(NEG_LINE)
    if not neg["pass"] or not neg["refused"]:
        print("FAILED:ARC-0007-probe2 negative control did not refuse")
        print(json.dumps(neg, indent=2))
        return 1
    if failed or preserved != 10:
        print(f"FAILED:ARC-0007-probe2 preservation failed={failed} preserved={preserved}")
        return 1
    snap = HERE / "fixtures/rollback-snapshot"
    dest = HERE / "fixtures/rollback-restore-probe"
    P.restore_tree(snap, dest)
    restored = sorted(P.walk_rel(dest))
    snap_rels = sorted(P.walk_rel(snap))
    if restored != snap_rels or not restored:
        print("FAILED:ARC-0007-probe2 rollback restore mismatch")
        return 1
    out = {
        "probe": "probe2-preservation-and-negative-control",
        "unit_id": "ARC-0007",
        "files_checked": preserved,
        "files_failed": failed,
        "negative_control_refused": True,
        "negative_control_live_unique_line": NEG_LINE,
        "rollback_restore_files": len(restored),
        "pass": True,
    }
    (HERE / "probe2-preservation.raw.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:ARC-0007-probe2 preservation and refuse-overwrite")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
