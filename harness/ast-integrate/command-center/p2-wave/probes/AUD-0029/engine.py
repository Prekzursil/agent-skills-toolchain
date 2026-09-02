#!/usr/bin/env python3
"""AUD-0029 language-floor engine.

Probe 1: AST + stdlib introduction-version map.
Probe 2: import / test / compile under actual floor interpreters.

Own fixtures are excluded from the live census and scored separately so a
planted 3.12 control cannot inflate the worktree floor.
"""
from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURES = HERE / "fixtures"
OWN_FIXTURE_PREFIX = "command-center/p2-wave/probes/AUD-0029/fixtures"
UNIT = "AUD-0029"

SKIP_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    ".tox",
    ".eggs",
    "wheelhouse",
}

PY_EXTS = {".py"}
JS_EXTS = {".js", ".mjs", ".cjs", ".ts"}

# Stdlib module introduction (major, minor).
STDLIB_MODULE = {
    "tomllib": (3, 11),
    "zoneinfo": (3, 9),
    "graphlib": (3, 9),
}

# from X import Y  /  X.Y
STDLIB_ATTR = {
    ("datetime", "UTC"): (3, 11),
    ("asyncio", "TaskGroup"): (3, 11),
    ("asyncio", "timeout"): (3, 11),
    ("typing", "Self"): (3, 11),
    ("typing", "override"): (3, 12),
    ("typing", "TypeAliasType"): (3, 12),
    ("typing", "TypeGuard"): (3, 10),
    ("enum", "StrEnum"): (3, 11),
    ("inspect", "get_annotations"): (3, 10),
    ("functools", "cache"): (3, 9),
    ("itertools", "pairwise"): (3, 10),
    ("contextlib", "chdir"): (3, 11),
    ("sys", "exception"): (3, 11),
}

PEP585_NAMES = {"list", "dict", "set", "tuple", "type", "frozenset"}

NODE_FEATURES = (
    ("optional_chaining", 14, re.compile(r"\?\.")),
    ("nullish_coalescing", 14, re.compile(r"\?\?")),
    ("promise_withResolvers", 22, re.compile(r"Promise\.withResolvers")),
    ("structuredClone", 17, re.compile(r"\bstructuredClone\b")),
    ("esm_export", 12, re.compile(r"(?m)^export\s")),
    ("esm_import", 12, re.compile(r"(?m)^import\s")),
)

REQUIRES_RE = re.compile(
    r"^requires-python\s*=\s*[\"']([^\"']+)[\"']", re.MULTILINE | re.IGNORECASE
)
PY_REQ_RE = re.compile(
    r"^python_requires\s*=\s*[\"']([^\"']+)[\"']", re.MULTILINE | re.IGNORECASE
)
MIN_VER_RE = re.compile(r"(\d+)\.(\d+)")

KNOWN_TOMLLIB = "command-center/p2-wave/_build_AUD0020.py"


def posix_rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return path.as_posix().replace("\\", "/")


def is_own_fixture(rel: str) -> bool:
    return rel.replace("\\", "/").startswith(OWN_FIXTURE_PREFIX)


def vfmt(ver: tuple[int, ...] | None) -> str | None:
    if not ver:
        return None
    return ".".join(str(x) for x in ver)


def vmax(*vers: tuple[int, ...] | None) -> tuple[int, ...] | None:
    present = [v for v in vers if v]
    return max(present) if present else None


def parse_min_version(spec: str) -> tuple[int, ...] | None:
    text = (spec or "").strip()
    if not text:
        return None
    match = MIN_VER_RE.search(text)
    if not match:
        return None
    return (int(match.group(1)), int(match.group(2)))


def looks_like_type(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant) and node.value is None:
        return True
    if isinstance(node, ast.Name):
        name = node.id
        if name in {"int", "str", "float", "bool", "bytes", "complex", "object"}:
            return True
        if name in PEP585_NAMES or name in {"Any", "Optional", "Union", "None"}:
            return True
        if name[:1].isupper():
            return True
        return False
    if isinstance(node, (ast.Subscript, ast.Attribute, ast.Constant)):
        return True
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return looks_like_type(node.left) or looks_like_type(node.right)
    return False


