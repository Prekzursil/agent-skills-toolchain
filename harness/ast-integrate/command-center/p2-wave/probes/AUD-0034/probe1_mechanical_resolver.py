#!/usr/bin/env python3
"""Probe 1: mechanical namespace resolver + 31 historically colliding pre-fix ids."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import corpus as C  # noqa: E402
import resolver as R  # noqa: E402
from constants import (  # noqa: E402
    CATALOG_SENTINEL,
    CLASS_ONE,
    CLASS_UNDECIDABLE,
    HISTORICAL_COLLISION_IDS,
    NS_MECH,
    NS_OPTION,
    OUTPUT_REL,
    UNIT_ID,
)

ART = REPO / OUTPUT_REL


def payload(doc: dict) -> dict:
    """Domain tables live in extensions on a receipt_core document."""
    ext = doc.get("extensions")
    if isinstance(ext, dict):
        merged = dict(doc)
        merged.update(ext)
        return merged
    return doc


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT_ID}-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if CATALOG_SENTINEL not in text:
        return fail("catalog sentinel absent")
    if doc.get("unit_id") != UNIT_ID:
        return fail(f"unit_id {doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")

    estate = C.materialize()
    hits = R.scan_tree(estate)

    option_ok = 0
    mech_ok = 0
    for token in HISTORICAL_COLLISION_IDS:
        opt = [
            h
            for h in hits
            if h["id"] == token
            and h["role"] == "historical-option"
            and h["classification"] == CLASS_ONE
            and h.get("namespace") == NS_OPTION
            and h.get("adjudicated") is False
        ]
        mech = [
            h
            for h in hits
            if h["id"] == token
            and h["role"] == "historical-mechanism"
            and h["classification"] == CLASS_ONE
            and h.get("namespace") == NS_MECH
            and h.get("adjudicated") is False
        ]
        if not opt:
            return fail(f"pre-fix option miss {token}")
        if not mech:
            return fail(f"pre-fix mechanism miss {token}")
        option_ok += 1
        mech_ok += 1

    if option_ok != 31 or mech_ok != 31:
        return fail(f"historical counts option={option_ok} mech={mech_ok}")

    synth = [h for h in hits if h["id"] == "M-12" and h["role"] == "synthetic"]
    if not synth:
        return fail("synthetic M-12 missing")
    if any(h["classification"] != CLASS_UNDECIDABLE for h in synth):
        return fail("synthetic M-12 was guessed")

    resolved = [h for h in hits if h["classification"] == CLASS_ONE]
    if not resolved:
        return fail("no RESOLVES-ONE hits")
    if any(h.get("adjudicated") for h in resolved):
        return fail("adjudicated RESOLVES-ONE")
    if any(h.get("confidence") != "token-rule" for h in resolved):
        return fail("RESOLVES-ONE not from token-rule")

    mech_prefix = [h for h in resolved if h["id"].startswith("MECH-")]
    if not mech_prefix:
        return fail("no MECH- hits")
    if any(h.get("namespace") != NS_MECH for h in mech_prefix):
        return fail("MECH- resolved outside architecture-mechanisms")

    stored = payload(doc).get("historical_collision_control") or {}
    if not stored.get("pass"):
        return fail("artifact historical_collision_control.pass is false")
    if stored.get("option_count") != 31 or stored.get("mechanism_count") != 31:
        return fail("artifact historical counts drifted")

    print(
        json.dumps(
            {
                "probe": "probe1-mechanical-resolver",
                "unit_id": UNIT_ID,
                "historical_option_ok": option_ok,
                "historical_mechanism_ok": mech_ok,
                "mech_prefix_resolved": len(mech_prefix),
                "resolves_one": len(resolved),
                "synthetic_undecidable": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(f"SUCCESS:{UNIT_ID}-probe1 mechanical resolver and 31 pre-fix collisions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
