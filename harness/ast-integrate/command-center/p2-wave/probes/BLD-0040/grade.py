#!/usr/bin/env python3
"""AST oracle-strength grader for BLD-0040."""
from __future__ import annotations

import ast
import json
from pathlib import Path

RANK = {
    "EXACT-VALUE": 6,
    "INVARIANT/PROPERTY": 5,
    "SCHEMA-SHAPE": 4,
    "SNAPSHOT": 6,
    "EXIT-CODE-ONLY": 2,
    "NO-CRASH-ONLY": 1,
    "NO-ORACLE": 0,
}
WEAK = frozenset({"EXIT-CODE-ONLY", "NO-CRASH-ONLY", "NO-ORACLE"})
EXIT_ATTRS = frozenset({"returncode", "exitcode", "exit_code", "code"})
EXIT_NAMES = frozenset({"rc", "code", "exit_code", "returncode", "exitcode"})
READ_ATTRS = frozenset({"read_text", "read_bytes", "read"})
SCHEMA_FUNCS = frozenset({"isinstance", "issubclass", "hasattr", "validate"})
GOLDEN_TOKS = ("golden", "snapshot", "expected.json")


def clip(text: str, n: int = 240) -> str:
    t = " ".join((text or "").split())
    return t if len(t) <= n else t[: n - 1] + "…"


def quote(src: str, node: ast.AST) -> str:
    frag = ast.get_source_segment(src, node)
    if frag:
        return clip(frag)
    try:
        return clip(ast.unparse(node))
    except Exception:
        return clip(type(node).__name__)


def nm(node: ast.AST | None) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Call):
        return nm(node.func)
    return ""


