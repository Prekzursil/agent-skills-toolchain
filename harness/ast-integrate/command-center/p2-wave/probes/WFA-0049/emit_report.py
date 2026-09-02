#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0049-adapter-langgraph.json from live runs."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import experiment  # noqa: E402
from graph_data import load_graph, load_quotes  # noqa: E402

OUT = REPO / "command-center/wfa/WFA-0049-adapter-langgraph.json"
SENTINEL = "SUCCESS:WFA-0049"


def main() -> int:
    live = experiment.live_bundle()
    if not live["ok"]:
        print("FAILED:WFA-0049 emit live bundle not ok")
        print(json.dumps({k: live[k] for k in ("import_guard", "mapping", "urgent", "normal") if k in live}, indent=2)[:4000])
        return 1
    graph = load_graph()
    quotes = load_quotes()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    dep_wfa0044 = (REPO / "command-center/wfa/WFA-0044-workflow-ir-spec.json").is_file()
    dep_wfa0027 = (REPO / "command-center/wfa/WFA-0027-teardown-adjacent-runtimes.json").is_file()
    schema = REPO / "command-center/wfa/schema/wfa-schema-pack.json"
    doc = {
        "record_type": "AdapterConformanceReport",
        "id": "WFA-0049",
        "unit_id": "WFA-0049",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "completion_sentinel": SENTINEL,
        "title": "Adapter: LangGraph state-graph semantics to IR (mechanism only, no runtime import)",
        "adapter": {
            "id": "langgraph-state-graph",
            "source_runtime": "LangGraph StateGraph",
            "imported": False,
            "vendored": False,
            "worked_from": "published source and docs",
        },
        "license": quotes["license"],
        "dependencies_on_this_tree": {
            "WFA-0044-workflow-ir-spec": dep_wfa0044,
            "WFA-0027-teardown-adjacent-runtimes": dep_wfa0027,
            "WFA-0001-schema-pack": schema.is_file(),
            "note": (
                "Official WorkflowIR and teardown artifacts are absent. This unit "
                "reads published LangGraph source/docs directly and emits the catalog "
                "IR surface. Absence of those files is recorded, not filled with a fake mapping."
            ),
        },
        "schema": {
            "declared": "command-center/wfa/schema/wfa-schema-pack.json#/$defs/AdapterConformanceReport",
            "pack_present": schema.is_file(),
        },
        "worked_graph": {
            "id": graph["id"],
            "path": "command-center/p2-wave/probes/WFA-0049/fixtures/worked-graph.json",
            "nodes": [n["id"] for n in graph["nodes"]],
            "interrupt_before": graph["compile"]["interrupt_before"],
            "checkpointer_class_not_imported": graph["compile"]["checkpointer"],
        },
        "ir": live["ir"],
        "construct_map": live["construct_map"],
        "lossy_field_ledger": live["lossy_field_ledger"],
        "runtime_import": live["import_guard"],
        "control_plane_execution": {
            "plane": "estate sequential IR walker (command-center/p2-wave/probes/WFA-0049/control_plane.py)",
            "independent_oracle": "published Pregel/reducer/interrupt_before walker (documented.py)",
            "urgent": {
                "inputs": graph["cases"]["urgent"],
                "documented_order": live["urgent"]["documented_full"],
                "estate_order": live["urgent"]["estate_full"],
                "orders_equal": live["urgent"]["orders_equal"],
                "paused_before": live["urgent"]["interrupt_node"],
                "resume_stages": live["urgent"]["estate_resume"],
            },
            "normal": {
                "inputs": graph["cases"]["normal"],
                "documented_order": live["normal"]["documented_full"],
                "estate_order": live["normal"]["estate_full"],
                "orders_equal": live["normal"]["orders_equal"],
                "paused_before": live["normal"]["interrupt_node"],
                "resume_stages": live["normal"]["estate_resume"],
            },
        },
        "resume_case": {
            "tested": True,
            "not_asserted": True,
            "same_thread_continues": live["urgent"]["estate_resume"],
            "wrong_thread_restarts": live["urgent"]["wrong_thread_restarts"],
            "checkpoint_present": live["urgent"]["checkpoint_present"],
            "checkpoint_bytes": live["urgent"]["checkpoint_bytes"],
        },
        "reducer_both_states": {
            "operator.add_concat": live["urgent"]["expected_concat_tags"],
            "counterfactual_last_write": live["urgent"]["counterfactual_last_write_tags"],
            "measured_estate_tags": live["urgent"]["estate_tags"],
            "discriminated": live["urgent"]["reducer_discriminated"],
            "custom_unique_append_not_silently_applied": live["urgent"]["flags_not_silently_merged"],
        },
        "tests": {
            "no_langgraph_import_or_vendor": live["import_guard"]["ok"],
            "unexpressible_reducers_in_ledger": live["mapping"]["custom_reducer_ledger_rows"] >= 1,
            "checkpointer_resume_measured": live["urgent"]["ok"] and live["normal"]["ok"],
            "mapping_complete": live["mapping"]["ok"],
        },
        "evidence": [
            {
                "id": "A",
                "requirement": "worked graph translated to IR with each construct mapped or NON-TRANSFERABLE",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/WFA-0049/adapter.py",
            },
            {
                "id": "B",
                "requirement": "IR control-flow executed on estate control plane; stage order compared to documented LangGraph order",
                "verdict": "CONFIRMED",
                "urgent_orders_equal": live["urgent"]["orders_equal"],
                "normal_orders_equal": live["normal"]["orders_equal"],
            },
        ],
        "generated_at": now,
        "SENTINEL": SENTINEL,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO).as_posix()} ok={live['ok']}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
