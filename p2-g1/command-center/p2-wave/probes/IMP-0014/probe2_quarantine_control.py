#!/usr/bin/env python3
"""Probe 2: quarantine negative control (fail before xattr, succeed after)."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ADAPTER_DIR = REPO / "release" / "platforms" / "macos"
sys.path.insert(0, str(ADAPTER_DIR))

import launch_adapter as A  # noqa: E402

ART = REPO / "command-center" / "receipts" / "IMP-0014.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0014-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("receipt missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:IMP-0014" not in json.dumps(doc):
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")

    with tempfile.TemporaryDirectory(prefix="imp0014-p2-") as tmp:
        nc = A.quarantine_both_states(Path(tmp))
    if not nc.get("pass"):
        print(json.dumps(nc, sort_keys=True, default=str)[:3000])
        return fail("quarantine both-states control did not pass")
    if not nc["before"].get("raised"):
        return fail("quarantined fixture launched before xattr")
    if nc["before"].get("code") != A.QUARANTINE_BLOCKED:
        return fail(f"before code {nc['before'].get('code')}")
    if nc["after"]["stdout"] != "LAUNCHED":
        return fail("post-xattr fixture did not print LAUNCHED")
    if nc["after"]["quarantined_after_clear"]:
        return fail("quarantine bit still set after clear")
    if not nc.get("clean_not_blocked"):
        return fail("clean fixture was blocked")

    missing = A.missing_tool_control()
    if not missing.get("pass"):
        print(json.dumps(missing, sort_keys=True))
        return fail("missing-tool control did not fire named error")
    if not missing.get("not_traceback"):
        return fail("missing-tool error looks like a traceback")

    controls = doc.get("negative_controls") or []
    fired = [
        c
        for c in controls
        if isinstance(c, dict)
        and c.get("fired_on_bad") is True
        and c.get("silent_on_good") is True
    ]
    if not fired:
        return fail("receipt negative_controls missing both-states row")

    print(
        json.dumps(
            {
                "pass": True,
                "probe": "probe2-quarantine-control",
                "unit_id": "IMP-0014",
                "before_blocked": True,
                "after_launched": True,
                "clean_not_blocked": True,
                "missing_tool_named": missing["code"],
                "backend": nc.get("backend"),
            },
            sort_keys=True,
        )
    )
    print(
        "pre_xattr_blocked=True post_xattr_launched=True "
        "clean_ok=True missing_tool=TOOL_NOT_FOUND"
    )
    print("SUCCESS:IMP-0014-probe2 quarantine negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
