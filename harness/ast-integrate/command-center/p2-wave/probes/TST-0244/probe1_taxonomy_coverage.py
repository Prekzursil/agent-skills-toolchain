#!/usr/bin/env python3
"""Probe 1: every closed taxonomy class is triggered and scores 3/3."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from gates.failure_taxonomy import TAXONOMY_CLASSES, measure_coverage  # noqa: E402

UNIT = "TST-0244"
RECEIPT = REPO / "command-center" / "receipts" / "TST-0244.json"
SENTINEL = "SUCCESS:TST-0244"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def receipt_ok() -> bool | None:
    if not RECEIPT.is_file() or RECEIPT.stat().st_size <= 0:
        return None
    text = RECEIPT.read_text(encoding="utf-8")
    doc = json.loads(text)
    state = str(doc.get("state") or "").upper()
    matrix = doc.get("coverage_matrix") or doc.get("matrix") or []
    if state in NOT_DELIVERING:
        return False
    if SENTINEL not in text:
        return False
    if not isinstance(matrix, list) or len(matrix) < len(TAXONOMY_CLASSES):
        return False
    return True


def main() -> int:
    report = measure_coverage(repo=REPO, execute_next=True)
    matrix = report["matrix"]
    rec = receipt_ok()
    ok = bool(report["pass"]) and rec is not False
    compact = [
        {
            "class": row["intended"],
            "classified": row["classified"],
            "match": row["match"],
            "score": row["rubric"]["score"],
            "next_command": row["next_command"],
            "inducer": (row["observation"] or {}).get("inducer"),
        }
        for row in matrix["rows"]
    ]
    payload = {
        "probe": "probe1-taxonomy-coverage",
        "unit_id": UNIT,
        "pass": ok,
        "method": "induce-classify-format-score",
        "data_field": "classified+rubric.score",
        "measurement_kind": "full-taxonomy-trigger-not-sample",
        "n_classes": matrix["n_classes"],
        "n_triggered": matrix["n_triggered"],
        "sampled": matrix["sampled"],
        "missing": matrix["missing"],
        "mismatches": matrix["mismatches"],
        "low_scores": matrix["low_scores"],
        "drift": matrix["drift"],
        "next_failed": report["next_commands"]["failed"],
        "rows": compact,
        "receipt_present": RECEIPT.is_file(),
        "receipt_ok": rec,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if matrix["sampled"]:
        return fail("coverage was sampled, not triggered")
    if matrix["n_triggered"] != len(TAXONOMY_CLASSES):
        return fail(f"n_triggered={matrix['n_triggered']}")
    if matrix["missing"] or matrix["mismatches"] or matrix["low_scores"] or matrix["drift"]:
        return fail(
            f"missing={matrix['missing']} mismatches={matrix['mismatches']} "
            f"low={matrix['low_scores']} drift={matrix['drift']}"
        )
    if report["next_commands"]["failed"]:
        return fail(f"next-commands-failed {report['next_commands']['failed']}")
    if rec is False:
        return fail("receipt does not match live coverage")
    print(
        f"triggered={matrix['n_triggered']}/{len(TAXONOMY_CLASSES)} "
        f"sampled={matrix['sampled']} next_ok={report['next_commands']['pass']}"
    )
    print(f"SUCCESS:{UNIT}-probe1 every taxonomy class triggered and scored 3/3")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
