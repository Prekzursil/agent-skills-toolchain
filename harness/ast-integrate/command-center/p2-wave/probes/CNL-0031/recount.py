"""Independent recount: list membership over serialized fact_ids.

Does not call topology.expected_lost or topology.simulate set-difference.
Mechanism is ordered unique via dict.fromkeys plus list membership.
"""
from __future__ import annotations

from typing import Any


def recount(run: dict[str, Any]) -> dict[str, Any]:
    caucus: list[str] = []
    for t in run.get("group_transcripts") or []:
        for fid in t.get("fact_ids") or []:
            caucus.append(str(fid))
    plenary: list[str] = []
    for p in run.get("plenary_payloads") or []:
        for fid in p.get("fact_ids") or []:
            plenary.append(str(fid))
    caucus_unique = list(dict.fromkeys(caucus))
    plenary_unique = list(dict.fromkeys(plenary))
    lost = [fid for fid in caucus_unique if fid not in plenary_unique]
    planted = str(run.get("planted_fact") or "F00")
    group0 = (run.get("group_transcripts") or [{}])[0]
    in_group0 = planted in list(group0.get("fact_ids") or [])
    in_plenary = planted in plenary_unique
    return {
        "caucus_count": len(caucus_unique),
        "plenary_count": len(plenary_unique),
        "lost_ids": lost,
        "lost_count": len(lost),
        "planted_in_group0": in_group0,
        "planted_in_plenary": in_plenary,
        "fragmentation_fires": bool(in_group0 and not in_plenary),
        "mechanism": "dict.fromkeys-then-list-membership",
    }
