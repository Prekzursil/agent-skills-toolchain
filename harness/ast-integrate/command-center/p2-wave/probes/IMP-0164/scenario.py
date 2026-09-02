"""IMP-0164 fixtures: imported workflows standing in for IMP-0160..IMP-0162.

Those adapters are not present on this worktree. The documents here are the
typed imported-workflow shape they are contracted to emit, paired with the
original source text so spans are real offsets, not labels.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from foundry.stage_extract import (  # noqa: E402
    extract_imported,
    plant_unanchored,
    projection,
)

FIX = HERE / "fixtures"

# --- Control: Claude-Code saved workflow (.mjs), IMP-0160 shape -------------

CONTROL_SOURCE = """\
export default async function workflow({ agent, parallel }) {
  await agent({ name: "ingest", prompt: "read the ticket" });
  await parallel({
    name: "implementers",
    agents: [
      { name: "worker-a", prompt: "patch A" },
      { name: "worker-b", prompt: "patch B" },
    ],
  });
  await agent({ name: "critic", prompt: "review the diff", gate: "diff.ok" });
}
"""

CONTROL_URI = (
    "command-center/p2-wave/probes/IMP-0164/fixtures/control.workflow.mjs"
)

CONTROL_GOLD: list[dict[str, Any]] = [
    {
        "index": 0,
        "id": "ingest",
        "kind": "UNIT",
        "fan_out_degree": None,
        "gate": None,
        "inputs": ["ticket"],
        "outputs": ["ticket-record"],
    },
    {
        "index": 1,
        "id": "implementers",
        "kind": "FAN_OUT",
        "fan_out_degree": 2,
        "gate": None,
        "inputs": ["ticket-record"],
        "outputs": ["patches"],
    },
    {
        "index": 2,
        "id": "critic",
        "kind": "UNIT",
        "fan_out_degree": None,
        "gate": "diff.ok",
        "inputs": ["patches"],
        "outputs": ["verdict"],
    },
]

# --- Codex fan-out profile, IMP-0161 shape ---------------------------------

CODEX_SOURCE = """\
{
  "id": "wf.codex.scan",
  "steps": [
    {"id": "static-scan", "type": "unit"},
    {"id": "shard", "type": "fanout", "width": 3},
    {"id": "join", "type": "barrier"}
  ]
}
"""

CODEX_URI = "command-center/p2-wave/probes/IMP-0164/fixtures/codex.fanout.json"

# --- Declarative DAG, IMP-0162 shape ---------------------------------------

DAG_SOURCE = """\
id: wf.dag.control
nodes:
  - id: load
    type: unit
  - id: split
    type: fan-out
    width: 2
  - id: join
    type: barrier
