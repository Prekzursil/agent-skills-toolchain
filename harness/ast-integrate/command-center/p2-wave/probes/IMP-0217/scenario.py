"""Load the colliding-internal-id fixture and run the Subworkflow executor."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SPEC_ROOT = REPO / "tools" / "agentspec"
if str(SPEC_ROOT) not in sys.path:
    sys.path.insert(0, str(SPEC_ROOT))

from agentspec.subworkflow_executor import (  # noqa: E402
    ExecuteOpts,
    Subworkflow,
    Task,
    Workflow,
    execute,
)

FIXTURE = HERE / "fixtures" / "colliding-internal-id.json"


def _node(raw: dict):
    kind = raw["kind"]
    if kind == "task":
        return Task(
            id=raw["id"],
            budget=int(raw["budget"]),
            write_name=raw.get("write_name", "out.txt"),
            write_from_param=raw.get("write_from_param", "label"),
        )
    if kind == "subworkflow":
        return Subworkflow(
            id=raw["id"],
            workflow_ref=raw["workflow_ref"],
            id_namespace=raw["id_namespace"],
            param_bindings=dict(raw.get("param_bindings") or {}),
        )
    raise ValueError(f"unknown node kind {kind!r}")


def _workflow(raw: dict) -> Workflow:
    return Workflow(id=raw["id"], nodes=tuple(_node(n) for n in raw["nodes"]))


def load_fixture(path: Path | None = None) -> tuple[Workflow, dict[str, Workflow], dict]:
    doc = json.loads((path or FIXTURE).read_text(encoding="utf-8"))
    parent = _workflow(doc["parent"])
    catalog = {k: _workflow(v) for k, v in doc["workflows"].items()}
    return parent, catalog, doc


def run_fixture(
    artifacts_root: Path,
    *,
    namespacing: bool = True,
    count_rollups_as_spend: bool = False,
    path: Path | None = None,
):
    parent, catalog, doc = load_fixture(path)
    result = execute(
        parent,
        catalog,
        artifacts_root,
        opts=ExecuteOpts(
            namespacing=namespacing,
            count_rollups_as_spend=count_rollups_as_spend,
        ),
    )
    return result, doc
