"""AUD-0054 census: decorator AST vs collect/execute, plus CI runs-on matrix."""
from __future__ import annotations

import ast
import json
import os
import sys
import types
import unittest
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURES = HERE / "fixtures"
LIVE_ROOTS = ("tools", "hooks", "platform")
SKIP_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".tox",
    "deps",
    "vendor",
}
PLATFORM_NEEDLES = (
    "sys.platform",
    "os.name",
    "platform.system",
    "win32",
    "windows",
    "linux",
    "darwin",
    "posix",
    "'nt'",
    '"nt"',
    "case_insensitive",
)
PLATFORMS = ("linux", "win32", "darwin")
RUNTIME_NODE = (
    "command-center/p2-wave/probes/AUD-0054/fixtures/test_platform_gates.py"
    "::PlatformGates::test_runtime_only_skip"
)
WINDOWS_NODE = (
    "command-center/p2-wave/probes/AUD-0054/fixtures/test_platform_gates.py"
    "::PlatformGates::test_windows_only"
)
POSIX_NODE = (
    "command-center/p2-wave/probes/AUD-0054/fixtures/test_platform_gates.py"
    "::PlatformGates::test_posix_only"
)


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO).as_posix()


def unparse(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:  # noqa: BLE001
        return ast.dump(node)


def _attr_chain(node: ast.AST) -> list[str]:
    parts: list[str] = []
    cur: ast.AST | None = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    return list(reversed(parts))


def decorator_kind(dec: ast.AST) -> str | None:
    target = dec.func if isinstance(dec, ast.Call) else dec
    if isinstance(target, ast.Name):
        chain = target.id
    else:
        chain = ".".join(_attr_chain(target))
    if chain.endswith("skipIf") or chain.lower().endswith("skipif"):
        return "skipif"
    if chain.endswith("skipUnless") or chain.lower().endswith("skipunless"):
        return "skipunless"
    if chain == "skip" or chain.endswith(".skip"):
        return "skip"
    return None


def decorator_predicate(dec: ast.AST) -> str:
    if not isinstance(dec, ast.Call):
        return ""
    for kw in dec.keywords:
        if kw.arg == "condition":
            return unparse(kw.value)
    if not dec.args:
        return ""
    arg0 = dec.args[0]
    if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
        return arg0.value
    return unparse(arg0)


def _fake_sys(platform: str) -> types.SimpleNamespace:
    return types.SimpleNamespace(
        platform=platform,
        maxsize=2**63 - 1,
        version_info=sys.version_info,
    )


def _fake_os(platform: str) -> types.SimpleNamespace:
    name = "nt" if platform.startswith("win") else "posix"
    sep = "\\" if name == "nt" else "/"
    return types.SimpleNamespace(name=name, path=types.SimpleNamespace(sep=sep))


def _fake_platform(platform: str) -> types.SimpleNamespace:
    system = {"win32": "Windows", "darwin": "Darwin", "linux": "Linux"}.get(
        platform, platform
    )
    return types.SimpleNamespace(
        system=lambda: system,
        machine=lambda: "x86_64",
    )


def eval_predicate(expr: str, platform: str) -> bool | None:
    if not expr.strip():
        return None
    ns = {
        "sys": _fake_sys(platform),
        "os": _fake_os(platform),
        "platform": _fake_platform(platform),
        "True": True,
        "False": False,
        "None": None,
    }
    try:
        val = eval(compile(expr, "<pred>", "eval"), {"__builtins__": {}}, ns)  # noqa: S307
    except Exception:  # noqa: BLE001
        return None
    return bool(val)


def would_skip(kind: str, expr: str, platform: str) -> bool | None:
    if kind == "skip":
        return True
    pred = eval_predicate(expr, platform)
    if pred is None:
        return None
    if kind == "skipunless":
        return not pred
    return pred


def required_platform(kind: str, expr: str) -> str:
    if kind == "skip":
        return "unconditional"
    skips = {p: would_skip(kind, expr, p) for p in PLATFORMS}
    if any(v is None for v in skips.values()):
        return "unresolved"
    required = [p for p, skip in skips.items() if skip is False]
    if not required:
        return "never"
    if set(required) == {"linux", "darwin"}:
        return "posix"
    if required == ["win32"]:
        return "windows"
    if required == ["linux"]:
        return "linux"
    if required == ["darwin"]:
        return "darwin"
    if len(required) == 3:
        return "all"
    return "+".join(required)


def looks_like_platform(expr: str, required: str) -> bool:
    if required in {"windows", "posix", "linux", "darwin", "never"}:
        return True
    low = (expr or "").lower()
    return any(n in low for n in PLATFORM_NEEDLES)


def art_section(doc: dict[str, Any], key: str) -> dict[str, Any]:
    """Read a census block from top-level, report, or extensions."""
    if isinstance(doc.get(key), dict):
        return doc[key]
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    if isinstance(report.get(key), dict):
        return report[key]
    ext = doc.get("extensions") if isinstance(doc.get("extensions"), dict) else {}
    if isinstance(ext.get(key), dict):
        return ext[key]
    return {}


@dataclass
class Gate:
    node_id: str
    path: str
    lineno: int
    kind: str
    predicate: str
    required_platform: str
    would_skip: dict[str, bool | None]
    population: str


@dataclass
class TestNode:
    node_id: str
    path: str
    name: str
    class_name: str | None
    lineno: int
    population: str
    gates: list[Gate] = field(default_factory=list)


def node_id_for(path: Path, class_name: str | None, name: str) -> str:
    rel_p = rel(path)
    if class_name:
        return f"{rel_p}::{class_name}::{name}"
    return f"{rel_p}::{name}"


def _gates_from(decs: list[ast.AST], nid: str, path: Path, population: str) -> list[Gate]:
    found: list[Gate] = []
    for dec in decs:
        kind = decorator_kind(dec)
        if kind is None:
            continue
        pred = decorator_predicate(dec)
        req = required_platform(kind, pred)
        found.append(
            Gate(
                node_id=nid,
                path=rel(path),
                lineno=int(getattr(dec, "lineno", 0) or 0),
                kind=kind,
                predicate=pred,
                required_platform=req,
                would_skip={p: would_skip(kind, pred, p) for p in PLATFORMS},
                population=population,
            )
        )
    return found


def _assign_pairs(node: ast.AST) -> list[tuple[str, ast.AST]]:
    out: list[tuple[str, ast.AST]] = []
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name):
                out.append((target.id, node.value))
    elif (
        isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.value is not None
    ):
        out.append((node.target.id, node.value))
    return out


