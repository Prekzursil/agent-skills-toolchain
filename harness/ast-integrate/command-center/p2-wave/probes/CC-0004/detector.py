#!/usr/bin/env python3
"""AST + import-graph detector for local completion-predicate forks (CC-0004).

Retry policy forbids a third regex attempt. This scanner never greps source
text for verdict names. It walks ast.FunctionDef / ast.Import / ast.ImportFrom
and classifies each verdict-shaped function as canonical, resolved, or fork.

A function is a verdict producer when its binding name (AST identifier) is in
VERDICT_NAMES. A site resolves when its body calls a name imported from the
shared reducer module. Documentary strings, comments, and markdown are not
FunctionDef nodes, so they cannot fire.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Iterator

REPO = Path(__file__).resolve().parents[4]

SHARED_PATH_TAILS = (
    "platform/lib/completion_predicate.py",
    "platform/lib/completion_predicate/__init__.py",
)
SHARED_MODULE_DOTTED = {
    "platform.lib.completion_predicate",
    "lib.completion_predicate",
    "completion_predicate",
}
SHARED_SYMBOLS = frozenset(
    {
        "evaluate",  # live CC-0003 export (platform/lib/completion_predicate.py)
        "evaluate_completion",  # fixture / catalog wording
        "completion_verdict",
        "reduce_completion",
        "CompletionVerdict",
        "load_receipt",
    }
)
VERDICT_NAMES = frozenset(
    {
        "artifact_delivered",
        "artifact_complete",
        "unit_delivered",
        "unit_complete",
        "is_complete",
        "is_delivered",
        "completion_verdict",
        "evaluate_completion",
        "reduce_completion",
        "check_complete",
        "check_delivered",
        "completion_predicate",
        "harvest_complete",
        "fanin_complete",
        "synthesis_complete",
        "monitor_complete",
        "dispatcher_complete",
    }
)
SKIP_DIR_NAMES = frozenset(
    {
        "__pycache__",
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "node_modules",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "dist",
        "build",
    }
)
DEFAULT_SKIP_PREFIXES = (
    "command-center/p2-wave/probes/",
    "command-center/p2-wave/_av2_tmp/",
)


def posix(path: Path) -> str:
    return path.as_posix()


def rel_posix(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def is_shared_module_path(rel: str) -> bool:
    norm = rel.replace("\\", "/")
    return any(norm.endswith(tail) for tail in SHARED_PATH_TAILS)


def is_shared_module_name(mod: str | None) -> bool:
    if not mod:
        return False
    dotted = mod.strip()
    if dotted in SHARED_MODULE_DOTTED:
        return True
    return dotted.endswith(".completion_predicate")


def skip_dir(name: str) -> bool:
    return name in SKIP_DIR_NAMES or name.startswith(".")


def iter_py_files(root: Path, skip_prefixes: Iterable[str] = ()) -> Iterator[Path]:
    root = root.resolve()
    prefixes = tuple(p.replace("\\", "/") for p in skip_prefixes)
    for path in root.rglob("*.py"):
        if any(skip_dir(part) for part in path.parts):
            continue
        try:
            rel = rel_posix(path, root)
        except ValueError:
            continue
        if any(rel.startswith(p) for p in prefixes):
            continue
        yield path


def module_name_for(path: Path, root: Path) -> str:
    rel = path.resolve().relative_to(root.resolve()).with_suffix("")
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def resolve_from_module(file_mod: str, node: ast.ImportFrom) -> str:
    if node.level == 0:
        return node.module or ""
    base = file_mod.split(".")
    base = base[: -node.level] if node.level <= len(base) else []
    leaf = (node.module or "").split(".") if node.module else []
    return ".".join(p for p in [*base, *leaf] if p)


def import_aliases(tree: ast.AST, file_mod: str) -> tuple[set[str], set[str]]:
    """Return (module_aliases, symbol_aliases) bound to the shared reducer."""
    modules: set[str] = set()
    symbols: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if is_shared_module_name(alias.name):
                    modules.add(alias.asname or alias.name.split(".")[-1])
        elif isinstance(node, ast.ImportFrom):
            resolved = resolve_from_module(file_mod, node)
            shared_mod = is_shared_module_name(resolved) or is_shared_module_name(
                node.module
            )
            for alias in node.names:
                local = alias.asname or alias.name
                if shared_mod and alias.name == "*":
                    symbols.update(SHARED_SYMBOLS)
                elif shared_mod and alias.name in SHARED_SYMBOLS:
                    symbols.add(local)
                elif alias.name == "completion_predicate" or is_shared_module_name(
                    f"{resolved}.{alias.name}" if resolved else alias.name
                ):
                    modules.add(local)
    return modules, symbols


def call_is_shared(
    call: ast.Call, module_aliases: set[str], symbol_aliases: set[str]
) -> bool:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id in symbol_aliases
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return func.value.id in module_aliases and func.attr in SHARED_SYMBOLS
    return False


def function_calls_shared(
    fn: ast.FunctionDef, module_aliases: set[str], symbol_aliases: set[str]
) -> bool:
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and call_is_shared(
            node, module_aliases, symbol_aliases
        ):
            return True
    return False


def iter_functions(tree: ast.Module) -> Iterator[tuple[str, ast.FunctionDef]]:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            yield node.name, node
        elif isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, ast.FunctionDef):
                    yield f"{node.name}.{child.name}", child


def classify_file(path: Path, root: Path) -> list[dict[str, Any]]:
    rel = rel_posix(path, root)
    source = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(source, filename=rel)
    except SyntaxError as exc:
        return [
            {
                "path": rel,
                "line": int(exc.lineno or 0),
                "name": "<unparseable>",
                "kind": "unparseable",
                "detail": exc.msg,
            }
        ]
    if not isinstance(tree, ast.Module):
        return []
    file_mod = module_name_for(path, root)
    canonical_file = is_shared_module_path(rel)
    module_aliases, symbol_aliases = import_aliases(tree, file_mod)
    rows: list[dict[str, Any]] = []
    for qualname, fn in iter_functions(tree):
        short = fn.name
        if short not in VERDICT_NAMES:
            continue
        if canonical_file:
            kind = "canonical"
        elif function_calls_shared(fn, module_aliases, symbol_aliases):
            kind = "resolved"
        else:
            kind = "fork"
        rows.append(
            {
                "path": rel,
                "line": int(fn.lineno),
                "end_line": int(getattr(fn, "end_lineno", fn.lineno) or fn.lineno),
                "name": short,
                "qualname": qualname,
                "kind": kind,
                "file_module": file_mod,
                "imports_shared_module": bool(module_aliases),
                "imports_shared_symbol": bool(symbol_aliases),
            }
        )
    return rows


def scan(root: Path, **kwargs: Any) -> dict[str, Any]:
    root = root.resolve()
    prefixes = kwargs.get("skip_prefixes")
    if prefixes is None:
        prefixes = DEFAULT_SKIP_PREFIXES
    files = sorted(iter_py_files(root, prefixes))
    hits: list[dict[str, Any]] = []
    unparseable: list[dict[str, Any]] = []
    for path in files:
        for row in classify_file(path, root):
            if row["kind"] == "unparseable":
                unparseable.append(row)
            else:
                hits.append(row)
    forks = [h for h in hits if h["kind"] == "fork"]
    resolved = [h for h in hits if h["kind"] == "resolved"]
    canonical = [h for h in hits if h["kind"] == "canonical"]
    shared_files = [
        rel_posix(p, root) for p in files if is_shared_module_path(rel_posix(p, root))
    ]
    nfiles = len(files)
    return {
        "root": posix(root),
        "method": "ast-import-graph",
        "files_scanned": nfiles,
        "shared_module_present": bool(shared_files),
        "shared_module_paths": shared_files,
        "canonical": canonical,
        "resolved": resolved,
        "forks": forks,
        "unparseable": unparseable,
        "fork_count": len(forks),
        "resolved_count": len(resolved),
        "canonical_count": len(canonical),
    }


def locator(hit: dict[str, Any]) -> str:
    rel = hit.get("path") or ""
    return f"{rel}:{hit['line']}:{hit['name']}"


def dumps(doc: Any) -> str:
    return json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    root = Path(args[0]).resolve() if args else REPO
    report = scan(root)
    sys.stdout.write(dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
