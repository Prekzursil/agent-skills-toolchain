#!/usr/bin/env python3
"""Native-to-IR-to-native projector.

Does not read the declared ledger. A native field survives iff CARRY names an
IR_FIELDS target. Dropped names are the measured differing-field set.
"""
from __future__ import annotations

from typing import Any

from corpus import CARRY, IR_FIELDS, native_doc


def carry_for(adapter_id: str) -> dict[str, str]:
    return dict(CARRY.get(adapter_id) or {})


def project_fields(
    adapter_id: str, fields: dict[str, Any]
) -> tuple[dict[str, Any], list[str], list[str]]:
    carry = carry_for(adapter_id)
    ir: dict[str, Any] = {}
    dropped: list[str] = []
    preserved: list[str] = []
    for name, value in fields.items():
        target = carry.get(name)
        if isinstance(target, str) and target in IR_FIELDS:
            ir[target] = value
            preserved.append(name)
        else:
            dropped.append(name)
    return ir, dropped, preserved


def rerender_native(ir: dict[str, Any], adapter_id: str) -> dict[str, Any]:
    """Rebuild a native field dict from IR keys only (inverse of carry)."""
    carry = carry_for(adapter_id)
    inverse: dict[str, str] = {}
    for native_name, ir_name in carry.items():
        if ir_name in IR_FIELDS and ir_name not in inverse:
            inverse[ir_name] = native_name
    out: dict[str, Any] = {}
    for ir_name, value in ir.items():
        native_name = inverse.get(ir_name)
        if native_name:
            out[native_name] = value
    return out


def roundtrip(adapter_id: str, fields: dict[str, Any] | None = None) -> dict:
    src = dict(fields if fields is not None else native_doc(adapter_id)["fields"])
    ir, dropped, preserved = project_fields(adapter_id, src)
    rerendered = rerender_native(ir, adapter_id)
    differing = sorted(set(src) - set(rerendered))
    if set(differing) != set(dropped):
        # Projector invariant: drop set == native-minus-rerender.
        differing = sorted(set(differing) | set(dropped))
    return {
        "adapter_id": adapter_id,
        "preserved": sorted(preserved),
        "dropped": sorted(dropped),
        "differing_fields": differing,
        "ir_keys": sorted(ir.keys()),
        "rerendered_keys": sorted(rerendered.keys()),
    }


def measure_all(
    natives: dict[str, dict] | None = None,
) -> dict[str, list[str]]:
    """Return adapter_id -> sorted measured loss field names."""
    out: dict[str, list[str]] = {}
    if natives is None:
        from corpus import ADAPTER_IDS

        for uid in ADAPTER_IDS:
            out[uid] = roundtrip(uid)["differing_fields"]
        return out
    for uid, doc in natives.items():
        fields = doc["fields"] if "fields" in doc else doc
        out[uid] = roundtrip(uid, fields)["differing_fields"]
    return out
