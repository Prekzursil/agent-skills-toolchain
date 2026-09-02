"""Live census of v1 $defs.stopping_expr vs in-tree stopping objects.

The catalog cites 11-COUNCIL-SPECIFICATION.schema.json $defs.stopping_expr.
That file is not in this Linux worktree. We probe candidate paths and then
measure the in-tree stopping shape (max_rounds / on_timeout) against the six
required examples.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

CITED_V1 = [
    Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json"),
    Path("/c/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json"),
    Path.home() / ".claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json",
    REPO / "11-COUNCIL-SPECIFICATION.schema.json",
]
LIVE_COUNCILSPEC = REPO / "platform/schema/councilspec.schema.json"

CNL0001 = (
    REPO
    / "command-center/design/council/"
    / "CNL-0001-councilspec-v2-root-envelope-that-supersedes-council-chart.schema.json"
)
CNL0001_V1_FIXTURE = (
    REPO / "command-center/p2-wave/probes/CNL-0001/fixtures/v1-council-charter.schema.json"
)
CNL0001_ENVELOPE = REPO / "command-center/p2-wave/probes/CNL-0001/envelope.py"

IN_TREE_STOPPING = (
    REPO / "command-center/p2-wave/probes/ARC-0010/registry.schema.json"
)
V1_STRING_SCHEMA = {"type": "string", "minLength": 1}
V1_WRAP_CLAIM = "$defs.stopping_expr becomes {mode:expression, expression:<string>}"


def probe_cited_v1_file() -> dict[str, Any]:
    rows = []
    found = None
    for p in CITED_V1:
        exists = p.is_file()
        rows.append({"path": str(p), "exists": exists, "bytes": p.stat().st_size if exists else 0})
        if exists and found is None:
            found = p
    defs_keys: list[str] = []
    has_stopping_expr = False
    stopping_expr_schema = None
    if found is not None:
        try:
            doc = json.loads(found.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            doc = None
        if isinstance(doc, dict):
            defs = doc.get("$defs") or doc.get("definitions") or {}
            if isinstance(defs, dict):
                defs_keys = sorted(defs.keys())
                has_stopping_expr = "stopping_expr" in defs
                if has_stopping_expr:
                    stopping_expr_schema = defs["stopping_expr"]
    return {
        "catalog_citation": (
            "command-center/WORK-UNIT-CATALOG.json:34775 cites "
            "$defs.stopping_expr in 11-COUNCIL-SPECIFICATION.schema.json"
        ),
        "found": found is not None,
        "found_path": str(found) if found else None,
        "paths_probed": rows,
        "defs_keys": defs_keys,
        "has_stopping_expr": has_stopping_expr,
        "stopping_expr_schema": stopping_expr_schema,
        "verdict": (
            "PRESENT"
            if has_stopping_expr
            else ("FILE-PRESENT-DEFS-MISSING-stopping_expr" if found else "ABSENT")
        ),
    }


def reconstructed_v1_from_cnl0001() -> dict[str, Any]:
    """CNL-0001 reconstructs v1 stopping_expr as a non-empty string wrapped in v2.

    Prefer the CNL-0001 catalog artifact when present. On this worktree that file
    is often absent (same leftover as this unit's own catalog output). Fall back
    to the live CNL-0001 probe fixture, which is the reconstruction CNL-0001
    actually executes. Do not emit CNL-0001's catalog path from this unit.
    """
    if CNL0001.is_file():
        doc = json.loads(CNL0001.read_text(encoding="utf-8"))
        defs = doc.get("$defs") or {}
        se = defs.get("stopping_expression") if isinstance(defs, dict) else None
        expr = (se or {}).get("properties", {}).get("expression") if isinstance(se, dict) else None
        is_string = isinstance(expr, dict) and expr.get("type") == "string"
        answer = ((doc.get("x-cnl-0001-delivery") or {}).get("answer") or "")
        return {
            "present": True,
            "source": "catalog-artifact",
            "path": CNL0001.relative_to(REPO).as_posix(),
            "stopping_expression": se,
            "expression_schema": expr,
            "v1_stopping_expr_is_string": is_string,
            "cnl0001_claims_v1_is_string": V1_WRAP_CLAIM in answer,
            "verdict": "STRING" if is_string else "UNEXPECTED-SHAPE",
        }
    if CNL0001_V1_FIXTURE.is_file():
        doc = json.loads(CNL0001_V1_FIXTURE.read_text(encoding="utf-8"))
        defs = doc.get("$defs") or {}
        se = defs.get("stopping_expr") if isinstance(defs, dict) else None
        is_string = isinstance(se, dict) and se.get("type") == "string"
        envelope_text = (
            CNL0001_ENVELOPE.read_text(encoding="utf-8") if CNL0001_ENVELOPE.is_file() else ""
        )
        return {
            "present": True,
            "source": "cnl0001-probe-fixture",
            "path": CNL0001_V1_FIXTURE.relative_to(REPO).as_posix(),
            "catalog_artifact_absent": True,
            "catalog_artifact_path": CNL0001.relative_to(REPO).as_posix(),
            "stopping_expr": se,
            "expression_schema": se,
            "v1_stopping_expr_is_string": is_string,
            "cnl0001_claims_v1_is_string": V1_WRAP_CLAIM in envelope_text,
            "verdict": "STRING" if is_string else "UNEXPECTED-SHAPE",
        }
    return {"present": False, "verdict": "CNL-0001-artifact-absent"}


def _to_stop_expression(node: dict[str, Any]) -> dict[str, Any] | None:
    """Map this unit's tree ops onto platform/schema/councilspec.schema.json $defs.stop_expression."""
    op = node.get("op")
    if op == "cmp":
        return {"metric": node["var"], "op": node["rel"], "value": node["value"]}
    if op == "var":
        return {"metric": node["name"], "op": "==", "value": True}
    if op == "not":
        inner = _to_stop_expression(node["arg"])
        return None if inner is None else {"not": inner}
    if op in {"and", "all"}:
        mapped = [_to_stop_expression(a) for a in node.get("args") or []]
        if any(m is None for m in mapped):
            return None
        if len(mapped) == 1:
            return mapped[0]
        return {"all_of": mapped}
    if op == "or":
        mapped = [_to_stop_expression(a) for a in node.get("args") or []]
        if any(m is None for m in mapped) or len(mapped) < 2:
            return None
        return {"any_of": mapped}
    if op == "any":
        return None
    if op == "weighted":
        clauses = []
        for t in node.get("terms") or []:
            when = _to_stop_expression(t["arg"])
            if when is None:
                return None
            clauses.append({"weight": t["weight"], "when": when})
        if not clauses:
            return None
        return {"weighted": {"threshold": node["threshold"], "clauses": clauses}}
    return None


def live_councilspec_stop_expression(six: list[dict[str, Any]]) -> dict[str, Any]:
    """Census live $defs.stop_expression (different name from cited stopping_expr)."""
    import jsonschema
    from grammar import parse

    path = LIVE_COUNCILSPEC
    if not path.is_file():
        return {"present": False, "path": path.relative_to(REPO).as_posix()}
    doc = json.loads(path.read_text(encoding="utf-8"))
    defs = doc.get("$defs") or {}
    has_stop_expression = "stop_expression" in defs
    has_stopping_expr = "stopping_expr" in defs
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$ref": "#/$defs/stop_expression",
        "$defs": defs,
    }
    validator = jsonschema.Draft202012Validator(schema) if has_stop_expression else None
    rows = []
    for ex in six:
        tree = parse(ex["surface"])
        mapped = _to_stop_expression(tree)
        errs: list[str] = []
        if validator is None:
            ok = False
            errs = ["no-$defs.stop_expression"]
        elif mapped is None:
            ok = False
            errs = ["no-mapping"]
        else:
            errs = [e.message for e in validator.iter_errors(mapped)]
            ok = not errs
        rows.append(
            {
                "id": ex["id"],
                "surface": ex["surface"],
                "mapped_ok": mapped is not None,
                "schema_ok": ok,
                "error": errs[0] if errs else None,
            }
        )
    yes = sum(1 for r in rows if r["schema_ok"])
    bound_unsat = _to_stop_expression(parse("unanimity AND NOT unanimity"))
    unbound_unsat = _to_stop_expression(parse("x AND NOT x"))
    bound_unsat_ok = False
    unbound_unsat_ok = False
    if validator is not None:
        if bound_unsat is not None:
            bound_unsat_ok = not list(validator.iter_errors(bound_unsat))
        if unbound_unsat is not None:
            unbound_unsat_ok = not list(validator.iter_errors(unbound_unsat))
    return {
        "present": True,
        "path": path.relative_to(REPO).as_posix(),
        "has_stop_expression": has_stop_expression,
        "has_stopping_expr": has_stopping_expr,
        "note": (
            "Live CouncilSpec uses $defs.stop_expression (all_of/any_of/not/weighted + typed "
            "leaves), not the cited v1 name $defs.stopping_expr. JSON Schema rejects unknown "
            "metric names (x AND NOT x) but accepts well-typed never-satisfiable trees "
            "(unanimity AND NOT unanimity). Static UNSAT/TAUTOLOGY is this unit's addition."
        ),
        "examples": rows,
        "expressible": yes,
        "inexpressible": len(rows) - yes,
        "bound_unsat_accepted_by_schema": bound_unsat_ok,
        "unbound_unsat_accepted_by_schema": unbound_unsat_ok,
        "unsat_tree_accepted_by_schema": bound_unsat_ok,
    }


