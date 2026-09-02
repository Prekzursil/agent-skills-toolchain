"""Council-of-councils topology: nested and flat fan-in share reducer.FANIN."""
from __future__ import annotations

from typing import Any

from reducer import FANIN, reduce_completion, reduce_many

# Identity the structural probe asserts: one object, two call sites.
assert FANIN is reduce_many
FLAT_FANIN = FANIN
NESTED_FANIN = FANIN


def run_flat(receipts: list[dict[str, Any]], source_ids: list[str]) -> dict[str, Any]:
    return FLAT_FANIN(receipts, site="flat", source_ids=source_ids)


def run_subcouncil(sub: dict[str, Any]) -> dict[str, Any]:
    members = list(sub["members"])
    ids = [str(m.get("source_id") or m.get("id")) for m in members]
    inner = NESTED_FANIN(members, site=f"subcouncil:{sub['id']}", source_ids=ids)
    inner["subcouncil_id"] = sub["id"]
    return inner


def run_nested(subcouncils: list[dict[str, Any]]) -> dict[str, Any]:
    """Depth-2: each subcouncil fans in members, parent fans in subcouncil receipts."""
    child_verdicts = []
    child_receipts = []
    child_ids = []
    for sub in subcouncils:
        inner = run_subcouncil(sub)
        child_verdicts.append(inner)
        rec = dict(inner["as_receipt"])
        rec["source_id"] = sub["id"]
        rec["id"] = sub["id"]
        child_receipts.append(rec)
        child_ids.append(sub["id"])
    parent = NESTED_FANIN(child_receipts, site="parent", source_ids=child_ids)
    parent["subcouncil_verdicts"] = child_verdicts
    parent["child_receipts"] = child_receipts
    parent["depth"] = 2
    parent["fanin_object_id"] = id(NESTED_FANIN)
    parent["reduce_completion_id"] = id(reduce_completion)
    return parent
