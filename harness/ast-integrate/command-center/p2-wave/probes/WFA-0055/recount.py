#!/usr/bin/env python3
"""Independent recount of dropped fields and P1 safety ids.

Signal B for declared-vs-measured: walk native keys and test carry targets
against a frozenset of IR names without calling projector.roundtrip.
Signal B for safety: P1 ids derived only from safety_class, not severity.
"""
from __future__ import annotations

from corpus import CARRY, IR_FIELDS, native_doc
from ledger import SAFETY


def dropped_fields(adapter_id: str, fields: dict | None = None) -> list[str]:
    src = dict(fields if fields is not None else native_doc(adapter_id)["fields"])
    carry_pairs = tuple((k, v) for k, v in (CARRY.get(adapter_id) or {}).items())
    ir_ok = frozenset(IR_FIELDS)
    dropped: list[str] = []
    for name in src:
        target = None
        for ck, cv in carry_pairs:
            if ck == name:
                target = cv
                break
        if target not in ir_ok:
            dropped.append(name)
    return sorted(dropped)


def measured_by_adapter(natives: dict[str, dict] | None = None) -> dict[str, set[str]]:
    from corpus import ADAPTER_IDS

    out: dict[str, set[str]] = {}
    if natives is None:
        for uid in ADAPTER_IDS:
            out[uid] = set(dropped_fields(uid))
        return out
    for uid, doc in natives.items():
        fields = doc["fields"] if isinstance(doc, dict) and "fields" in doc else doc
        out[uid] = set(dropped_fields(uid, fields))
    return out


def p1_ids_from_safety(rows: list[dict]) -> list[str]:
    ids: list[str] = []
    for row in rows:
        if row.get("safety_class") in SAFETY:
            ids.append(str(row.get("loss_id")))
    return sorted(ids)


def p1_ids_from_severity(rows: list[dict]) -> list[str]:
    return sorted(
        str(r.get("loss_id")) for r in rows if r.get("severity") == "P1"
    )
