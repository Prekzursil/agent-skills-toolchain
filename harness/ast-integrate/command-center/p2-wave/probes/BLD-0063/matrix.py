"""Coverage matrix: receipts on disk, not catalog intent."""
from __future__ import annotations

import json
from pathlib import Path

from questions import (
    ELEVEN,
    INPUT_IDS,
    SELF_ID,
    is_meta,
    load_catalog_units,
    parse_tag,
    planned_by_question,
)
from verdicts import classify_unit, collect_verdicts, receipt_question


def receipt_path(receipts_dir: Path, uid: str) -> Path:
    return receipts_dir / f"{uid}.json"


def read_receipt(path: Path) -> tuple[dict | None, bool, bool]:
    if not path.is_file() or path.stat().st_size <= 0:
        return None, False, True
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, False, False
    if not isinstance(doc, dict):
        return None, False, False
    return doc, True, False


def compute_matrix(
    catalog_path: Path,
    receipts_dir: Path,
    extra_exclude: frozenset[str] | None = None,
) -> dict:
    exclude = {SELF_ID} | set(extra_exclude or ())
    catalog_units = load_catalog_units(catalog_path)
    planned = planned_by_question(catalog_units)

    receipts_read = 0
    missing: list[str] = []
    unparseable: list[str] = []
    uncontrolled: list[str] = []
    per_q: dict[str, list[dict]] = {label: [] for _, label in ELEVEN}

    for uid in INPUT_IDS:
        if uid in exclude:
            continue
        path = receipt_path(receipts_dir, uid)
        doc, parse_ok, empty_file = read_receipt(path)
        if empty_file and doc is None and not path.is_file():
            missing.append(uid)
            continue
        if not parse_ok:
            unparseable.append(uid)
            uncontrolled.append(uid)
            continue
        receipts_read += 1
        assert doc is not None
        unit = catalog_units.get(uid) or {}
        catalog_tag = parse_tag(str(unit.get("question_or_target") or ""))
        if is_meta(catalog_tag) and not doc.get("phase13_question"):
            continue
        question = receipt_question(doc, catalog_tag)
        verdicts = collect_verdicts(doc)
        klass = classify_unit(verdicts, True, False)
        if klass == "empty":
            uncontrolled.append(uid)
        if question is None:
            continue
        try:
            stored = str(
                path.resolve().relative_to(receipts_dir.resolve().parent.parent)
            ).replace("\\", "/")
        except ValueError:
            stored = str(path).replace("\\", "/")
        per_q[question].append(
            {
                "id": uid,
                "path": stored,
                "verdicts": verdicts,
                "class": klass,
            }
        )

    questions_out = []
    uncovered: list[str] = []
    covered: list[str] = []
    for qid, label in ELEVEN:
        rows = per_q[label]
        evidence = [r for r in rows if r["class"] == "evidence-bearing"]
        not_checked = [r for r in rows if r["class"] == "not-checked-only"]
        empty_rows = [r for r in rows if r["class"] == "empty"]
        if evidence:
            coverage = "COVERED"
            reason = (
                f"{len(evidence)} receipt(s) carry CONFIRMED or REFUTED "
                f"({', '.join(r['id'] for r in evidence)})"
            )
            covered.append(label)
        elif not_checked and not evidence:
            coverage = "UNCOVERED"
            reason = (
                "covered only by NOT-CHECKED/PARTIAL units: "
                + ", ".join(r["id"] for r in not_checked)
            )
            uncovered.append(label)
        elif empty_rows:
            coverage = "UNCOVERED"
            reason = (
                "receipts present but uncontrolled or empty: "
                + ", ".join(r["id"] for r in empty_rows)
            )
            uncovered.append(label)
        else:
            coverage = "UNCOVERED"
            reason = (
                "no receipt on disk for any planned unit "
                f"({len(planned.get(label) or [])} planned)"
            )
            uncovered.append(label)
        questions_out.append(
            {
                "id": qid,
                "question": label,
                "planned_units": list(planned.get(label) or []),
                "receipt_units": rows,
                "coverage": coverage,
                "reason": reason,
            }
        )

    return {
        "receipts_expected": len(INPUT_IDS),
        "receipts_read": receipts_read,
        "receipts_missing": missing,
        "receipts_unparseable": unparseable,
        "uncontrolled_or_empty_units": uncontrolled,
        "questions": questions_out,
        "uncovered_questions": uncovered,
        "covered_questions": covered,
        "self_reference_excluded": True,
        "self_id": SELF_ID,
        "catalog_path": str(catalog_path).replace("\\", "/"),
        "receipts_dir": str(receipts_dir).replace("\\", "/"),
    }


MATRIX_FIELD_KEYS = (
    "uncovered_questions",
    "covered_questions",
    "receipts_read",
    "receipts_expected",
    "questions",
    "cells",
    "self_reference_excluded",
    "uncontrolled_or_empty_units",
    "receipts_missing",
    "receipts_unparseable",
)


def artifact_matrix_fields(doc: dict) -> dict:
    """Read matrix fields from report (receipt_core) or the document root."""
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    out: dict = {}
    for key in MATRIX_FIELD_KEYS:
        if key in report:
            out[key] = report[key]
        elif key in doc:
            out[key] = doc[key]
        else:
            out[key] = None
    return out


def question_cells(matrix: dict) -> list[dict]:
    """Schema cells for the eleven Phase 13 questions.

    EXERCISED means at least one CONFIRMED or REFUTED receipt for that
    question. NEVER-TESTED means no such evidence-bearing verdict on disk.
    Domain verdicts on sibling receipts (EXERCISED, APPROVED-DROP, MERGE)
    do not satisfy BLD-0063's CONFIRMED/REFUTED rule.
    """
    cells: list[dict] = []
    for row in matrix["questions"]:
        covered = row["coverage"] == "COVERED"
        cells.append(
            {
                "id": row["id"],
                "semantic": f"Phase 13 question: {row['question']}",
                "verdict": "EXERCISED" if covered else "NEVER-TESTED",
                "code_path": (
                    "command-center/p2-wave/probes/BLD-0063/matrix.py:"
                    "compute_matrix"
                ),
                "evidence": row["reason"],
                "fixture": "command-center/receipts",
                "named_error": None,
            }
        )
    return cells


def write_scratch_receipt(
    receipts_dir: Path,
    uid: str,
    question: str,
    verdicts: list[str],
    extra: dict | None = None,
) -> Path:
    receipts_dir.mkdir(parents=True, exist_ok=True)
    claims = [
        {
            "id": f"c{i}",
            "claim": f"{uid} answers {question}",
            "verdict": v,
            "anchor": "scratch-receipt",
        }
        for i, v in enumerate(verdicts, 1)
    ]
    doc = {
        "unit_id": uid,
        "phase13_question": question,
        "state": "SUCCESS",
        "claims": claims,
    }
    if extra:
        doc.update(extra)
    path = receipt_path(receipts_dir, uid)
    path.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    return path
