"""AST / import-graph detector for a second completion predicate.

Call sites are enumerated by resolving Import / ImportFrom nodes, never
by grepping a name. A planted partial re-implementation must fire before
any zero-duplicate verdict is accepted.
"""
from __future__ import annotations

import ast
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Iterable

CANONICAL_MODULE = "lib.completion_reducer"
CANONICAL_SYMBOL = "reduce_completion"
FANIN_CONST = "FANIN_ROLE"

NAME_RE = re.compile(
    r"(reduce_completion|completion_predicate|evaluate_completion|"
    r"check_complet|is_complete|is_done|completion_verdict|done_predicate)",
    re.I,
)

PLANT_PARTIAL = '''\
"""Planted partial re-implementation (detector-control)."""
from pathlib import Path

FANIN_ROLE = "rogue-partial"


def reduce_completion(receipt):
    path = receipt.get("artifact_path") or ""
    exists = bool(path)  # truthiness stand-in for the reducer
    if receipt.get("exit_code") == 0:
        return {"verdict": "COMPLETE", "conditions": []}
    return {"verdict": "COMPLETE" if exists else "INCOMPLETE", "conditions": []}
'''

PLANT_TRUTHINESS = '''\
"""Planted exit-zero truthiness stand-in (detector-control)."""

FANIN_ROLE = "rogue-truthiness"


def is_complete(receipt):
    return receipt.get("exit_code") == 0
'''


def _qualname(root: Path, path: Path) -> str:
    rel = path.relative_to(root).with_suffix("")
    return ".".join(rel.parts)


def _resolve_from(file_qual: str, module: str | None, level: int) -> str:
    # Absolute import (level 0) is not relative to the current package.
    if not level:
        return module or ""
    pkg = file_qual.split(".")[:-1]
    drop = level - 1
    if drop:
        pkg = pkg[:-drop] if drop <= len(pkg) else []
    if module:
        return ".".join([*pkg, *module.split(".")]) if pkg else module
    return ".".join(pkg)


def _parse(path: Path) -> ast.AST | None:
    try:
        src = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    try:
        return ast.parse(src, filename=str(path))
    except SyntaxError:
        return None


def _const_str(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _fanin_role(tree: ast.AST) -> str | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == FANIN_CONST for t in node.targets):
                value = _const_str(node.value)
                if value:
                    return value
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == FANIN_CONST:
                value = _const_str(node.value)
                if value:
                    return value
    return None


