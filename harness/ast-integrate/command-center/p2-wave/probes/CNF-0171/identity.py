"""Structural identity of completion.reducer.judge at the six declared sites.

Primary signal: import-graph + bound-object identity + code-object origin.
Behavioural agreement is a second signal only.
"""
from __future__ import annotations

import ast
import hashlib
import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from completion.census import import_graph_site  # noqa: E402
from completion.reducer import judge as LIBRARY_JUDGE  # noqa: E402
from completion.sites import SITE_FILES, load_site  # noqa: E402

DECLARED_SITE_IDS: tuple[str, ...] = (
    "local_runner",
    "cloud_dispatcher",
    "monitor",
    "harvester",
    "workflow_fanin",
    "cross_vendor_adapter",
)
SEVENTH_SITE_ID = "final_synthesis"
SHARED_SYMBOL = "completion.reducer.judge"
LIBRARY_MOD = "completion.reducer"
SITE_ALIASES: dict[str, tuple[str, str]] = {
    "local_runner": ("exit_code", "output_path"),
    "cloud_dispatcher": ("rc", "artifact"),
    "monitor": ("exit_code", "receipt_path"),
    "harvester": ("harvest_rc", "harvested"),
    "workflow_fanin": ("step_rc", "workflow_artifact"),
    "cross_vendor_adapter": ("vendor_rc", "vendor_output"),
    "final_synthesis": ("synth_rc", "report_path"),
    "dynamic_fixture": ("exit_code", "artifact_path"),
}

_DYNAMIC_ATTRS = frozenset({"import_module", "__import__", "spec_from_file_location"})
_SKIP_DIRS = frozenset(
    {".git", ".work", "__pycache__", "node_modules", "receipts", "adversarial", "casualty", ".pytest_cache"}
)


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def library_origin() -> Path:
    spec = importlib.util.find_spec(LIBRARY_MOD)
    if spec is None or not spec.origin:
        raise RuntimeError("completion.reducer has no import spec origin")
    return Path(spec.origin).resolve()


def judge_ast_fingerprint(source_path: Path) -> str | None:
    try:
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "judge":
            dumped = ast.dump(node, include_attributes=False)
            return hashlib.sha256(dumped.encode("utf-8")).hexdigest()
    return None