class FeatureVisitor(ast.NodeVisitor):
    def __init__(self, rel: str) -> None:
        self.rel = rel
        self.syntax: list[dict[str, Any]] = []
        self.api: list[dict[str, Any]] = []
        self._imported: dict[str, str] = {}

    def _syn(self, feature: str, ver: tuple[int, int], node: ast.AST) -> None:
        self.syntax.append(
            {
                "feature": feature,
                "version": list(ver),
                "path": self.rel,
                "line": int(getattr(node, "lineno", 0) or 0),
            }
        )

    def _api(self, symbol: str, ver: tuple[int, int], node: ast.AST) -> None:
        self.api.append(
            {
                "symbol": symbol,
                "version": list(ver),
                "path": self.rel,
                "line": int(getattr(node, "lineno", 0) or 0),
            }
        )

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        self._syn("walrus", (3, 8), node)
        self.generic_visit(node)

    def visit_Match(self, node: ast.AST) -> None:
        self._syn("match-case", (3, 10), node)
        self.generic_visit(node)

    def visit_TryStar(self, node: ast.AST) -> None:
        self._syn("except*", (3, 11), node)
        self.generic_visit(node)

    def visit_TypeAlias(self, node: ast.AST) -> None:
        self._syn("type-alias", (3, 12), node)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if getattr(node, "type_params", None):
            self._syn("type-params", (3, 12), node)
        if node.args.posonlyargs:
            self._syn("positional-only", (3, 8), node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        if getattr(node, "type_params", None):
            self._syn("type-params", (3, 12), node)
        if node.args.posonlyargs:
            self._syn("positional-only", (3, 8), node)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if getattr(node, "type_params", None):
            self._syn("type-params", (3, 12), node)
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            root = alias.name.split(".")[0]
            bound = alias.asname or root
            self._imported[bound] = alias.name
            if root in STDLIB_MODULE:
                self._api(root, STDLIB_MODULE[root], node)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        mod = node.module or ""
        root = mod.split(".")[0] if mod else ""
        if root in STDLIB_MODULE:
            self._api(root, STDLIB_MODULE[root], node)
        for alias in node.names:
            bound = alias.asname or alias.name
            self._imported[bound] = f"{mod}.{alias.name}" if mod else alias.name
            key = (mod, alias.name)
            if key in STDLIB_ATTR:
                self._api(f"{mod}.{alias.name}", STDLIB_ATTR[key], node)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.value, ast.Name):
            origin = self._imported.get(node.value.id, node.value.id)
            root = origin.split(".")[0]
            key = (root, node.attr)
            if key in STDLIB_ATTR:
                self._api(f"{root}.{node.attr}", STDLIB_ATTR[key], node)
            if origin in STDLIB_MODULE:
                pass
        if (
            node.attr == "walk"
            and isinstance(node.value, ast.Attribute)
            and node.value.attr == "Path"
        ):
            self._api("pathlib.Path.walk", (3, 12), node)
        self.generic_visit(node)

    def visit_keyword(self, node: ast.keyword) -> None:
        if node.arg == "onexc":
            self._api("shutil.rmtree.onexc", (3, 12), node)
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        if isinstance(node.op, ast.BitOr) and (
            looks_like_type(node.left) or looks_like_type(node.right)
        ):
            self._api("pep604-union", (3, 10), node)
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        if isinstance(node.value, ast.Name) and node.value.id in PEP585_NAMES:
            self._api("pep585-builtin-generics", (3, 9), node)
        self.generic_visit(node)


def iter_source_files(exts: set[str], *, include_own_fixtures: bool) -> list[Path]:
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(REPO):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            path = Path(dirpath) / name
            if path.suffix.lower() not in exts:
                continue
            rel = posix_rel(path)
            if not include_own_fixtures and is_own_fixture(rel):
                continue
            found.append(path)
    found.sort()
    return found