def _import_bindings(tree: ast.AST, file_qual: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound = alias.asname or alias.name.split(".")[-1]
                rows.append(
                    {
                        "kind": "import",
                        "lineno": node.lineno,
                        "bound": bound,
                        "module": alias.name,
                        "symbol": None,
                    }
                )
        elif isinstance(node, ast.ImportFrom):
            mod = _resolve_from(file_qual, node.module, node.level or 0)
            for alias in node.names:
                bound = alias.asname or alias.name
                if mod == CANONICAL_MODULE:
                    rows.append(
                        {
                            "kind": "from-import",
                            "lineno": node.lineno,
                            "bound": bound,
                            "module": mod,
                            "symbol": alias.name,
                            "level": node.level or 0,
                        }
                    )
                elif alias.name == "completion_reducer" and (
                    mod == "lib" or mod.endswith(".lib")
                ):
                    rows.append(
                        {
                            "kind": "from-parent",
                            "lineno": node.lineno,
                            "bound": bound,
                            "module": f"{mod}.completion_reducer"
                            if mod != "lib"
                            else CANONICAL_MODULE,
                            "symbol": None,
                            "level": node.level or 0,
                        }
                    )
                else:
                    rows.append(
                        {
                            "kind": "from-other",
                            "lineno": node.lineno,
                            "bound": bound,
                            "module": mod,
                            "symbol": alias.name,
                            "level": node.level or 0,
                        }
                    )
    return rows


def _imports_canonical(bindings: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    for row in bindings:
        if row.get("module") == CANONICAL_MODULE:
            if row.get("symbol") in {None, CANONICAL_SYMBOL, "*"}:
                return row
            if row.get("kind") == "import":
                return row
        if row.get("kind") == "from-parent" and row.get("module") == CANONICAL_MODULE:
            return row
    return None


def _canonical_call_linenos(tree: ast.AST, bindings: list[dict[str, Any]]) -> list[int]:
    bound_fn = set()
    bound_mod = set()
    for row in bindings:
        if row.get("module") != CANONICAL_MODULE:
            continue
        if row.get("symbol") in {CANONICAL_SYMBOL, "*"}:
            bound_fn.add(row["bound"])
        else:
            bound_mod.add(row["bound"])
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id in bound_fn:
            lines.append(node.lineno)
        elif (
            isinstance(func, ast.Attribute)
            and func.attr == CANONICAL_SYMBOL
            and isinstance(func.value, ast.Name)
            and func.value.id in bound_mod
        ):
            lines.append(node.lineno)
    return sorted(set(lines))


def _looks_like_completion_return(fn: ast.FunctionDef) -> bool:
    for node in ast.walk(fn):
        if not isinstance(node, ast.Return) or node.value is None:
            continue
        if isinstance(node.value, ast.Dict):
            keys = [_const_str(k) for k in node.value.keys]
            if "verdict" in keys or "COMPLETE" in keys or "INCOMPLETE" in keys:
                return True
            for val in node.value.values:
                if _const_str(val) in {"COMPLETE", "INCOMPLETE", "UNKNOWN"}:
                    return True
        if isinstance(node.value, ast.Constant) and node.value.value in {
            "COMPLETE",
            "INCOMPLETE",
        }:
            return True
    return False


def _exit_zero_truthiness(fn: ast.FunctionDef) -> bool:
    """A Compare of exit_code == 0 that stands in for the reducer."""
    names_ok = bool(NAME_RE.search(fn.name))
    saw_exit_eq_zero = False
    for node in ast.walk(fn):
        if not isinstance(node, ast.Compare):
            continue
        left = node.left
        if isinstance(left, ast.Constant) and left.value == 0:
            comparators = node.comparators
            other = comparators[0] if comparators else None
        elif node.comparators and isinstance(node.comparators[0], ast.Constant):
            other = left
            if node.comparators[0].value != 0:
                continue
        else:
            continue
        ident = None
        if isinstance(other, ast.Name):
            ident = other.id
        elif isinstance(other, ast.Attribute):
            ident = other.attr
        elif (
            isinstance(other, ast.Call)
            and isinstance(other.func, ast.Attribute)
            and other.func.attr == "get"
            and other.args
            and _const_str(other.args[0]) == "exit_code"
        ):
            ident = "exit_code"
        if ident in {"exit_code", "rc", "returncode"}:
            saw_exit_eq_zero = True
    if saw_exit_eq_zero and (names_ok or _looks_like_completion_return(fn)):
        return True
    return names_ok and saw_exit_eq_zero


def _calls_canonical(fn: ast.FunctionDef, bindings: list[dict[str, Any]]) -> bool:
    lines = set(_canonical_call_linenos(fn, bindings))
    return bool(lines)


def _second_impls(
    path: Path,
    rel: str,
    file_qual: str,
    tree: ast.AST,
    bindings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if file_qual == CANONICAL_MODULE:
        return []
    found: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if _calls_canonical(node, bindings):
            continue
        name_hit = bool(NAME_RE.search(node.name))
        shape = _looks_like_completion_return(node)
        truthy = _exit_zero_truthiness(node)
        if not (name_hit or shape or truthy):
            continue
        kind = "partial-reimplementation" if name_hit or shape else "truthiness-stand-in"
        if truthy:
            kind = "truthiness-stand-in" if not name_hit else "partial-reimplementation"
        if name_hit and node.name == CANONICAL_SYMBOL:
            kind = "local-copy"
        found.append(
            {
                "path": rel,
                "qualname": file_qual,
                "function": node.name,
                "lineno": node.lineno,
                "kind": kind,
                "name_match": name_hit,
                "completion_shaped_return": shape,
                "exit_zero_truthiness": truthy,
            }
        )
    return found


def iter_py(root: Path) -> list[Path]:
    out: list[Path] = []
    for path in sorted(root.rglob("*.py")):
        if any(part == "__pycache__" or part.startswith(".") for part in path.parts):
            continue
        out.append(path)
    return out


def scan_tree(root: Path) -> dict[str, Any]:
    root = root.resolve()
    call_sites: list[dict[str, Any]] = []
    seconds: list[dict[str, Any]] = []
    mentions: list[str] = []
    graph: list[dict[str, str]] = []
    canonical_path = None

    for path in iter_py(root):
        rel = path.relative_to(root).as_posix()
        file_qual = _qualname(root, path)
        tree = _parse(path)
        if tree is None:
            continue
        if file_qual == CANONICAL_MODULE:
            canonical_path = rel
        bindings = _import_bindings(tree, file_qual)
        for row in bindings:
            if row.get("module"):
                graph.append(
                    {
                        "from": file_qual,
                        "to": str(row["module"]),
                        "kind": str(row["kind"]),
                    }
                )
        role = _fanin_role(tree)
        imported = _imports_canonical(bindings)
        calls = _canonical_call_linenos(tree, bindings)
        if role:
            call_sites.append(
                {
                    "path": rel,
                    "qualname": file_qual,
                    "role": role,
                    "imports_shared_reducer": imported is not None,
                    "import_kind": None if imported is None else imported.get("kind"),
                    "bound_name": None if imported is None else imported.get("bound"),
                    "resolved_module": None if imported is None else imported.get("module"),
                    "resolved_symbol": CANONICAL_SYMBOL if imported is not None else None,
                    "import_lineno": None if imported is None else imported.get("lineno"),
                    "call_linenos": calls,
                    "method": "ast-import-graph",
                }
            )
        if imported is None and "reduce_completion" in path.read_text(
            encoding="utf-8", errors="replace"
        ):
            mentions.append(rel)
        seconds.extend(_second_impls(path, rel, file_qual, tree, bindings))

    missing = [s for s in call_sites if not s["imports_shared_reducer"]]
    return {
        "root": str(root),
        "method": "ast-import-graph",
        "used_grep": False,
        "canonical_module": CANONICAL_MODULE,
        "canonical_symbol": CANONICAL_SYMBOL,
        "canonical_path": canonical_path,
        "canonical_present": canonical_path is not None,
        "call_sites": call_sites,
        "fan_in_count": len(call_sites),
        "missing_imports": missing,
        "second_implementations": seconds,
        "mention_only_files": mentions,
        "import_graph_edges": graph,
        "zero_duplicates": len(seconds) == 0,
    }


def plant_second_impl(tree: Path) -> list[str]:
    planted = []
    partial = tree / "fanin" / "fork_partial.py"
    truthy = tree / "fanin" / "fork_truthiness.py"
    partial.write_text(PLANT_PARTIAL, encoding="utf-8")
    truthy.write_text(PLANT_TRUTHINESS, encoding="utf-8")
    planted.append(partial.relative_to(tree).as_posix())
    planted.append(truthy.relative_to(tree).as_posix())
    return planted


def scan_with_control(clean_root: Path) -> dict[str, Any]:
    """Plant first, then accept a zero-duplicate verdict only if the plant fired."""
    clean = scan_tree(clean_root)
    tmp = Path(tempfile.mkdtemp(prefix="arc0107-plant-"))
    try:
        dest = tmp / "tree"
        shutil.copytree(clean_root, dest)
        planted_paths = plant_second_impl(dest)
        dirty = scan_tree(dest)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    dirty_paths = {s["path"] for s in dirty["second_implementations"]}
    fired = all(p in dirty_paths for p in planted_paths) or (
        any("fork_partial" in p for p in dirty_paths)
        and any("fork_truthiness" in p or "is_complete" in str(dirty["second_implementations"]) for p in dirty_paths)
    )
    # Require each planted file to appear in findings.
    fired = all(
        any(p == s["path"] for s in dirty["second_implementations"])
        for p in planted_paths
    )
    mention_clean = [
        s for s in clean["second_implementations"] if "mention_only" in s["path"]
    ]
    silent = clean["zero_duplicates"] and not mention_clean
    accepted = bool(fired and silent)
    return {
        "method": "ast-import-graph",
        "used_grep": False,
        "control_ran_before_zero_duplicate_verdict": True,
        "planted_paths": planted_paths,
        "planted_findings": dirty["second_implementations"],
        "control_fired": fired,
        "silent_on_clean": silent,
        "clean": clean,
        "zero_duplicate_accepted": accepted,
        "mention_only_not_flagged": "docs/mention_only.py" in clean.get(
            "mention_only_files", []
        )
        and not any("mention_only" in s["path"] for s in clean["second_implementations"]),
    }
