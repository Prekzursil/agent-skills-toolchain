#!/usr/bin/env python3
"""Probe 1: two-rail quotes in captured bytes, exclusive hardness needles."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from lib import (  # noqa: E402
    ARTIFACT,
    MIN_BYTES,
    NOT_DELIVERING,
    SENTINEL,
    UID,
    grade_claim,
    hardness_scan,
    load_harvest_index,
)


def fail(msg: str) -> int:
    print(f"FAILED:RES-0176-probe1 {msg}")
    return 1


def main() -> int:
    if not ARTIFACT.is_file():
        return fail("artifact-absent")
    raw = ARTIFACT.read_bytes().replace(b"\r\n", b"\n")
    if len(raw) < MIN_BYTES:
        return fail("artifact-too-small")
    text = raw.decode("utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable:{exc}")
    if not isinstance(doc, dict):
        return fail("not-object")
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        return fail(f"self-declared:{st}")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    if doc.get("unit_id") != UID:
        return fail("unit-id")
    if str(doc.get("report_kind") or "") != "ecosystem-teardown":
        return fail("report-kind")
    claims = [c for c in (doc.get("claims") or []) if isinstance(c, dict)]
    if len(claims) < 3:
        return fail("too-few-claims")
    idx = load_harvest_index()
    for c in claims:
        g = grade_claim(c, idx)
        print(
            f"claim {c.get('claim_id')} rails={g['ok_rails']} "
            f"kinds={g['rail_kinds']} tier={g['tier']} "
            f"citable={g['citable_as_measured_fact']} problems={g['problems']}"
        )
        if not g["citable_as_measured_fact"] or g["ok_rails"] < 2:
            return fail(f"claim-not-e2:{c.get('claim_id')}")
        if len(str(c.get("quoted_mechanism") or "")) < 16:
            return fail(f"empty-mechanism-quote:{c.get('claim_id')}")

    hard = hardness_scan()
    for row in hard["rows"]:
        print(
            f"hardness {row['abstraction']} owner={row['owner']} "
            f"exclusive={row['exclusive']} leaked={row['present_in_others']}"
        )
        if not row["exclusive"]:
            return fail(f"hardness-not-exclusive:{row['abstraction']}")
    if not hard["all_exclusive"]:
        return fail("hardness-scan-failed")

    nc = doc.get("negative_control") or {}
    if nc.get("transferable") is not False:
        return fail("negative-control-not-false")
    if "GroupChatManager" not in str(nc.get("runtime_service") or ""):
        return fail("negative-control-runtime-unnamed")

    print(
        f"claims={len(claims)} hardness_exclusive=True "
        f"negative_control={nc.get('abstraction')} completion_sentinel=True"
    )
    print(
        "SUCCESS:RES-0176-probe1 two-rail quotes, exclusive hardness, "
        "named non-transferable runtime"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