def scan_python_file(path: Path) -> dict[str, Any]:
    rel = posix_rel(path)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return {
            "path": rel,
            "parse_ok": False,
            "error": f"{type(exc).__name__}:{exc}",
            "syntax": [],
            "api": [],
            "syntax_floor": None,
            "api_floor": None,
            "combined_floor": None,
        }
    try:
        tree = ast.parse(text, filename=rel)
    except SyntaxError as exc:
        return {
            "path": rel,
            "parse_ok": False,
            "error": f"SyntaxError:{exc.lineno}:{exc.msg}",
            "syntax": [],
            "api": [],
            "syntax_floor": None,
            "api_floor": None,
            "combined_floor": None,
        }
    visitor = FeatureVisitor(rel)
    visitor.visit(tree)
    syn_floor = vmax(*[tuple(h["version"]) for h in visitor.syntax])
    api_floor = vmax(*[tuple(h["version"]) for h in visitor.api])
    return {
        "path": rel,
        "parse_ok": True,
        "error": None,
        "syntax": visitor.syntax,
        "api": visitor.api,
        "syntax_floor": list(syn_floor) if syn_floor else None,
        "api_floor": list(api_floor) if api_floor else None,
        "combined_floor": list(vmax(syn_floor, api_floor))
        if vmax(syn_floor, api_floor)
        else None,
    }


def scan_js_file(path: Path) -> dict[str, Any]:
    rel = posix_rel(path)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return {
            "path": rel,
            "ok": False,
            "error": f"{type(exc).__name__}",
            "features": [],
            "floor": None,
        }
    features = []
    for name, ver, pattern in NODE_FEATURES:
        if pattern.search(text):
            features.append({"feature": name, "node_major": ver, "path": rel})
    floor = max((f["node_major"] for f in features), default=None)
    return {
        "path": rel,
        "ok": True,
        "error": None,
        "features": features,
        "floor": floor,
    }


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        import tomllib
    except ImportError:
        tomllib = None  # type: ignore[assignment]
    text = path.read_text(encoding="utf-8")
    if tomllib is not None:
        try:
            data = tomllib.loads(text)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {}


def collect_declarations(*, live_only: bool) -> dict[str, Any]:
    requires: list[dict[str, Any]] = []
    engines: list[dict[str, Any]] = []
    plugin_floors: list[dict[str, Any]] = []
    pyproject_files = 0
    package_json_files = 0
    plugin_json_files = 0

    for dirpath, dirnames, filenames in os.walk(REPO):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            path = Path(dirpath) / name
            rel = posix_rel(path)
            rel_posix = rel.replace("\\", "/")
            if live_only and (
                is_own_fixture(rel_posix) or "/fixtures/" in f"/{rel_posix}/"
            ):
                continue
            if name == "pyproject.toml":
                pyproject_files += 1
                data = _load_toml(path)
                value = None
                if isinstance(data.get("project"), dict):
                    value = data["project"].get("requires-python")
                if not value:
                    match = REQUIRES_RE.search(path.read_text(encoding="utf-8"))
                    value = match.group(1) if match else None
                if value:
                    requires.append(
                        {
                            "path": rel,
                            "value": str(value),
                            "min": list(parse_min_version(str(value)) or ()),
                        }
                    )
            elif name == "setup.cfg":
                match = PY_REQ_RE.search(path.read_text(encoding="utf-8"))
                if match:
                    requires.append(
                        {
                            "path": rel,
                            "value": match.group(1),
                            "min": list(parse_min_version(match.group(1)) or ()),
                        }
                    )
            elif name == "package.json":
                package_json_files += 1
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if not isinstance(data, dict):
                    continue
                eng = data.get("engines")
                node = None
                if isinstance(eng, dict):
                    node = eng.get("node")
                if node:
                    engines.append(
                        {
                            "path": rel,
                            "value": str(node),
                            "min": parse_min_version(str(node)),
                        }
                    )
            elif name == "plugin.json":
                plugin_json_files += 1
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                interps = data.get("interpreters") if isinstance(data, dict) else None
                if isinstance(interps, list):
                    for item in interps:
                        if not isinstance(item, dict):
                            continue
                        if item.get("id") in {"python3", "python", "node"}:
                            plugin_floors.append(
                                {
                                    "path": rel,
                                    "id": item.get("id"),
                                    "floor": item.get("floor"),
                                }
                            )

    return {
        "pyproject_toml_files": pyproject_files,
        "package_json_files": package_json_files,
        "plugin_json_files": plugin_json_files,
        "requires_python": requires,
        "engines_node": engines,
        "plugin_interpreters": plugin_floors,
    }


