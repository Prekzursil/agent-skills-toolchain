#!/usr/bin/env python3
"""Entry-point reachability census for BLD-0002.

Builds a static import graph over a shipped package tree, marks entry points
from plugin/hook/MCP/workflow/CI sources plus ``if __name__ == "__main__"``
guards, overlays a dynamic-import search, then emits the unreachable set.

False unreachability is the dangerous direction (it invites deletion). When a
symbol cannot be resolved conservatively, it is treated as reachable.
"""
from __future__ import annotations

import ast
import json
import re
import xml.etree.ElementTree as ET
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Iterable

SKIP_DIRS = frozenset(
    {
        "__pycache__",
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "_deps",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "dist",
        "build",
    }
)
MODULE_KEYS = frozenset(
    {
        "module",
        "entry",
        "command",
        "script",
        "import",
        "target",
        "qualified_name",
        "entry_point",
        "entrypoint",
        "py_module",
        "python_module",
        "dynamic_module",
    }
)
SYMBOL_KEYS = frozenset({"handler", "function", "callable", "symbol", "method"})
CI_MOD_RE = re.compile(r"\bpython(?:3)?\s+-m\s+([A-Za-z_][\w.]*)")
CI_PY_RE = re.compile(
    r"\bpython(?:3)?\s+((?:[A-Za-z0-9_.-]+[/\\])+[A-Za-z0-9_.-]+\.py)"
)
MOD_TOKEN_RE = re.compile(r"\b[A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)+\b")
ENTRY_SPEC_RE = re.compile(
    r"^([A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)+)(?::([A-Za-z_][\w]*))?$"
)
DYNAMIC_CALLS = frozenset(
    {"import_module", "__import__", "import_module_from", "load_module"}
)


def list_py_files(root: Path) -> list[Path]:
    out: list[Path] = []
    if not root.is_dir():
        return out
    for path in root.rglob("*.py"):
        if any(part in SKIP_DIRS or part.startswith(".") for part in path.parts):
            continue
        out.append(path)
    return sorted(out)


def modname(py_file: Path, root: Path) -> str:
    rel = py_file.resolve().relative_to(root.resolve()).with_suffix("")
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def parse_ast(path: Path) -> ast.AST | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return None


def _import_targets(node: ast.AST, me: str) -> list[str]:
    targets: list[str] = []
    if isinstance(node, ast.Import):
        targets.extend(a.name for a in node.names if a.name)
    elif isinstance(node, ast.ImportFrom):
        if node.level:
            base = me.split(".")[: max(len(me.split(".")) - node.level, 0)]
            if node.module:
                targets.append(".".join(base + [node.module]))
            elif base:
                targets.append(".".join(base))
        elif node.module:
            targets.append(node.module)
    return targets


def resolve_import(target: str, known: set[str], siblings: dict[tuple[str, str], str]) -> str | None:
    parts = target.split(".")
    for i in range(len(parts), 0, -1):
        cand = ".".join(parts[:i])
        if cand in known:
            return cand
    leaf = parts[0]
    for (_parent, name), full in siblings.items():
        if name == leaf:
            return full
    return None