def _call_attr(func: ast.AST) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _const_str(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def ast_import_facts(source: str) -> dict[str, Any]:
    tree = ast.parse(source)
    facts: dict[str, Any] = {
        "imported_judge_static": False,
        "imported_reducer_module_static": False,
        "calls_judge": False,
        "local_judge_def_lines": [],
        "import_from_modules": [],
        "dynamic_imports": [],
        "dynamic_unresolved": [],
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            facts["import_from_modules"].append(mod)
            if mod in {LIBRARY_MOD, "completion"}:
                facts["imported_reducer_module_static"] = True
            for alias in node.names:
                if alias.name == "judge" and mod in {LIBRARY_MOD, "completion"}:
                    facts["imported_judge_static"] = True
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in {LIBRARY_MOD, "completion"}:
                    facts["imported_reducer_module_static"] = True
        elif isinstance(node, ast.FunctionDef) and node.name == "judge":
            facts["local_judge_def_lines"].append(int(node.lineno))
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "judge":
                facts["calls_judge"] = True
            if isinstance(node.func, ast.Attribute) and node.func.attr == "judge":
                facts["calls_judge"] = True
            attr = _call_attr(node.func)
            if attr in _DYNAMIC_ATTRS:
                name = _const_str(node.args[0] if node.args else None)
                rec = {
                    "kind": attr,
                    "lineno": int(getattr(node, "lineno", 0) or 0),
                    "module_string": name,
                }
                if name:
                    facts["dynamic_imports"].append(rec)
                else:
                    rec["status"] = "NOT-CHECKED"
                    rec["reason"] = "dynamic import argument is not a string literal"
                    facts["dynamic_unresolved"].append(rec)
    return facts


def describe_bound_judge(fn: Any) -> dict[str, Any]:
    code = getattr(fn, "__code__", None)
    filename = str(code.co_filename) if code is not None else ""
    origin = Path(filename).resolve() if filename else None
    lib = library_origin()
    return {
        "qualname": getattr(fn, "__qualname__", ""),
        "module": getattr(fn, "__module__", ""),
        "object_id": id(fn),
        "library_object_id": id(LIBRARY_JUDGE),
        "same_object_as_library": fn is LIBRARY_JUDGE,
        "co_filename": rel(origin) if origin else filename,
        "co_firstlineno": int(code.co_firstlineno) if code is not None else None,
        "library_origin": rel(lib),
        "co_filename_is_library": bool(origin and origin == lib),
        "ast_fingerprint_at_origin": judge_ast_fingerprint(origin)
        if origin and origin.is_file()
        else None,
        "library_ast_fingerprint": judge_ast_fingerprint(lib),
    }


def load_site_module(site_id: str) -> Any:
    return load_site(site_id)


def load_path_as_module(path: Path, modname: str) -> Any:
    spec = importlib.util.spec_from_file_location(modname, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


def resolve_site_file(path: Path, *, site_id: str, module: Any | None = None) -> dict[str, Any]:
    source = path.read_text(encoding="utf-8")
    facts = ast_import_facts(source)
    graph = import_graph_site(path)
    graph["path"] = rel(path)

    dynamic_resolved: list[dict[str, Any]] = []
    for dyn in facts["dynamic_imports"]:
        name = dyn.get("module_string") or ""
        spec = importlib.util.find_spec(name) if name else None
        origin = spec.origin if spec is not None else None
        dynamic_resolved.append(
            {
                **dyn,
                "resolved_origin": rel(Path(origin)) if origin else None,
                "is_library_module": bool(origin and Path(origin).resolve() == library_origin()),
                "status": "RESOLVED" if origin else "NOT-CHECKED",
            }
        )

    if module is None:
        module = load_path_as_module(path, f"cnf0171_{site_id}_{path.stem}_{id(path)}")
    bound = getattr(module, "judge", None)
    if not callable(bound):
        bound = None

    if bound is None:
        bound_info: dict[str, Any] = {
            "same_object_as_library": False,
            "reason": "module has no callable judge",
            "object_id": None,
        }
        identity_status = "NOT-CHECKED" if facts["dynamic_unresolved"] else "DIVERGENT"
    else:
        bound_info = describe_bound_judge(bound)
        if bound is LIBRARY_JUDGE and not facts["local_judge_def_lines"]:
            identity_status = "SHARED"
        else:
            identity_status = "DIVERGENT"

    static_ok = bool(
        facts["imported_judge_static"]
        and facts["calls_judge"]
        and facts["imported_reducer_module_static"]
        and graph.get("ok")
    )
    return {
        "site_id": site_id,
        "path": rel(path),
        "identity_status": identity_status,
        "static_import_graph_ok": static_ok,
        "census_import_graph": graph,
        "ast": {
            "imported_judge_static": facts["imported_judge_static"],
            "imported_reducer_module_static": facts["imported_reducer_module_static"],
            "calls_judge": facts["calls_judge"],
            "local_judge_def_lines": facts["local_judge_def_lines"],
            "import_from_modules": facts["import_from_modules"],
            "dynamic_imports": dynamic_resolved,
            "dynamic_unresolved": facts["dynamic_unresolved"],
        },
        "bound_judge": bound_info,
        "resolved_import_path": bound_info.get("co_filename") or bound_info.get("library_origin"),
        "object_id": bound_info.get("object_id"),
    }


def resolve_declared_sites() -> list[dict[str, Any]]:
    rows = []
    for site_id in DECLARED_SITE_IDS:
        path = REPO / SITE_FILES[site_id]
        rows.append(resolve_site_file(path, site_id=site_id, module=load_site_module(site_id)))
    return rows


def all_shared(rows: list[dict[str, Any]]) -> bool:
    if len(rows) != len(DECLARED_SITE_IDS):
        return False
    ids = {r.get("object_id") for r in rows}
    return (
        len(ids) == 1
        and None not in ids
        and all(r.get("identity_status") == "SHARED" for r in rows)
        and all(r.get("bound_judge", {}).get("same_object_as_library") for r in rows)
        and all(r.get("static_import_graph_ok") for r in rows)
    )


def vendor_copy_control(tmp: Path) -> dict[str, Any]:
    """Vendor a copy of the reducer into a fake call site; identity must fire."""
    src = library_origin()
    vendored = tmp / "vendored_reducer.py"
    vendored.write_bytes(src.read_bytes())
    site = tmp / "forked_local_runner.py"
    site.write_text(
        '''"""Known-broken control: vendored copy of the reducer, not the library object."""
from __future__ import annotations
from typing import Any, Mapping
from vendored_reducer import judge, observation_from_mapping

SITE_ID = "forked_local_runner"


def check_unit(payload: Mapping[str, Any]) -> dict[str, Any]:
    obs = observation_from_mapping(SITE_ID, payload)
    return judge(obs).as_dict()
''',
        encoding="utf-8",
    )
    if str(tmp) not in sys.path:
        sys.path.insert(0, str(tmp))
    import vendored_reducer as vendored_mod  # type: ignore  # noqa: E402

    row = resolve_site_file(site, site_id="forked_local_runner")
    ast_same = (
        row["bound_judge"].get("ast_fingerprint_at_origin")
        == row["bound_judge"].get("library_ast_fingerprint")
        and row["bound_judge"].get("ast_fingerprint_at_origin") is not None
    )
    fired = (
        row["identity_status"] == "DIVERGENT"
        and row["bound_judge"].get("same_object_as_library") is False
        and vendored_mod.judge is not LIBRARY_JUDGE
        and not row["static_import_graph_ok"]
    )
    return {
        "fired": fired,
        "vendored_path": rel(vendored),
        "site_path": rel(site),
        "vendored_judge_is_library": vendored_mod.judge is LIBRARY_JUDGE,
        "ast_fingerprint_matches_library": ast_same,
        "row": row,
        "note": (
            "A byte-copied reducer can share the judge AST and still be a second "
            "code object. Structural identity must fire on object/origin, not on "
            "behavioural agreement or AST equality alone."
        ),
    }


def find_undeclared_reducer_importers() -> list[dict[str, Any]]:
    declared_files = {SITE_FILES[s] for s in DECLARED_SITE_IDS}
    skip_prefixes = (
        "command-center/p2-wave/probes/",
        "tools/completion/tests/",
    )
    skip_exact = {
        "tools/completion/reducer.py",
        "tools/completion/census.py",
        "tools/completion/__init__.py",
        "tools/completion/sites/__init__.py",
    }
    needle = "from completion.reducer import"
    hits: list[dict[str, Any]] = []
    for path in sorted((REPO / "tools").rglob("*.py")):
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        rel_path = rel(path)
        if rel_path in declared_files or rel_path in skip_exact:
            continue
        if any(rel_path.startswith(p) for p in skip_prefixes):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if needle not in text:
            continue
        line = text[: text.find(needle)].count("\n") + 1
        hits.append({"path": rel_path, "line": line, "snippet": needle})
    return hits


def site_files_on_disk() -> list[str]:
    d = REPO / "tools" / "completion" / "sites"
    return sorted(p.name for p in d.glob("*.py") if p.name != "__init__.py")
