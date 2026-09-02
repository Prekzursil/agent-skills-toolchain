#!/usr/bin/env python3
"""Named probe 1: renderer controls (delete receipt, fail survives, all-pass vs mixed)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from renderer import renderer_controls  # noqa: E402

ART = REPO / "command-center/receipts/REL-0015.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 2048:
        print("FAILED:REL-0015-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:REL-0015" not in json.dumps(doc):
        print("FAILED:REL-0015-probe1 sentinel absent")
        return 1
    html = (doc.get("published_table") or {}).get("html") or ""
    md = (doc.get("published_table") or {}).get("markdown") or ""
    css = (doc.get("published_table") or {}).get("css_classes") or {}
    if css.get("pass") == css.get("not_checked"):
        print("FAILED:REL-0015-probe1 PASS and NOT-CHECKED share a CSS class")
        return 1
    if "NOT-CHECKED" not in html or "NOT-CHECKED" not in md:
        print("FAILED:REL-0015-probe1 published table lacks NOT-CHECKED token")
        return 1
    if css.get("not_checked") not in html:
        print("FAILED:REL-0015-probe1 hatched NOT-CHECKED class absent from HTML")
        return 1

    ctrl = renderer_controls()
    print(json.dumps({k: v for k, v in ctrl.items() if k != "pass"}, indent=2, default=str)[:2000])
    if not ctrl.get("pass"):
        print("FAILED:REL-0015-probe1 renderer controls")
        return 1
    if not ctrl.get("delete_receipt_shows_not_checked"):
        print("FAILED:REL-0015-probe1 delete-receipt did not render NOT-CHECKED")
        return 1
    if not ctrl.get("fail_survives"):
        print("FAILED:REL-0015-probe1 FAIL cell dropped")
        return 1
    if not ctrl.get("all_pass_differs_from_mixed"):
        print("FAILED:REL-0015-probe1 renderer ignored its input (all-pass == mixed)")
        return 1
    print("SUCCESS:REL-0015-probe1 renderer controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
