"""Declared permission catalog extraction."""
from __future__ import annotations

from typing import Any

EMPTY_SURFACE_LINE = "no permissions declared"


def _items(pkg: dict[str, Any]) -> list[dict[str, Any]]:
    raw = pkg.get("permissions")
    if raw is None:
        return []
    if isinstance(raw, list):
        out: list[dict[str, Any]] = []
        for item in raw:
            if isinstance(item, str):
                out.append({"id": item, "risk": "low", "enforcement": "gated"})
            elif isinstance(item, dict) and item.get("id"):
                rec = dict(item)
                rec.setdefault("risk", "low")
                rec.setdefault("enforcement", rec.get("enforcement") or rec.get("hook") or "gated")
                out.append(rec)
        return out
    if isinstance(raw, dict):
        out = []
        for key, val in raw.items():
            rec = {"id": key, "risk": "low", "enforcement": "gated"}
            if isinstance(val, dict):
                rec.update({k: v for k, v in val.items() if k != "id"})
                rec["id"] = key
                rec.setdefault("enforcement", val.get("enforcement") or val.get("hook") or "gated")
            elif isinstance(val, str):
                rec["enforcement"] = val
            out.append(rec)
        return out
    return []


def extract_declared(pkg: dict[str, Any]) -> list[str]:
    return [item["id"] for item in _items(pkg)]


def extract_records(pkg: dict[str, Any]) -> list[dict[str, Any]]:
    return _items(pkg)
