"""Load IMP-0196 workflow fixtures and run the progress analyzer."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PKG = REPO / "tools" / "agentspec"
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))

from agentspec.progress import analyze  # noqa: E402

FIXTURES = HERE / "fixtures"

CORPUS = (
    "mutual_wait.json",
    "safe_linear.json",
    "bounded_livelock.json",
    "converging_loop.json",
    "loop_body_deadlock.json",
    "subworkflow_mutual_wait.json",
    "per_unit_pipelines.json",
    "cohort_hang.json",
)


def load_workflow(name: str) -> dict[str, Any]:
    path = FIXTURES / name
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"fixture {name} is not an object")
    return data


def report_for(name: str) -> dict[str, Any]:
    wf = load_workflow(name)
    report = analyze(wf)
    report["fixture"] = name
    report["path"] = str((FIXTURES / name).relative_to(REPO).as_posix())
    return report


def corpus_reports() -> list[dict[str, Any]]:
    return [report_for(name) for name in CORPUS]
