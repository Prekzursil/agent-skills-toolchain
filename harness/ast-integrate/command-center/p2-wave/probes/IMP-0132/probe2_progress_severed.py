#!/usr/bin/env python3
"""Probe 2: PROGRESS stream is severed-stream; oracle bypass makes that test go red."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.dynamic_fanout import resolve_dynamic_fanout  # noqa: E402
from agentspec.oracle import TAXONOMY_SEVERED_STREAM, is_progress_stream  # noqa: E402
from agentspec.spec import DynamicFanOut, UnitTemplate  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures"


def _node() -> DynamicFanOut:
    return DynamicFanOut(
        id="fan-dyn",
        producer_unit="produce-items",
        item_path="result.items",
        unit_template=UnitTemplate(id="work-item"),
        max_cardinality=64,
    )


def main() -> int:
    failures: list[str] = []
    body = (FIX / "producer_progress.json").read_text(encoding="utf-8")
    node = _node()

    if not is_progress_stream(body):
        failures.append("fixture not classified as PROGRESS stream")

    honest = resolve_dynamic_fanout(node, body, oracle=True)
    if honest.reason != TAXONOMY_SEVERED_STREAM:
        failures.append(
            f"honest reason={honest.reason!r} expected={TAXONOMY_SEVERED_STREAM!r}"
        )
    if honest.verdict != "failed":
        failures.append(f"honest verdict={honest.verdict!r}")
    if honest.cardinality != 0 or honest.planned_units:
        failures.append("honest planned units from a PROGRESS stream")
    if honest.progress_stream is not True:
        failures.append("honest progress_stream flag false")
    if honest.schema_validated:
        failures.append("PROGRESS body claimed schema-validated")

    mutant = resolve_dynamic_fanout(node, body, oracle=False)
    mutant_severed = mutant.reason == TAXONOMY_SEVERED_STREAM
    mutant_kills_probe = (not mutant_severed) and mutant.cardinality == 7
    if mutant_severed:
        failures.append("oracle bypass still reported severed-stream (mutation not killed)")
    if mutant.cardinality != 7:
        failures.append(
            f"oracle bypass cardinality={mutant.cardinality} (decoy items not misread)"
        )

    ndjson = "\n".join(
        [
            json.dumps({"type": "PROGRESS", "pct": 10}),
            json.dumps({"type": "PROGRESS", "pct": 50}),
            json.dumps({"type": "PROGRESS", "pct": 90}),
        ]
    )
    nd = resolve_dynamic_fanout(node, ndjson, oracle=True)
    if nd.reason != TAXONOMY_SEVERED_STREAM:
        failures.append(f"ndjson reason={nd.reason!r}")

    report = {
        "probe": "probe2-progress-severed-stream",
        "unit_id": "IMP-0132",
        "taxonomy_reason": TAXONOMY_SEVERED_STREAM,
        "honest_reason": honest.reason,
        "honest_cardinality": honest.cardinality,
        "honest_progress_stream": honest.progress_stream,
        "mutant_reason": mutant.reason,
        "mutant_cardinality": mutant.cardinality,
        "mutant_severed_stream_test_goes_red": mutant_kills_probe,
        "ndjson_reason": nd.reason,
        "pass": not failures,
        "failures": failures,
    }
    print(json.dumps(report, sort_keys=True))
    if failures:
        print("FAILED:IMP-0132-probe2 " + "; ".join(failures))
        return 1
    print(
        "SUCCESS:IMP-0132-probe2 taxonomy reason severed-stream; "
        "oracle-bypass mutant goes red"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
