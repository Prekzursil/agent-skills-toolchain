#!/usr/bin/env python3
"""Probe 2: static field census of import-time model context (not probe 1).

Walks importer.py via AST plus a live render: which definition fields are
interpolated into the cataloguer prompt versus left inert. A field copied
into model context is a live injection surface whether or not this payload
fired. Also records that production IMP-0169 source classes omit workflow
definition fields, and that import_definition never calls run_workflow.
"""
from __future__ import annotations

import ast
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

from fixtures import hostile_definition  # noqa: E402
from importer import (  # noqa: E402
    INERT_FIELDS,
    LIVE_FIELDS,
    data_payload,
    import_definition,
    parse_spans,
    render_quarantined,
)

OUT = HERE / "probe2-field-census.raw.json"
IMPORTER_SRC = HERE / "importer.py"
QUARANTINE = REPO / "tools/import_quarantine.py"


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0072-probe2 {msg}")
    return 1


def _fn(tree: ast.AST, name: str) -> ast.FunctionDef | None:
    for node in tree.body if isinstance(tree, ast.Module) else []:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _calls_named(fn: ast.FunctionDef, name: str) -> bool:
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == name:
                return True
            if isinstance(func, ast.Attribute) and func.attr == name:
                return True
    return False


def _const_tuple(tree: ast.AST, name: str) -> tuple[str, ...]:
    for node in tree.body if isinstance(tree, ast.Module) else []:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    if isinstance(node.value, (ast.Tuple, ast.List)):
                        out: list[str] = []
                        for elt in node.value.elts:
                            if isinstance(elt, ast.Constant) and isinstance(
                                elt.value, str
                            ):
                                out.append(elt.value)
                        return tuple(out)
    return ()


def production_source_classes() -> list[str]:
    if not QUARANTINE.is_file():
        return []
    tree = ast.parse(QUARANTINE.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "SOURCE_CLASSES":
                    if isinstance(node.value, ast.Call):
                        args = node.value.args
                        if args and isinstance(
                            args[0], (ast.Set, ast.Tuple, ast.List)
                        ):
                            vals = []
                            for elt in args[0].elts:
                                if isinstance(elt, ast.Constant) and isinstance(
                                    elt.value, str
                                ):
                                    vals.append(elt.value)
                            return sorted(vals)
    return []


def production_workflow_renderers() -> list[str]:
    hits: list[str] = []
    tools = REPO / "tools"
    needles = ("workflow definition", "imported workflow", "stage names")
    for path in tools.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="replace")
        if "render_prompt" in text and any(n in text.lower() for n in needles):
            hits.append(path.relative_to(REPO).as_posix())
    return sorted(hits)


def definition_text(definition: dict, field_id: str) -> str:
    if field_id == "description":
        return str(definition.get("description") or "")
    if field_id == "prompts.system":
        return str((definition.get("prompts") or {}).get("system") or "")
    if field_id == "prompts.user":
        return str((definition.get("prompts") or {}).get("user") or "")
    if field_id == "stages[0].name":
        return str(((definition.get("stages") or [{}])[0]).get("name") or "")
    if field_id == "stages[0].examples[0]":
        examples = ((definition.get("stages") or [{}])[0]).get("examples") or []
        return str(examples[0] if examples else "")
    raise KeyError(field_id)


def main() -> int:
    source = IMPORTER_SRC.read_text(encoding="utf-8")
    tree = ast.parse(source)
    import_fn = _fn(tree, "import_definition")
    render_q = _fn(tree, "render_quarantined")
    render_n = _fn(tree, "render_naive")
    run_fn = _fn(tree, "run_workflow")
    if import_fn is None or render_q is None or render_n is None or run_fn is None:
        return fail("required functions missing from importer.py")

    import_calls_run = _calls_named(import_fn, "run_workflow")
    render_q_frames = _calls_named(render_q, "frame_data")
    render_n_frames = _calls_named(render_n, "frame_data")
    ast_live = _const_tuple(tree, "LIVE_FIELDS")
    ast_inert = _const_tuple(tree, "INERT_FIELDS")

    definition = hostile_definition()
    prompt = render_quarantined(definition)
    spans = parse_spans(prompt)
    data_fields = [s.field_id for s in spans if s.channel == "data" and s.field_id]
    census: list[dict] = []
    round_ok = True
    for field_id in LIVE_FIELDS:
        payload = data_payload(prompt, field_id)
        in_data = payload == definition_text(definition, field_id).encode("utf-8")
        round_ok = round_ok and in_data
        census.append(
            {
                "field_id": field_id,
                "channel": "data",
                "rendered_into_model_context": True,
                "inert": False,
                "payload_round_trip": in_data,
                "nbytes": len(payload),
            }
        )
    for field_id in INERT_FIELDS:
        census.append(
            {
                "field_id": field_id,
                "channel": "inert",
                "rendered_into_model_context": False,
                "inert": True,
            }
        )

    with tempfile.TemporaryDirectory(prefix="adv0072-probe2-") as tmp:
        report_import = import_definition(
            definition, sandbox=Path(tmp), mode="quarantined"
        )

    src_classes = production_source_classes()
    workflow_like = [c for c in src_classes if "workflow" in c]
    prod_renderers = production_workflow_renderers()

    live_all_data = set(data_fields) >= set(LIVE_FIELDS)
    ok = (
        not import_calls_run
        and render_q_frames
        and not render_n_frames
        and ast_live == LIVE_FIELDS
        and ast_inert == INERT_FIELDS
        and live_all_data
        and round_ok
        and not report_import.executed
        and not workflow_like
        and prod_renderers == []
        and "id" not in data_fields
        and report_import.fired_tokens == []
    )
    report = {
        "probe": "probe2-field-census",
        "unit_id": "ADV-0072",
        "pass": bool(ok),
        "ast": {
            "import_definition_calls_run_workflow": import_calls_run,
            "render_quarantined_calls_frame_data": render_q_frames,
            "render_naive_calls_frame_data": render_n_frames,
            "LIVE_FIELDS": list(ast_live),
            "INERT_FIELDS": list(ast_inert),
        },
        "census": census,
        "data_fields_in_render": data_fields,
        "production_imp0169_source_classes": src_classes,
        "production_imp0169_workflow_classes": workflow_like,
        "production_workflow_prompt_renderers": prod_renderers,
        "import_executed": report_import.executed,
        "mechanically_different_from_probe1": True,
    }
    OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    if not ok:
        return fail("census/AST mismatch")
    print(
        "SUCCESS:ADV-0072-probe2 free-text fields are DATA in import context; "
        "structural fields inert; import never executes; IMP-0169 omits workflow fields"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
