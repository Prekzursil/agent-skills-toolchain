#!/usr/bin/env python3
"""Compute per-class / per-mode coverage from emitted records only.

A unit that planned a class in its catalog row but never cited one in
its output counts as not-covered. Blind spots are draft work-unit
definitions, not prose.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from canon import RESEARCH_MODES, SOURCE_CLASSES
from extract import cited_from_record

REPO = Path(__file__).resolve().parents[3]


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def load_emitted_records(
    paths: Iterable[Path],
) -> list[tuple[str, Path, Any, str]]:
    """Return (unit_id, path, doc, status) for each candidate output.

    status is 'parsed' | 'absent' | 'unparseable' | 'empty'.
    Catalog plan rows are never loaded here.
    """
    out: list[tuple[str, Path, Any, str]] = []
    for path in paths:
        uid = path.stem
        if not path.is_file():
            out.append((uid, path, None, "absent"))
            continue
        if path.stat().st_size <= 0:
            out.append((uid, path, None, "empty"))
            continue
        doc = _load_json(path)
        if not isinstance(doc, (dict, list)):
            out.append((uid, path, None, "unparseable"))
            continue
        out.append((uid, path, doc, "parsed"))
    return out


def catalog_res_bucket(catalog: dict) -> list[dict]:
    rows = []
    for unit in catalog.get("work_units") or []:
        if not isinstance(unit, dict):
            continue
        uid = str(unit.get("id") or "")
        if not uid.startswith("RES-"):
            continue
        try:
            n = int(uid.split("-", 1)[1])
        except ValueError:
            continue
        if 1 <= n <= 127:
            rows.append(unit)
    rows.sort(key=lambda u: u["id"])
    return rows


def live_output_paths(repo: Path, catalog: dict) -> list[tuple[str, Path]]:
    pairs = []
    for unit in catalog_res_bucket(catalog):
        rel = str(unit.get("output_path") or "").replace("\\", "/")
        pairs.append((unit["id"], repo / rel if rel else repo / f"command-center/research/{unit['id']}.json"))
    return pairs


def _empty_counts() -> dict[str, list[str]]:
    return defaultdict(list)


def coverage_from_docs(
    docs: list[tuple[str, Any]],
    *,
    expected_units: list[str] | None = None,
) -> dict[str, Any]:
    class_units: dict[str, list[str]] = _empty_counts()
    mode_units: dict[str, list[str]] = _empty_counts()
    per_unit: list[dict[str, Any]] = []
    parsed = 0
    for uid, doc in docs:
        if doc is None:
            per_unit.append(
                {
                    "unit_id": uid,
                    "emitted": False,
                    "classes": [],
                    "modes": [],
                    "planned_fields_ignored": [],
                }
            )
            continue
        cited = cited_from_record(doc, unit_id=uid)
        parsed += 1
        per_unit.append(
            {
                "unit_id": uid,
                "emitted": True,
                "classes": cited["classes"],
                "modes": cited["modes"],
                "planned_fields_ignored": cited["planned_fields_ignored"],
            }
        )
        for cls in cited["classes"]:
            if uid not in class_units[cls]:
                class_units[cls].append(uid)
        for mode in cited["modes"]:
            if uid not in mode_units[mode]:
                mode_units[mode].append(uid)

    class_table = []
    for cls in SOURCE_CLASSES:
        units = sorted(class_units.get(cls, []))
        class_table.append(
            {
                "id": cls,
                "kind": "source-class",
                "unit_count": len(units),
                "unit_ids": units,
                "covered": len(units) > 0,
            }
        )
    mode_table = []
    for mode in RESEARCH_MODES:
        units = sorted(mode_units.get(mode, []))
        mode_table.append(
            {
                "id": mode,
                "kind": "research-mode",
                "unit_count": len(units),
                "unit_ids": units,
                "covered": len(units) > 0,
            }
        )

    expected = list(expected_units or [u["unit_id"] for u in per_unit])
    missing = [u for u in expected if u not in {r["unit_id"] for r in per_unit if r["emitted"]}]

    return {
        "class_count_spec": 16,
        "mode_count_spec": 12,
        "records_parsed": parsed,
        "units_expected": expected,
        "units_missing_emitted": missing,
        "classes": class_table,
        "modes": mode_table,
        "per_unit": per_unit,
    }


def _draft_unit(
    *,
    rank: int,
    kind: str,
    spec_id: str,
    unit_count: int,
    unit_ids: list[str],
) -> dict[str, Any]:
    if kind == "source-class":
        ident = f"RES-0128-BS-C-{rank:02d}"
        title = (
            f"Exercise source class '{spec_id}' which RES-0001..RES-0127 never cited"
            if unit_count == 0
            else f"Replicate source class '{spec_id}' beyond the single citing unit"
        )
        question = (
            f"Which independent, fetch-addressed sources in class '{spec_id}' "
            f"bear on the Phase-2 research bucket, and can a unit cite at least "
            f"one such source in its emitted record (not merely in its plan)?"
        )
        tests = [
            f"emitted output lists '{spec_id}' under source_classes_cited or citations[].source_class",
            "control: a catalog plan that names the class but cites none must not increment coverage",
            "lineage: each citation carries a URL or sha256 of fetched bytes",
        ]
    else:
        ident = f"RES-0128-BS-M-{rank:02d}"
        title = (
            f"Run research mode '{spec_id}' which RES-0001..RES-0127 never used"
            if unit_count == 0
            else f"Replicate research mode '{spec_id}' beyond the single using unit"
        )
        question = (
            f"What questions in this bucket require research mode '{spec_id}', "
            f"and can an emitted record demonstrate that mode was actually used "
            f"(research_modes_used / claims[].research_mode) rather than assigned?"
        )
        tests = [
            f"emitted output lists '{spec_id}' under research_modes_used or claims[].research_mode",
            "control: assigned_model_vendor_role.role in the catalog must not count as mode use",
        ]
    return {
        "kind": "draft-work-unit",
        "id": ident,
        "title": title,
        "question_or_target": question,
        "tests_required": tests,
        "rank": rank,
        "rank_key": {
            "gap": "uncovered" if unit_count == 0 else "single-unit",
            "kind": kind,
            "id": spec_id,
            "cited_unit_count": unit_count,
            "cited_unit_ids": unit_ids,
        },
        "evidence_requirement": (
            "Coverage is computed from the emitted record's citation fields, "
            "not from the unit definition. A planned class with zero citations "
            "is a blind spot, not coverage."
        ),
        "suggested_bucket": "RES second half",
        "dependencies": ["RES-0128"],
    }


def ranked_blind_spots(coverage: dict[str, Any]) -> list[dict[str, Any]]:
    """Every entry is a draft unit definition. Uncovered first, then singleton."""
    rows: list[tuple[int, str, str, int, list[str]]] = []
    for row in coverage["classes"]:
        if row["unit_count"] == 0:
            rows.append((0, "source-class", row["id"], 0, row["unit_ids"]))
        elif row["unit_count"] == 1:
            rows.append((1, "source-class", row["id"], 1, row["unit_ids"]))
    for row in coverage["modes"]:
        if row["unit_count"] == 0:
            rows.append((0, "research-mode", row["id"], 0, row["unit_ids"]))
        elif row["unit_count"] == 1:
            rows.append((1, "research-mode", row["id"], 1, row["unit_ids"]))
    rows.sort(key=lambda t: (t[0], 0 if t[1] == "source-class" else 1, t[2]))
    drafts = []
    for i, (_prio, kind, spec_id, count, uids) in enumerate(rows, start=1):
        drafts.append(
            _draft_unit(
                rank=i,
                kind=kind,
                spec_id=spec_id,
                unit_count=count,
                unit_ids=uids,
            )
        )
    return drafts


def is_draft_unit(entry: Any) -> bool:
    if not isinstance(entry, dict):
        return False
    if entry.get("kind") != "draft-work-unit":
        return False
    if not isinstance(entry.get("id"), str) or not entry["id"]:
        return False
    if not isinstance(entry.get("title"), str) or len(entry["title"]) < 12:
        return False
    q = entry.get("question_or_target")
    if not isinstance(q, str) or len(q) < 40:
        return False
    tests = entry.get("tests_required")
    if not isinstance(tests, list) or not tests:
        return False
    if not all(isinstance(t, str) and t.strip() for t in tests):
        return False
    return True


def control_singleton(coverage: dict[str, Any], class_id: str) -> dict[str, Any]:
    row = next((c for c in coverage["classes"] if c["id"] == class_id), None)
    count = int(row["unit_count"]) if row else -1
    return {
        "class_id": class_id,
        "unit_count": count,
        "unit_ids": list(row["unit_ids"]) if row else [],
        "pass": count == 1,
    }