def build_import_graph(files: list[Path], root: Path) -> tuple[dict[str, set[str]], dict[str, Path]]:
    known = {modname(p, root): p for p in files if modname(p, root)}
    siblings: dict[tuple[str, str], str] = {}
    for path in files:
        name = modname(path, root)
        siblings[(str(path.parent.resolve()), path.stem)] = name
    edges: dict[str, set[str]] = defaultdict(set)
    for path in files:
        me = modname(path, root)
        edges.setdefault(me, set())
        tree = parse_ast(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            for target in _import_targets(node, me):
                hit = resolve_import(target, set(known), siblings)
                if hit and hit != me:
                    edges[me].add(hit)
            if isinstance(node, ast.ImportFrom) and node.module:
                for alias in node.names:
                    qualified = f"{node.module}.{alias.name}"
                    hit = resolve_import(qualified, set(known), siblings)
                    if hit and hit != me:
                        edges[me].add(hit)
    return edges, known


def _call_name(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Call):
        return None
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _const_str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def module_has_dynamic_import(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        name = _call_name(node)
        if name in DYNAMIC_CALLS:
            return True
        if isinstance(node, ast.Attribute) and node.attr == "entry_points":
            return True
    return False


def literal_dynamic_targets(tree: ast.AST, known: set[str]) -> set[str]:
    hits: set[str] = set()
    for node in ast.walk(tree):
        if _call_name(node) not in DYNAMIC_CALLS:
            continue
        if not isinstance(node, ast.Call) or not node.args:
            continue
        literal = _const_str(node.args[0])
        if literal and literal in known:
            hits.add(literal)
        elif literal:
            for k in known:
                if k == literal or k.startswith(literal + ".") or literal.startswith(k + "."):
                    hits.add(k)
    return hits


def collect_config_module_strings(root: Path, known: set[str]) -> set[str]:
    found: set[str] = set()
    patterns = ("*.json", "*.yml", "*.yaml", "*.toml", "*.cfg", "*.ini")
    files: list[Path] = []
    for pat in patterns:
        files.extend(root.rglob(pat))
    for path in files:
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for token in MOD_TOKEN_RE.findall(text):
            if token in known:
                found.add(token)
        for spec in re.findall(r"[A-Za-z_][\w.]*(?::[A-Za-z_][\w]*)", text):
            mod = spec.split(":", 1)[0]
            if mod in known:
                found.add(mod)
    return found


def apply_dynamic_edges(
    edges: dict[str, set[str]],
    known_files: dict[str, Path],
    root: Path,
) -> dict[str, Any]:
    known = set(known_files)
    config_mods = collect_config_module_strings(root, known)
    dynamic_modules: list[str] = []
    literal_edges = 0
    config_edges = 0
    for name, path in known_files.items():
        tree = parse_ast(path)
        if tree is None:
            continue
        for target in literal_dynamic_targets(tree, known):
            if target != name:
                edges[name].add(target)
                literal_edges += 1
        if module_has_dynamic_import(tree):
            dynamic_modules.append(name)
            for target in config_mods:
                if target != name:
                    edges[name].add(target)
                    config_edges += 1
    return {
        "dynamic_importer_modules": sorted(dynamic_modules),
        "config_named_modules": sorted(config_mods),
        "literal_dynamic_edges": literal_edges,
        "config_dynamic_edges": config_edges,
    }


def public_functions(path: Path, module: str) -> list[dict[str, Any]]:
    tree = parse_ast(path)
    if tree is None:
        return []
    rows: list[dict[str, Any]] = []

    def consider(fn: ast.FunctionDef | ast.AsyncFunctionDef, qual: str, decorated: bool) -> None:
        if fn.name.startswith("_"):
            return
        rows.append(
            {
                "symbol": f"{module}:{qual}",
                "name": fn.name,
                "module": module,
                "line": int(fn.lineno),
                "decorated": decorated,
            }
        )

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            consider(node, node.name, bool(node.decorator_list))
        elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    consider(
                        child,
                        f"{node.name}.{child.name}",
                        bool(child.decorator_list),
                    )
    return rows


def loaded_names(path: Path) -> set[str]:
    tree = parse_ast(path)
    names: set[str] = set()
    if tree is None:
        return names
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.alias) and node.name:
            names.add(node.name.split(".")[-1])
            if node.asname:
                names.add(node.asname)
    return names


def is_test_surface(module: str, path: Path | None = None) -> bool:
    """Tests are not user-facing entry points (AUD-0032 vs BLD-0002 delta)."""
    if ".tests." in module or module.endswith(".tests") or ".test." in module:
        return True
    parts = module.split(".")
    if any(p in {"tests", "test"} for p in parts):
        return True
    if path is not None:
        if any(p in {"tests", "test"} for p in path.parts):
            return True
        name = path.name
        if name.startswith("test_") or name.endswith("_test.py"):
            return True
    return False


def has_main_guard(path: Path) -> int | None:
    tree = parse_ast(path)
    if tree is None:
        return None
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.ops[0], ast.Eq):
            left, comps = test.left, test.comparators
            pair = (_const_str(left), _const_str(comps[0]) if comps else None)
            rev = (_const_str(comps[0]) if comps else None, _const_str(left))
            names = set()
            if isinstance(left, ast.Name):
                names.add(left.id)
            if comps and isinstance(comps[0], ast.Name):
                names.add(comps[0].id)
            if "__name__" in names and ("__main__" in pair or "__main__" in rev):
                return int(node.lineno)
    return None


