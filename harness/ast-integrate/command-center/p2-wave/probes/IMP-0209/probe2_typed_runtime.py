#!/usr/bin/env python3
"""Probe 2: scout executes as a typed Workflow through the shared runtime.

Not a bespoke script: the document is JSON, the runtime refuses a .py file,
the live receipt passes the shared oracle, and AST shows execute() looping
over workflow stages.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _repo() -> Path:
    for p in [HERE, *HERE.parents]:
        if (p / "command-center" / "WORK-UNIT-CATALOG.json").is_file():
            return p
    return HERE.parents[4]


REPO = _repo()
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

import scenario as S  # noqa: E402
from foundry.runtime import TypedWorkflowError, load_workflow  # noqa: E402

RUNTIME_PY = REPO / "tools" / "foundry" / "runtime.py"
SCOUT_PY = REPO / "tools" / "foundry" / "scout.py"
PROBE1 = HERE / "probe1_planted_incumbent.py"
SCENARIO = HERE / "scenario.py"


def _loop_over_stages(tree: ast.AST) -> bool:
    """True if some `for ... in ...stages` (or wf['stages']) exists."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.For):
            continue
        it = node.iter
        if isinstance(it, ast.Subscript):
            sl = it.slice
            if isinstance(sl, ast.Constant) and sl.value == "stages":
                return True
        if isinstance(it, ast.Attribute) and it.attr == "stages":
            return True
    return False


def _calls_runtime(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    text_hits = False
    src = path.read_text(encoding="utf-8")
    if "run_via_runtime" in src or "runtime.execute" in src or "from foundry.runtime import" in src:
        text_hits = True
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        if isinstance(node, ast.Attribute):
            names.add(node.attr)
    return text_hits and ("execute" in names or "run_via_runtime" in names or "scout" in names)


def main() -> int:
    outputs, receipt = S.scout(S.KNOWN_GOAL)
    oracle = S.oracle(receipt)

    wf_doc = json.loads(S.WORKFLOW_PATH.read_text(encoding="utf-8"))
    json_is_workflow = (
        wf_doc.get("kind") == "typed-workflow"
        and wf_doc.get("id") == S.WORKFLOW_ID
        and isinstance(wf_doc.get("stages"), list)
        and len(wf_doc["stages"]) >= 9
    )
    loaded = load_workflow(S.WORKFLOW_PATH)
    loaded_ok = loaded.get("id") == S.WORKFLOW_ID and len(loaded.get("stages") or []) >= 9

    py_refused = False
    try:
        load_workflow(SCOUT_PY)
    except TypedWorkflowError as exc:
        py_refused = "bespoke script" in str(exc) or "JSON" in str(exc)

    runtime_ast = ast.parse(RUNTIME_PY.read_text(encoding="utf-8"))
    loops = _loop_over_stages(runtime_ast)
    probe1_uses_runtime = _calls_runtime(PROBE1) or _calls_runtime(SCENARIO)
    scout_src = SCOUT_PY.read_text(encoding="utf-8")
    dogfoods = (
        "load_workflow(WORKFLOW_PATH)" in scout_src
        and "execute(wf" in scout_src
    )

    trace_ids = [s.get("id") for s in (receipt.get("trace") or [])]
    expected = [s.get("id") for s in wf_doc.get("stages") or []]
    trace_matches = trace_ids == expected

    doc = {
        "probe": "probe2-typed-runtime",
        "unit_id": "IMP-0209",
        "json_is_typed_workflow": json_is_workflow,
        "loaded_ok": loaded_ok,
        "py_script_refused": py_refused,
        "runtime_loops_over_stages": loops,
        "probe1_calls_runtime": probe1_uses_runtime,
        "scout_dogfoods_runtime": dogfoods,
        "oracle_ok": oracle.get("ok"),
        "oracle_errors": oracle.get("errors"),
        "trace_ids": trace_ids,
        "trace_matches_document": trace_matches,
        "bespoke_script_flag": receipt.get("bespoke_script"),
        "engine": receipt.get("engine"),
        "workflow_id": (receipt.get("workflow") or {}).get("id"),
        "ranked_n": len(outputs.get("ranked") or []),
        "pass": bool(
            json_is_workflow
            and loaded_ok
            and py_refused
            and loops
            and probe1_uses_runtime
            and dogfoods
            and oracle.get("ok")
            and trace_matches
            and receipt.get("bespoke_script") is False
        ),
    }
    (HERE / "probe2-typed-runtime.raw.json").write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "oracle_ok": doc["oracle_ok"],
                "py_script_refused": py_refused,
                "loops": loops,
                "trace_matches": trace_matches,
                "dogfoods": dogfoods,
            },
            sort_keys=True,
        )
    )
    if not doc["pass"]:
        print(f"FAILED:IMP-0209-probe2 {doc}")
        return 1
    print(
        f"oracle_ok={oracle.get('ok')} py_refused={py_refused} "
        f"loops={loops} trace={trace_ids}"
    )
    print("SUCCESS:IMP-0209-probe2 typed Workflow through shared runtime; script refused")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
