"""Live both-sides experiment: documented oracle vs estate IR walker."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import adapter
import control_plane
import documented
from graph_data import load_graph
from import_guard import assert_no_runtime


def last_write_tags(graph: dict, order: list[str]) -> list[str]:
    """Counterfactual: if operator.add were last-write, tags would be the last write."""
    by_id = {n["id"]: n for n in graph["nodes"]}
    last: list[str] = []
    for nid in order:
        w = (by_id[nid].get("writes") or {}).get("tags")
        if w is not None:
            last = list(w)
    return last


def concat_tags(graph: dict, order: list[str], initial: list | None = None) -> list[str]:
    out = list(initial or [])
    by_id = {n["id"]: n for n in graph["nodes"]}
    for nid in order:
        w = (by_id[nid].get("writes") or {}).get("tags")
        if w is not None:
            out.extend(list(w))
    return out


def run_case(case_name: str, tmp: Path | None = None) -> dict:
    graph = load_graph()
    trans = adapter.translate(graph)
    ir = trans["ir"]
    inputs = dict(graph["cases"][case_name])
    thread = f"wfa0049-{case_name}"
    own_tmp = tmp is None
    if tmp is None:
        tmpdir = TemporaryDirectory()
        tmp = Path(tmpdir.name)
    else:
        tmpdir = None
    try:
        store = tmp / "estate-checkpoints"
        doc_first = documented.run(graph, inputs=inputs, thread_id=thread, resume=False)
        est_first = control_plane.run(
            ir, inputs=inputs, thread_id=thread, store=store, resume=False
        )
        if doc_first["status"] != "interrupted" or est_first["status"] != "interrupted":
            return {
                "ok": False,
                "why": "expected interrupt_before on first invoke",
                "doc": doc_first,
                "estate": est_first,
            }
        doc_resume = documented.run(
            graph,
            inputs=inputs,
            thread_id=thread,
            checkpoint=doc_first["checkpoint"],
            resume=True,
        )
        est_resume = control_plane.run(
            ir, inputs=inputs, thread_id=thread, store=store, resume=True
        )
        wrong_thread = f"{thread}-other"
        doc_wrong = documented.run(graph, inputs=inputs, thread_id=wrong_thread, resume=False)
        est_wrong = control_plane.run(
            ir,
            inputs=inputs,
            thread_id=wrong_thread,
            store=store,
            resume=False,
        )

        full_doc = doc_first["stage_order"] + doc_resume["stage_order"]
        full_est = est_first["stage_order"] + est_resume["stage_order"]
        tags_est = est_resume["state"].get("tags")
        expected_concat = concat_tags(graph, full_est, initial=list(inputs.get("tags") or []))
        expected_last = last_write_tags(graph, full_est)
        flags_est = list(est_resume["state"].get("flags") or [])
        flags_doc = list(doc_resume["state"].get("flags") or [])
        flags_input = list(inputs.get("flags") or [])
        flags_not_silently_merged = flags_est == flags_input and flags_doc != flags_est

        ck_path = store / f"{thread}.json"
        ok = (
            full_doc == full_est
            and doc_first["stage_order"] == est_first["stage_order"]
            and doc_resume["stage_order"] == est_resume["stage_order"]
            and doc_first["interrupt_before"] == est_first["interrupt_before"] == "human_review"
            and doc_resume["status"] == est_resume["status"] == "completed"
            and tags_est == expected_concat
            and tags_est != expected_last
            and doc_wrong["stage_order"] == est_wrong["stage_order"] == doc_first["stage_order"]
            and ck_path.is_file()
            and flags_not_silently_merged
        )
        return {
            "ok": ok,
            "case": case_name,
            "documented_first": doc_first["stage_order"],
            "estate_first": est_first["stage_order"],
            "documented_resume": doc_resume["stage_order"],
            "estate_resume": est_resume["stage_order"],
            "documented_full": full_doc,
            "estate_full": full_est,
            "orders_equal": full_doc == full_est,
            "interrupt_node": est_first.get("interrupt_before"),
            "estate_tags": tags_est,
            "expected_concat_tags": expected_concat,
            "counterfactual_last_write_tags": expected_last,
            "reducer_discriminated": tags_est == expected_concat and tags_est != expected_last,
            "wrong_thread_restarts": doc_wrong["stage_order"] == doc_first["stage_order"],
            "checkpoint_present": ck_path.is_file(),
            "checkpoint_bytes": ck_path.stat().st_size if ck_path.is_file() else 0,
            "flags_not_silently_merged": flags_not_silently_merged,
            "flags_estate": flags_est,
            "flags_documented": flags_doc,
            "estate_final_state": est_resume["state"],
            "documented_final_state": doc_resume["state"],
        }
    finally:
        if own_tmp and tmpdir is not None:
            tmpdir.cleanup()


def mapping_complete(trans: dict, graph: dict) -> dict:
    mapped = {c["construct"]: c for c in trans["construct_map"]}
    required = []
    for n in graph["nodes"]:
        required.append(f"node.{n['id']}")
    for e in graph["edges"]:
        required.append(f"edge.{e['from']}->{e['to']}")
    for ce in graph["conditional_edges"]:
        required.append(f"conditional_edges.{ce['source']}.{ce['path']}")
    for ch in graph["state_schema"]:
        required.append(f"state.{ch['key']}.reducer={ch['reducer']}")
    for nid in graph["compile"].get("interrupt_before") or []:
        required.append(f"compile.interrupt_before.{nid}")
    required.append("compile.checkpointer.mechanism")
    missing = [r for r in required if r not in mapped]
    unstatused = [
        r
        for r in required
        if r in mapped and mapped[r]["status"] not in {"MAPPED", "NON-TRANSFERABLE"}
    ]
    custom = [
        row
        for row in trans["lossy_field_ledger"]
        if "unique_append" in str(row.get("source_reducer") or row.get("source_construct") or "")
    ]
    return {
        "ok": not missing and not unstatused and len(custom) >= 1,
        "missing": missing,
        "unstatused": unstatused,
        "custom_reducer_ledger_rows": len(custom),
        "construct_count": len(trans["construct_map"]),
        "ledger_count": len(trans["lossy_field_ledger"]),
    }


def live_bundle() -> dict:
    guard = assert_no_runtime()
    graph = load_graph()
    trans = adapter.translate(graph)
    m = mapping_complete(trans, graph)
    urgent = run_case("urgent")
    normal = run_case("normal")
    ok = bool(guard["ok"] and m["ok"] and urgent["ok"] and normal["ok"])
    return {
        "ok": ok,
        "import_guard": guard,
        "mapping": m,
        "urgent": urgent,
        "normal": normal,
        "ir": trans["ir"],
        "construct_map": trans["construct_map"],
        "lossy_field_ledger": trans["lossy_field_ledger"],
    }
