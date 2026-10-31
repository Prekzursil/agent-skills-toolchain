"""Presence matrix and defaults-are-not-complete checker for work units."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from catalog import WORK_UNIT_FIELDS, load as load_catalog

DEFAULT_ONLY_EXPECTED = (
    "assignment",
    "tool_permissions",
    "execution_substrate",
    "timeout_seconds",
    "output_schema",
    "evidence_requirement",
    "tests_required",
    "reviewer_requirement",
    "retry_policy",
    "failure_classification",
    "owner_approval_required",
)


def _collections(catalog: dict[str, Any]) -> dict[str, list]:
    return {
        "items": list(catalog.get("items") or []),
        "work_units": list(catalog.get("work_units") or []),
    }


def presence_matrix(catalog: dict[str, Any]) -> dict[str, Any]:
    fields = list(WORK_UNIT_FIELDS)
    defaults = catalog.get("defaults") or {}
    out_cols = {}
    for name, rows in _collections(catalog).items():
        per = {}
        n = len(rows)
        for field in fields:
            on_unit = sum(1 for r in rows if isinstance(r, dict) and field in r)
            in_defaults = n if field in defaults else 0
            per[field] = {"on_unit": on_unit, "defaults": in_defaults}
        out_cols[name] = {"n": n, "per_field": per}
    return {"n_fields": len(fields), "fields": fields, "collections": out_cols}


def check_catalog(
    catalog: dict[str, Any],
    *,
    require_complete: bool = False,
    enforce_enums: bool = False,
    collections: tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    if not require_complete:
        return []
    names = collections or ("items", "work_units")
    defaults = catalog.get("defaults") or {}
    viol = []
    for name in names:
        rows = _collections(catalog).get(name) or []
        for row in rows:
            if not isinstance(row, dict):
                continue
            for field in WORK_UNIT_FIELDS:
                if field in row:
                    continue
                if field in defaults:
                    viol.append(
                        {
                            "id": row.get("id"),
                            "field": field,
                            "rule": "R-DEFAULTS-NOT-COMPLETE",
                            "collection": name,
                        }
                    )
    return viol


def conforming_catalog() -> dict[str, Any]:
    row = {f: f"x-{f}" for f in WORK_UNIT_FIELDS}
    row["id"] = "WU-GOOD"
    return {"items": [dict(row)], "work_units": [dict(row)], "defaults": {}}


def defaults_only_catalog() -> dict[str, Any]:
    defaults = {f: f"d-{f}" for f in DEFAULT_ONLY_EXPECTED}
    item = {"id": "WU-DEF", "title": "t", "phase": "p", "target": "t", "inputs": [],
            "dependencies": [], "output_path": "x", "completion_sentinel": "S"}
    return {"items": [item], "work_units": [], "defaults": defaults}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    path = None
    items_only = "--items-only" in argv
    if "--catalog" in argv:
        path = argv[argv.index("--catalog") + 1]
    catalog = json.loads(Path(path).read_text(encoding="utf-8")) if path else load_catalog()
    cols = ("items",) if items_only else None
    viol = check_catalog(catalog, require_complete=True, collections=cols)
    if viol:
        print(json.dumps(viol[:5], indent=2))
        print(f"violations={len(viol)}")
        return 1
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