def _cap(hits: list[dict[str, Any]], n: int = 8) -> list[dict[str, Any]]:
    ranked = sorted(
        hits, key=lambda h: (tuple(h.get("version") or [0, 0]), h.get("path") or "")
    )
    return ranked[-n:]


def live_census() -> dict[str, Any]:
    py_files = iter_source_files(PY_EXTS, include_own_fixtures=False)
    js_files = iter_source_files(JS_EXTS, include_own_fixtures=False)
    py_rows = [scan_python_file(p) for p in py_files]
    js_rows = [scan_js_file(p) for p in js_files]
    syn_hits = [h for row in py_rows for h in row["syntax"]]
    api_hits = [h for row in py_rows for h in row["api"]]
    parse_errors = [row for row in py_rows if not row["parse_ok"]]
    syn_floor = vmax(*[tuple(h["version"]) for h in syn_hits])
    api_floor = vmax(*[tuple(h["version"]) for h in api_hits])
    combined = vmax(syn_floor, api_floor)
    js_floor = max((r["floor"] or 0 for r in js_rows), default=0) or None
    decls = collect_declarations(live_only=True)

    by_bucket: dict[str, list[tuple[int, ...] | None]] = defaultdict(list)
    for row in py_rows:
        rel = row["path"]
        if rel.startswith("tools/"):
            bucket = "tools"
        elif rel.startswith("command-center/p2-wave/"):
            bucket = "p2-wave"
        elif rel.startswith("command-center/"):
            bucket = "command-center"
        else:
            bucket = "other"
        floor = tuple(row["combined_floor"]) if row["combined_floor"] else None
        by_bucket[bucket].append(floor)
    bucket_floors = {
        name: vfmt(vmax(*floors)) for name, floors in sorted(by_bucket.items())
    }

    tomllib_hits = [h for h in api_hits if h["symbol"] == "tomllib"]
    onexc_hits = [h for h in api_hits if "onexc" in str(h.get("symbol"))]

    declared_py_mins = [
        tuple(r["min"]) for r in decls["requires_python"] if r.get("min")
    ]
    declared_node_mins = [
        r["min"] for r in decls["engines_node"] if r.get("min")
    ]
    if combined and declared_py_mins:
        declared_min = min(declared_py_mins)
        py_match = "MATCH" if combined <= declared_min else "MISMATCH-ACTUAL-HIGHER"
    elif combined and not declared_py_mins:
        py_match = "NOT-DECLARED"
    elif not combined:
        py_match = "NOT-CHECKED"
    else:
        py_match = "NOT-CHECKED"

    if js_floor and declared_node_mins:
        dmin = min(int(x[0]) if isinstance(x, (list, tuple)) else int(x) for x in declared_node_mins)
        node_match = "MATCH" if js_floor <= dmin else "MISMATCH-ACTUAL-HIGHER"
    elif js_files and not declared_node_mins:
        node_match = "NOT-DECLARED"
    else:
        node_match = "NOT-CHECKED"

    return {
        "python_file_count": len(py_rows),
        "js_file_count": len(js_rows),
        "parse_error_count": len(parse_errors),
        "parse_errors": parse_errors[:12],
        "syntax_floor": vfmt(syn_floor),
        "api_floor": vfmt(api_floor),
        "python_floor": vfmt(combined),
        "python_floor_tuple": list(combined) if combined else None,
        "node_floor": js_floor,
        "bucket_floors": bucket_floors,
        "syntax_hit_count": len(syn_hits),
        "api_hit_count": len(api_hits),
        "syntax_samples": _cap(syn_hits),
        "api_samples_high": _cap(api_hits),
        "tomllib_hits": tomllib_hits[:8],
        "onexc_hits": onexc_hits[:8],
        "declarations": decls,
        "python_match_status": py_match,
        "node_match_status": node_match,
        "js_samples": [
            {"path": r["path"], "floor": r["floor"], "features": r["features"]}
            for r in js_rows
            if r.get("floor")
        ][:16],
        "plugin_zip": {
            "path": "plugin.zip",
            "exists": (REPO / "plugin.zip").is_file(),
        },
        "platform_fsops": {
            "path": "platform/plugin/fsops.py",
            "exists": (REPO / "platform/plugin/fsops.py").is_file(),
        },
    }