"""

DAG_URI = "command-center/p2-wave/probes/IMP-0164/fixtures/dag.control.yaml"

EMPTY_SOURCE = "// no stages declared\n"
EMPTY_URI = "command-center/p2-wave/probes/IMP-0164/fixtures/empty.workflow.mjs"

UNMAPPED_SOURCE = 'await agent({ name: "weird-step", kind: "critik" });\n'
UNMAPPED_URI = "command-center/p2-wave/probes/IMP-0164/fixtures/unmapped.workflow.mjs"


def _span(source: str, token: str) -> dict[str, int]:
    start = source.find(token)
    if start < 0:
        raise ValueError(f"token {token!r} not in source")
    return {"start": start, "end": start + len(token)}


def control_imported() -> dict[str, Any]:
    src = CONTROL_SOURCE
    return {
        "id": "wf.control.foundry",
        "adapter": "IMP-0160",
        "spec_version": "foundry.imported-workflow.v1",
        "source_uri": CONTROL_URI,
        "nodes": [
            {
                "id": "ingest",
                "kind": "agent",
                "inputs": ["ticket"],
                "outputs": ["ticket-record"],
                "source_span": _span(src, '"ingest"'),
            },
            {
                "id": "implementers",
                "kind": "parallel",
                "unit_ids": ["worker-a", "worker-b"],
                "inputs": ["ticket-record"],
                "outputs": ["patches"],
                "source_span": _span(src, '"implementers"'),
            },
            {
                "id": "critic",
                "kind": "agent",
                "gate": "diff.ok",
                "inputs": ["patches"],
                "outputs": ["verdict"],
                "source_span": _span(src, '"critic"'),
            },
        ],
    }


def codex_imported() -> dict[str, Any]:
    src = CODEX_SOURCE
    return {
        "id": "wf.codex.scan",
        "adapter": "IMP-0161",
        "spec_version": "foundry.imported-workflow.v1",
        "source_uri": CODEX_URI,
        "nodes": [
            {
                "id": "static-scan",
                "kind": "unit",
                "source_span": _span(src, '"static-scan"'),
            },
            {
                "id": "shard",
                "kind": "fanout",
                "width": 3,
                "source_span": _span(src, '"shard"'),
            },
            {
                "id": "join",
                "kind": "barrier",
                "source_span": _span(src, '"join"'),
            },
        ],
    }


def dag_imported() -> dict[str, Any]:
    src = DAG_SOURCE
    return {
        "id": "wf.dag.control",
        "adapter": "IMP-0162",
        "spec_version": "foundry.imported-workflow.v1",
        "source_uri": DAG_URI,
        "nodes": [
            {
                "id": "load",
                "kind": "unit",
                "source_span": _span(src, "id: load"),
            },
            {
                "id": "split",
                "kind": "fan-out",
                "width": 2,
                "source_span": _span(src, "id: split"),
            },
            {
                "id": "join",
                "kind": "barrier",
                "source_span": _span(src, "id: join"),
            },
        ],
    }


def empty_imported() -> dict[str, Any]:
    return {
        "id": "wf.empty",
        "adapter": "IMP-0160",
        "spec_version": "foundry.imported-workflow.v1",
        "source_uri": EMPTY_URI,
        "nodes": [],
    }


def unmapped_imported() -> dict[str, Any]:
    src = UNMAPPED_SOURCE
    return {
        "id": "wf.unmapped",
        "adapter": "IMP-0160",
        "spec_version": "foundry.imported-workflow.v1",
        "source_uri": UNMAPPED_URI,
        "nodes": [
            {
                "id": "weird-step",
                "kind": "critik",
                "source_span": _span(src, '"weird-step"'),
            }
        ],
    }


def write_sources() -> None:
    FIX.mkdir(parents=True, exist_ok=True)
    (FIX / "control.workflow.mjs").write_text(CONTROL_SOURCE, encoding="utf-8")
    (FIX / "codex.fanout.json").write_text(CODEX_SOURCE, encoding="utf-8")
    (FIX / "dag.control.yaml").write_text(DAG_SOURCE, encoding="utf-8")
    (FIX / "empty.workflow.mjs").write_text(EMPTY_SOURCE, encoding="utf-8")
    (FIX / "unmapped.workflow.mjs").write_text(UNMAPPED_SOURCE, encoding="utf-8")
    (FIX / "control.gold.json").write_text(
        json.dumps(CONTROL_GOLD, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (FIX / "control.imported.json").write_text(
        json.dumps(control_imported(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def extract_control() -> dict[str, Any]:
    write_sources()
    return extract_imported(control_imported(), CONTROL_SOURCE, CONTROL_URI)


def extract_all() -> dict[str, dict[str, Any]]:
    write_sources()
    return {
        "control": extract_imported(control_imported(), CONTROL_SOURCE, CONTROL_URI),
        "codex": extract_imported(codex_imported(), CODEX_SOURCE, CODEX_URI),
        "dag": extract_imported(dag_imported(), DAG_SOURCE, DAG_URI),
        "empty": extract_imported(empty_imported(), EMPTY_SOURCE, EMPTY_URI),
        "unmapped": extract_imported(unmapped_imported(), UNMAPPED_SOURCE, UNMAPPED_URI),
        "unanchored": extract_imported(
            plant_unanchored(control_imported(), "critic"),
            CONTROL_SOURCE,
            CONTROL_URI,
        ),
    }


def gold_matches(extraction: dict[str, Any]) -> bool:
    return projection(extraction) == CONTROL_GOLD
