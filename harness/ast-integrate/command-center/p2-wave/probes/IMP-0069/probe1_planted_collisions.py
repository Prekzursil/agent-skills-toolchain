#!/usr/bin/env python3
"""IMP-0069 probe 1: validator rejects each planted collision class.

Signal 1 of the catalog evidence requirement. Negative control: the real
existing name agent-skills-toolchain is accepted.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.name_grammar import validate_name  # noqa: E402

PLANTED_PATH = REPO / "tools/marketplace/fixtures/planted_collisions.json"
RECEIPT = REPO / "command-center/receipts/IMP-0069.json"
REAL = "agent-skills-toolchain"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0069-probe1 {msg}")
    return 1


def main() -> int:
    planted = json.loads(PLANTED_PATH.read_text(encoding="utf-8"))
    existing = planted["existing"]
    rejected: dict[str, list[str]] = {
        "reserved": [],
        "casefold_collision": [],
        "confusable_collision": [],
        "grammar": [],
    }

    for name in planted["valid"]:
        v = validate_name(name, existing)
        if not v.accepted:
            return fail(f"valid-rejected {name} {v.code}")

    for name in planted["reserved"]:
        v = validate_name(name, existing)
        if v.accepted or v.code != "reserved":
            return fail(f"reserved {name} -> {v.code}")
        rejected["reserved"].append(name)

    for row in planted["casefold"]:
        v = validate_name(row["name"], existing)
        if v.accepted or v.code != "casefold_collision":
            return fail(f"casefold {row} -> {v.code}")
        if v.collides_with != row["collides_with"]:
            return fail(f"casefold-target {v.collides_with}")
        rejected["casefold_collision"].append(row["name"])

    cyr = planted["confusable"][0]
    if "\u0430" not in cyr["name"]:
        return fail("planted confusable missing Cyrillic U+0430")
    v = validate_name(cyr["name"], existing)
    if v.accepted or v.code != "confusable_collision":
        return fail(f"confusable {cyr['name']!r} -> {v.code}")
    if v.collides_with != REAL:
        return fail(f"confusable target {v.collides_with}")
    rejected["confusable_collision"].append(cyr["name"])

    for name in planted["punctuation"]:
        v = validate_name(name, existing)
        if v.accepted or v.code != "grammar":
            return fail(f"punct {name!r} -> {v.code}")
        rejected["grammar"].append(name)

    neg = validate_name(REAL, existing)
    if not neg.accepted:
        return fail(f"negative-control {REAL} rejected code={neg.code}")

    if not RECEIPT.is_file() or RECEIPT.stat().st_size <= 0:
        return fail("receipt missing")
    text = RECEIPT.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"receipt state {doc.get('state')}")
    if "SUCCESS:IMP-0069" not in text:
        return fail("sentinel-absent")

    out = {
        "probe": "probe1-planted-collisions",
        "unit_id": "IMP-0069",
        "rejected_counts": {k: len(v) for k, v in rejected.items()},
        "negative_control_accepted": True,
        "cyrillic_a_collides": True,
        "pass": True,
    }
    print(json.dumps(out, ensure_ascii=False))
    print(
        "reserved={reserved} casefold={casefold_collision} "
        "confusable={confusable_collision} grammar={grammar}".format(**out["rejected_counts"])
    )
    print("SUCCESS:IMP-0069-probe1 planted collision classes rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