def file_exceeds_declared(
    scan: dict[str, Any], declared: tuple[int, ...]
) -> bool:
    floor = scan.get("combined_floor")
    if not floor:
        return False
    return tuple(floor) > declared


def js_exceeds_declared(scan: dict[str, Any], declared_major: int) -> bool:
    floor = scan.get("floor")
    if not floor:
        return False
    return int(floor) > declared_major


def control_scan() -> dict[str, Any]:
    decls = collect_declarations(live_only=False)
    fixture_py = next(
        (
            r
            for r in decls["requires_python"]
            if r["path"].startswith(OWN_FIXTURE_PREFIX)
        ),
        None,
    )
    fixture_node = next(
        (
            r
            for r in decls["engines_node"]
            if r["path"].startswith(OWN_FIXTURE_PREFIX)
        ),
        None,
    )
    declared_py = tuple(fixture_py["min"]) if fixture_py and fixture_py.get("min") else (3, 10)
    declared_node = 16
    if fixture_node and fixture_node.get("min"):
        mn = fixture_node["min"]
        declared_node = int(mn[0]) if isinstance(mn, (list, tuple)) else int(mn)

    newer = scan_python_file(FIXTURES / "newer_than_floor.py")
    at = scan_python_file(FIXTURES / "at_floor.py")
    node_newer = scan_js_file(FIXTURES / "node_newer_than_floor.mjs")
    node_at = scan_js_file(FIXTURES / "node_at_floor.mjs")

    py_newer_flagged = file_exceeds_declared(newer, declared_py)
    py_at_flagged = file_exceeds_declared(at, declared_py)
    js_newer_flagged = js_exceeds_declared(node_newer, declared_node)
    js_at_flagged = js_exceeds_declared(node_at, declared_node)

    return {
        "declared_python": vfmt(declared_py),
        "declared_node": declared_node,
        "fixture_requires_python": fixture_py,
        "fixture_engines_node": fixture_node,
        "newer_python": {
            "path": newer["path"],
            "combined_floor": newer["combined_floor"],
            "syntax": newer["syntax"],
            "flagged": py_newer_flagged,
        },
        "at_floor_python": {
            "path": at["path"],
            "combined_floor": at["combined_floor"],
            "flagged": py_at_flagged,
        },
        "newer_node": {
            "path": node_newer["path"],
            "floor": node_newer["floor"],
            "features": node_newer["features"],
            "flagged": js_newer_flagged,
        },
        "at_floor_node": {
            "path": node_at["path"],
            "floor": node_at["floor"],
            "flagged": js_at_flagged,
        },
        "python_control_pass": py_newer_flagged and not py_at_flagged,
        "node_control_pass": js_newer_flagged and not js_at_flagged,
        "control_pass": py_newer_flagged
        and not py_at_flagged
        and js_newer_flagged
        and not js_at_flagged,
    }


def _candidate_pythons(mm: str) -> list[Path]:
    names = [f"python{mm}", f"python{mm.replace('.', '')}"]
    out: list[Path] = []
    for name in names:
        found = shutil.which(name)
        if found:
            out.append(Path(found))
    roots = [
        Path("/root/.local/bin"),
        Path("/usr/bin"),
        Path("/usr/local/bin"),
        Path.home() / ".local" / "bin",
    ]
    for root in roots:
        for name in names:
            cand = root / name
            if cand.is_file():
                out.append(cand)
    uv = Path("/root/.local/share/uv/python")
    if uv.is_dir():
        out.extend(uv.glob(f"cpython-{mm}-*/bin/python{mm}"))
        out.extend(uv.glob(f"cpython-{mm}.*-linux-*/bin/python{mm}"))
    # de-dupe while preserving order
    seen: set[str] = set()
    uniq: list[Path] = []
    for path in out:
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(path)
    return uniq


