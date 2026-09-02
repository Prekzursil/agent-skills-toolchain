#!/usr/bin/env python3
"""Probe 1: git rev-list -n 1 <tag> — never the caret form.

Recomputes tag dereference live. A planted tag with no release must still
resolve to a commit. Does not trust the artifact without a live re-run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from inventory import (  # noqa: E402
    CARET_FORBIDDEN,
    ORPHAN_TAG,
    PUBLISHED_TAG,
    assert_control,
    build,
    probe1_payload,
)

ART = REPO / "command-center/audit/AUD-0005-tag-release-parity.json"
SENTINEL = "SUCCESS:AUD-0005"


def main() -> int:
    cen = build()
    payload = probe1_payload(cen)
    print(json.dumps(payload, sort_keys=True))
    assert_control(cen)
    if payload["caret_form_used"] or any(
        CARET_FORBIDDEN in r["command"] for r in cen["p1"]
    ):
        print("FAILED:AUD-0005-probe1 caret deref form was used")
        return 1
    orphan = next(r for r in payload["tags"] if r["tag"] == ORPHAN_TAG)
    pub = next(r for r in payload["tags"] if r["tag"] == PUBLISHED_TAG)
    if orphan["probe1_verdict"] != "LIVE":
        print("FAILED:AUD-0005-probe1 orphan tag did not deref")
        return 1
    if pub["probe1_verdict"] != "LIVE":
        print("FAILED:AUD-0005-probe1 published tag did not deref")
        return 1
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:AUD-0005-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:AUD-0005-probe1 self-declared {doc.get('state')}")
        return 1
    if SENTINEL not in text:
        print("FAILED:AUD-0005-probe1 sentinel absent")
        return 1
    art_ctl = doc.get("planted_control") or {}
    if art_ctl.get("probe1_verdict") != "LIVE":
        print("FAILED:AUD-0005-probe1 artifact control probe1 not LIVE")
        return 1
    if art_ctl.get("independent") is not True:
        print("FAILED:AUD-0005-probe1 artifact control not independent")
        return 1
    by_id = {i["id"]: i for i in doc.get("items") or []}
    row = by_id.get(f"tag:{ORPHAN_TAG}")
    if not row or row.get("probe1_verdict") != "LIVE":
        print("FAILED:AUD-0005-probe1 artifact orphan item not LIVE on probe1")
        return 1
    print("SUCCESS:AUD-0005-probe1 rev-list deref matches artifact; caret unused")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
