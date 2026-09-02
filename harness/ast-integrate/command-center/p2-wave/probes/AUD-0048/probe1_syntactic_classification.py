#!/usr/bin/env python3
"""Probe 1: syntactic classification of each uses: ref (sha / tag / branch).

Required control: branch-pinned fixture flagged at highest severity; sha-pinned
fixture not flagged. Mention-only strings must not count as uses.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import emit as E  # noqa: E402
from classify import HIGHEST  # noqa: E402
from scan import scan_all  # noqa: E402

ART = REPO / E.OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0048-probe1 {msg}")
    return 1


def main() -> int:
    bundle = scan_all()
    controls = E.evaluate_controls(bundle)
    print(
        json.dumps(
            {
                "live_workflow_count": bundle["live_workflow_count"],
                "live_files": bundle["live_files"],
                "control_pass": controls["pass"],
                "errors": controls["errors"],
                "branch_pin_class": (controls["branch"] or {}).get("pin_class"),
                "branch_severity": (controls["branch"] or {}).get("severity"),
                "sha_pin_class": (controls["sha"] or {}).get("pin_class"),
                "sha_flagged": (controls["sha"] or {}).get("flagged"),
                "tag_pin_class": (controls["tag"] or {}).get("pin_class"),
                "mention_uses": len(controls["mention_uses"]),
                "highest": HIGHEST,
            },
            indent=2,
            sort_keys=True,
        )
    )
    if not controls["pass"]:
        return fail("control did not discriminate: " + "; ".join(controls["errors"]))
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if E.SENTINEL not in text:
        return fail("sentinel absent from artifact")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if not doc.get("controls", {}).get("pass"):
        return fail("artifact control.pass is not true")
    print("SUCCESS:AUD-0048-probe1 syntactic classification; branch=critical sha=silent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
