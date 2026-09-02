#!/usr/bin/env python3
"""Probe 1: both-states control on live A2 registry schema.

A narrowed workflow on_error enum must classify MAJOR.
An added optional plugin field must not.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from calculator import both_states_from_registry_schema  # noqa: E402
from historical import live_registry_schema  # noqa: E402

ART = REPO / "command-center/phase4/contracts/ARC-0092.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:ARC-0092-probe1 contract missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:ARC-0092" not in text:
        print("FAILED:ARC-0092-probe1 sentinel absent")
        return 1
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ARC-0092-probe1 self-declared {st}")
        return 1
    result = both_states_from_registry_schema(live_registry_schema())
    print(
        json.dumps(
            {
                "narrowed_enum_major": result["narrowed_enum_major"],
                "added_optional_not_major": result["added_optional_not_major"],
                "narrowed_bump": result["narrowed_enum_verdict"]["required_bump"],
                "added_bump": result["added_optional_verdict"]["required_bump"],
                "original_enum": result["original_enum"],
                "pass": result["pass"],
            },
            sort_keys=True,
        )
    )
    if not result["pass"]:
        print("FAILED:ARC-0092-probe1 both-states")
        return 1
    print("SUCCESS:ARC-0092-probe1 both-states narrowed-enum-MAJOR added-optional-not-MAJOR")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