def _mark_aliases(tree: ast.Module) -> dict[str, ast.AST]:
    aliases: dict[str, ast.AST] = {}
    for node in tree.body:
        for name, val in _assign_pairs(node):
            if decorator_kind(val) is not None:
                aliases[name] = val
            elif name == "pytestmark":
                aliases["__pytestmark__"] = val
    return aliases


def _as_decorator_list(node: ast.AST | None) -> list[ast.AST]:
    if node is None:
        return []
    if isinstance(node, ast.List):
        return list(node.elts)
    return [node]


def _expand_decorators(decs: list[ast.AST], aliases: dict[str, ast.AST]) -> list[ast.AST]:
    expanded: list[ast.AST] = []
    for dec in decs:
        if isinstance(dec, ast.Name) and dec.id in aliases:
            expanded.append(aliases[dec.id])
        else:
            expanded.append(dec)
    return expanded


def parse_file(path: Path, population: str) -> list[TestNode]:
    try:
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
    except (OSError, UnicodeDecodeError, SyntaxError):
        return []
    aliases = _mark_aliases(tree)
    module_marks = _expand_decorators(
        _as_decorator_list(aliases.get("__pytestmark__")), aliases
    )
    out: list[TestNode] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            class_decs = _expand_decorators(list(node.decorator_list), aliases)
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name.startswith(
                    "test_"
                ):
                    nid = node_id_for(path, node.name, item.name)
                    decs = module_marks + class_decs + _expand_decorators(
                        list(item.decorator_list), aliases
                    )
                    out.append(
                        TestNode(
                            nid,
                            rel(path),
                            item.name,
                            node.name,
                            item.lineno,
                            population,
                            _gates_from(decs, nid, path, population),
                        )
                    )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
            "test_"
        ):
            nid = node_id_for(path, None, node.name)
            decs = module_marks + _expand_decorators(list(node.decorator_list), aliases)
            out.append(
                TestNode(
                    nid,
                    rel(path),
                    node.name,
                    None,
                    node.lineno,
                    population,
                    _gates_from(decs, nid, path, population),
                )
            )
    return out


