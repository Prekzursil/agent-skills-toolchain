#!/usr/bin/env python3
"""Probe 2: static audit + planted bypass + public-mode negative control.

Independent signal (2): AST audit of tools/marketplace finds zero
outbound-publish-capable calls outside pr_only_guard.py. The same auditor
MUST fire on a planted urllib.request.urlopen bypass (detector control)
and go silent after the plant is removed.

Reviewer attempt: reach _outbound_publish from a throwaway module; the
auditor must classify that Call. Under PUBLIC_MARKETPLACE the live path
proceeds, proving the guard is mode-driven rather than a stub.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
MKT = REPO / "tools" / "marketplace"
sys.path.insert(0, str(MKT))

from pr_only_audit import audit_tree, plant_and_detect  # noqa: E402
from pr_only_guard import (  # noqa: E402
    PROCEEDED,
    PUBLISHING_ENTRY_POINTS,
    outbound_log,
    reset_outbound_log,
)
from publishing import invoke, publish  # noqa: E402
from release_mode import BINDING_MODE, PUBLIC_MODE  # noqa: E402

PR_ONLY = MKT / "fixtures" / "release-mode.pr-only.json"
PUBLIC = MKT / "fixtures" / "release-mode.public.json"


def main() -> int:
    clean = audit_tree(MKT)
    print(
        f"audit_clean={clean['clean']} findings={clean['finding_count']} "
        f"scanned={len(clean['scanned'])}"
    )
    if not clean["clean"]:
        print("FAILED:IMP-0112-probe2 live tree has outbound calls outside the guard")
        print(json.dumps(clean["findings"], indent=1)[:2000])
        return 1
    if "publishing.py" not in clean["scanned"] or "pr_only_guard.py" not in clean["scanned"]:
        print("FAILED:IMP-0112-probe2 audit did not scan required modules")
        return 1

    control = plant_and_detect(MKT)
    print(
        f"planted_found={control['planted_found']} "
        f"silent_after_removal={control['silent_after_removal']} "
        f"detector_control_ok={control['detector_control_ok']}"
    )
    if not control["detector_control_ok"]:
        print("FAILED:IMP-0112-probe2 detector control (planted bypass)")
        print(json.dumps(control, indent=1)[:2000])
        return 1

    # Reviewer: call each entry point around "just skip the wrapper name" by
    # using invoke() AND the dedicated function; both must still gate.
    reset_outbound_log()
    pub_blocked = publish("imp0112.reviewer", config_path=str(PR_ONLY))
    if pub_blocked.get("status") != "BLOCKED-NEEDS-OWNER":
        print("FAILED:IMP-0112-probe2 reviewer publish() under PR-ONLY did not block")
        return 1

    reset_outbound_log()
    public_rows = []
    for name in PUBLISHING_ENTRY_POINTS:
        blocked = invoke(name, {"pkg": "imp0112.nc"}, config_path=str(PR_ONLY))
        proceeded = invoke(name, {"pkg": "imp0112.nc"}, config_path=str(PUBLIC))
        ok = (
            blocked.get("status") == "BLOCKED-NEEDS-OWNER"
            and proceeded.get("status") == PROCEEDED
            and proceeded.get("release_mode") == PUBLIC_MODE
            and proceeded.get("outbound", {}).get("sink") == "_outbound_publish"
        )
        public_rows.append({"entry_point": name, "ok": ok})
        print(
            f"both_states {name} blocked={blocked.get('status')} "
            f"public={proceeded.get('status')} ok={ok}"
        )
        if not ok:
            print("FAILED:IMP-0112-probe2 negative control (PUBLIC_MARKETPLACE)")
            return 1
    if len(outbound_log()) != len(PUBLISHING_ENTRY_POINTS):
        print("FAILED:IMP-0112-probe2 public-mode sink log length")
        return 1

    print(
        json.dumps(
            {
                "probe": "probe2-audit-bypass-public-mode",
                "unit_id": "IMP-0112",
                "audit_clean": True,
                "planted_bypass_detected": True,
                "silent_after_removal": True,
                "public_mode_proceeds": True,
                "binding_mode": BINDING_MODE,
                "public_mode": PUBLIC_MODE,
                "reviewer_pr_only_blocked": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:IMP-0112-probe2 audit planted-bypass public-mode reviewer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
