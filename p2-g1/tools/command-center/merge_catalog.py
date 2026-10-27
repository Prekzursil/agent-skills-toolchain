#!/usr/bin/env python3
"""Deterministic catalog-slice merger with a fail-closed collision gate.

Shipped for CC-0008 (prefix-to-bucket allocation + order-independent merge) and
also the TST-0158 CLI contract (refuse colliding id namespaces, never last-wins
in production). Collision is never resolved by renaming: the merger names every
source path and every colliding id, then stops.

CLI:
  python3 tools/command-center/merge_catalog.py SLICE.json [SLICE.json ...] [--output OUT]
  python3 tools/command-center/merge_catalog.py --slices command-center/catalog-slices --output OUT

Overwriting command-center/WORK-UNIT-CATALOG.json requires --in-place.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

if __package__ in (None, ""):  # pragma: no cover - import shim for direct runs
    sys.path.insert(0, str(Path(__file__).resolve().parent))

REPO = Path(__file__).resolve().parents[2]
ALLOC_REL = "command-center/id-namespace-allocation.json"
ALLOC_PATH = REPO / ALLOC_REL
LIVE_CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
DEFAULT_SLICES = REPO / "command-center" / "catalog-slices"

# Prompt-Two work-unit id: PREFIX-NNNN. TST-0158 M-1 / TST-A-0001 do not match,
# so they are not subjected to the 13-prefix allocation gate.
ID_RE = re.compile(r"^([A-Z]{2,5})-(\d{4})$")

PROMPT_TWO_FIELDS: tuple[str, ...] = (
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
    "target": ("question_or_target",),
    "assignment": ("assigned_model_vendor_role",),
    "question_or_target": ("target",),
    "assigned_model_vendor_role": ("assignment",),
}

# Same hole as tools/command-center/validate.py V-FIELDS: a root may have
# empty inputs/dependencies. An empty title is not this hole.
EMPTY_OK = frozenset({"inputs", "dependencies"})


class MergeError(Exception):
    """Fail-closed merge defect. kind is a stable token the probes substring-match."""

    def __init__(
        self,
        kind: str,
        detail: str,
        paths: list[str] | None = None,
        collision_ids: list[str] | None = None,
    ) -> None:
        self.kind = kind
        self.detail = detail
        self.paths = [str(p) for p in (paths or [])]
        self.collision_ids = list(collision_ids or [])
        super().__init__(f"{kind}: {detail}")


def sort_ids(ids: list[str] | set[str]) -> list[str]:
    def key(token: str) -> tuple[str, int, str]:
        head, sep, tail = str(token).rpartition("-")
        if sep and tail.isdigit():
            return (head, int(tail), str(token))
        return (str(token), 0, str(token))

    return sorted(ids, key=key)


def canonical_dumps(doc: Any) -> str:
    return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def write_canonical(path: Path | str, doc: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(canonical_dumps(doc), encoding="utf-8", newline="\n")
    return None


def load_allocation(path: Path | str | None = None) -> dict[str, Any]:
    target = Path(path) if path else ALLOC_PATH
    try:
        raw = target.read_text(encoding="utf-8")
        doc = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MergeError(
            "malformed-slice",
            f"allocation table unreadable: {type(exc).__name__}",
            [target.as_posix()],
        ) from exc
    if not isinstance(doc, dict):
        raise MergeError(
            "malformed-slice",
            "allocation table root is not an object",
            [target.as_posix()],
        )
    prefix_map = doc.get("_prefix_to_bucket")
    if not isinstance(prefix_map, dict) or not prefix_map:
        prefix_map = {}
        for row in doc.get("buckets") or []:
            if isinstance(row, dict) and row.get("prefix") and row.get("bucket"):
                prefix_map[str(row["prefix"])] = str(row["bucket"])
        doc = dict(doc)
        doc["_prefix_to_bucket"] = prefix_map
    return doc


def prefix_of(uid: str) -> str:
    text = str(uid or "")
    matched = ID_RE.match(text)
    if matched:
        return matched.group(1)
    head, sep, _tail = text.rpartition("-")
    return head if sep else text


def counts_by_prefix(units: list[Any]) -> dict[str, int]:
    out: dict[str, int] = {}
    for unit in units:
        if not isinstance(unit, dict):
            continue
        uid = str(unit.get("id") or "")
        if not uid:
            continue
        pref = prefix_of(uid)
        out[pref] = out.get(pref, 0) + 1
    return dict(sorted(out.items()))


def counts_by_allocated_bucket(
    units: list[Any], allocation: dict[str, Any] | None = None
) -> dict[str, int]:
    alloc = allocation if allocation is not None else load_allocation()
    prefix_map = alloc.get("_prefix_to_bucket") or {}
    out: dict[str, int] = {}
    for row in alloc.get("buckets") or []:
        if isinstance(row, dict) and row.get("bucket"):
            out[str(row["bucket"])] = 0
    for unit in units:
        if not isinstance(unit, dict):
            continue
        uid = str(unit.get("id") or "")
        bucket = prefix_map.get(prefix_of(uid))
        if bucket:
            out[str(bucket)] = out.get(str(bucket), 0) + 1
    return dict(sorted(out.items()))


def _lookup(unit: dict[str, Any], defaults: dict[str, Any], field: str) -> Any:
    keys = (field,) + FIELD_ALIASES.get(field, ())
    for key in keys:
        if key in unit and unit[key] is not None:
            return unit[key]
    for key in keys:
        if key in defaults and defaults[key] is not None:
            return defaults[key]
    return None


def _value_present(field: str, value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        stripped = value.strip()
        return bool(stripped) and not stripped.startswith("UNKNOWN")
    if isinstance(value, (list, dict)):
        if field in EMPTY_OK:
            return True
        return bool(value)
    return True


def completeness_gaps(
    unit: dict[str, Any], defaults: dict[str, Any] | None = None
) -> list[str]:
    """CC-0001 armed-gate fields after alias resolution. Empty list = complete."""
    defaults = defaults if isinstance(defaults, dict) else {}
    missing: list[str] = []
    for field in PROMPT_TWO_FIELDS:
        if not _value_present(field, _lookup(unit, defaults, field)):
            missing.append(field)
    return missing


def minimal_unit(uid: str, **overrides: Any) -> dict[str, Any]:
    unit: dict[str, Any] = {
        "id": uid,
        "title": f"minimal {uid}",
        "phase": "0",
        "question_or_target": f"target for {uid}",
        "target": f"target for {uid}",
        "inputs": ["fixture"],
        "dependencies": [],
        "assigned_model_vendor_role": {
            "model": "opus",
            "role": "implementer",
            "vendor": "anthropic",
        },
        "assignment": {
            "model": "opus",
            "role": "implementer",
            "vendor": "anthropic",
        },
        "tool_permissions": ["Read"],
        "execution_substrate": "worktree-isolated",
        "timeout_seconds": 60,
        "output_path": f"command-center/receipts/{uid}.json",
        "output_schema": "command-center/schema/receipt.schema.json",
        "evidence_requirement": "fixture",
        "tests_required": ["fixture"],
        "reviewer_requirement": "fixture",
        "completion_sentinel": f"SUCCESS:{uid}",
        "retry_policy": "two strikes then pivot",
        "failure_classification": ["overclaim"],
        "owner_approval_required": False,
    }
    unit.update(overrides)
    return unit


def extract_units(doc: Any, source: str) -> tuple[list[dict[str, Any]], str]:
    if isinstance(doc, list):
        units = [row for row in doc if isinstance(row, dict)]
        if len(units) != len(doc):
            raise MergeError(
                "malformed-slice",
                "slice array contains a non-object unit",
                [source],
            )
        return units, "work_units"
    if isinstance(doc, dict):
        if isinstance(doc.get("work_units"), list):
            rows = doc["work_units"]
            units = [row for row in rows if isinstance(row, dict)]
            if len(units) != len(rows):
                raise MergeError(
                    "malformed-slice",
                    "work_units contains a non-object unit",
                    [source],
                )
            return units, "work_units"
        if isinstance(doc.get("items"), list):
            rows = doc["items"]
            units = [row for row in rows if isinstance(row, dict)]
            if len(units) != len(rows):
                raise MergeError(
                    "malformed-slice",
                    "items contains a non-object unit",
                    [source],
                )
            return units, "items"
        raise MergeError(
            "malformed-slice",
            "slice has neither work_units nor items array",
            [source],
        )
    raise MergeError(
        "malformed-slice",
        f"slice root is {type(doc).__name__}, expected object or array",
        [source],
    )


def load_slice(path: Path) -> tuple[list[dict[str, Any]], str]:
    source = path.as_posix()
    try:
        raw = path.read_text(encoding="utf-8")
        doc = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MergeError(
            "malformed-slice",
            f"unparseable JSON ({type(exc).__name__})",
            [source],
        ) from exc
    return extract_units(doc, source)


def discover_slice_paths(directory: Path) -> list[Path]:
    if not directory.is_dir():
        raise MergeError(
            "malformed-slice",
            "slices directory missing",
            [directory.as_posix()],
        )
    paths = [
        p
        for p in sorted(directory.glob("*.json"))
        if p.is_file() and not p.name.startswith("_")
    ]
    return paths


def merge_slices(
    paths: list[Path | str],
    *,
    allocation: dict[str, Any] | None = None,
    require_complete: bool = False,
    defaults: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Fold slices into one id-sorted unit list. Raises MergeError; never renames."""
    alloc = allocation if allocation is not None else load_allocation()
    prefix_map = alloc.get("_prefix_to_bucket") or {}
    loaded: list[tuple[Path, list[dict[str, Any]]]] = []
    for raw_path in paths:
        path = Path(raw_path)
        units, _key = load_slice(path)
        loaded.append((path, units))

    by_id: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    for path, units in loaded:
        source = path.as_posix()
        for unit in units:
            uid = str(unit.get("id") or "").strip()
            if not uid:
                raise MergeError(
                    "incomplete-unit",
                    "unit missing id",
                    [source],
                )
            by_id[uid].append((source, unit))

    colliding = {uid: srcs for uid, srcs in by_id.items() if len(srcs) > 1}
    if colliding:
        ids = sort_ids(colliding)
        path_list: list[str] = []
        for uid in ids:
            for source, _unit in colliding[uid]:
                if source not in path_list:
                    path_list.append(source)
        raise MergeError(
            "id-collision",
            (
                "duplicate units from colliding catalogs; never rename; "
                f"ids={ids}"
            ),
            path_list,
            collision_ids=ids,
        )

    merged: list[dict[str, Any]] = []
    for uid in sort_ids(by_id):
        source, unit = by_id[uid][0]
        matched = ID_RE.match(uid)
        if matched:
            pref = matched.group(1)
            if pref not in prefix_map:
                raise MergeError(
                    "unallocated-prefix",
                    f"prefix {pref!r} is not bound to a B01-B13 bucket; never rename",
                    [source, uid],
                )
        if require_complete:
            gaps = completeness_gaps(unit, defaults)
            if gaps:
                raise MergeError(
                    "incomplete-unit",
                    f"CC-0001 armed gate gaps={gaps}",
                    [source, uid],
                )
        merged.append(unit)
    return merged