def iter_live_test_files() -> list[Path]:
    files: list[Path] = []
    for root_name in LIVE_ROOTS:
        root = REPO / root_name
        if not root.is_dir():
            continue
        for p in root.rglob("*.py"):
            if any(part in SKIP_DIRS for part in p.parts):
                continue
            if p.name.startswith("test_") or p.name.endswith("_test.py"):
                files.append(p)
    return sorted(files)


def _gate_dict(g: Gate) -> dict[str, Any]:
    return {
        "node_id": g.node_id,
        "path": g.path,
        "lineno": g.lineno,
        "kind": g.kind,
        "predicate": g.predicate,
        "required_platform": g.required_platform,
        "would_skip": g.would_skip,
        "population": g.population,
    }


def ast_census() -> dict[str, Any]:
    live_files = iter_live_test_files()
    fixture_files = sorted(FIXTURES.glob("test_*.py"))
    nodes: list[TestNode] = []
    for p in live_files:
        nodes.extend(parse_file(p, "live-suite"))
    for p in fixture_files:
        nodes.extend(parse_file(p, "control-fixture"))
    gates = [g for n in nodes for g in n.gates]
    platform_gates = [
        g
        for g in gates
        if g.kind in {"skipif", "skipunless"}
        and g.required_platform not in {"unconditional", "all"}
        and looks_like_platform(g.predicate, g.required_platform)
    ]
    decorator_ids = {g.node_id for g in platform_gates}
    return {
        "live_test_files": [rel(p) for p in live_files],
        "live_test_file_count": len(live_files),
        "fixture_test_files": [rel(p) for p in fixture_files],
        "nodes": [
            {
                "node_id": n.node_id,
                "path": n.path,
                "name": n.name,
                "class_name": n.class_name,
                "lineno": n.lineno,
                "population": n.population,
                "decorator_kinds": [g.kind for g in n.gates],
            }
            for n in nodes
        ],
        "gates": [_gate_dict(g) for g in gates],
        "platform_gates": [_gate_dict(g) for g in platform_gates],
        "live_platform_gate_count": sum(
            1 for g in platform_gates if g.population == "live-suite"
        ),
        "fixture_platform_gate_count": sum(
            1 for g in platform_gates if g.population == "control-fixture"
        ),
        "decorator_platform_node_ids": sorted(decorator_ids),
        "runtime_control_in_decorator_scan": RUNTIME_NODE in decorator_ids,
        "windows_control_in_decorator_scan": WINDOWS_NODE in decorator_ids,
        "posix_control_in_decorator_scan": POSIX_NODE in decorator_ids,
        "live_test_function_count": sum(1 for n in nodes if n.population == "live-suite"),
        "fixture_test_function_count": sum(
            1 for n in nodes if n.population == "control-fixture"
        ),
    }


class _Result(unittest.TestResult):
    def __init__(self) -> None:
        super().__init__()
        self.by_id: dict[str, str] = {}

    def startTest(self, test: unittest.TestCase) -> None:  # noqa: N802
        super().startTest(test)
        self.by_id.setdefault(_testid(test), "started")

    def addSuccess(self, test: unittest.TestCase) -> None:  # noqa: N802
        super().addSuccess(test)
        self.by_id[_testid(test)] = "passed"

    def addFailure(self, test: unittest.TestCase, err: Any) -> None:  # noqa: N802
        super().addFailure(test, err)
        self.by_id[_testid(test)] = "failed"

    def addError(self, test: unittest.TestCase, err: Any) -> None:  # noqa: N802
        super().addError(test, err)
        self.by_id[_testid(test)] = "error"

    def addSkip(self, test: unittest.TestCase, reason: str) -> None:  # noqa: N802
        super().addSkip(test, reason)
        self.by_id[_testid(test)] = f"skipped:{reason}"


