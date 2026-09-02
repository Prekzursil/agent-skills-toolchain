#!/usr/bin/env python3
"""Probe 1: seven producer items plan exactly seven units; empty is explicit."""
from __future__ import annotations

import json
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.dynamic_fanout import resolve_dynamic_fanout  # noqa: E402
from agentspec.oracle import TAXONOMY_EMPTY_FANOUT  # noqa: E402
from agentspec.spec import DynamicFanOut, FanOut, UnitTemplate  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures"


def _load(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def _node(*, max_cardinality: int = 64) -> DynamicFanOut:
    return DynamicFanOut(
        id="fan-dyn",
        producer_unit="produce-items",
        item_path="result.items",
        unit_template=UnitTemplate(id="work-item", prompt_ref="work.md"),
        max_cardinality=max_cardinality,
    )


def main() -> int:
    failures: list[str] = []
    node = _node()

    try:
        node.max_cardinality = 99  # type: ignore[misc]
        failures.append("DynamicFanOut was mutable")
    except (FrozenInstanceError, AttributeError):
        pass

    static = FanOut(id="fan-static", unit_ids=("a", "b", "c"))
    if list(static.unit_ids) != ["a", "b", "c"]:
        failures.append("static FanOut lost unit ids")

    seven = resolve_dynamic_fanout(node, _load("producer_seven.json"), oracle=True)
    planned_ids = [u.id for u in seven.planned_units]
    expected_ids = [f"work-item:{i}" for i in range(7)]
    if seven.verdict != "planned":
        failures.append(f"seven verdict={seven.verdict!r}")
    if seven.cardinality != 7:
        failures.append(f"seven cardinality={seven.cardinality}")
    if planned_ids != expected_ids:
        failures.append(f"seven ids={planned_ids}")
    if seven.schema_validated is not True:
        failures.append("seven not schema-validated")
    if seven.reason is not None:
        failures.append(f"seven reason={seven.reason!r}")
    if [u.item for u in seven.planned_units] != [
        "alpha",
        "bravo",
        "charlie",
        "delta",
        "echo",
        "foxtrot",
        "golf",
    ]:
        failures.append("seven items mismatch")

    empty = resolve_dynamic_fanout(node, _load("producer_empty.json"), oracle=True)
    if empty.verdict != "empty-fanout":
        failures.append(f"empty verdict={empty.verdict!r} (silent pass)")
    if empty.reason != TAXONOMY_EMPTY_FANOUT:
        failures.append(f"empty reason={empty.reason!r}")
    if empty.cardinality != 0 or empty.planned_units != ():
        failures.append("empty produced units")
    if empty.schema_validated is not True:
        failures.append("empty skipped oracle")

    runaway = resolve_dynamic_fanout(_node(max_cardinality=5), _load("producer_runaway.json"))
    if runaway.cardinality != 5 or not runaway.capped:
        failures.append(
            f"runaway cardinality={runaway.cardinality} capped={runaway.capped}"
        )
    if runaway.source_cardinality != 20:
        failures.append(f"runaway source={runaway.source_cardinality}")

    missing = resolve_dynamic_fanout(node, None, oracle=True)
    if missing.verdict == "planned" or missing.verdict == "empty-fanout":
        failures.append("missing receipt treated as success")
    if not missing.reason:
        failures.append("missing receipt had no typed reason")

    garbage = resolve_dynamic_fanout(node, _load("producer_garbage.txt"), oracle=True)
    if garbage.verdict != "failed":
        failures.append(f"garbage verdict={garbage.verdict!r}")

    report = {
        "probe": "probe1-seven-items",
        "unit_id": "IMP-0132",
        "seven_cardinality": seven.cardinality,
        "seven_ids": planned_ids,
        "empty_verdict": empty.verdict,
        "empty_reason": empty.reason,
        "runaway_cardinality": runaway.cardinality,
        "runaway_capped": runaway.capped,
        "missing_reason": missing.reason,
        "garbage_reason": garbage.reason,
        "frozen": True,
        "pass": not failures,
        "failures": failures,
    }
    print(json.dumps(report, sort_keys=True))
    if failures:
        print("FAILED:IMP-0132-probe1 " + "; ".join(failures))
        return 1
    print("SUCCESS:IMP-0132-probe1 seven planned units and explicit empty-fanout")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