def in_tree_stopping_schema() -> dict[str, Any]:
    path = IN_TREE_STOPPING
    doc = json.loads(path.read_text(encoding="utf-8"))
    stopping = doc["definitions"]["council_preset"]["properties"]["stopping"]
    keys = sorted((stopping.get("properties") or {}).keys())
    return {
        "path": path.relative_to(REPO).as_posix(),
        "keys": keys,
        "required": list(stopping.get("required") or []),
        "additionalProperties": stopping.get("additionalProperties"),
        "schema": stopping,
    }


def example_expressible_in_tree(surface: str, tree: dict[str, Any], stopping_schema: dict[str, Any]) -> dict[str, Any]:
    """A stopping object expresses E only if its allowed keys can name E's atoms and combinators.

    In-tree stopping allows only max_rounds and on_timeout. Combinators AND/OR/NOT/ANY/ALL/
    weighted and comparison atoms have no home. Even E3, which mentions max_rounds, is a
    disjunction with unanimity — inexpressible as {max_rounds, on_timeout}.
    """
    import jsonschema

    ops: set[str] = set()

    def walk(n: dict[str, Any]) -> None:
        ops.add(str(n.get("op")))
        if n.get("op") == "not":
            walk(n["arg"])
        elif n.get("op") in {"and", "or", "all", "any"}:
            for a in n.get("args") or []:
                walk(a)
        elif n.get("op") == "weighted":
            for t in n.get("terms") or []:
                walk(t["arg"])

    walk(tree)
    allowed = set(stopping_schema.get("keys") or [])
    combinators = ops & {"and", "or", "not", "any", "all", "weighted", "cmp", "var"}
    # Try validating the tree itself as a stopping object (must fail).
    try:
        jsonschema.Draft7Validator(stopping_schema["schema"]).validate(tree)
        tree_validates_as_stopping = True
    except Exception:
        tree_validates_as_stopping = False
    expressible = False
    reason = (
        f"combinators/atoms {sorted(combinators)} have no home in in-tree stopping keys "
        f"{sorted(allowed)}; tree_validates_as_stopping={tree_validates_as_stopping}"
    )
    return {
        "surface": surface,
        "ops": sorted(ops),
        "expressible": expressible,
        "tree_validates_as_stopping": tree_validates_as_stopping,
        "reason": reason,
    }


