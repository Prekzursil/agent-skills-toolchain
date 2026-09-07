#!/usr/bin/env python3
"""CC-0008: deterministic catalog-slice merge + collision gate.

Folds command-center/catalog-slices/*.json into WORK-UNIT-CATALOG.json under
`work_units` (preserving the legacy `items` backlog). Never renames on collision —
raises CollisionError naming every source path that claimed the id.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
DEFAULT_SLICES = REPO / "command-center" / "catalog-slices"
DEFAULT_CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
DEFAULT_ALLOC = REPO / "command-center" / "ID-NAMESPACE-ALLOCATION.json"

# Prompt-Two 19 fields (_USER-PROMPTS.md:10607-10625). Slice authors use the
# question_or_target / assigned_model_vendor_role spellings; both resolve.
WORK_UNIT_FIELDS: tuple[str, ...] = (
    "id",
    "title",
    "phase",
    "target",
    "inputs",
    "dependencies",
    "assignment",
    "tool_permissions",
    "execution_substrate",
    "timeout_seconds",
    "output_path",
    "output_schema",
    "evidence_requirement",
    "tests_required",
    "reviewer_requirement",
    "completion_sentinel",
    "retry_policy",
    "failure_classification",
    "owner_approval_required",
)

FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "target": ("target", "question_or_target"),
    "assignment": ("assignment", "assigned_model_vendor_role"),
}


class CollisionError(ValueError):
    """Raised when two slices claim the same unit id. Never auto-renames."""


class FieldCompletenessError(ValueError):
    """Raised when a merged unit fails the CC-0001-armed 19-field gate."""


class PrefixAllocationError(ValueError):
    """Raised when a unit id prefix is not in the allocation table."""


def load_allocation(path: Path | None = None) -> dict[str, Any]:
    p = path or DEFAULT_ALLOC
    return json.loads(p.read_text(encoding="utf-8"))


def prefix_to_bucket(allocation: dict[str, Any]) -> dict[str, str]:
    return {row["prefix"]: row["bucket"] for row in allocation["buckets"]}


def bucket_quotas(allocation: dict[str, Any]) -> dict[str, int]:
    return {row["bucket"]: int(row["quota_units"]) for row in allocation["buckets"]}


def field_resolved(unit: dict[str, Any], field: str) -> bool:
    keys = FIELD_ALIASES.get(field, (field,))
    for key in keys:
        if key not in unit:
            continue
        val = unit[key]
        if field in ("inputs", "dependencies") and val == []:
            return True
        if val is None:
            continue
        if val == "" and field not in ("inputs", "dependencies"):
            continue
        return True
    return False


def check_field_completeness(units: list[dict[str, Any]]) -> list[str]:
    missing: list[str] = []
    for unit in units:
        uid = str(unit.get("id", "<missing-id>"))
        for field in WORK_UNIT_FIELDS:
            if not field_resolved(unit, field):
                missing.append(f"{uid}.{field}")
    return missing


def _unit_prefix(unit_id: str) -> str:
    if "-" not in unit_id:
        return unit_id
    return unit_id.split("-", 1)[0]


def load_slices(
    slice_dir: Path,
    *,
    allocation: dict[str, Any] | None = None,
    extra_slices: list[Path] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    """Load slice files. Returns (units_sorted_by_id, sources_by_id).

    Paths are sorted so load order cannot affect the merged unit list. A
    CollisionError is raised if any id appears in more than one source path.
    """
    alloc = allocation or load_allocation()
    pmap = prefix_to_bucket(alloc)

    paths = sorted(slice_dir.glob("*.json"))
    if extra_slices:
        # Extra paths are included for deliberate collision fixtures; still sorted.
        paths = sorted(set(paths) | {Path(p) for p in extra_slices})

    sources: dict[str, list[str]] = defaultdict(list)
    by_id: dict[str, dict[str, Any]] = {}

    for path in paths:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError(f"slice {path} root must be a JSON array, got {type(raw).__name__}")
        rel = str(path) if path.is_absolute() else str(path)
        for unit in raw:
            if not isinstance(unit, dict) or "id" not in unit:
                raise ValueError(f"slice {rel} contains a non-object or id-less unit")
            uid = str(unit["id"])
            sources[uid].append(rel)
            prefix = _unit_prefix(uid)
            if prefix not in pmap:
                raise PrefixAllocationError(
                    f"unit {uid} prefix {prefix!r} is not allocated to any B01-B13 bucket"
                )
            stamped = deepcopy(unit)
            stamped["_source_slice_file"] = Path(rel).name
            stamped["bucket"] = pmap[prefix]
            by_id[uid] = stamped

    collisions = {uid: paths_ for uid, paths_ in sources.items() if len(paths_) > 1}
    if collisions:
        parts = []
        for uid in sorted(collisions):
            named = ", ".join(collisions[uid])
            parts.append(f"{uid} claimed by: {named}")
        raise CollisionError(
            "duplicate units from colliding catalogs:\n" + "\n".join(parts)
        )

    units = [by_id[uid] for uid in sorted(by_id)]
    missing = check_field_completeness(units)
    if missing:
        raise FieldCompletenessError(
            "CC-0001 armed gate: unresolved work-unit fields:\n"
            + "\n".join(missing[:50])
            + (f"\n... and {len(missing) - 50} more" if len(missing) > 50 else "")
        )
    return units, {k: list(v) for k, v in sources.items()}


def per_bucket_counts(units: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for unit in units:
        counts[str(unit.get("bucket", "?"))] += 1
    return dict(sorted(counts.items()))


def merge_into_catalog(
    catalog: dict[str, Any],
    units: list[dict[str, Any]],
    *,
    allocation: dict[str, Any] | None = None,
    slice_files: list[str] | None = None,
) -> dict[str, Any]:
    """Replace catalog['work_units'] with the merged list. Never appends/duplicates."""
    alloc = allocation or load_allocation()
    quotas = bucket_quotas(alloc)
    counts = per_bucket_counts(units)
    total = len(units)
    floor = int(alloc.get("floor_units", 2048))
    out = deepcopy(catalog)
    out["work_units"] = units
    out["work_units_meta"] = {
        **(out.get("work_units_meta") or {}),
        "status": "MERGED from command-center/catalog-slices/*.json via catalog_slice_merge",
        "merger": "tools/command-center/catalog_slice_merge.py",
        "work_unit_count": total,
        "target": floor,
        "shortfall": max(floor - total, 0),
        "meets_floor": total >= floor,
        "per_bucket_counts": counts,
        "per_bucket_quotas": quotas,
        "slice_files_merged": sorted(slice_files or []),
        "id_allocation": "command-center/ID-NAMESPACE-ALLOCATION.json",
    }
    return out


def dump_work_units_bytes(units: list[dict[str, Any]]) -> bytes:
    """Canonical bytes for order-independence / idempotence compares."""
    text = json.dumps(units, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    return text.encode("utf-8")


def merge_slices(
    slice_dir: Path,
    catalog_path: Path,
    *,
    write: bool = False,
    allocation_path: Path | None = None,
) -> dict[str, Any]:
    allocation = load_allocation(allocation_path)
    units, _sources = load_slices(slice_dir, allocation=allocation)
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    slice_files = sorted(p.name for p in slice_dir.glob("*.json"))
    merged = merge_into_catalog(
        catalog, units, allocation=allocation, slice_files=slice_files
    )
    if write:
        text = json.dumps(merged, indent=1, ensure_ascii=False, sort_keys=True) + "\n"
        catalog_path.write_text(text, encoding="utf-8", newline="\n")
    return merged


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slices", type=Path, default=DEFAULT_SLICES)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--allocation", type=Path, default=DEFAULT_ALLOC)
    parser.add_argument(
        "--write",
        action="store_true",
        help="Persist merged work_units into --catalog (default: dry measure).",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable summary.")
    args = parser.parse_args(argv)

    try:
        merged = merge_slices(
            args.slices,
            args.catalog,
            write=args.write,
            allocation_path=args.allocation,
        )
    except (CollisionError, FieldCompletenessError, PrefixAllocationError, ValueError) as exc:
        print(f"FAILED:catalog-slice-merge {exc}")
        return 1

    meta = merged["work_units_meta"]
    # Read-back count off the structure we would write (and did write, if --write).
    read_back = len(merged["work_units"])
    summary = {
        "work_unit_count_read_back": read_back,
        "floor": meta["target"],
        "shortfall": meta["shortfall"],
        "meets_floor": meta["meets_floor"],
        "per_bucket_counts": meta["per_bucket_counts"],
        "wrote": bool(args.write),
    }
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(
            f"SUCCESS:catalog-slice-merge count={read_back} "
            f"floor={meta['target']} shortfall={meta['shortfall']} "
            f"buckets={meta['per_bucket_counts']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
