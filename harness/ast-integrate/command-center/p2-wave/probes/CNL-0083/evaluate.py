#!/usr/bin/env python3
"""Bind proof_of_impossibility from an on-disk record + visit ledger.

The single-term expression `proof_of_impossibility == true` is evaluated
against that binding. Mid-turn writes are invisible: evaluation reads the
files present at call time (end-of-round snapshot for this unit).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from a10_grammar import UNIT_EXPRESSION, eval_source
from record import validate

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
EXPR = UNIT_EXPRESSION


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_dir(path: Path) -> dict[str, Any]:
    record_path = path / "record.json"
    visits_path = path / "visits.json"
    present = {
        "record.json": record_path.is_file(),
        "visits.json": visits_path.is_file(),
    }
    if not present["record.json"]:
        verdict = {
            "metric": False,
            "fires": False,
            "reason": "record-absent",
            "coverage": 0,
            "cardinality": 0,
        }
        bindings = {"proof_of_impossibility": False}
        value = eval_source(EXPR, bindings)
        return {
            "dir": path.name,
            "on_disk": present,
            "verdict": verdict,
            "bindings": bindings,
            "expression": EXPR,
            "value": value,
            "fires": value is True,
            "silent": value is False,
        }
    record = load_json(record_path)
    visits_doc = load_json(visits_path) if visits_path.is_file() else {}
    visits = visits_doc.get("visits") if isinstance(visits_doc, dict) else None
    if visits is None:
        visits = []
        verdict = {
            "metric": False,
            "fires": False,
            "reason": "visit-ledger-absent",
            "coverage": 0,
            "cardinality": 0,
        }
    else:
        verdict = validate(record, visits)
    bindings = {"proof_of_impossibility": bool(verdict["metric"])}
    value = eval_source(EXPR, bindings)
    return {
        "dir": path.name,
        "on_disk": present,
        "record_path": str(record_path),
        "visits_path": str(visits_path) if visits_path.is_file() else None,
        "verdict": verdict,
        "bindings": bindings,
        "expression": EXPR,
        "value": value,
        "fires": value is True,
        "silent": value is False,
        "claim": record.get("claim") if isinstance(record, dict) else None,
    }


def run_named_fixtures() -> dict[str, Any]:
    names = (
        "fire",
        "silent-search",
        "silent-unfalsifiable",
        "silent-circular",
    )
    rows = {name: evaluate_dir(FIXTURES / name) for name in names}
    fire = rows["fire"]["fires"] is True
    silent_search = rows["silent-search"]["silent"] is True
    silent_unfalsifiable = rows["silent-unfalsifiable"]["silent"] is True
    silent_circular = rows["silent-circular"]["silent"] is True
    both_states = fire and silent_search
    return {
        "expression": EXPR,
        "fixtures": rows,
        "both_states": {
            "fires_on_exhaustive": fire,
            "silent_on_unsuccessful_search": silent_search,
            "pass": both_states,
        },
        "extra_silents": {
            "unfalsifiable": silent_unfalsifiable,
            "circular": silent_circular,
        },
        "detector_measures": fire != (not silent_search) or both_states,
    }


if __name__ == "__main__":
    import json as _json

    doc = run_named_fixtures()
    print(_json.dumps(doc["both_states"], indent=2))
    for name, row in doc["fixtures"].items():
        v = row["verdict"]
        print(
            f"fixture={name} fires={row['fires']} silent={row['silent']} "
            f"reason={v['reason']} coverage={v.get('coverage')}/{v.get('cardinality')}"
        )
    ok = (
        doc["both_states"]["pass"]
        and doc["extra_silents"]["unfalsifiable"]
        and doc["extra_silents"]["circular"]
    )
    raise SystemExit(0 if ok else 1)