def discover_interpreters() -> dict[str, Any]:
    pythons: dict[str, dict[str, Any]] = {}
    for mm in ("3.10", "3.11", "3.12", "3.13", "3.14"):
        exe = None
        version = None
        rc = None
        err = None
        for cand in _candidate_pythons(mm):
            try:
                proc = subprocess.run(
                    [str(cand), "--version"],
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                err = f"{type(exc).__name__}"
                continue
            rc = proc.returncode
            text = ((proc.stdout or "") + (proc.stderr or "")).strip()
            if proc.returncode == 0 and text:
                exe = str(cand)
                version = text
                err = None
                break
            err = text[-200:]
        pythons[mm] = {"exe": exe, "version": version, "rc": rc, "error": err}

    node_exe = shutil.which("node") or shutil.which("nodejs")
    node_ver = None
    if node_exe:
        proc = subprocess.run(
            [node_exe, "--version"], capture_output=True, text=True, timeout=20
        )
        node_ver = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return {
        "python": pythons,
        "node": {"exe": node_exe, "version": node_ver},
        "current": sys.version.split()[0],
    }


def run_exe(exe: str, args: list[str], *, cwd: Path | None = None, timeout: int = 60) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            [exe, *args],
            cwd=str(cwd or REPO),
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1"},
        )
    except subprocess.TimeoutExpired:
        return {"rc": 124, "out": "TIMEOUT", "exe": exe, "args": args}
    except OSError as exc:
        return {"rc": 127, "out": f"{type(exc).__name__}:{exc}", "exe": exe, "args": args}
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return {"rc": proc.returncode, "out": text[-1500:], "exe": exe, "args": args}


