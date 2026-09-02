#!/usr/bin/env python3
"""Probe 2: second JSON-Schema implementation reaches the same verdicts.

Evidence signal (2): a walker that does not import jsonschema agrees with
Draft202012Validator on the live index, the additive extension, and each of
the six named mutants. Guards against a dialect quirk.
"""
from __future__ import annotations

import ast
import inspect
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from marketplace import index_schema as S  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0067.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0067-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:IMP-0067-probe2 unparseable:{exc}")
        return 1
    if "SUCCESS:IMP-0067" not in text:
        print("FAILED:IMP-0067-probe2 sentinel absent")
        return 1
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:IMP-0067-probe2 self-declared:{st}")
        return 1

    import ast

    tree = ast.parse(inspect.getsource(S))
    top_mods = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                top_mods.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            top_mods.add(node.module.split(".")[0])
    if "jsonschema" in top_mods:
        print("FAILED:IMP-0067-probe2 jsonschema imported at module top-level")
        return 1
    fn_b: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "validate_engine_b":
            for sub in ast.walk(node):
                if isinstance(sub, ast.Import):
                    fn_b.extend(a.name for a in sub.names)
                elif isinstance(sub, ast.ImportFrom) and sub.module:
                    fn_b.append(sub.module)
    if any(n == "jsonschema" or n.startswith("jsonschema.") for n in fn_b):
        print("FAILED:IMP-0067-probe2 engine B imports jsonschema")
        return 1

    index = S.load_index()
    schema = S.load_schema()
    current_a = S.validate_engine_a(index, schema)
    current_b = S.validate_engine_b(index, schema)
    if not current_a.ok or not current_b.ok:
        print("FAILED:IMP-0067-probe2 current index not accepted by both engines")
        print(json.dumps({"a": current_a.as_dict(), "b": current_b.as_dict()}, indent=2)[:4000])
        return 1

    extended = S.extended_example(index)
    ext_a = S.validate_engine_a(extended, schema)
    ext_b = S.validate_engine_b(extended, schema)
    if not ext_a.ok or not ext_b.ok:
        print("FAILED:IMP-0067-probe2 extended index not accepted by both engines")
        print(json.dumps({"a": ext_a.as_dict(), "b": ext_b.as_dict()}, indent=2)[:4000])
        return 1

    compared = []
    mismatches = []
    rows = S.mutation_verdicts(index, schema)
    for mid in S.MUTATION_IDS:
        row = rows[mid]
        compared.append(
            {
                "id": mid,
                "a": row["engine_a"]["primary_code"],
                "b": row["engine_b"]["primary_code"],
                "a_ok": row["engine_a"]["ok"],
                "b_ok": row["engine_b"]["ok"],
            }
        )
        if (
            row["engine_a"]["ok"]
            or row["engine_b"]["ok"]
            or row["engine_a"]["primary_code"] != mid
            or row["engine_b"]["primary_code"] != mid
            or not row["agree"]
        ):
            mismatches.append(row)

    if mismatches:
        print("FAILED:IMP-0067-probe2 engine disagreement")
        print(json.dumps(mismatches, indent=2)[:4000])
        return 1

    payload = {
        "probe": "probe2-second-engine",
        "unit_id": "IMP-0067",
        "ok": True,
        "engine_a": current_a.engine,
        "engine_b": current_b.engine,
        "current_ok_both": True,
        "extended_ok_both": True,
        "mutants_compared": compared,
        "walker_imports_jsonschema": False,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"engine_a={current_a.engine} engine_b={current_b.engine} "
        f"current_ok_both=True mutants={len(compared)}"
    )
    print("SUCCESS:IMP-0067-probe2 second JSON-Schema engine agrees")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
