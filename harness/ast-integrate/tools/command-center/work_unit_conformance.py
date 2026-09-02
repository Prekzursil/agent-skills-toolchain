#!/usr/bin/env python3
"""Executable conformance contract for the 19-field work-unit schema (TST-0038).

The catalog (``command-center/WORK-UNIT-CATALOG.json``) carries two
collections that both claim the Prompt-Two work-unit shape:

* ``items`` -- the 103-row backlog, whose 11 operational fields live only in
  the global ``defaults`` block (present as a key on 0/103 rows);
* ``work_units`` -- the 2,007-row decomposition, which stamps every field on
  the unit itself, two of them under documented aliases
  (``assignment`` -> ``assigned_model_vendor_role``,
  ``target`` -> ``question_or_target``).

``validate.py``'s V-FIELDS treats a value *resolved through defaults* as
complete, so deleting the whole defaults block is invisible to CI when the
tool is invoked with ``--no-require-complete`` (the measured hole).  This
module is the stricter, per-unit contract:

R-PER-UNIT-KEY
    every one of the 19 fields must be a key on the unit (directly or via a
    documented alias); a field absent from the unit *and* from defaults.
R-DEFAULTS-NOT-COMPLETE
    a field absent from the unit but present in ``defaults`` is still a
    violation -- defaults are a convenience, not completeness.
R-EMPTY-REJECTED
    a present key whose value is ``None`` or a blank string is not a value.
R-SUBSTRATE-ENUM
    ``execution_substrate`` must be one of :data:`EXECUTION_SUBSTRATES`.
R-FAILURE-ENUM
    every ``failure_classification`` token must be in :data:`FAILURE_CLASSES`.
R-BARE-ARMED
    the CLI, invoked with no flags, enforces all of the above; only the
    explicit ``--allow-defaults`` / ``--no-enums`` flags disarm a rule.

Everything is computed from the catalog handed in; nothing here consults
``validate.py`` and nothing is asserted that is not derived from the rows.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):  # pragma: no cover - import shim for direct runs
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from catalog import WORK_UNIT_FIELDS, load as load_catalog  # noqa: E402

RULES: tuple[str, ...] = (
    "R-PER-UNIT-KEY",
    "R-DEFAULTS-NOT-COMPLETE",
    "R-EMPTY-REJECTED",
    "R-SUBSTRATE-ENUM",
    "R-FAILURE-ENUM",
    "R-BARE-ARMED",
)

# Prompt-Two field name -> alternative key names the ``work_units`` slices
# used when they were merged (``work_units_meta.preserved`` in the catalog).
# A unit satisfies the field through any one of them.
FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "assignment": ("assigned_model_vendor_role",),
    "target": ("question_or_target",),
}

# Closed enums.  The substrate set is every value the live catalog uses
# (defaults + the four work_units values); the failure taxonomy is the
# six-value set the catalog's defaults block declares.
EXECUTION_SUBSTRATES: frozenset[str] = frozenset(
    {
        "local-windows-pwsh7",
        "local-parallel",
        "local-serialized",
        "worktree-isolated",
        "cloud-batch",
    }
)
FAILURE_CLASSES: frozenset[str] = frozenset(
    {
        "green-not-live",
        "overclaim",
        "detector-failure",
        "uncontrolled-silence",
        "dependency-blocked",
        "owner-blocked",
    }
)

# The 11 fields that, on the live ``items`` collection, exist only in the
# defaults block (measured 0/103 as per-unit keys).
DEFAULT_ONLY_EXPECTED: tuple[str, ...] = (
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

COLLECTIONS: tuple[str, ...] = ("items", "work_units")

PROVENANCE_ITEM = "item"
PROVENANCE_ALIAS = "alias"
PROVENANCE_ABSENT = "absent"


# --------------------------------------------------------------------------
# field resolution
# --------------------------------------------------------------------------


def resolve_key(row: dict[str, Any], field: str) -> tuple[str | None, str]:
    """Return ``(key, provenance)`` for *field* on *row*.

    ``key`` is the actual dictionary key that carries the field (the field
    itself or a documented alias) or ``None``; ``provenance`` is one of
    ``"item"``, ``"alias"``, ``"absent"``.  The canonical name wins over an
    alias when both are present.
    """
    if field in row:
        return field, PROVENANCE_ITEM
    for alias in FIELD_ALIASES.get(field, ()):
        if alias in row:
            return alias, PROVENANCE_ALIAS
    return None, PROVENANCE_ABSENT


def is_empty(value: Any) -> bool:
    """``None`` and blank strings are empty.

    Empty lists, ``0`` and ``False`` are *values* (``dependencies: []`` and
    ``owner_approval_required: false`` are legitimate on live units).
    """
    if value is None:
        return True
    return isinstance(value, str) and value.strip() == ""


def _rows(catalog: dict[str, Any], name: str) -> list[dict[str, Any]]:
    raw = catalog.get(name) or []
    if not isinstance(raw, list):
        return []
    return [row for row in raw if isinstance(row, dict)]


def _defaults(catalog: dict[str, Any]) -> dict[str, Any]:
    defaults = catalog.get("defaults")
    return defaults if isinstance(defaults, dict) else {}


# --------------------------------------------------------------------------
# presence matrix
# --------------------------------------------------------------------------


def presence_matrix(catalog: dict[str, Any]) -> dict[str, Any]:
    """Per-field, per-collection presence counts over *catalog*.

    For every field in :data:`WORK_UNIT_FIELDS` and each collection the row
    reports ``n`` (rows in the collection), ``item`` (key present under its
    own name), ``alias`` (present only under a documented alias),
    ``on_unit`` (= item + alias), ``defaults`` (rows that carry no key and
    would be *resolved* through the defaults block), ``absent`` (rows that
    carry no key and have no default either -- a hole) and ``empty`` (key
    present but :func:`is_empty`).  ``on_unit + defaults + absent == n``.
    """
    fields = list(WORK_UNIT_FIELDS)
    defaults = _defaults(catalog)
    collections: dict[str, Any] = {}
    for name in COLLECTIONS:
        rows = _rows(catalog, name)
        n = len(rows)
        per_field: dict[str, dict[str, int]] = {}
        for field in fields:
            item = alias = via_defaults = absent = empty = 0
            for row in rows:
                key, provenance = resolve_key(row, field)
                if provenance == PROVENANCE_ITEM:
                    item += 1
                elif provenance == PROVENANCE_ALIAS:
                    alias += 1
                elif field in defaults:
                    via_defaults += 1
                else:
                    absent += 1
                if key is not None and is_empty(row[key]):
                    empty += 1
            per_field[field] = {
                "n": n,
                "item": item,
                "alias": alias,
                "on_unit": item + alias,
                "defaults": via_defaults,
                "absent": absent,
                "empty": empty,
            }
        collections[name] = {"n": n, "per_field": per_field}
    return {
        "n_fields": len(fields),
        "fields": fields,
        "defaults_keys": sorted(k for k in defaults if k in fields),
        "collections": collections,
    }


def defaults_only_fields(catalog: dict[str, Any], collection: str = "items") -> list[str]:
    """Fields present on 0 rows of *collection* that exist in ``defaults``."""
    matrix = presence_matrix(catalog)
    col = matrix["collections"].get(collection) or {"n": 0, "per_field": {}}
    out: list[str] = []
    for field in matrix["fields"]:
        row = col["per_field"].get(field)
        if row and row["on_unit"] == 0 and row["defaults"] == col["n"] and col["n"] > 0:
            out.append(field)
    return out


# --------------------------------------------------------------------------
# checker
# --------------------------------------------------------------------------


def _violation(
    rule: str, collection: str, row: dict[str, Any], field: str, message: str
) -> dict[str, Any]:
    unit_id = row.get("id")
    return {
        "rule": rule,
        "collection": collection,
        "id": unit_id,
        "field": field,
        "message": message,
        "ref": f"{unit_id}.{field}",
    }


def _failure_tokens(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def check_row(
    row: dict[str, Any],
    defaults: dict[str, Any],
    *,
    collection: str = "items",
    require_complete: bool = True,
    enforce_enums: bool = True,
) -> list[dict[str, Any]]:
    """Violations for a single unit row (see module docstring for the rules)."""
    out: list[dict[str, Any]] = []
    for field in WORK_UNIT_FIELDS:
        key, provenance = resolve_key(row, field)
        if key is None:
            if field in defaults:
                if require_complete:
                    out.append(
                        _violation(
                            "R-DEFAULTS-NOT-COMPLETE",
                            collection,
                            row,
                            field,
                            f"{field} exists only in catalogue defaults, "
                            "not as a per-unit key",
                        )
                    )
            else:
                out.append(
                    _violation(
                        "R-PER-UNIT-KEY",
                        collection,
                        row,
                        field,
                        f"{field} is neither a per-unit key nor in defaults",
                    )
                )
            continue
        value = row[key]
        if is_empty(value):
            shown = "null" if value is None else "blank string"
            out.append(
                _violation(
                    "R-EMPTY-REJECTED",
                    collection,
                    row,
                    field,
                    f"{field} is present as {key!r} but its value is {shown}",
                )
            )
            continue
        if not enforce_enums:
            continue
        if field == "execution_substrate" and value not in EXECUTION_SUBSTRATES:
            out.append(
                _violation(
                    "R-SUBSTRATE-ENUM",
                    collection,
                    row,
                    field,
                    f"execution_substrate {value!r} not in "
                    f"{sorted(EXECUTION_SUBSTRATES)}",
                )
            )
        elif field == "failure_classification":
            unknown = [t for t in _failure_tokens(value) if t not in FAILURE_CLASSES]
            if unknown:
                out.append(
                    _violation(
                        "R-FAILURE-ENUM",
                        collection,
                        row,
                        field,
                        f"failure_classification tokens {unknown!r} not in "
                        f"{sorted(FAILURE_CLASSES)}",
                    )
                )
    return out


def check_catalog(
    catalog: dict[str, Any],
    *,
    require_complete: bool = True,
    enforce_enums: bool = True,
    collections: tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    """Every violation over the requested collections (default: both).

    ``require_complete=False`` restores the historical V-FIELDS reading in
    which a default counts as resolution (R-DEFAULTS-NOT-COMPLETE is not
    raised); a field missing from both the unit and defaults is still
    R-PER-UNIT-KEY.  ``enforce_enums=False`` skips the two enum rules.
    """
    names = tuple(collections) if collections else COLLECTIONS
    defaults = _defaults(catalog)
    out: list[dict[str, Any]] = []
    for name in names:
        for row in _rows(catalog, name):
            out.extend(
                check_row(
                    row,
                    defaults,
                    collection=name,
                    require_complete=require_complete,
                    enforce_enums=enforce_enums,
                )
            )
    return out


def format_violation(row: dict[str, Any]) -> str:
    return f"{row['rule']} {row['ref']}: {row['message']}"


# --------------------------------------------------------------------------
# fixtures (both-states controls)
# --------------------------------------------------------------------------


def conforming_unit(unit_id: str = "R-G01") -> dict[str, Any]:
    """A unit carrying all 19 fields as real, enum-valid per-unit keys."""
    return {
        "id": unit_id,
        "title": "Conforming fixture unit",
        "phase": "P2",
        "target": "Does the checker stay silent on a fully keyed unit?",
        "inputs": ["command-center/WORK-UNIT-CATALOG.json"],
        "dependencies": [],
        "assignment": {"vendor": "anthropic", "model": "opus", "role": "implementer"},
        "tool_permissions": ["Read", "Grep"],
        "execution_substrate": "local-serialized",
        "timeout_seconds": 600,
        "output_path": f"command-center/receipts/{unit_id}.json",
        "output_schema": "command-center/schema/receipt.schema.json",
        "evidence_requirement": "two mechanically independent signals",
        "tests_required": ["a both-states control"],
        "reviewer_requirement": "one independent adversarial reviewer",
        "completion_sentinel": f"SUCCESS:{unit_id}",
        "retry_policy": "two strikes then pivot",
        "failure_classification": ["green-not-live", "overclaim"],
        "owner_approval_required": False,
    }


def conforming_catalog() -> dict[str, Any]:
    """GREEN fixture: one item and one work unit, every field on the unit."""
    return {
        "schema_version": 1,
        "defaults": {},
        "items": [conforming_unit("R-G01")],
        "work_units": [conforming_unit("R-G02")],
    }


def defaults_only_catalog() -> dict[str, Any]:
    """RED fixture: the 11 operational fields exist only in ``defaults``."""
    unit = conforming_unit("R-D01")
    defaults = {field: unit.pop(field) for field in DEFAULT_ONLY_EXPECTED}
    return {
        "schema_version": 1,
        "defaults": defaults,
        "items": [unit],
        "work_units": [],
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="work_unit_conformance",
        description="Per-unit work-unit schema conformance (armed by default).",
    )
    parser.add_argument("--catalog", help="catalog JSON path (default: live catalog)")
    parser.add_argument(
        "--items-only", action="store_true", help="check only the items collection"
    )
    parser.add_argument(
        "--work-units-only",
        action="store_true",
        help="check only the work_units collection",
    )
    parser.add_argument(
        "--allow-defaults",
        action="store_true",
        help="historical reading: a value resolved through defaults counts as present",
    )
    parser.add_argument(
        "--no-enums", action="store_true", help="skip the two closed-enum rules"
    )
    parser.add_argument(
        "--limit", type=int, default=20, help="violations to print (default 20)"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(sys.argv[1:] if argv is None else list(argv))
    if args.catalog:
        catalog = json.loads(Path(args.catalog).read_text(encoding="utf-8"))
    else:
        catalog = load_catalog()
    if args.items_only:
        cols: tuple[str, ...] = ("items",)
    elif args.work_units_only:
        cols = ("work_units",)
    else:
        cols = COLLECTIONS
    require_complete = not args.allow_defaults
    enforce_enums = not args.no_enums
    violations = check_catalog(
        catalog,
        require_complete=require_complete,
        enforce_enums=enforce_enums,
        collections=cols,
    )
    for row in violations[: max(args.limit, 0)]:
        print("  " + format_violation(row))
    if len(violations) > max(args.limit, 0):
        print(f"  ... {len(violations) - max(args.limit, 0)} more")
    print(
        f"work-unit-conformance violations={len(violations)} "
        f"require_complete={require_complete} enforce_enums={enforce_enums} "
        f"fields={len(WORK_UNIT_FIELDS)} collections={','.join(cols)}"
    )
    if violations:
        print(f"FAILED:work-unit-conformance violations={len(violations)}")
        return 1
    print("SUCCESS:work-unit-conformance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
