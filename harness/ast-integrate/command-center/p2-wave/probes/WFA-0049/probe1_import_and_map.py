#!/usr/bin/env python3
"""Probe 1: no LangGraph import/vendor, mapping complete, reducer ledger, both-states."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import adapter  # noqa: E402
import experiment  # noqa: E402
from graph_data import load_graph  # noqa: E402
from import_guard import assert_no_runtime  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0049-adapter-langgraph.json"


def main() -> int:
    guard = assert_no_runtime()
    print(f"importable={guard['importable']} vendored={guard['vendored']} ok={guard['ok']}")
    if not guard["ok"]:
        print("FAILED:WFA-0049-probe1 langgraph present")
        return 1

    graph = load_graph()
    trans = adapter.translate(graph)
    mapping = experiment.mapping_complete(trans, graph)
    print(
        f"mapping_ok={mapping['ok']} missing={mapping['missing']} "
        f"ledger_custom={mapping['custom_reducer_ledger_rows']}"
    )
    if not mapping["ok"]:
        print("FAILED:WFA-0049-probe1 mapping incomplete")
        return 1

    statuses = {c["construct"]: c["status"] for c in trans["construct_map"]}
    if statuses.get("state.flags.reducer=custom:unique_append") != "NON-TRANSFERABLE":
        print("FAILED:WFA-0049-probe1 custom reducer not NON-TRANSFERABLE")
        return 1
    if statuses.get("state.tags.reducer=operator.add") != "MAPPED":
        print("FAILED:WFA-0049-probe1 operator.add not MAPPED")
        return 1
    if statuses.get("compile.interrupt_before.human_review") != "MAPPED":
        print("FAILED:WFA-0049-probe1 interrupt_before not MAPPED")
        return 1

    if not ART.is_file():
        print("FAILED:WFA-0049-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:WFA-0049-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:WFA-0049" not in text:
        print("FAILED:WFA-0049-probe1 sentinel absent")
        return 1
    if doc.get("runtime_import", {}).get("ok") is not True:
        print("FAILED:WFA-0049-probe1 artifact runtime_import not ok")
        return 1
    disc = (doc.get("reducer_both_states") or {}).get("discriminated")
    print(f"reducer_discriminated={disc}")
    if disc is not True:
        print("FAILED:WFA-0049-probe1 reducer both-states not discriminated")
        return 1
    if (doc.get("reducer_both_states") or {}).get("custom_unique_append_not_silently_applied") is not True:
        print("FAILED:WFA-0049-probe1 custom reducer silently applied")
        return 1
    print("SUCCESS:WFA-0049-probe1 import-guard mapping reducer-ledger")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
