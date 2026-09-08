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
from collections import Counter, defaultdict
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


class ContiguityError(ValueError):
    """Raised when assembled ids have gaps, duplicates, or count ≠ declared floor.

    IMP-0456: any nonzero gap or duplicate blocks the merge; total must equal
    the declared program count (allocation floor_units).
    """


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


def parse_unit_index(unit_id: str) -> tuple[str, int] | None:
    """Split PREFIX-NNNN into (prefix, int). Returns None if not PREFIX-digits."""
    if "-" not in unit_id:
        return None
    prefix, rest = unit_id.split("-", 1)
    if not rest.isdigit():
        return None
    return prefix, int(rest)


def format_unit_id(prefix: str, index: int) -> str:
    return f"{prefix}-{index:04d}"


def scan_slice_id_inventory(
    slice_dir: Path,
    *,
    extra_slices: list[Path] | None = None,
) -> dict[str, Any]:
    """Read ids from slice files without the 19-field completeness gate.

    Used by IMP-0456 merge reporting and planted gap/dup controls. Still
    surfaces duplicate ids across sources (never silently drops).
    """
    paths = sorted(slice_dir.glob("*.json"))
    if extra_slices:
        paths = sorted(set(paths) | {Path(p) for p in extra_slices})

    sources: dict[str, list[str]] = defaultdict(list)
    per_slice: list[dict[str, Any]] = []
    all_ids: list[str] = []

    for path in paths:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError(
                f"slice {path} root must be a JSON array, got {type(raw).__name__}"
            )
        rel = str(path)
        ids: list[str] = []
        for unit in raw:
            if not isinstance(unit, dict) or "id" not in unit:
                raise ValueError(f"slice {rel} contains a non-object or id-less unit")
            uid = str(unit["id"])
            ids.append(uid)
            sources[uid].append(rel)
            all_ids.append(uid)
        nums = []
        for uid in ids:
            parsed = parse_unit_index(uid)
            if parsed is not None:
                nums.append(parsed[1])
        per_slice.append(
            {
                "path": path.name,
                "abs_path": rel,
                "count": len(ids),
                "ids_min": format_unit_id(
                    parse_unit_index(ids[0])[0], min(nums)
                )
                if ids and nums and parse_unit_index(ids[0])
                else (ids[0] if ids else None),
                "ids_max": format_unit_id(
                    parse_unit_index(ids[-1])[0], max(nums)
                )
                if ids and nums and parse_unit_index(ids[-1])
                else (ids[-1] if ids else None),
                "id_range_numeric_min": min(nums) if nums else None,
                "id_range_numeric_max": max(nums) if nums else None,
                "unique_count": len(set(ids)),
                "internal_duplicates": sorted(
                    {i for i in ids if ids.count(i) > 1}
                ),
            }
        )

    collisions = {
        uid: paths_ for uid, paths_ in sources.items() if len(paths_) > 1
    }
    return {
        "slice_files": [p.name for p in paths],
        "per_slice": per_slice,
        "total_id_mentions": len(all_ids),
        "unique_ids": len(sources),
        "duplicates": {uid: list(paths_) for uid, paths_ in sorted(collisions.items())},
        "duplicate_count": len(collisions),
        "sources_by_id": {k: list(v) for k, v in sources.items()},
        "all_ids_sorted": sorted(sources.keys()),
    }


