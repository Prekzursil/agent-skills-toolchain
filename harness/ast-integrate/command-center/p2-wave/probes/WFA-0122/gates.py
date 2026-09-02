"""Per-hop gates. A surviving mutant at any hop is a P1 hole.

Each gate inspects THAT hop's output carry fields only (not notes, not
side-channel lists). Losing the primary provenance_anchor or licence_class
fires the named gate for that hop.
"""
from __future__ import annotations

from typing import Any

from carry import ANCHOR_KEY, LICENCE_KEY, field_lost, gate_id_for


def inspect(hop: str, artifact: dict[str, Any]) -> dict[str, Any]:
    lost_fields: list[str] = []
    if field_lost(artifact, ANCHOR_KEY):
        lost_fields.append(ANCHOR_KEY)
    if field_lost(artifact, LICENCE_KEY):
        lost_fields.append(LICENCE_KEY)
    fired = bool(lost_fields)
    gid = gate_id_for(hop)
    if fired:
        reason = (
            f"{gid} fired at hop {hop}: lost {lost_fields} "
            "(empty-string treated as missing)"
        )
    else:
        reason = f"{gid} silent: provenance_anchor and licence_class present"
    return {
        "gate_id": gid,
        "hop": hop,
        "fired": fired,
        "lost_fields": lost_fields,
        "reason": reason,
    }