def _testid(test: unittest.TestCase) -> str:
    raw = test.id()
    parts = raw.split(".")
    if len(parts) >= 3:
        mod, cls, meth = parts[0], parts[1], parts[2]
        path = rel(FIXTURES / f"{mod}.py")
        return f"{path}::{cls}::{meth}"
    return raw


def run_fixture_suite() -> dict[str, Any]:
    loader = unittest.defaultTestLoader
    suite = loader.discover(str(FIXTURES), pattern="test_*.py")
    result = _Result()
    suite.run(result)
    collected = sorted(result.by_id)
    executed = sorted(nid for nid, st in result.by_id.items() if not st.startswith("skipped"))
    skipped = sorted(nid for nid, st in result.by_id.items() if st.startswith("skipped"))
    return {
        "host_platform": sys.platform,
        "os_name": os.name,
        "collected": collected,
        "executed": executed,
        "skipped": skipped,
        "outcomes": result.by_id,
        "collected_minus_executed": sorted(set(collected) - set(executed)),
        "runtime_control_collected": RUNTIME_NODE in collected,
        "runtime_control_executed": RUNTIME_NODE in executed,
        "runtime_control_skipped": RUNTIME_NODE in skipped,
        "windows_control_skipped": WINDOWS_NODE in skipped,
        "posix_control_executed": POSIX_NODE in executed,
        "posix_control_skipped": POSIX_NODE in skipped,
        "tests_run": result.testsRun,
        "errors": len(result.errors),
        "failures": len(result.failures),
    }


def _runs_on_family(value: Any) -> str | None:
    text = json.dumps(value) if not isinstance(value, str) else value
    low = text.lower()
    if "windows" in low or "win32" in low:
        return "windows"
    if "macos" in low or "darwin" in low:
        return "darwin"
    if "ubuntu" in low or "linux" in low:
        return "linux"
    return None


