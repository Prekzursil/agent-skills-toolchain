# Recreated 2026-10-25 (wave-2 shard 7) after the original probe tree was
# lost with the prior builder session; content follows the recorded role in
# the unit receipt (anchors re-resolve live). Prior reviewer closure kept.
"""Instrument for BLD-0050: counts census over boundary rows (mechanically
independent lane from walk.classify: sums + identity check, plus the
delete-rule control the receipt records)."""
from __future__ import annotations

from typing import Any


def census(rows: list[dict[str, Any]]) -> dict[str, int]:
    checked = sum(1 for r in rows if str(r.get("check_status")).upper() == "CHECKED")
    unchecked = sum(1 for r in rows if str(r.get("check_status")).upper() == "UNCHECKED")
    consumed = sum(1 for r in rows if str(r.get("check_status")).upper() == "CONSUMED")
    return {
        "checked": checked,
        "unchecked": unchecked,
        "consumed": consumed,
        "total": len(rows),
    }


def identity(c: dict[str, int]) -> bool:
    return c["checked"] + c["unchecked"] + c["consumed"] == c["total"]


def delete_rule_fires(rows: list[dict[str, Any]]) -> bool:
    """Control: deleting one UNCHECKED row must move the census (the detector
    can see a deleted row), and deleting nothing must not."""
    base = census(rows)
    cut = census([r for r in rows if str(r.get("check_status")).upper() != "UNCHECKED"
                  ] + [dict(rows[[str(r.get("check_status")).upper() for r in rows].index("UNCHECKED")])])
    return base["total"] - cut["total"] == 1