def _relpath(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _anchor(path: Path, root: Path, needle: str) -> tuple[str, int]:
    rel = _relpath(path, root)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return rel, 1
    idx = text.find(needle)
    if idx < 0:
        return rel, 1
    return rel, text[:idx].count("\n") + 1


def _add_ep(
    entries: list[dict[str, Any]],
    *,
    module: str,
    symbol: str | None,
    kind: str,
    source: Path,
    root: Path,
    needle: str,
    seen: set[tuple[str, str, str]],
) -> None:
    key = (module, symbol or "", kind)
    if key in seen:
        return
    seen.add(key)
    rel, line = _anchor(source, root, needle)
    entries.append(
        {
            "module": module,
            "symbol": symbol,
            "kind": kind,
            "source_path": rel,
            "line": line,
            "anchor": f"{rel}:{line}",
        }
    )


def _walk_json_modules(obj: Any, known: set[str]) -> Iterable[tuple[str, str | None, str]]:
    if isinstance(obj, dict):
        module_here: str | None = None
        symbol_here: str | None = None
        needle_here = ""
        for key, val in obj.items():
            if not isinstance(val, str):
                continue
            key_l = str(key).lower()
            spec = ENTRY_SPEC_RE.match(val.strip())
            if spec and spec.group(1) in known:
                module_here = spec.group(1)
                symbol_here = spec.group(2) or symbol_here
                needle_here = val
            elif key_l in MODULE_KEYS or key_l.endswith("_module"):
                if val in known:
                    module_here = val
                    needle_here = val
                dotted = val.replace("/", ".").removesuffix(".py")
                spec2 = ENTRY_SPEC_RE.match(dotted)
                if spec2 and spec2.group(1) in known:
                    module_here = spec2.group(1)
                    symbol_here = spec2.group(2) or symbol_here
                    needle_here = val
            elif key_l in SYMBOL_KEYS and re.fullmatch(
                r"[A-Za-z_][\w]*", val
            ):
                symbol_here = val
                if not needle_here:
                    needle_here = val
        if module_here:
            yield module_here, symbol_here, needle_here or module_here
        for val in obj.values():
            if isinstance(val, (dict, list)):
                yield from _walk_json_modules(val, known)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk_json_modules(item, known)


def harvest_manifest_entry_points(
    root: Path, known: set[str], kind_globs: list[tuple[str, str]]
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    files: list[tuple[str, Path]] = []
    for kind, pattern in kind_globs:
        for path in root.rglob(pattern):
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            files.append((kind, path))
    for kind, path in files:
        if path.suffix.lower() not in {".json", ".toml"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            doc = json.loads(text)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        for module, symbol, needle in _walk_json_modules(doc, known):
            _add_ep(
                entries,
                module=module,
                symbol=symbol,
                kind=kind,
                source=path,
                root=root,
                needle=needle,
                seen=seen,
            )
    return entries


def harvest_ci_entry_points(
    texts: list[tuple[Path, str]],
    known: set[str],
    root: Path,
    package_root_name: str,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for path, text in texts:
        for line in text.splitlines():
            if "pytest" in line:
                continue
            for match in CI_MOD_RE.finditer(line):
                mod = match.group(1)
                if mod in known and not is_test_surface(mod):
                    _add_ep(
                        entries,
                        module=mod,
                        symbol=None,
                        kind="ci_invocation",
                        source=path,
                        root=root,
                        needle=match.group(0),
                        seen=seen,
                    )
            for match in CI_PY_RE.finditer(line):
                raw = match.group(1).replace("\\", "/")
                parts = Path(raw).with_suffix("").parts
                if parts and parts[0] == package_root_name:
                    parts = parts[1:]
                cand = ".".join(parts)
                if cand in known and not is_test_surface(cand, Path(raw)):
                    _add_ep(
                        entries,
                        module=cand,
                        symbol=None,
                        kind="ci_invocation",
                        source=path,
                        root=root,
                        needle=match.group(0),
                        seen=seen,
                    )
    return entries


def harvest_cli_mains(known_files: dict[str, Path], root: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for module, path in known_files.items():
        if is_test_surface(module, path):
            continue
        line = has_main_guard(path)
        if line is None:
            continue
        _add_ep(
            entries,
            module=module,
            symbol=None,
            kind="cli_main_guard",
            source=path,
            root=root,
            needle='if __name__ == "__main__"',
            seen=seen,
        )
    return entries


def reachable_from(entry_modules: Iterable[str], edges: dict[str, set[str]]) -> set[str]:
    start = [m for m in entry_modules if m in edges or True]
    seen: set[str] = set()
    q = deque(start)
    while q:
        cur = q.popleft()
        if cur in seen:
            continue
        seen.add(cur)
        for nxt in edges.get(cur, ()):
            if nxt not in seen:
                q.append(nxt)
    return seen


def parse_coverage_files(coverage_xml: Path, known_files: dict[str, Path], root: Path) -> set[str]:
    covered: set[str] = set()
    if not coverage_xml.is_file():
        return covered
    try:
        tree = ET.parse(coverage_xml)
    except (OSError, ET.ParseError):
        return covered
    filenames: list[str] = []
    for cls in tree.iter("class"):
        hits = False
        for line in cls.iter("line"):
            try:
                if int(line.get("hits") or "0") > 0:
                    hits = True
                    break
            except ValueError:
                continue
        if not hits:
            continue
        filenames.append((cls.get("filename") or cls.get("name") or "").replace("\\", "/"))
    for module, path in known_files.items():
        rel = path.relative_to(root).as_posix()
        for fn in filenames:
            if not fn:
                continue
            if fn == rel or rel.endswith(fn) or fn.endswith(rel) or Path(fn).stem == path.stem:
                covered.add(module)
                break
    return covered


def load_aud0032_dead(path: Path) -> tuple[str, set[str]]:
    if not path.is_file():
        return "absent", set()
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return "unparseable", set()
    dead: set[str] = set()
    if not isinstance(doc, dict):
        return "unparseable", dead
    for key in ("dead_modules", "unreferenced_modules", "unreachable_modules"):
        val = doc.get(key)
        if isinstance(val, list):
            for item in val:
                if isinstance(item, str):
                    dead.add(item)
                elif isinstance(item, dict) and isinstance(item.get("module"), str):
                    dead.add(item["module"])
    return "present", dead


def run_census(
    package_root: Path,
    *,
    extra_ci_texts: list[tuple[Path, str]] | None = None,
    coverage_xml: Path | None = None,
    aud0032_path: Path | None = None,
    package_root_name: str | None = None,
) -> dict[str, Any]:
    root = package_root.resolve()
    files = list_py_files(root)
    edges, known_files = build_import_graph(files, root)
    dyn = apply_dynamic_edges(edges, known_files, root)
    known = set(known_files)
    pkg_name = package_root_name or root.name

    manifest_eps = harvest_manifest_entry_points(
        root,
        known,
        [
            ("plugin_manifest", "plugin.json"),
            ("plugin_manifest", "*plugin*.json"),
            ("hook_manifest", "hooks.json"),
            ("hook_manifest", "hooks/*.json"),
            ("mcp_export", "mcp/*.json"),
            ("mcp_export", "*mcp*.json"),
            ("workflow_stage", "workflows/*.json"),
            ("workflow_stage", "registry.json"),
        ],
    )
    ci_texts: list[tuple[Path, str]] = []
    for path in list(root.rglob("*.yml")) + list(root.rglob("*.yaml")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        try:
            ci_texts.append((path, path.read_text(encoding="utf-8", errors="replace")))
        except OSError:
            continue
    if extra_ci_texts:
        ci_texts.extend(extra_ci_texts)
    ci_eps = harvest_ci_entry_points(ci_texts, known, root, pkg_name)
    cli_eps = harvest_cli_mains(known_files, root)
    entry_points = manifest_eps + ci_eps + cli_eps

    entry_modules = sorted({e["module"] for e in entry_points if e["module"] in known})
    handler_symbols = {
        f"{e['module']}:{e['symbol']}"
        for e in entry_points
        if e.get("symbol")
    }
    reached = reachable_from(entry_modules, edges)
    # Package parents of a reachable module are live: deleting __init__.py
    # would break the entry. This is the safe direction.
    extra_parents: set[str] = set()
    for name in list(reached) + entry_modules:
        parts = name.split(".")
        for i in range(1, len(parts)):
            parent = ".".join(parts[:i])
            if parent in known:
                extra_parents.add(parent)
    reached |= extra_parents

    unreachable_modules = sorted(m for m in known if m not in reached)
    covered = parse_coverage_files(
        coverage_xml or (root / "coverage.xml"),
        known_files,
        root,
    )
    aud_status, aud_dead = load_aud0032_dead(
        aud0032_path or Path("/nonexistent")
    )
    delta_modules = sorted(m for m in unreachable_modules if m not in aud_dead)

    reached_names: set[str] = set()
    for module in reached:
        path = known_files.get(module)
        if path is not None:
            reached_names |= loaded_names(path)

    static_imported: set[str] = set(entry_modules)
    dyn_importers = set(dyn["dynamic_importer_modules"])
    for src, dsts in edges.items():
        if src in dyn_importers:
            continue
        static_imported.update(dsts)

    unreachable_functions: list[dict[str, Any]] = []
    for module, path in known_files.items():
        for fn in public_functions(path, module):
            symbol = fn["symbol"]
            if fn["name"] in reached_names or fn["decorated"] or symbol in handler_symbols:
                continue
            if (
                module in dyn["config_named_modules"]
                and module in reached
                and module not in static_imported
            ):
                continue
            if module not in reached:
                reason = "module-unreachable-from-entry-points"
            else:
                reason = "public-function-unreferenced-in-reachable-ast"
            unreachable_functions.append(
                {
                    "symbol": symbol,
                    "module": module,
                    "line": fn["line"],
                    "reason": reason,
                    "deletion_safe": False,
                }
            )
    unreachable_functions.sort(key=lambda r: r["symbol"])

    covered_but_unreachable: list[dict[str, Any]] = []
    for module in unreachable_modules:
        if module not in covered:
            continue
        path = known_files[module]
        rel = path.relative_to(root).as_posix()
        covered_but_unreachable.append(
            {
                "module": module,
                "path": rel,
                "reason_code": "covered-by-tests-no-user-facing-entry-point",
                "explanation": (
                    f"{rel} has coverage hits but is not reachable from plugin "
                    "commands, hook registrations, MCP exports, workflow stages, "
                    "CI production invocations, or CLI __main__ guards."
                ),
            }
        )

    serial_edges = {k: sorted(v) for k, v in sorted(edges.items())}
    return {
        "package_root": str(root),
        "module_count": len(known),
        "entry_point_count": len(entry_points),
        "entry_modules": entry_modules,
        "entry_points": sorted(entry_points, key=lambda e: (e["kind"], e["module"], e["anchor"])),
        "reachable_module_count": len(reached),
        "unreachable_modules": [
            {
                "module": m,
                "path": known_files[m].relative_to(root).as_posix(),
                "dynamic_import_search_survived": True,
                "deletion_safe": False,
                "reason_code": (
                    "test-only-no-user-facing-entry-point"
                    if is_test_surface(m, known_files[m])
                    else "no-path-from-declared-entry-points"
                ),
                "explanation": (
                    "Referenced by tests or present as a test module, but not "
                    "reachable from a plugin command, hook registration, MCP "
                    "export, workflow stage, CI production invocation, or CLI "
                    "__main__ guard."
                    if is_test_surface(m, known_files[m])
                    else "No import/call path from the declared entry-point set "
                    "after dynamic-import search (importlib, __import__, "
                    "config-named modules, plugin glob)."
                ),
            }
            for m in unreachable_modules
        ],
        "unreachable_functions": unreachable_functions,
        "covered_modules": sorted(covered),
        "covered_but_unreachable": covered_but_unreachable,
        "aud0032": {"status": aud_status, "dead_count": len(aud_dead)},
        "aud0032_delta_modules": delta_modules,
        "dynamic_import_search": dyn,
        "edges": serial_edges,
        "known_modules": sorted(known),
    }
