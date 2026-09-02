"""Probe 2: import graph, path reconstruction, and CI/collection resolution.

Mechanically different from probe 1: a reference built from parts, or raised
as ModuleNotFoundError at import/collection time, will not match a full-string
search of surviving files.
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

from inventory import DeletedPath

CONSTRUCTED_REL = (
    "command-center/p2-wave/probes/AUD-0094/fixtures/estate/surviving/constructed.py"
)
CONSTRUCTED_PATH = "aud0094-retired/tree-tools-a/file-01.py"
DELETED_MODULE = "aud0094_retired_tree_harness_file_00"
TEST_IMPORT_REL = (
    "command-center/p2-wave/probes/AUD-0094/fixtures/estate/surviving/"
    "test_retired_import.py"
)


def _rel(repo: Path, path: Path) -> str:
    try:
        return path.relative_to(repo).as_posix()
    except ValueError:
        return path.as_posix()


def _const_str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _join_binop(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _join_binop(node.left)
        right = _join_binop(node.right)
        if left is not None and right is not None:
            return left + right
    return None


def _str_env(tree: ast.AST) -> dict[str, str]:
    env: dict[str, str] = {}
    for node in getattr(tree, "body", []):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        s = _const_str(node.value)
        if s is not None:
            env[target.id] = s
    return env


def _resolve(node: ast.AST, env: dict[str, str]) -> str | None:
    s = _const_str(node)
    if s is not None:
        return s
    if isinstance(node, ast.Name) and node.id in env:
        return env[node.id]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _resolve(node.left, env)
        right = _resolve(node.right, env)
        if left is not None and right is not None:
            return left + right
    return None


def reconstruct_strings(tree: ast.AST) -> list[str]:
    env = _str_env(tree)
    found: list[str] = []
    for node in ast.walk(tree):
        joined = _join_binop(node) if isinstance(node, ast.BinOp) else None
        if joined:
            found.append(joined)
        resolved = _resolve(node, env)
        if resolved:
            found.append(resolved)
        if isinstance(node, ast.Call):
            func = node.func
            is_join = isinstance(func, ast.Attribute) and func.attr == "join"
            if is_join and node.args:
                arg0 = node.args[0]
                parts: list[str] = []
                seq = None
                if isinstance(arg0, (ast.List, ast.Tuple)):
                    seq = arg0.elts
                if seq is not None:
                    for elt in seq:
                        s = _resolve(elt, env)
                        if s is None:
                            parts = []
                            break
                        parts.append(s)
                    if parts:
                        sep = ""
                        if isinstance(func.value, ast.Constant) and isinstance(
                            func.value.value, str
                        ):
                            sep = func.value.value
                        found.append(sep.join(parts))
    return found


def import_names(tree: ast.AST) -> list[str]:
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
            for alias in node.names:
                names.append(f"{node.module}.{alias.name}")
        elif isinstance(node, ast.Call):
            func = node.func
            attr = isinstance(func, ast.Attribute) and func.attr == "import_module"
            if attr or (
                isinstance(func, ast.Name) and func.id == "import_module"
            ):
                if node.args:
                    s = _const_str(node.args[0])
                    if s:
                        names.append(s)
    return names


def runtime_py_files(repo: Path) -> list[Path]:
    files: list[Path] = []
    surviving = (
        repo / "command-center/p2-wave/probes/AUD-0094/fixtures/estate/surviving"
    )
    if surviving.is_dir():
        files.extend(sorted(surviving.glob("*.py")))
    tools = repo / "tools"
    if tools.is_dir():
        for path in tools.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            files.append(path)
    return files


def scan_runtime(
    repo: Path,
    deleted: list[DeletedPath],
    py_files: list[Path] | None = None,
) -> dict:
    py_files = py_files if py_files is not None else runtime_py_files(repo)
    by_path = {d.path: d for d in deleted}
    by_mod = {d.module_name: d for d in deleted if d.module_name}
    reconstructed_hits: list[dict] = []
    import_hits: list[dict] = []
    parse_errors: list[dict] = []
    for path in py_files:
        try:
            src = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError as exc:
            parse_errors.append({"path": _rel(repo, path), "error": str(exc)})
            continue
        rel = _rel(repo, path)
        for rebuilt in reconstruct_strings(tree):
            if rebuilt in by_path:
                reconstructed_hits.append(
                    {
                        "deleted_path": rebuilt,
                        "citing_path": rel,
                        "kind": "USE",
                        "detector": "ast-join-reconstruction",
                        "line": 0,
                        "snippet": rebuilt,
                    }
                )
        for name in import_names(tree):
            row = by_mod.get(name)
            if row is None:
                continue
            import_hits.append(
                {
                    "deleted_path": row.path,
                    "citing_path": rel,
                    "kind": "USE",
                    "detector": "import-graph",
                    "line": 0,
                    "snippet": name,
                    "module_name": name,
                }
            )
    constructed_file = repo / CONSTRUCTED_REL
    constructed_text = (
        constructed_file.read_text(encoding="utf-8") if constructed_file.is_file() else ""
    )
    literal_present = CONSTRUCTED_PATH in constructed_text
    collection = run_deleted_import(repo)
    return {
        "reconstructed_hits": reconstructed_hits,
        "import_hits": import_hits,
        "parse_errors": parse_errors,
        "constructed_path": CONSTRUCTED_PATH,
        "constructed_file": CONSTRUCTED_REL,
        "constructed_literal_absent": not literal_present,
        "constructed_rebuilt": any(
            h["deleted_path"] == CONSTRUCTED_PATH for h in reconstructed_hits
        ),
        "collection": collection,
        "deleted_module": DELETED_MODULE,
    }


def run_deleted_import(repo: Path) -> dict:
    target = repo / TEST_IMPORT_REL
    env_python = sys.executable
    try:
        p = subprocess.run(
            [env_python, "-B", str(target)],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=20,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "exit_code": 124,
            "error_names_deleted": False,
            "stderr": "TIMEOUT",
        }
    err = ((p.stderr or "") + (p.stdout or ""))
    names = DELETED_MODULE in err or "ModuleNotFoundError" in err
    return {
        "ok": p.returncode != 0 and names,
        "exit_code": p.returncode,
        "error_names_deleted": DELETED_MODULE in err,
        "stderr": err[-1500:],
        "command": f"{env_python} -B {TEST_IMPORT_REL}",
    }


def control_verdict(runtime: dict) -> dict:
    rebuilt = bool(runtime.get("constructed_rebuilt"))
    absent = bool(runtime.get("constructed_literal_absent"))
    collection_ok = bool((runtime.get("collection") or {}).get("ok"))
    named = bool((runtime.get("collection") or {}).get("error_names_deleted"))
    import_hit = any(
        h.get("module_name") == DELETED_MODULE for h in runtime.get("import_hits") or []
    )
    return {
        "constructed_rebuilt": rebuilt,
        "constructed_literal_absent": absent,
        "collection_error_on_deleted_import": collection_ok,
        "error_names_deleted_module": named,
        "import_graph_hit": import_hit,
        "pass": rebuilt and absent and collection_ok and named and import_hit,
    }