def compile_under(exe: str, files: Iterable[Path]) -> dict[str, Any]:
    payload = json.dumps([str(p) for p in files])
    try:
        proc = subprocess.run(
            [exe, "-B", str(HERE / "compile_stdin.py")],
            input=payload,
            capture_output=True,
            text=True,
            timeout=90,
            cwd=str(REPO),
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
    except subprocess.TimeoutExpired:
        return {"rc": 124, "ok": 0, "n_failed": -1, "failed": [{"error": "TIMEOUT"}]}
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return {"rc": proc.returncode, "ok": 0, "n_failed": -1, "failed": [{"error": text[-400:]}]}
    data["rc"] = proc.returncode
    return data


def runtime_matrix() -> dict[str, Any]:
    interps = discover_interpreters()
    live_py = iter_source_files(PY_EXTS, include_own_fixtures=False)
    rows: dict[str, Any] = {"interpreters": interps, "runs": {}}

    for mm, meta in interps["python"].items():
        exe = meta.get("exe")
        if not exe:
            rows["runs"][mm] = {"present": False, "reason": meta.get("error") or "absent"}
            continue
        compile_live = compile_under(exe, live_py)
        newer = run_exe(exe, [str(FIXTURES / "newer_than_floor.py")])
        at = run_exe(exe, [str(FIXTURES / "at_floor.py")])
        tomllib_fix = run_exe(exe, [str(FIXTURES / "runtime_tomllib.py")])
        onexc_fix = run_exe(exe, [str(FIXTURES / "runtime_onexc.py")])
        tests = run_exe(exe, [str(FIXTURES / "test_floor.py")], cwd=FIXTURES)
        tools_import = run_exe(
            exe,
            [
                "-c",
                "import sys; sys.path[:0]=['tools']; import plugin.json_codec, council; print('tools-import-ok')",
            ],
        )
        catalog_import = run_exe(
            exe,
            [
                "-c",
                "import sys; sys.path[:0]=['tools/command-center']; import catalog; print('catalog-import-ok')",
            ],
        )
        ready_import = run_exe(
            exe,
            [
                "-c",
                "import sys; sys.path[:0]=['command-center']; import ready_units; print('ready-import-ok')",
            ],
        )
        sig = run_exe(
            exe,
            [
                "-c",
                "import inspect, shutil; print('onexc' in inspect.signature(shutil.rmtree).parameters)",
            ],
        )
        tomllib_mod = run_exe(exe, ["-c", "import tomllib; print('tomllib-mod-ok')"])
        rows["runs"][mm] = {
            "present": True,
            "exe": exe,
            "version": meta.get("version"),
            "compile_live": {
                "ok": compile_live.get("ok"),
                "n_failed": compile_live.get("n_failed"),
                "failed": compile_live.get("failed") or [],
                "rc": compile_live.get("rc"),
            },
            "fixture_newer_than_floor": {"rc": newer["rc"], "out": newer["out"][-400:]},
            "fixture_at_floor": {"rc": at["rc"], "out": at["out"][-200:]},
            "fixture_tomllib": {"rc": tomllib_fix["rc"], "out": tomllib_fix["out"][-200:]},
            "fixture_onexc": {"rc": onexc_fix["rc"], "out": onexc_fix["out"][-200:]},
            "unittest_at_floor": {"rc": tests["rc"], "out": tests["out"][-400:]},
            "import_tools": {"rc": tools_import["rc"], "out": tools_import["out"][-200:]},
            "import_catalog": {"rc": catalog_import["rc"], "out": catalog_import["out"][-200:]},
            "import_ready_units": {"rc": ready_import["rc"], "out": ready_import["out"][-200:]},
            "rmtree_accepts_onexc": {"rc": sig["rc"], "out": sig["out"][-80:]},
            "import_tomllib": {"rc": tomllib_mod["rc"], "out": tomllib_mod["out"][-200:]},
        }

    node_exe = interps["node"].get("exe")
    node_runs: dict[str, Any] = {"present": bool(node_exe)}
    if node_exe:
        node_runs["at_floor"] = run_exe(node_exe, [str(FIXTURES / "node_at_floor.mjs")])
        node_runs["newer"] = run_exe(node_exe, [str(FIXTURES / "node_newer_than_floor.mjs")])
        # Live Node 16 is not installed; current node only proves current.
        node_runs["current_only"] = True
        node_runs["version"] = interps["node"].get("version")
    rows["node_runs"] = node_runs

    py310 = rows["runs"].get("3.10") or {}
    py311 = rows["runs"].get("3.11") or {}
    py312 = rows["runs"].get("3.12") or {}

    # Independent falsification of the probe-1 headline:
    # 3.10 cannot import tomllib; 3.11 can. 3.10 cannot parse 3.12 type-params;
    # 3.12 can. 3.10/3.11 reject onexc; 3.12 accepts.
    falsify = {
        "py310_present": bool(py310.get("present")),
        "py311_present": bool(py311.get("present")),
        "py312_present": bool(py312.get("present")),
        "tomllib_fails_on_310": bool(py310.get("present"))
        and (py310.get("import_tomllib") or {}).get("rc") != 0,
        "tomllib_ok_on_311": bool(py311.get("present"))
        and (py311.get("import_tomllib") or {}).get("rc") == 0,
        "newer_syntax_fails_on_310": bool(py310.get("present"))
        and (py310.get("fixture_newer_than_floor") or {}).get("rc") != 0,
        "newer_syntax_ok_on_312": bool(py312.get("present"))
        and (py312.get("fixture_newer_than_floor") or {}).get("rc") == 0,
        "at_floor_ok_on_310": bool(py310.get("present"))
        and (py310.get("fixture_at_floor") or {}).get("rc") == 0
        and (py310.get("unittest_at_floor") or {}).get("rc") == 0,
        "onexc_rejected_on_310": bool(py310.get("present"))
        and (py310.get("fixture_onexc") or {}).get("rc") != 0,
        "onexc_rejected_on_311": bool(py311.get("present"))
        and (py311.get("fixture_onexc") or {}).get("rc") != 0,
        "onexc_ok_on_312": bool(py312.get("present"))
        and (py312.get("fixture_onexc") or {}).get("rc") == 0,
        "tools_import_ok_on_310": bool(py310.get("present"))
        and (py310.get("import_tools") or {}).get("rc") == 0,
    }
    falsify["pass"] = all(
        [
            falsify["py310_present"],
            falsify["py311_present"],
            falsify["py312_present"],
            falsify["tomllib_fails_on_310"],
            falsify["tomllib_ok_on_311"],
            falsify["newer_syntax_fails_on_310"],
            falsify["newer_syntax_ok_on_312"],
            falsify["at_floor_ok_on_310"],
            falsify["onexc_rejected_on_310"],
            falsify["onexc_rejected_on_311"],
            falsify["onexc_ok_on_312"],
            falsify["tools_import_ok_on_310"],
        ]
    )
    rows["falsify"] = falsify
    return rows


def known_tomllib_mapped(census: dict[str, Any]) -> bool:
    path = REPO / KNOWN_TOMLLIB
    if not path.is_file():
        return True
    text = path.read_text(encoding="utf-8")
    if "import tomllib" not in text and "from tomllib" not in text:
        return True
    return any(h.get("path") == KNOWN_TOMLLIB for h in census.get("tomllib_hits") or [])