def load_ci_matrix() -> dict[str, Any]:
    aud49 = REPO / "command-center/audit/AUD-0049-runner-matrix-vs-support.json"
    source = "absent"
    jobs: list[dict[str, Any]] = []
    if aud49.is_file():
        source = "AUD-0049"
        try:
            doc = json.loads(aud49.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            source = f"AUD-0049-unparseable:{type(exc).__name__}"
            doc = {}
        blob = json.dumps(doc)
        for token in ("ubuntu-latest", "windows-latest", "macos-latest"):
            if token in blob:
                jobs.append({"runs_on": token, "source": "AUD-0049-token"})
    wfdir = REPO / ".github/workflows"
    if wfdir.is_dir():
        source = f"{source}+workflows" if source != "absent" else "workflows"
        for wf in sorted(list(wfdir.glob("*.yml")) + list(wfdir.glob("*.yaml"))):
            text = wf.read_text(encoding="utf-8", errors="replace")
            for line in text.splitlines():
                if "runs-on" in line:
                    jobs.append(
                        {
                            "file": rel(wf),
                            "line": line.strip()[:200],
                            "family": _runs_on_family(line),
                            "runs_on": line.split(":", 1)[-1].strip() if ":" in line else line,
                        }
                    )
    aud41 = REPO / "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json"
    if not jobs and aud41.is_file():
        source = "AUD-0041-yaml-inventory"
        try:
            inv = json.loads(aud41.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            inv = {}
        for wf in inv.get("workflows") or []:
            for job in wf.get("jobs") or []:
                ro = job.get("runs_on") or job.get("runs-on")
                jobs.append(
                    {
                        "file": wf.get("file"),
                        "job_id": job.get("job_id"),
                        "runs_on": ro,
                        "family": _runs_on_family(ro),
                    }
                )
    families = sorted({j.get("family") for j in jobs if j.get("family")})
    labels = sorted({str(j.get("runs_on")) for j in jobs if j.get("runs_on")})
    note = "CI matrix measured from available sources."
    if "AUD-0041" in source:
        note = (
            "AUD-0049 artifact is absent on this worktree; CI runs-on values "
            "are taken from AUD-0041's YAML inventory (all ubuntu-latest)."
        )
    elif source == "absent":
        note = "No workflow files and no AUD-0049 artifact; CI matrix NOT-CHECKED."
        families = []
    return {
        "source": source,
        "job_rows": jobs,
        "runner_labels": labels,
        "platform_families": families,
        "windows_in_matrix": "windows" in families,
        "darwin_in_matrix": "darwin" in families,
        "linux_in_matrix": "linux" in families,
        "note": note,
    }


def never_on_ci(
    platform_gates: list[dict[str, Any]], matrix: dict[str, Any]
) -> list[dict[str, Any]]:
    families = set(matrix.get("platform_families") or [])
    if not families:
        families = {"linux"}
    mapping = {"linux": "linux", "windows": "win32", "darwin": "darwin"}
    out: list[dict[str, Any]] = []
    for g in platform_gates:
        skips = g.get("would_skip") or {}
        skip_on_all = True
        for fam in families:
            key = mapping.get(str(fam), str(fam))
            val = skips.get(key)
            if val is not True:
                skip_on_all = False
                break
        if skip_on_all:
            out.append({**g, "never_on_ci": True, "ci_families": sorted(families)})
    return out


def independence(ast_doc: dict[str, Any], run_doc: dict[str, Any]) -> dict[str, Any]:
    p1_runtime = bool(ast_doc.get("runtime_control_in_decorator_scan"))
    p2_runtime = bool(run_doc.get("runtime_control_skipped"))
    independent = (not p1_runtime) and p2_runtime
    return {
        "runtime_only_node": RUNTIME_NODE,
        "probe1_found_runtime_skip": p1_runtime,
        "probe2_found_runtime_skip": p2_runtime,
        "independent": independent,
        "windows_decorator_seen_by_probe1": bool(
            ast_doc.get("windows_control_in_decorator_scan")
        ),
        "posix_decorator_seen_by_probe1": bool(
            ast_doc.get("posix_control_in_decorator_scan")
        ),
        "reason": (
            "probe 2 found the body-raised SkipTest and probe 1 did not treat it "
            "as a skip/skipif decorator"
            if independent
            else "pair is not independent: runtime skip was not exclusive to probe 2"
        ),
    }


def full_census() -> dict[str, Any]:
    ast_doc = ast_census()
    run_doc = run_fixture_suite()
    matrix = load_ci_matrix()
    live_gates = [g for g in ast_doc["platform_gates"] if g["population"] == "live-suite"]
    fixture_gates = [
        g for g in ast_doc["platform_gates"] if g["population"] == "control-fixture"
    ]
    never_live = never_on_ci(live_gates, matrix)
    never_fix = never_on_ci(fixture_gates, matrix)
    indep = independence(ast_doc, run_doc)
    return {
        "ast": ast_doc,
        "runtime": run_doc,
        "ci_matrix": matrix,
        "independence": indep,
        "never_executed_on_ci_live": never_live,
        "never_executed_on_ci_control": never_fix,
        "headline": {
            "live_test_files": ast_doc["live_test_file_count"],
            "live_test_functions": ast_doc["live_test_function_count"],
            "live_platform_gated": ast_doc["live_platform_gate_count"],
            "live_never_on_ci": len(never_live),
            "control_platform_gated": ast_doc["fixture_platform_gate_count"],
            "ci_platform_families": matrix.get("platform_families") or ["linux"],
            "host_platform": run_doc["host_platform"],
            "probes_independent": indep["independent"],
        },
    }
