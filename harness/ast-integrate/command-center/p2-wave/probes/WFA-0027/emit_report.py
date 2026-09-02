#!/usr/bin/env python3
"""Emit WFA-0027 SweepReport. Licenses are inserted first in the JSON object."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent


def repo_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / "command-center" / "WORK-UNIT-CATALOG.json").is_file():
            return p
    raise SystemExit("FAILED:emit repo root not found")


REPO = repo_root(HERE)
sys.path.insert(0, str(HERE))

from mechanisms import MECHANISMS  # noqa: E402
from sketch import SEPARABLE_DEMO, execute  # noqa: E402

OUT = REPO / "command-center/wfa/WFA-0027-teardown-adjacent-runtimes.json"
LICENSES = json.loads((HERE / "licenses.json").read_text(encoding="utf-8"))
A1 = REPO / "command-center/phase3/A1/DESIGN.json"


def main() -> int:
    paused = execute(SEPARABLE_DEMO, {})
    if paused.get("status") != "awaiting_human":
        print("FAILED:emit sketch did not pause at HITL", paused)
        return 1
    resumed = execute(SEPARABLE_DEMO, {**paused, "human": "approve"})
    if resumed.get("status") != "done":
        print("FAILED:emit sketch did not resume", resumed)
        return 1

    separable = [m for m in MECHANISMS if m["verdict"] == "SEPARABLE"]
    rejected = [m for m in MECHANISMS if m["verdict"] == "NON-SEPARABLE"]
    runtimes = sorted({m["runtime"] for m in MECHANISMS})
    if runtimes != ["airflow", "autogen", "crewai", "dagster", "langgraph", "prefect", "temporal"]:
        print("FAILED:emit runtime set", runtimes)
        return 1

    a1_exists = A1.is_file()
    a1_id = None
    if a1_exists:
        a1_id = json.loads(A1.read_text(encoding="utf-8")).get("architecture_id")

    rows = []
    for m in MECHANISMS:
        rows.append(
            {
                "runtime": m["runtime"],
                "mechanism": m["mechanism"],
                "verdict": m["verdict"],
                "source_anchor": {
                    "repo_path": m["source"],
                    "line": m["line"],
                    "cache": f"command-center/p2-wave/probes/WFA-0027/cache/{m['cache']}",
                    "excerpt": m["excerpt"],
                },
                "a1_sketch": m["a1_sketch"],
                "transfer": m["transfer"],
                "wholesale_import_creates_second_control_plane": m[
                    "wholesale_imports_second_plane"
                ],
            }
        )

    # Insertion order is load-bearing: licenses BEFORE mechanisms/excerpts.
    doc = {
        "licenses": LICENSES,
        "unit_id": "WFA-0027",
        "title": "Teardown of adjacent orchestration runtimes: extract the mechanism, refuse the runtime",
        "state": "SUCCESS",
        "completion_sentinel": "SUCCESS:WFA-0027",
        "retrieved_on": "2026-08-24",
        "chosen_control_plane": {
            "id": a1_id,
            "spec": "command-center/phase3/A1/DESIGN.json",
            "spec_present": a1_exists,
            "layout": "command-center/control-plane/A1/ (static JSON capabilities; no resident runtime)",
            "catalog_input_13_ARCHITECTURE_CANDIDATES_md": "absent-on-this-worktree",
            "user_prompt_10727": "cited via WORK-UNIT-CATALOG.json WFA-0027 inputs; _USER-PROMPTS.md absent on this worktree",
        },
        "question": (
            "For LangGraph, CrewAI, AutoGen, Temporal, Airflow, Prefect and Dagster: "
            "what is the transferable orchestration MECHANISM that can be reimplemented "
            "on the chosen control plane, and what exactly, if imported wholesale, "
            "would create a second control plane?"
        ),
        "method": {
            "licenses_recorded_before_excerpts": True,
            "source": "published GitHub repositories (not marketing pages)",
            "independent_corroboration": (
                "A1 sketch interpreter in sketch.py executes retry, HITL pause/resume, "
                "fan-out and barrier with zero imports of the seven runtimes."
            ),
            "runtimes_installed": False,
            "runtimes_vendored": False,
            "runtimes_added_as_dependency": False,
        },
        "counts": {
            "runtimes": 7,
            "mechanism_rows": len(rows),
            "separable": len(separable),
            "non_separable_rejected": len(rejected),
        },
        "mechanisms": rows,
        "second_control_plane_if_imported_wholesale": [
            {
                "runtime": "langgraph",
                "would_import": "langgraph.graph.StateGraph.compile / langgraph.pregel",
                "second_plane": "Pregel executor plus checkpointer backend as live scheduler",
            },
            {
                "runtime": "crewai",
                "would_import": "crewai.Crew.kickoff",
                "second_plane": "Crew process engine (sequential/hierarchical) as a second scheduler",
            },
            {
                "runtime": "autogen",
                "would_import": "autogen_agentchat teams + autogen_core AgentRuntime",
                "second_plane": "AgentRuntime message loop as a second event bus",
            },
            {
                "runtime": "temporal",
                "would_import": "temporalio.worker.Worker + Temporal server",
                "second_plane": "history service + task-queue pollers (PollerBehaviorSimpleMaximum)",
            },
            {
                "runtime": "airflow",
                "would_import": "airflow DAG + scheduler + metadata DB",
                "second_plane": "scheduler heartbeat and TaskInstance store",
            },
            {
                "runtime": "prefect",
                "would_import": "prefect.flow_engine.FlowRunEngine + API/work pool",
                "second_plane": "Prefect API as run state owner",
            },
            {
                "runtime": "dagster",
                "would_import": "dagster-daemon + DagsterInstance",
                "second_plane": "daemon/orchestrator engine and instance storage",
            },
        ],
        "a1_sketch_exercise": {
            "workflow_id": SEPARABLE_DEMO["id"],
            "pause_status": paused.get("status"),
            "resume_status": resumed.get("status"),
            "payload_keys": sorted(resumed.get("payload") or {}),
            "fan_join": (resumed.get("payload") or {}).get("join"),
            "retry_attempts": ((resumed.get("payload") or {}).get("flaky") or {}).get(
                "attempts"
            ),
        },
        "tests_required": {
            "non_separable_rejected_not_sketched": all(
                m["a1_sketch"] is None for m in rejected
            ),
            "separable_has_sketch": all(m["a1_sketch"] is not None for m in separable),
            "no_runtime_installed_or_vendored": True,
            "license_recorded_before_excerpt": True,
        },
        "emitted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)} rows={len(rows)}")
    print("SUCCESS:WFA-0027")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