def is_none(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value is None


def is_literal(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return all(is_literal(x) for x in node.elts)
    if isinstance(node, ast.Dict):
        return all(
            k is not None and is_literal(k) and is_literal(v)
            for k, v in zip(node.keys, node.values)
        )
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        return is_literal(node.operand)
    return False


def dump(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return ""


def looks_path(node: ast.AST) -> bool:
    text = dump(node).lower()
    return bool(text) and (
        any(t in text for t in GOLDEN_TOKS) or "path(" in text or ".json" in text
    )


def is_read(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    attr = nm(node.func).lower()
    if attr in READ_ATTRS:
        return True
    if isinstance(node.func, ast.Attribute) and node.func.attr in READ_ATTRS:
        return True
    if attr in {"loads", "load"} and node.args:
        inner = node.args[0]
        return is_read(inner) or looks_path(inner)
    return False


def is_exit(node: ast.AST) -> bool:
    if isinstance(node, ast.Attribute) and node.attr in EXIT_ATTRS:
        return True
    if isinstance(node, ast.Name) and node.id in EXIT_NAMES:
        return True
    if isinstance(node, ast.Call) and nm(node.func) in {"main", "run", "call"}:
        return True
    return False


def is_schema(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and nm(node.func) in SCHEMA_FUNCS


def is_len(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and nm(node.func) == "len"


def is_keys(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"keys", "values", "items"}
    )


def load_regen(directory: Path) -> dict | None:
    for name in ("REGEN.json", ".regen.json", "regen.json"):
        p = directory / name
        if not p.is_file():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            return data
    return None


def regen_meta(regen: dict | None) -> tuple[bool, str, str]:
    if not regen:
        return False, "NOT-RECORDED", "NOT-RECORDED"
    when = str(
        regen.get("last_regenerated")
        or regen.get("regenerated_at")
        or regen.get("when")
        or "NOT-RECORDED"
    )
    proc = str(
        regen.get("process")
        or regen.get("regenerated_by")
        or regen.get("by")
        or "NOT-RECORDED"
    )
    source = str(regen.get("source") or "").lower().replace("_", "-")
    flag = bool(regen.get("self_confirming"))
    if source in {"code-under-test", "sut", "code under test"}:
        flag = True
    return flag, when, proc


def loaded_names(func: ast.AST, tree: ast.Module) -> set[str]:
    names: set[str] = set()

    def take(value: ast.AST, targets) -> None:
        if is_read(value) or looks_path(value):
            for t in targets:
                if isinstance(t, ast.Name):
                    names.add(t.id)

    for node in tree.body:
        if isinstance(node, ast.Assign):
            take(node.value, node.targets)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            take(node.value, [node.target])
    for node in ast.walk(func):
        if isinstance(node, ast.Assign):
            take(node.value, node.targets)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            take(node.value, [node.target])
    return names


def writes_file(func: ast.AST) -> bool:
    for node in ast.walk(func):
        if isinstance(node, ast.Call) and nm(node.func) in {
            "write_text",
            "write_bytes",
            "write",
            "dump",
        }:
            return True
    return False


def expr_loaded(node: ast.AST, loaded: set[str]) -> bool:
    if is_read(node) or looks_path(node):
        return True
    if isinstance(node, ast.Name) and node.id in loaded:
        return True
    if (
        isinstance(node, ast.Call)
        and nm(node.func) in {"loads", "load"}
        and node.args
    ):
        return expr_loaded(node.args[0], loaded)
    return False


def grade_compare(node: ast.Compare, loaded: set[str]) -> str:
    left = node.left
    if not node.ops or not node.comparators:
        return "INVARIANT/PROPERTY"
    op = node.ops[0]
    right = node.comparators[0]
    if expr_loaded(left, loaded) or expr_loaded(right, loaded):
        if isinstance(op, (ast.Eq, ast.NotEq, ast.Is, ast.IsNot)):
            return "SNAPSHOT"
    if isinstance(op, (ast.Is, ast.IsNot)) and (is_none(left) or is_none(right)):
        return "NO-CRASH-ONLY"
    if is_exit(left) or is_exit(right):
        return "EXIT-CODE-ONLY"
    if (
        is_schema(left)
        or is_schema(right)
        or is_len(left)
        or is_len(right)
        or is_keys(left)
        or is_keys(right)
    ):
        return "SCHEMA-SHAPE"
    if isinstance(op, (ast.Eq, ast.NotEq)):
        if is_literal(left) or is_literal(right):
            return "EXACT-VALUE"
        joined = (nm(left) + " " + nm(right)).lower()
        if any(t in joined for t in ("expected", "golden", "snapshot")):
            return "SNAPSHOT"
        return "INVARIANT/PROPERTY"
    return "INVARIANT/PROPERTY"


def grade_expr(node: ast.AST, loaded: set[str]) -> str:
    if isinstance(node, ast.Compare):
        return grade_compare(node, loaded)
    if isinstance(node, ast.BoolOp):
        parts = [grade_expr(v, loaded) for v in node.values]
        return max(parts, key=lambda g: RANK[g])
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        inner = grade_expr(node.operand, loaded)
        return "INVARIANT/PROPERTY" if inner == "NO-CRASH-ONLY" else inner
    if isinstance(node, (ast.Constant, ast.Name)):
        return "NO-CRASH-ONLY"
    if isinstance(node, ast.Call):
        if is_schema(node):
            return "SCHEMA-SHAPE"
        return "INVARIANT/PROPERTY"
    return "INVARIANT/PROPERTY"


def is_raises(node: ast.With) -> bool:
    for item in node.items:
        ctx = item.context_expr
        if isinstance(ctx, ast.Call) and nm(ctx.func) in {
            "raises",
            "assertRaises",
            "assertRaisesRegex",
        }:
            return True
    return False


def extra_oracles(func: ast.AST) -> list[tuple[ast.AST, str]]:
    found: list[tuple[ast.AST, str]] = []
    mapping = {
        "assertEqual": "EXACT-VALUE",
        "assertEquals": "EXACT-VALUE",
        "assertNotEqual": "EXACT-VALUE",
        "assertIsNone": "NO-CRASH-ONLY",
        "assertIsNotNone": "NO-CRASH-ONLY",
        "assertTrue": "NO-CRASH-ONLY",
        "assertIn": "INVARIANT/PROPERTY",
        "assertNotIn": "INVARIANT/PROPERTY",
        "assertGreater": "INVARIANT/PROPERTY",
        "assertIsInstance": "SCHEMA-SHAPE",
        "validate": "SCHEMA-SHAPE",
        "check_schema": "SCHEMA-SHAPE",
    }
    for node in ast.walk(func):
        if isinstance(node, ast.With) and is_raises(node):
            found.append((node, "INVARIANT/PROPERTY"))
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            fname = nm(node.value.func)
            if fname in mapping:
                found.append((node.value, mapping[fname]))
    return found


def test_funcs(tree: ast.Module) -> list[ast.AST]:
    out: list[ast.AST] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test_"):
                out.append(node)
        if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for item in node.body:
                if isinstance(
                    item, (ast.FunctionDef, ast.AsyncFunctionDef)
                ) and item.name.startswith("test_"):
                    out.append(item)
    return out


def grade_function(
    src: str,
    func: ast.FunctionDef | ast.AsyncFunctionDef,
    tree: ast.Module,
    rel: str,
    regen: dict | None,
) -> dict:
    loaded = loaded_names(func, tree)
    assertions: list[dict] = []
    grades: list[str] = []
    snap = False
    for node in ast.walk(func):
        if isinstance(node, ast.Assert):
            g = grade_expr(node.test, loaded)
            if g == "SNAPSHOT":
                snap = True
            assertions.append(
                {
                    "path": rel,
                    "line": int(node.lineno),
                    "quote": quote(src, node),
                    "grade": g,
                }
            )
            grades.append(g)
    for node, g in extra_oracles(func):
        assertions.append(
            {
                "path": rel,
                "line": int(getattr(node, "lineno", func.lineno)),
                "quote": quote(src, node),
                "grade": g,
            }
        )
        grades.append(g)
    self_conf, when, process = regen_meta(regen)
    if snap and writes_file(func):
        self_conf = True
        if process == "NOT-RECORDED":
            process = "test writes golden from the code under test before comparing"
    if not grades:
        strongest = "NO-ORACLE"
        effective = "NO-ORACLE"
    else:
        strongest = max(grades, key=lambda g: RANK[g])
        effective = strongest
        if strongest == "SNAPSHOT" and self_conf:
            effective = "NO-ORACLE"
    lead = assertions[0] if assertions else {}
    row = {
        "test_id": f"{rel}::{func.name}",
        "name": func.name,
        "path": rel,
        "line": int(func.lineno),
        "strongest_oracle": strongest,
        "effective_oracle": effective,
        "self_confirming": bool(self_conf and snap),
        "assertions": assertions,
        "assertion_count": len(assertions),
        "quote": lead.get("quote") or f"def {func.name}():",
        "corpus": "",
    }
    if snap:
        row["golden_last_regenerated"] = when
        row["golden_regenerated_by"] = process
        row["snapshot"] = True
    return row


def grade_file(path: Path, repo: Path) -> list[dict]:
    rel = path.resolve().relative_to(repo.resolve()).as_posix()
    try:
        src = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    regen = load_regen(path.parent)
    return [
        grade_function(src, func, tree, rel, regen) for func in test_funcs(tree)
    ]


RANK = RANK
WEAK = WEAK
quote = quote
loaded_names = loaded_names
regen_meta = regen_meta
writes_file = writes_file
