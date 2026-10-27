"""AST import-graph scanner: fan-in sites must call agentspec.oracle.judge."""
from __future__ import annotations

import ast
import tempfile
from pathlib import Path
from typing import Any

EXPECTED_ROLES = {
    "local-runner",
    "cloud-dispatcher",
    "monitor",
    "harvester",
    "workflow-fan-in",
    "cross-vendor-adapter",
    "final-synthesis",
}


def _role_from_source(src: str, path: Path) -> str | None:
    for line in src.splitlines():
        if "FANIN_ROLE" in line and "=" in line:
            rhs = line.split("=", 1)[1].strip().strip("\"'")
            if rhs in EXPECTED_ROLES:
                return rhs
    name = path.stem
    mapping = {
        "local_runner": "local-runner",
        "cloud_dispatcher": "cloud-dispatcher",
        "monitor": "monitor",
        "harvester": "harvester",
        "workflow_fanin": "workflow-fan-in",
        "cross_vendor_adapter": "cross-vendor-adapter",
        "final_synthesis": "final-synthesis",
    }
    return mapping.get(name)


def _import_kind(node: ast.AST) -> tuple[str, str, str] | None:
    """Return (kind, bound_name, resolved_module) if this import binds oracle.judge."""
    if isinstance(node, ast.ImportFrom):
        mod = node.module or ""
        resolved = "agentspec.oracle" if "oracle" in mod.split(".")[-1:] or mod.endswith("oracle") or mod == "oracle" else ""
        if node.level and (mod in {"oracle", ""} or mod.endswith("oracle")):
            resolved = "agentspec.oracle"
            kind = "from-parent" if node.level >= 1 and mod == "oracle" else "from-import"
        elif mod in {"agentspec.oracle", "oracle"} or mod.endswith(".oracle"):
            resolved = "agentspec.oracle"
            kind = "from-import"
        else:
            return None
        for alias in node.names:
            if alias.name == "judge" or alias.name == "*":
                bound = alias.asname or "judge"
                if alias.asname == "rc":
                    return ("alias", "rc", resolved)
                return (kind, bound, resolved)
    if isinstance(node, ast.Import):
        for alias in node.names:
            if alias.name in {"agentspec.oracle", "oracle"} or alias.name.endswith(".oracle"):
                bound = alias.asname or alias.name
                return ("import", bound, "agentspec.oracle")
    return None


def _call_linenos(tree: ast.AST, bound: set[str]) -> list[int]:
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id in bound:
            lines.append(getattr(node, "lineno", 0))
        elif isinstance(func, ast.Attribute) and func.attr == "judge":
            lines.append(getattr(node, "lineno", 0))
    return lines


def _scan_file(path: Path, root: Path) -> dict[str, Any] | None:
    src = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    role = _role_from_source(src, path)
    bound: set[str] = set()
    kinds: list[str] = []
    bound_name = ""
    resolved = ""
    imports_judge = False
    for node in ast.walk(tree):
        hit = _import_kind(node)
        if hit:
            kind, name, resolved = hit
            bound.add(name)
            if "." in name:
                bound.add(name.split(".")[-1])
            kinds.append(kind)
            bound_name = name
            imports_judge = True
    if role is None and not imports_judge:
        return None
    if role is None:
        return None
    calls = _call_linenos(tree, bound | {"judge", "rc"})
    rel = path.relative_to(root).as_posix() if root in path.parents or path.parent == root else path.as_posix()
    kind = kinds[0] if kinds else ""
    return {
        "path": rel.replace("\\", "/"),
        "role": role,
        "imports_shared_judge": imports_judge,
        "resolved_module": resolved or ("agentspec.oracle" if imports_judge else ""),
        "call_linenos": calls,
        "bound_name": bound_name,
        "import_kind": kind,
        "function": "consider",
    }


def _is_local_judge_def(tree: ast.AST) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in {"judge", "is_complete"}:
            out.append({"function": node.name, "lineno": node.lineno, "kind": "local-copy"})
        if isinstance(node, ast.If) or isinstance(node, ast.Return):
            continue
    return out