def analyze_contiguity(
    unit_ids: list[str],
    allocation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Per-prefix contiguity against each bucket's quota_units (1..quota).

    Declared program count is allocation['floor_units']. Contiguous + unique +
    exact means: no duplicate ids, every prefix fills 1..quota with no gaps,
    and total unique ids == floor_units.
    """
    alloc = allocation or load_allocation()
    floor = int(alloc.get("floor_units", 2048))
    quotas = {row["prefix"]: int(row["quota_units"]) for row in alloc["buckets"]}
    buckets = {row["prefix"]: row["bucket"] for row in alloc["buckets"]}

    by_prefix: dict[str, list[int]] = defaultdict(list)
    malformed: list[str] = []
    for uid in unit_ids:
        parsed = parse_unit_index(uid)
        if parsed is None:
            malformed.append(uid)
            continue
        prefix, idx = parsed
        by_prefix[prefix].append(idx)

    per_prefix: list[dict[str, Any]] = []
    total_gaps = 0
    total_dups = 0
    total_quota_shortfall = 0

    for prefix in sorted(set(quotas) | set(by_prefix)):
        nums = by_prefix.get(prefix, [])
        quota = quotas.get(prefix)
        counted = Counter(nums)
        dups = sorted(n for n, c in counted.items() if c > 1)
        present = set(counted)
        if quota is None:
            gaps: list[int] = []
            expected = None
            shortfall = None
        else:
            expected = list(range(1, quota + 1))
            gaps = [i for i in expected if i not in present]
            shortfall = quota - len(present)
            total_quota_shortfall += max(shortfall, 0)
        total_gaps += len(gaps)
        total_dups += len(dups)
        per_prefix.append(
            {
                "prefix": prefix,
                "bucket": buckets.get(prefix),
                "quota_units": quota,
                "count": len(nums),
                "unique": len(present),
                "min": min(present) if present else None,
                "max": max(present) if present else None,
                "gaps": gaps,
                "gap_count": len(gaps),
                "duplicates": [format_unit_id(prefix, n) for n in dups],
                "duplicate_index_count": len(dups),
                "quota_shortfall": shortfall,
                "contiguous_1_to_quota": bool(
                    quota is not None and not gaps and not dups and len(present) == quota
                ),
            }
        )

    unique_total = len(set(unit_ids))
    # Cross-source duplicate ids (same string claimed twice) are separate from
    # within-prefix numeric dups; callers pass unique ids for gap analysis but
    # merge reports still carry inventory.duplicates.
    ok = (
        total_gaps == 0
        and total_dups == 0
        and not malformed
        and unique_total == floor
        and all(row["contiguous_1_to_quota"] for row in per_prefix if row["quota_units"])
    )
    return {
        "declared_program_count": floor,
        "unique_id_count": unique_total,
        "id_mention_count": len(unit_ids),
        "total_equals_declared": unique_total == floor,
        "total_gap_count": total_gaps,
        "total_duplicate_index_count": total_dups,
        "total_quota_shortfall": total_quota_shortfall,
        "malformed_ids": malformed,
        "per_prefix": per_prefix,
        "contiguous_unique_exact": ok,
    }


def mechanism_collisions(units: list[dict[str, Any]]) -> dict[str, Any]:
    """Detect identical non-empty `mechanism` strings claimed by ≥2 unit ids."""
    by_mech: dict[str, list[str]] = defaultdict(list)
    for unit in units:
        mech = unit.get("mechanism")
        if mech is None or mech == "":
            continue
        by_mech[str(mech)].append(str(unit.get("id", "<missing-id>")))
    collisions = {
        mech: ids for mech, ids in sorted(by_mech.items()) if len(ids) > 1
    }
    return {
        "units_with_mechanism": sum(len(v) for v in by_mech.values()),
        "unique_mechanisms": len(by_mech),
        "collision_count": len(collisions),
        "collisions": collisions,
    }


def build_merge_report(
    slice_dir: Path,
    *,
    allocation: dict[str, Any] | None = None,
    catalog_path: Path | None = None,
    require_field_complete: bool = False,
) -> dict[str, Any]:
    """Assemble IMP-0456 evidence: per-slice count/range + gaps/dups vs floor."""
    alloc = allocation or load_allocation()
    inventory = scan_slice_id_inventory(slice_dir)
    # Prefer unique ids for contiguity; duplicate presence is in inventory.
    contiguity = analyze_contiguity(inventory["all_ids_sorted"], allocation=alloc)

    units: list[dict[str, Any]] | None = None
    field_complete_ok: bool | None = None
    field_error: str | None = None
    collision_error: str | None = None
    if inventory["duplicate_count"]:
        collision_error = (
            "duplicate units from colliding catalogs:\n"
            + "\n".join(
                f"{uid} claimed by: {', '.join(paths)}"
                for uid, paths in inventory["duplicates"].items()
            )
        )
    elif require_field_complete:
        try:
            units, _ = load_slices(slice_dir, allocation=alloc)
            field_complete_ok = True
        except (CollisionError, FieldCompletenessError, PrefixAllocationError, ValueError) as exc:
            field_complete_ok = False
            field_error = str(exc)

    mech = mechanism_collisions(units or [])
    merge_blocked = bool(
        inventory["duplicate_count"]
        or contiguity["total_gap_count"]
        or not contiguity["total_equals_declared"]
        or mech["collision_count"]
        or collision_error
        or (field_complete_ok is False)
    )

    catalog_meta = None
    cat = catalog_path or DEFAULT_CATALOG
    if cat.is_file():
        try:
            raw_cat = json.loads(cat.read_text(encoding="utf-8"))
            catalog_meta = {
                "path": str(cat.relative_to(REPO))
                if cat.is_relative_to(REPO)
                else str(cat),
                "work_unit_count": len(raw_cat.get("work_units") or []),
                "work_units_meta_shortfall": (raw_cat.get("work_units_meta") or {}).get(
                    "shortfall"
                ),
                "work_units_meta_target": (raw_cat.get("work_units_meta") or {}).get(
                    "target"
                ),
            }
        except (OSError, json.JSONDecodeError, ValueError):
            catalog_meta = {"path": str(cat), "error": "unreadable"}

    return {
        "schema_version": 1,
        "unit_id": "IMP-0456",
        "kind": "catalog-slice-merge-contiguity-report",
        "slice_dir": str(slice_dir.relative_to(REPO))
        if slice_dir.is_relative_to(REPO)
        else str(slice_dir),
        "inventory": {
            "slice_files": inventory["slice_files"],
            "per_slice": inventory["per_slice"],
            "total_id_mentions": inventory["total_id_mentions"],
            "unique_ids": inventory["unique_ids"],
            "duplicate_count": inventory["duplicate_count"],
            "duplicates": inventory["duplicates"],
        },
        "contiguity": contiguity,
        "mechanism_collisions": mech,
        "field_completeness": {
            "checked": require_field_complete,
            "ok": field_complete_ok,
            "error": field_error,
        },
        "collision_error": collision_error,
        "live_catalog": catalog_meta,
        "merge_allowed": not merge_blocked,
        "block_reasons": [
            r
            for r, cond in [
                ("duplicate-unit-id", inventory["duplicate_count"] > 0),
                ("index-gap", contiguity["total_gap_count"] > 0),
                (
                    "count-claimed-not-read",
                    not contiguity["total_equals_declared"],
                ),
                ("mechanism-collision", mech["collision_count"] > 0),
                ("field-completeness", field_complete_ok is False),
            ]
            if cond
        ],
        "exact_question": {
            "text": (
                "across all assembled slices, are the ids contiguous, unique, "
                "and exactly equal to the declared program count?"
            ),
            "contiguous": contiguity["total_gap_count"] == 0
            and all(
                row.get("contiguous_1_to_quota")
                for row in contiguity["per_prefix"]
                if row.get("quota_units")
            ),
            "unique": inventory["duplicate_count"] == 0
            and contiguity["total_duplicate_index_count"] == 0,
            "exactly_equal_to_declared": contiguity["total_equals_declared"],
            "answer": bool(contiguity["contiguous_unique_exact"])
            and inventory["duplicate_count"] == 0
            and mech["collision_count"] == 0,
        },
    }


def assert_merge_contiguous(
    slice_dir: Path,
    *,
    allocation: dict[str, Any] | None = None,
    require_field_complete: bool = True,
) -> dict[str, Any]:
    """Load + refuse on duplicate id, index gap, or count ≠ floor. Returns report."""
    alloc = allocation or load_allocation()
    report = build_merge_report(
        slice_dir,
        allocation=alloc,
        require_field_complete=require_field_complete,
    )
    if report["inventory"]["duplicate_count"]:
        raise CollisionError(report["collision_error"] or "duplicate unit ids")
    if require_field_complete and report["field_completeness"]["ok"] is False:
        raise FieldCompletenessError(
            report["field_completeness"]["error"] or "field completeness failed"
        )
    if report["mechanism_collisions"]["collision_count"]:
        parts = [
            f"{mech!r} claimed by: {', '.join(ids)}"
            for mech, ids in report["mechanism_collisions"]["collisions"].items()
        ]
        raise ContiguityError(
            "mechanism collisions block merge:\n" + "\n".join(parts)
        )
    if not report["exact_question"]["answer"]:
        c = report["contiguity"]
        raise ContiguityError(
            "catalog slice merge refused: "
            f"gaps={c['total_gap_count']} "
            f"dup_indexes={c['total_duplicate_index_count']} "
            f"unique={c['unique_id_count']} "
            f"declared={c['declared_program_count']} "
            f"block_reasons={report['block_reasons']}"
        )
    return report


def merge_slices(
    slice_dir: Path,
    catalog_path: Path,
    *,
    write: bool = False,
    allocation_path: Path | None = None,
    allocation: dict[str, Any] | None = None,
    require_contiguous: bool = False,
) -> dict[str, Any]:
    alloc = allocation if allocation is not None else load_allocation(allocation_path)
    if require_contiguous:
        assert_merge_contiguous(
            slice_dir, allocation=alloc, require_field_complete=True
        )
    units, _sources = load_slices(slice_dir, allocation=alloc)
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    slice_files = sorted(p.name for p in slice_dir.glob("*.json"))
    merged = merge_into_catalog(
        catalog, units, allocation=alloc, slice_files=slice_files
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
    parser.add_argument(
        "--require-contiguous",
        action="store_true",
        help=(
            "IMP-0456 gate: refuse when ids are non-contiguous, duplicated, "
            "or total ≠ allocation floor_units."
        ),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Write IMP-0456 merge-contiguity report JSON to this path.",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable summary.")
    args = parser.parse_args(argv)

    allocation = load_allocation(args.allocation)
    report = build_merge_report(
        args.slices,
        allocation=allocation,
        catalog_path=args.catalog,
        require_field_complete=False,
    )
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    try:
        if args.require_contiguous:
            assert_merge_contiguous(
                args.slices, allocation=allocation, require_field_complete=True
            )
        merged = merge_slices(
            args.slices,
            args.catalog,
            write=args.write,
            allocation_path=args.allocation,
            require_contiguous=False,  # already asserted above when requested
        )
    except (
        CollisionError,
        ContiguityError,
        FieldCompletenessError,
        PrefixAllocationError,
        ValueError,
    ) as exc:
        print(f"FAILED:catalog-slice-merge {exc}")
        if args.json:
            print(json.dumps({"ok": False, "report": report}, indent=2, sort_keys=True))
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
        "contiguous_unique_exact": report["exact_question"]["answer"],
        "merge_allowed": report["merge_allowed"],
        "block_reasons": report["block_reasons"],
    }
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(
            f"SUCCESS:catalog-slice-merge count={read_back} "
            f"floor={meta['target']} shortfall={meta['shortfall']} "
            f"buckets={meta['per_bucket_counts']} "
            f"contiguous_unique_exact={report['exact_question']['answer']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
