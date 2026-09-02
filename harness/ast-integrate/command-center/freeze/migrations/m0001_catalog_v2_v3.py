"""Catalog freeze epoch v2 → v3."""
from __future__ import annotations

from typing import Any

MIGRATION_ID = "m0001_catalog_v2_v3"
FROM_VERSION = 2
TO_VERSION = 3
TARGETS = ["command-center/freeze/fixtures/prefreeze_catalog_slice.json"]
MARKER = "cc0012_freeze_epoch"


def up(doc: Any) -> dict:
    if not isinstance(doc, dict):
        raise TypeError("catalog migration expects object")
    out = dict(doc)
    out["schema_version"] = 3
    out[MARKER] = {"unit_id": "CC-0012", "from_version": 2, "to_version": 3}
    units = list(out.get("work_units") or [])
    if not any(isinstance(u, dict) and u.get("id") == "CC-0012" for u in units):
        units.append({"id": "CC-0012", "title": "freeze schemas and launchers"})
        out["work_units"] = units
    out["work_unit_CC-0012"] = {"id": "CC-0012", "title": "freeze schemas and launchers"}
    return out


def down(doc: Any) -> dict:
    if not isinstance(doc, dict):
        raise TypeError("catalog migration expects object")
    out = dict(doc)
    out.pop(MARKER, None)
    out.pop("work_unit_CC-0012", None)
    out["schema_version"] = 2
    return out
