"""Provenance: holdout tokens must not appear in implementation-unit inputs."""
from __future__ import annotations

import json
from pathlib import Path

import contract as C
from corpus import build_corpus

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def _walk_strings(obj) -> list[str]:
    out: list[str] = []
    if obj is None:
        return out
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, (int, float, bool)):
        out.append(str(obj))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str):
                out.append(k)
            out.extend(_walk_strings(v))
    elif isinstance(obj, list):
        for item in obj:
            out.extend(_walk_strings(item))
    else:
        out.append(str(obj))
    return out


def _is_implementation_unit(unit: dict) -> bool:
    uid = str(unit.get("id") or "")
    if uid.startswith("IMP-"):
        return True
    role = unit.get("assigned_model_vendor_role") or {}
    if isinstance(role, dict) and str(role.get("role") or "").lower() == "implementer":
        return True
    return False


def holdout_needles(corpus: dict | None = None) -> list[str]:
    corpus = corpus or build_corpus()
    needles = [C.HOLDOUT_PREFIX_FILE]
    for case in corpus["holdout"]:
        needles.append(case["id"])
        needles.append(case["payload_sha256"])
    return needles


def scan_inputs(inputs, needles: list[str]) -> list[str]:
    hay = "\n".join(_walk_strings(inputs))
    return [n for n in needles if n and n in hay]


def scan_catalog(corpus: dict | None = None) -> dict:
    corpus = corpus or build_corpus()
    needles = holdout_needles(corpus)
    catalog_path = REPO / C.CATALOG_REL
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    units = data.get("work_units") or data.get("items") or []
    impl = []
    leaks = []
    other_leaks = []
    for unit in units:
        if not isinstance(unit, dict):
            continue
        uid = str(unit.get("id") or "")
        hits = scan_inputs(unit.get("inputs"), needles)
        rec = {
            "unit_id": uid,
            "hits": hits,
            "n_inputs": len(unit.get("inputs") or [])
            if isinstance(unit.get("inputs"), list)
            else 0,
        }
        if _is_implementation_unit(unit):
            impl.append(rec)
            if hits:
                leaks.append(rec)
        elif hits:
            other_leaks.append(rec)
    planted_inputs = ["IMP-9999 synthetic", needles[1] if len(needles) > 1 else needles[0]]
    planted_hits = scan_inputs(planted_inputs, needles)
    return {
        "catalog": C.CATALOG_REL,
        "needles": needles,
        "holdout_ids": [c["id"] for c in corpus["holdout"]],
        "implementation_units_scanned": len(impl),
        "total_units_scanned": len(units),
        "leak_count": len(leaks),
        "leaks": leaks,
        "non_implementation_leaks": other_leaks,
        "planted_control": {
            "inputs": planted_inputs,
            "hits": planted_hits,
            "fired": bool(planted_hits),
        },
        "planted_control_fired": bool(planted_hits),
        "clean": len(leaks) == 0 and len(other_leaks) == 0,
    }
