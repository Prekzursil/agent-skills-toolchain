#!/usr/bin/env python3
"""Benchmark harness with mandatory non-empty-input control (TST-0105)."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Callable

REASON_EMPTY = "empty-input"
VALUE_TOKEN = "value_ms="
N_TOKEN = "n_inputs="
HISTORICAL_EMPTY_GREENS = ("router-eval-empty", "legacy-empty")


def default_work(inputs: list[Any]) -> float:
    n = 0
    for item in inputs:
        n += len(str(item))
    time.sleep(0)
    return float(n + 1)


def measure(name: str, inputs: list[Any], work: Callable[[list[Any]], Any] | None = None) -> dict[str, Any]:
    work = work or default_work
    n = len(inputs)
    if n == 0:
        printed = f"{name} {REASON_EMPTY} n_inputs=0"
        return {
            "name": name,
            "ok": False,
            "value_ms": None,
            "n_inputs": 0,
            "reason": REASON_EMPTY,
            "printed": printed,
            "work_invoked": False,
        }
    t0 = time.perf_counter()
    work(inputs)
    ms = (time.perf_counter() - t0) * 1000.0
    printed = f"{name} {VALUE_TOKEN}{ms:.3f} {N_TOKEN}{n}"
    return {
        "name": name,
        "ok": True,
        "value_ms": ms,
        "n_inputs": n,
        "reason": "",
        "printed": printed,
        "work_invoked": True,
    }


def naive_measure(name: str, inputs: list[Any]) -> dict[str, Any]:
    t0 = time.perf_counter()
    time.sleep(0)
    ms = max((time.perf_counter() - t0) * 1000.0, 0.01)
    printed = f"{name} {VALUE_TOKEN}{ms:.3f}"
    return {"name": name, "ok": True, "value_ms": ms, "n_inputs": None, "printed": printed}


def json_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": row.get("name"),
        "ok": row.get("ok"),
        "value_ms": row.get("value_ms"),
        "n_inputs": row.get("n_inputs"),
        "reason": row.get("reason"),
        "printed": row.get("printed"),
    }


def measure_cases(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for c in cases:
        inputs = list(c.get("inputs") or [])
        rows.append(measure(str(c.get("name") or "case"), inputs))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases-json", type=Path)
    ap.add_argument("--inputs-json", type=Path)
    ap.add_argument("--name", default="")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    cases = []
    if args.inputs_json and args.inputs_json.is_file():
        raw = json.loads(args.inputs_json.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            inputs = raw
        elif isinstance(raw, dict) and "inputs" in raw:
            inputs = list(raw.get("inputs") or [])
        else:
            inputs = []
        cases = [{"name": args.name or "cli", "inputs": inputs}]
    elif args.cases_json and args.cases_json.is_file():
        doc = json.loads(args.cases_json.read_text(encoding="utf-8"))
        if isinstance(doc, list):
            cases = doc
        else:
            cases = list(doc.get("cases") or doc.get("rows") or [])
    rows = []
    any_fail = False
    for c in cases:
        name = str(c.get("name") or "case")
        inputs = list(c.get("inputs") or [])
        row = measure(name, inputs)
        rows.append(row)
        if not row["ok"]:
            any_fail = True
        if not args.json:
            print(row["printed"])
    if args.json:
        print(json.dumps({"rows": [json_row(r) for r in rows]}, indent=2))
    return 1 if any_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
