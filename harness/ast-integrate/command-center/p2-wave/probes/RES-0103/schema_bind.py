"""Catalog shim vs unit-local bound schema for RES-0103."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG_SCHEMA = REPO / "command-center/schema/research-claim-record.schema.json"
BOUND_SCHEMA = HERE / "bound.schema.json"


def load_discriminator() -> tuple[dict, str]:
    if not CATALOG_SCHEMA.is_file():
        raise FileNotFoundError(CATALOG_SCHEMA)
    catalog = json.loads(CATALOG_SCHEMA.read_text(encoding="utf-8"))
    if not isinstance(catalog, dict) or not catalog:
        raise ValueError("catalog schema empty")
    props = catalog.get("properties") or {}
    if "threshold_recommendation" in props or "source_lineage" in props:
        return catalog, "catalog"
    if not BOUND_SCHEMA.is_file():
        raise FileNotFoundError(BOUND_SCHEMA)
    return json.loads(BOUND_SCHEMA.read_text(encoding="utf-8")), "bound"
