#!/usr/bin/env python3
"""Probe 2: GitHub-shaped releases API + asset byte-size check.

A release row with zero assets, or assets whose fetched body is zero
bytes, is not published. The planted tag with no release must be DEAD.
Independent of probe 1 (HTTP + bytes, not git).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from inventory import (  # noqa: E402
    ORPHAN_TAG,
    PUBLISHED_TAG,
    ZERO_ASSET_TAG,
    ZERO_BYTE_TAG,
    assert_control,
    build,
    probe2_payload,
)

ART = REPO / "command-center/audit/AUD-0005-tag-release-parity.json"
SENTINEL = "SUCCESS:AUD-0005"


def main() -> int:
    cen = build()
    payload = probe2_payload(cen)
    print(json.dumps(payload, sort_keys=True))
    assert_control(cen)
    by_tag = {r["tag"]: r for r in payload["tags"]}
    if by_tag[ORPHAN_TAG]["probe2_verdict"] != "DEAD":
        print("FAILED:AUD-0005-probe2 absence treated as parity")
        return 1
    if by_tag[PUBLISHED_TAG]["probe2_verdict"] != "LIVE":
        print("FAILED:AUD-0005-probe2 published tag not LIVE")
        return 1
    if by_tag[ZERO_ASSET_TAG]["probe2_verdict"] != "DEAD":
        print("FAILED:AUD-0005-probe2 zero-asset release counted as published")
        return 1
    if by_tag[ZERO_BYTE_TAG]["probe2_verdict"] != "DEAD":
        print("FAILED:AUD-0005-probe2 zero-byte asset counted as published")
        return 1
    if by_tag[PUBLISHED_TAG]["fetched_bytes_total"] <= 0:
        print("FAILED:AUD-0005-probe2 published asset bytes not fetched")
        return 1
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:AUD-0005-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:AUD-0005-probe2 self-declared {doc.get('state')}")
        return 1
    if SENTINEL not in text:
        print("FAILED:AUD-0005-probe2 sentinel absent")
        return 1
    art_ctl = doc.get("planted_control") or {}
    if art_ctl.get("probe2_verdict") != "DEAD":
        print("FAILED:AUD-0005-probe2 artifact control probe2 not DEAD")
        return 1
    by_id = {i["id"]: i for i in doc.get("items") or []}
    row = by_id.get(f"tag:{ORPHAN_TAG}")
    if not row or row.get("probe2_verdict") != "DEAD":
        print("FAILED:AUD-0005-probe2 artifact orphan item not DEAD")
        return 1
    pub = by_id.get(f"tag:{PUBLISHED_TAG}")
    if not pub or pub.get("probe2_verdict") != "LIVE":
        print("FAILED:AUD-0005-probe2 artifact published item not LIVE")
        return 1
    print(
        "SUCCESS:AUD-0005-probe2 release+bytes match artifact; "
        "orphan and zero-asset are unpublished"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
