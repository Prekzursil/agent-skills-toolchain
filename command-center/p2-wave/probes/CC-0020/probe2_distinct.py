#!/usr/bin/env python3
"""Probe 2: false-merge + error-direction + determinism on distinct set."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
GATE_PATH = REPO / "tools/command-center/mechanism_dedup_gate.py"
FIXTURES = PROBE / "fixtures/planted-mutants.json"
OUT_JSON = PROBE / "probe2-distinct.json"
OUT_RAW = PROBE / "probe2-distinct.raw.txt"


def _load_gate():
    spec = importlib.util.spec_from_file_location("mechanism_dedup_gate", GATE_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["mechanism_dedup_gate"] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    gate = _load_gate()
    fix = json.loads(FIXTURES.read_text(encoding="utf-8"))
    units = fix["distinct_units"]
    rep = gate.evaluate_distinct_set(units)
    det = gate.determinism_check(fix["seed"], fix["mutants"]["paraphrase"], runs=5)

    # Error-direction report: mutants + distinct disagreements
    error_rows = []
    per = gate.evaluate_mutants(fix["seed"], fix["mutants"])
    for cls, row in per.items():
        error_rows.append(
            {
                "pair": f"seed::{cls}",
                "expected": "duplicate",
                "predicted": row["verdict"],
                "error_direction": row["error_direction"],
            }
        )
    for d in rep["disagreements"]:
        error_rows.append(
            {
                "pair": f"{d['left_id']}::{d['right_id']}",
                "expected": "distinct",
                "predicted": d["verdict"],
                "error_direction": d["error_direction"],
            }
        )

    summary = {
        "ok": (
            len(units) >= 24
            and rep["false_merge_count"] == 0
            and det["deterministic"] is True
            and all(
                (e["error_direction"] in (None, "over-merge", "under-merge"))
                for e in error_rows
            )
        ),
        "unit_count": len(units),
        "pair_count": rep["pair_count"],
        "false_merge_count": rep["false_merge_count"],
        "contested_count": rep["contested_count"],
        "false_merges": rep["false_merges"],
        "error_direction_report": error_rows,
        "determinism": det,
        "unit_ids": [u["id"] for u in units],
    }
    text = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    OUT_JSON.write_text(text, encoding="utf-8")
    OUT_RAW.write_text(text, encoding="utf-8")
    print(text)
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
