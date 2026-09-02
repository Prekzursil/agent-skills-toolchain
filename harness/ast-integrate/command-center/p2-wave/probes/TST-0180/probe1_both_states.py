#!/usr/bin/env python3
"""Probe 1: both-states — distinct case-folded keys ACCEPT; colliding keys REJECT."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from plugin.case_collision import (  # noqa: E402
    independent_signal,
    iter_document_keysets,
    validate_document,
)

CLEAN = (HERE / "fixtures" / "clean_plugin.json").read_text(encoding="utf-8")
MARKET = (HERE / "fixtures" / "clean_marketplace.json").read_text(encoding="utf-8")
COLLIDE = (HERE / "fixtures" / "collision_top.json").read_text(encoding="utf-8")
NESTED = (HERE / "fixtures" / "collision_nested.json").read_text(encoding="utf-8")


def pack(label: str, text: str) -> dict:
    result = validate_document(text)
    sig = independent_signal(iter_document_keysets(text))
    return {
        "label": label,
        "accepted": result.accepted,
        "reason": result.reason,
        "verdict": "ACCEPT" if result.accepted else "REJECT",
        "independent_signal": sig,
        "same_code_path": "plugin.case_collision.validate_document",
    }


def main() -> int:
    clean = pack("clean-plugin", CLEAN)
    market = pack("clean-marketplace", MARKET)
    collide = pack("collision-top", COLLIDE)
    nested = pack("collision-nested", NESTED)
    ok = (
        clean["accepted"] is True
        and market["accepted"] is True
        and collide["accepted"] is False
        and nested["accepted"] is False
        and not clean["independent_signal"]["sizes_differ"]
        and collide["independent_signal"]["sizes_differ"] is True
        and collide["independent_signal"]["worst_raw_keyset_size"]
        > collide["independent_signal"]["worst_casefolded_keyset_size"]
        and "case-collision" in collide["reason"]
        and "Name" in collide["reason"]
        and "name" in collide["reason"]
    )
    payload = {
        "pass": bool(ok),
        "probe": "probe1-both-states",
        "unit_id": "TST-0180",
        "clean": clean,
        "marketplace": market,
        "collision": collide,
        "nested": nested,
        "verdicts_differ": clean["verdict"] != collide["verdict"],
        "same_code_path": "plugin.case_collision.validate_document",
    }
    print(json.dumps(payload, sort_keys=True))
    if not ok:
        print(
            "FAILED:TST-0180-probe1 both-states distinct keys must ACCEPT "
            "and collisions REJECT"
        )
        return 1
    print(
        "SUCCESS:TST-0180-probe1 both-states ACCEPT distinct casefolded keys "
        "vs REJECT Name/name collision"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
