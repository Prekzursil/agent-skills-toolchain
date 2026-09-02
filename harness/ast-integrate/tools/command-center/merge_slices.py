"""Catalog-slice merger: refuse duplicate ids, mechanism collisions, and index gaps.

IMP-0456. Last-wins on a colliding id is forbidden. A count-only merger that
accepts unique==declared while skipping an unfilled index is forbidden. The
written catalog, when a merge is accepted, is re-read for the count.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

ID_RE = re.compile(r"^([A-Z]{2,5})-(\d{4})$")
BLOCKER_DUPS = "duplicate-ids"
BLOCKER_MECH = "mechanism-collisions"
BLOCKER_GAPS = "index-gaps"
BLOCKER_COUNT = "count-mismatch-vs-declared"
BLOCKER_MALFORMED = "malformed-ids"
BLOCKER_UNREADABLE = "unreadable-slices"
BLOCKER_DECLARED_VOTES = "declared-count-disagreement"


def mechanism_fingerprint(unit: Mapping[str, Any]) -> str:
    """Normalized target text. Same id + different fingerprint = collision."""
    text = str(unit.get("question_or_target") or unit.get("target") or "")
    return " ".join(text.lower().split())


def _as_path(path: Path | str) -> Path:
    return path if isinstance(path, Path) else Path(path)


def load_slice(path: Path | str) -> tuple[list[dict[str, Any]], int | None]:
    """Load one slice file. Arrays and {work_units, declared_program_count} both work."""
    p = _as_path(path)
    try:
        raw = p.read_text(encoding="utf-8")
        doc = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"unreadable-slice:{p.name}:{type(exc).__name__}") from exc
    if isinstance(doc, list):
        units = [u for u in doc if isinstance(u, dict)]
        if len(units) != len(doc):
            raise ValueError(f"unreadable-slice:{p.name}:non-object-unit")
        return units, None
    if not isinstance(doc, dict):
        raise ValueError(f"unreadable-slice:{p.name}:root-{type(doc).__name__}")
    units = doc.get("work_units")
    if not isinstance(units, list):
        raise ValueError(f"unreadable-slice:{p.name}:missing-work_units")
    if any(not isinstance(u, dict) for u in units):
        raise ValueError(f"unreadable-slice:{p.name}:non-object-unit")
    declared = doc.get("declared_program_count")
    if declared is None:
        return list(units), None
    try:
        return list(units), int(declared)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"unreadable-slice:{p.name}:bad-declared") from exc


def _normalize_records(
    records: Iterable[Any],
) -> list[tuple[str, dict[str, Any]]]:
    out: list[tuple[str, dict[str, Any]]] = []
    for rec in records:
        if isinstance(rec, dict) and "unit" in rec:
            source = str(rec.get("source") or rec.get("path") or "")
            unit = rec["unit"]
            if isinstance(unit, dict):
                out.append((source, unit))
            continue
        if isinstance(rec, (tuple, list)) and len(rec) >= 2:
            unit = rec[1]
            if isinstance(unit, dict):
                out.append((str(rec[0]), unit))
    return out


def inspect_records(
    records: Iterable[Any],
    declared: int | None = None,
) -> dict[str, Any]:
    """Inspect already-loaded (source, unit) records. Does not write."""
    rows = _normalize_records(records)
    by_id: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    per_slice_counts: dict[str, int] = defaultdict(int)
    malformed: list[dict[str, str]] = []
    for source, unit in rows:
        per_slice_counts[source] += 1
        uid = str(unit.get("id") or "")
        if not ID_RE.match(uid):
            malformed.append({"id": uid, "source": source})
        by_id[uid].append((source, unit))

    duplicates: list[dict[str, Any]] = []
    mechanism_collisions: list[dict[str, Any]] = []
    for uid, occ in sorted(by_id.items(), key=lambda kv: kv[0]):
        if len(occ) > 1:
            sources = [s for s, _ in occ]
            duplicates.append(
                {
                    "id": uid,
                    "count": len(occ),
                    "sources": sorted(set(sources)),
                }
            )
        fingerprints = {(s, mechanism_fingerprint(u)) for s, u in occ}
        uniq = {fp for _s, fp in fingerprints if fp}
        if len(uniq) > 1:
            mechanism_collisions.append(
                {
                    "id": uid,
                    "sources": sorted({s for s, _fp in fingerprints}),
                    "fingerprints": sorted(uniq),
                }
            )

    by_prefix: dict[str, set[int]] = defaultdict(set)
    for uid in by_id:
        m = ID_RE.match(uid)
        if not m:
            continue
        by_prefix[m.group(1)].add(int(m.group(2), 10))

    gaps: list[dict[str, Any]] = []
    prefix_ranges: dict[str, dict[str, Any]] = {}
    for prefix, nums in sorted(by_prefix.items()):
        lo, hi = min(nums), max(nums)
        missing = [f"{prefix}-{n:04d}" for n in range(1, hi + 1) if n not in nums]
        prefix_ranges[prefix] = {
            "min": lo,
            "max": hi,
            "present": len(nums),
            "missing_count": len(missing),
        }
        if missing:
            gaps.append(
                {
                    "prefix": prefix,
                    "min": lo,
                    "max": hi,
                    "missing": missing,
                }
            )

    unique_count = len(by_id)
    blockers: list[str] = []
    if duplicates:
        blockers.append(BLOCKER_DUPS)
    if mechanism_collisions:
        blockers.append(BLOCKER_MECH)
    if gaps:
        blockers.append(BLOCKER_GAPS)
    if malformed:
        blockers.append(BLOCKER_MALFORMED)
    if declared is not None and unique_count != int(declared):
        blockers.append(BLOCKER_COUNT)

    per_slice = [
        {"source": name, "count": per_slice_counts[name]}
        for name in sorted(per_slice_counts)
    ]
    accepted = not blockers
    return {
        "accepted": accepted,
        "blockers": blockers,
        "declared_program_count": declared,
        "duplicates": duplicates,
        "gaps": gaps,
        "malformed_ids": malformed,
        "mechanism_collisions": mechanism_collisions,
        "per_slice": per_slice,
        "prefix_ranges": prefix_ranges,
        "unique_count_in_memory": unique_count,
        "wrote": False,
        "read_back_count": None,
    }


def read_back_count(path: Path | str) -> int:
    """Count work_units by reading the written file. Never trust in-memory length."""
    p = _as_path(path)
    doc = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(doc, list):
        return len(doc)
    if not isinstance(doc, dict):
        raise ValueError(f"read-back root is {type(doc).__name__}")
    units = doc.get("work_units")
    if not isinstance(units, list):
        raise ValueError("read-back missing work_units")
    return len(units)


def _canonical_catalog(units: Sequence[Mapping[str, Any]], declared: int | None) -> str:
    ordered = sorted((dict(u) for u in units), key=lambda u: str(u.get("id") or ""))
    doc: dict[str, Any] = {"work_units": ordered}
    if declared is not None:
        doc["declared_program_count"] = declared
    return json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def merge_paths(
    paths: Iterable[Path | str],
    output_path: Path | str | None = None,
    declared_program_count: int | None = None,
) -> dict[str, Any]:
    """Merge slice files. Writes only on a fully accepted merge. Never last-wins."""
    path_list = [_as_path(p) for p in paths]
    records: list[tuple[str, dict[str, Any]]] = []
    votes: list[int] = []
    unreadable: list[dict[str, str]] = []
    for path in path_list:
        try:
            units, declared = load_slice(path)
        except ValueError as exc:
            unreadable.append({"source": path.name, "reason": str(exc)})
            continue
        if declared is not None:
            votes.append(declared)
        for unit in units:
            records.append((path.name, unit))

    declared = declared_program_count
    if declared is None and votes:
        if len(set(votes)) == 1:
            declared = votes[0]
        else:
            declared = None

    report = inspect_records(records, declared)
    report["unreadable"] = unreadable
    if unreadable:
        report["accepted"] = False
        blockers = list(report.get("blockers") or [])
        if BLOCKER_UNREADABLE not in blockers:
            blockers.append(BLOCKER_UNREADABLE)
        report["blockers"] = blockers
    if declared_program_count is None and votes and len(set(votes)) > 1:
        report["accepted"] = False
        blockers = list(report.get("blockers") or [])
        if BLOCKER_DECLARED_VOTES not in blockers:
            blockers.append(BLOCKER_DECLARED_VOTES)
        report["blockers"] = blockers
        report["declared_votes"] = sorted(set(votes))

    report["wrote"] = False
    report["read_back_count"] = None
    if not report["accepted"] or output_path is None:
        return report

    by_id: dict[str, dict[str, Any]] = {}
    for source, unit in sorted(records, key=lambda r: r[0]):
        uid = str(unit.get("id") or "")
        by_id.setdefault(uid, unit)
    dest = _as_path(output_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        _canonical_catalog(list(by_id.values()), declared),
        encoding="utf-8",
        newline="\n",
    )
    back = read_back_count(dest)
    report["wrote"] = True
    report["read_back_count"] = back
    report["output_path"] = dest.as_posix()
    return report


def reconstruct_live_records(
    catalog_path: Path | str,
) -> tuple[list[tuple[str, dict[str, Any]]], int | None]:
    """Rebuild (source, unit) rows from work_units[]._source_slice_file."""
    p = _as_path(catalog_path)
    doc = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError("catalog root is not an object")
    meta = doc.get("work_units_meta") if isinstance(doc.get("work_units_meta"), dict) else {}
    declared = meta.get("target")
    if declared is None:
        declared = doc.get("declared_program_count")
    declared_i = int(declared) if declared is not None else None
    records: list[tuple[str, dict[str, Any]]] = []
    for unit in doc.get("work_units") or []:
        if not isinstance(unit, dict):
            continue
        source = str(unit.get("_source_slice_file") or "UNKNOWN.json")
        records.append((source, unit))
    return records, declared_i


def catalog_slice_paths(slice_dir: Path | str) -> list[Path]:
    d = _as_path(slice_dir)
    return sorted(p for p in d.glob("*.json") if p.is_file())