def _string_schema_accepts(surface: str) -> bool:
    import jsonschema

    try:
        jsonschema.Draft202012Validator(V1_STRING_SCHEMA).validate(surface)
        return True
    except Exception:
        return False


def census(six: list[dict[str, Any]]) -> dict[str, Any]:
    from grammar import parse
    import jsonschema

    v1 = probe_cited_v1_file()
    recon = reconstructed_v1_from_cnl0001()
    live_cs = live_councilspec_stop_expression(six)
    stopping = in_tree_stopping_schema()
    rows = []
    for ex in six:
        tree = parse(ex["surface"])
        store = _string_schema_accepts(ex["surface"])
        tree_as_string_ok = False
        try:
            jsonschema.Draft202012Validator(V1_STRING_SCHEMA).validate(tree)
            tree_as_string_ok = True
        except Exception:
            tree_as_string_ok = False
        rows.append(
            {
                "id": ex["id"],
                "surface": ex["surface"],
                "cited_v1_file": v1["verdict"],
                "v1_string_store_expressible": store,
                "v1_string_accepts_tree": tree_as_string_ok,
                "v1_structurally_typed": False,
                "in_tree": example_expressible_in_tree(ex["surface"], tree, stopping),
            }
        )
    in_tree_yes = sum(1 for r in rows if r["in_tree"]["expressible"])
    in_tree_no = len(rows) - in_tree_yes
    store_yes = sum(1 for r in rows if r["v1_string_store_expressible"])
    structural_yes = sum(1 for r in rows if r["v1_structurally_typed"])
    unsat_on_v1_string = _string_schema_accepts("x AND NOT x")
    return {
        "v1": v1,
        "v1_reconstructed_from_cnl0001": recon,
        "live_councilspec_stop_expression": live_cs,
        "in_tree_stopping": {
            "path": stopping["path"],
            "keys": stopping["keys"],
            "required": stopping["required"],
            "additionalProperties": stopping["additionalProperties"],
        },
        "examples": rows,
        "v1_string_silent_on_unsat": unsat_on_v1_string,
        "counts": {
            "six": len(rows),
            "v1_store_expressible": store_yes,
            "v1_store_inexpressible": len(rows) - store_yes,
            "v1_structurally_expressible": structural_yes,
            "v1_structurally_inexpressible": len(rows) - structural_yes,
            "in_tree_expressible": in_tree_yes,
            "in_tree_inexpressible": in_tree_no,
        },
    }