def merge_to_catalog(
    paths: list[Path | str],
    *,
    allocation: dict[str, Any] | None = None,
    require_complete: bool = False,
    defaults: dict[str, Any] | None = None,
    array_key: str = "work_units",
) -> dict[str, Any]:
    units = merge_slices(
        paths,
        allocation=allocation,
        require_complete=require_complete,
        defaults=defaults,
    )
    key = array_key if array_key in {"work_units", "items"} else "work_units"
    return {key: units}


def read_back_count(path: Path | str) -> tuple[int, dict[str, int]]:
    target = Path(path)
    try:
        doc = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MergeError(
            "malformed-slice",
            f"read-back unparseable ({type(exc).__name__})",
            [target.as_posix()],
        ) from exc
    units: list[Any] = []
    if isinstance(doc, dict):
        if isinstance(doc.get("work_units"), list):
            units = doc["work_units"]
        elif isinstance(doc.get("items"), list):
            units = doc["items"]
    elif isinstance(doc, list):
        units = doc
    n = len([u for u in units if isinstance(u, dict)])
    return n, counts_by_prefix([u for u in units if isinstance(u, dict)])


def export_slices_from_catalog(
    catalog: dict[str, Any], dest: Path | str
) -> list[Path]:
    """Reconstruct per-slice files from live work_units. Never writes the live catalog."""
    dest_dir = Path(dest)
    dest_dir.mkdir(parents=True, exist_ok=True)
    units = catalog.get("work_units") if isinstance(catalog, dict) else None
    if not isinstance(units, list):
        raise MergeError(
            "malformed-slice",
            "catalog has no work_units array",
            ["<catalog>"],
        )
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for unit in units:
        if not isinstance(unit, dict):
            continue
        name = str(unit.get("_source_slice_file") or "ungrouped.json")
        grouped[name].append(unit)
    written: list[Path] = []
    for name in sorted(grouped):
        members = grouped[name]
        members = sorted(
            members, key=lambda u: sort_ids([str(u.get("id") or "")])[0]
        )
        path = dest_dir / name
        write_canonical(path, {"slice_file": name, "work_units": members})
        written.append(path)
    return written