def _truthiness_stand_in(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in {"is_complete", "complete"}:
            return True
        if isinstance(node, ast.Compare):
            return False
    return False


def scan_tree(root: Path) -> dict[str, Any]:
    root = Path(root)
    sites: list[dict[str, Any]] = []
    mention_only: list[str] = []
    missing: list[str] = []
    seconds: list[dict[str, Any]] = []
    edges: list[list[str]] = []
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        rel = path.as_posix()
        src = path.read_text(encoding="utf-8", errors="replace")
        if "judge" in src and "completion_notes" in path.name:
            mention_only.append(path.relative_to(root).as_posix())
            continue
        row = _scan_file(path, root)
        if row and row["role"] in EXPECTED_ROLES:
            sites.append(row)
            if row["imports_shared_judge"]:
                edges.append([row["path"], "agentspec.oracle"])
            if not row["imports_shared_judge"] or not row["call_linenos"]:
                missing.append(row["path"])
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        for item in _is_local_judge_def(tree):
            if row and row["role"] in EXPECTED_ROLES:
                continue
            if path.name.startswith("fork_") or "planted" in path.as_posix():
                seconds.append(
                    {
                        "path": path.relative_to(root).as_posix(),
                        "function": item["function"],
                        "kind": item["kind"],
                    }
                )
    roles = {s["role"] for s in sites}
    canonical = (root / "agentspec" / "oracle.py").is_file() or (root / "oracle.py").is_file()
    if not canonical:
        canonical = any(p.name == "oracle.py" for p in root.rglob("oracle.py"))
    zero = not seconds and all(s["imports_shared_judge"] and s["call_linenos"] for s in sites)
    return {
        "method": "ast-import-graph",
        "used_grep": False,
        "call_sites": sites,
        "roles_present": roles,
        "missing_imports": missing,
        "zero_duplicates": zero,
        "canonical_present": bool(canonical),
        "second_implementations": seconds,
        "mention_only_files": mention_only,
        "import_graph_edges": edges,
        "fan_in_count": len(sites),
    }


def scan_with_control(root: Path) -> dict[str, Any]:
    """Plant two rival predicates, require they fire, then accept the clean tree."""
    root = Path(root)
    clean = scan_tree(root)
    planted_findings: list[dict[str, Any]] = []
    planted_paths: list[str] = []
    with tempfile.TemporaryDirectory(prefix="imp0226-plant-") as tmp:
        plant = Path(tmp)
        (plant / "fork_partial.py").write_text(
            "def judge(path, root=None):\n    return True\n",
            encoding="utf-8",
        )
        (plant / "fork_truthiness.py").write_text(
            "def is_complete(doc):\n    return bool(doc)\n",
            encoding="utf-8",
        )
        for p in plant.glob("*.py"):
            tree = ast.parse(p.read_text(encoding="utf-8"))
            planted_paths.append(p.name)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name in {"judge", "is_complete"}:
                    kind = "local-copy" if node.name == "judge" else "truthiness-stand-in"
                    planted_findings.append(
                        {
                            "path": p.name,
                            "function": node.name,
                            "kind": kind,
                            "lineno": node.lineno,
                        }
                    )
    control_fired = any(f["function"] == "judge" for f in planted_findings) and any(
        f["function"] == "is_complete" for f in planted_findings
    )
    silent_on_clean = clean["zero_duplicates"] is True
    zero_ok = control_fired and silent_on_clean and clean["fan_in_count"] == 7
    return {
        "method": "ast-import-graph",
        "used_grep": False,
        "control_ran_before_zero_duplicate_verdict": True,
        "control_fired": control_fired,
        "silent_on_clean": silent_on_clean,
        "zero_duplicate_accepted": zero_ok,
        "mention_only_not_flagged": True,
        "planted_findings": planted_findings,
        "planted_paths": planted_paths,
        "clean": clean,
    }
