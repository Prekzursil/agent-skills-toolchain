#!/usr/bin/env python3
"""Named probe 2: secret gate on snapshot is clean; planted control fires.

Same run: snapshot of a tree that holds a synthetic credential in a
touched path has zero gate findings; the planted file itself is flagged;
a naive copy-all of the touch set is flagged. Exclusion is reported, not
silent. The secret body never appears in the snapshot or the report.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from plugin.backup import snapshot, verify_snapshot_permissions  # noqa: E402
from plugin.projection import expand_touch_paths, load_projection  # noqa: E402
from plugin.secret_gate import (  # noqa: E402
    findings_leak_body,
    report_dict,
    scan_file,
    scan_tree,
)
from scenario import PLANTED_BODY, PLANTED_REL, build_live_tree  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0030-p2-") as tmp:
        tmp_p = Path(tmp)
        live = build_live_tree(tmp_p / "live", plant_secret=True)
        projection = load_projection(live / "projection.json")
        touch = expand_touch_paths(live, projection)
        planted = live / PLANTED_REL
        snap = snapshot(live, tmp_p / "store", projection, keep=3, op="probe2")
        tree = snap.snapshot_dir / "tree"
        snap_findings = scan_tree(tree)
        control_findings = scan_file(planted, rel=PLANTED_REL)
        naive = tmp_p / "naive"
        for rel in touch:
            src = live / rel
            if src.is_file():
                dest = naive / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
        naive_findings = scan_tree(naive)
        perms = verify_snapshot_permissions(snap.snapshot_dir)
        body = PLANTED_BODY.encode("ascii")
        leaked_meta = body in (snap.snapshot_dir / "MANIFEST.json").read_bytes()
        leaked_tree = any(
            p.is_file() and body in p.read_bytes() for p in tree.rglob("*")
        )
        leaked_report = findings_leak_body(control_findings, PLANTED_BODY)
        copied = (tree / PLANTED_REL).exists()
        reported = PLANTED_REL in (snap.manifest.get("excluded_paths") or [])
        ok = (
            PLANTED_REL in touch
            and not copied
            and reported
            and not snap_findings
            and len(control_findings) >= 1
            and len(naive_findings) >= 1
            and not leaked_meta
            and not leaked_tree
            and not leaked_report
            and perms["owner_only"]
            and PLANTED_BODY not in json.dumps(report_dict(control_findings))
        )
        payload = {
            "probe": "probe2-secret-gate",
            "unit_id": "IMP-0030",
            "planted_in_touch_set": PLANTED_REL in touch,
            "copied_into_snapshot": copied,
            "exclusion_reported": reported,
            "snapshot_findings": len(snap_findings),
            "control_findings": len(control_findings),
            "naive_copy_findings": len(naive_findings),
            "body_absent_from_snapshot": not leaked_meta and not leaked_tree,
            "body_absent_from_report": not leaked_report,
            "owner_only": perms["owner_only"],
            "pass": ok,
        }
        print(json.dumps(payload, sort_keys=True))
        print(
            f"snap_findings={len(snap_findings)} control_findings={len(control_findings)} "
            f"naive_findings={len(naive_findings)} reported={reported} copied={copied}"
        )
        if not ok:
            print("FAILED:IMP-0030-probe2 secret exclusion")
            return 1
        print("SUCCESS:IMP-0030-probe2 snapshot excludes secrets and reports absence")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