def last_wins_merge(
    named_docs: list[tuple[str, dict[str, Any]]],
) -> dict[str, Any]:
    """Negative-control API: silently collapse by id (last writer wins).

    Production merge_slices never calls this. TST-0158 uses it to prove that
    catalog.by_id last-wins hides colliding namespaces.
    """
    by_id: dict[str, dict[str, Any]] = {}
    for name, doc in named_docs:
        units, _key = extract_units(doc, name)
        for unit in units:
            uid = str(unit.get("id") or "")
            if uid:
                by_id[uid] = unit
    ids = sort_ids(by_id)
    return {
        "count": len(by_id),
        "ids": ids,
        "refused": False,
        "strategy": "last-wins",
    }


def _infer_array_key(paths: list[Path]) -> str:
    keys: set[str] = set()
    for path in paths:
        _units, key = load_slice(path)
        keys.add(key)
    if keys == {"items"}:
        return "items"
    return "work_units"


def _emit_json(payload: dict[str, Any], code: int) -> int:
    sys.stdout.write(json.dumps(payload, sort_keys=True, ensure_ascii=True) + "\n")
    return code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Merge catalog slices. Collision refuses and never renames."
    )
    parser.add_argument(
        "slices",
        nargs="*",
        help="slice JSON files (TST-0158 positional form)",
    )
    parser.add_argument(
        "--slices",
        dest="slices_dir",
        default=None,
        help="directory of *.json slices (CC-0008 form)",
    )
    parser.add_argument("--output", "-o", default=None, help="merged catalog path")
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="required to overwrite command-center/WORK-UNIT-CATALOG.json",
    )
    parser.add_argument(
        "--allocation",
        default=None,
        help="path to id-namespace-allocation.json",
    )
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="apply the CC-0001 armed completeness gate to every merged unit",
    )
    args = parser.parse_args(argv)

    paths = [Path(p) for p in args.slices]
    if args.slices_dir:
        paths.extend(discover_slice_paths(Path(args.slices_dir)))
    if not paths:
        parser.error("no slice files given")

    output = Path(args.output) if args.output else None
    if (
        output is not None
        and output.resolve() == LIVE_CATALOG.resolve()
        and not args.in_place
    ):
        print(
            "refusing to overwrite live WORK-UNIT-CATALOG.json without --in-place",
            file=sys.stderr,
        )
        return 2

    try:
        allocation = load_allocation(args.allocation) if args.allocation else load_allocation()
        array_key = _infer_array_key(paths)
        units = merge_slices(
            paths,
            allocation=allocation,
            require_complete=args.require_complete,
        )
    except MergeError as exc:
        payload: dict[str, Any] = {
            "refused": True,
            "reason": exc.kind,
            "detail": exc.detail,
            "paths": exc.paths,
        }
        if exc.kind == "id-collision":
            payload["collision_ids"] = exc.collision_ids
            payload["collision_count"] = len(exc.collision_ids)
            return _emit_json(payload, 2)
        return _emit_json(payload, 1)

    ids = [str(u.get("id")) for u in units]
    if output is not None:
        write_canonical(output, {array_key: units})
    return _emit_json(
        {
            "refused": False,
            "count": len(units),
            "ids": ids,
            "array_key": array_key,
            "wrote": output.as_posix() if output is not None else None,
        },
        0,
    )


if __name__ == "__main__":
    raise SystemExit(main())
