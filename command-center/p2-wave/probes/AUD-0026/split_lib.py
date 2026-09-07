#!/usr/bin/env python3
"""Shared helpers for AUD-0026 runtime-vs-dev split probes."""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
THIS_FIXTURE_PREFIX = "command-center/p2-wave/probes/AUD-0026/fixtures/"

SKIP_DIR_NAMES = {
    "node_modules",
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".tox",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "coverage",
    "htmlcov",
    "vendor",
    ".eggs",
    "*.egg-info",
}

# optional-dependency / dependency-group names treated as development-class
DEV_GROUP_NAMES = {
    "dev",
    "devel",
    "develop",
    "development",
    "test",
    "tests",
    "testing",
    "lint",
    "linters",
    "linting",
    "type",
    "types",
    "typing",
    "docs",
    "doc",
    "coverage",
    "ci",
    "qa",
}

# Top-level stdlib / builtins that must never be treated as third-party deps.
# Kept deliberately incomplete for obscure modules; false "prod" misses are safer
# than inventing packaging defects against the stdlib.
PY_STDLIB = set(sys.stdlib_module_names) | {
    "__future__",
    "typing_extensions",  # often vendored / runtime; never a "dev-only" signal alone
}

REQ = re.compile(
    r"^\s*(?P<name>[A-Za-z0-9][A-Za-z0-9._+-]*)\s*(?P<extras>\[[^\]]*\])?\s*(?P<spec>.*)$"
)
JS_FROM = re.compile(
    r"""(?:import|export)\s+(?:[\s\w\{\}\*,]+\s+from\s+)?['"]([^'"]+)['"]"""
)
JS_REQUIRE = re.compile(r"""require\s*\(\s*['"]([^'"]+)['"]\s*\)""")


def rel(p: Path) -> str:
    try:
        return p.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return p.as_posix().replace("\\", "/")


def should_skip_dir(name: str) -> bool:
    return name in SKIP_DIR_NAMES or name.endswith(".egg-info")


def norm_pip(name: str) -> str:
    return re.sub(r"[-_.]+", "-", (name or "").strip()).lower()


def norm_npm(name: str) -> str:
    return (name or "").strip().lower()


def parse_req_name(raw: str) -> str | None:
    s = (raw or "").split("#")[0].strip()
    if not s or s.startswith("-"):
        return None
    m = REQ.match(s)
    if not m:
        return None
    return norm_pip(m.group("name"))


def is_our_fixture(path: str) -> bool:
    return path.startswith(THIS_FIXTURE_PREFIX)


def is_other_probe_scratch(path: str) -> bool:
    if not path.startswith("command-center/p2-wave/probes/"):
        return False
    return not path.startswith("command-center/p2-wave/probes/AUD-0026/")


def discover_manifests() -> list[Path]:
    out: list[Path] = []
    for root, dirs, files in os_walk_filtered(REPO):
        if "pyproject.toml" in files:
            out.append(Path(root) / "pyproject.toml")
        if "package.json" in files:
            out.append(Path(root) / "package.json")
    return sorted(out, key=lambda p: rel(p))


def os_walk_filtered(base: Path):
    import os

    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if not should_skip_dir(d)]
        # never descend into other units' probe fixtures except ours already filtered by name
        yield root, dirs, files


def parse_pyproject_split(path: Path) -> dict:
    """Return prod/dev declared dependency sets for a pyproject.toml."""
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}", "ecosystem": "pip"}

    project = data.get("project") or {}
    prod: set[str] = set()
    dev: set[str] = set()

    for raw in project.get("dependencies") or []:
        n = parse_req_name(str(raw))
        if n:
            prod.add(n)

    opt = project.get("optional-dependencies") or {}
    if isinstance(opt, dict):
        for group, items in opt.items():
            g = str(group).lower()
            target = dev if g in DEV_GROUP_NAMES else prod
            for raw in items or []:
                n = parse_req_name(str(raw))
                if n:
                    target.add(n)

    # PEP 735 dependency-groups
    groups = data.get("dependency-groups") or {}
    if isinstance(groups, dict):
        for group, items in groups.items():
            g = str(group).lower()
            target = dev if g in DEV_GROUP_NAMES else prod
            for raw in items or []:
                if isinstance(raw, dict):
                    continue  # include-group markers
                n = parse_req_name(str(raw))
                if n:
                    target.add(n)

    # poetry
    poetry = ((data.get("tool") or {}).get("poetry") or {})
    for k, v in (poetry.get("dependencies") or {}).items():
        if norm_pip(k) == "python":
            continue
        prod.add(norm_pip(k))
    for group, body in (poetry.get("group") or {}).items():
        g = str(group).lower()
        target = dev if g in DEV_GROUP_NAMES else prod
        deps = (body or {}).get("dependencies") or {}
        for k in deps:
            target.add(norm_pip(k))

    # tool.uv.dev-dependencies (legacy uv)
    uv = (data.get("tool") or {}).get("uv") or {}
    for raw in uv.get("dev-dependencies") or []:
        n = parse_req_name(str(raw))
        if n:
            dev.add(n)

    name = project.get("name") or poetry.get("name")
    packages_cfg = ((data.get("tool") or {}).get("setuptools") or {}).get("packages")
    return {
        "ecosystem": "pip",
        "manifest": rel(path),
        "root": rel(path.parent),
        "name": name,
        "prod": sorted(prod),
        "dev": sorted(dev),
        "dev_only": sorted(dev - prod),
        "prod_only": sorted(prod - dev),
        "both": sorted(prod & dev),
        "packages_cfg": packages_cfg,
        "error": None,
    }


def parse_package_json_split(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}", "ecosystem": "npm"}
    if not isinstance(data, dict):
        return {"error": "manifest is not an object", "ecosystem": "npm"}

    def grab(key: str) -> set[str]:
        v = data.get(key)
        if not isinstance(v, dict):
            return set()
        return {norm_npm(str(k)) for k in v}

    prod = grab("dependencies") | grab("optionalDependencies") | grab("peerDependencies")
    # peer/optional are still runtime-ish for consumers; treat as prod-class for split
    dev = grab("devDependencies")
    return {
        "ecosystem": "npm",
        "manifest": rel(path),
        "root": rel(path.parent),
        "name": data.get("name"),
        "prod": sorted(prod),
        "dev": sorted(dev),
        "dev_only": sorted(dev - prod),
        "prod_only": sorted(prod - dev),
        "both": sorted(prod & dev),
        "files": data.get("files"),
        "main": data.get("main"),
        "exports": data.get("exports"),
        "error": None,
    }


def parse_manifest(path: Path) -> dict | None:
    if path.name == "pyproject.toml":
        return parse_pyproject_split(path)
    if path.name == "package.json":
        # skip package.json that is clearly not a package root when nested under
        # node_modules already filtered; still skip workspace tooling without deps? keep all
        return parse_package_json_split(path)
    return None


def shippable_python_roots(rec: dict) -> list[Path]:
    """Directories whose .py files count as shipped for a pyproject package."""
    root = REPO / rec["root"]
    cfg = rec.get("packages_cfg")
    roots: list[Path] = []
    if isinstance(cfg, list):
        for pkg in cfg:
            # dotted package name → path
            p = root / str(pkg).replace(".", "/")
            if p.is_dir():
                roots.append(p)
            elif (root / f"{pkg}.py").is_file():
                roots.append(root)  # single-module; scan carefully later
    elif isinstance(cfg, dict):
        find = cfg.get("find") or {}
        wheres = find.get("where") or ["."]
        for w in wheres:
            p = (root / str(w)).resolve()
            if p.is_dir():
                roots.append(p)
    if not roots:
        # fallback: top-level packages matching sanitized project name, else nothing
        # Prefer explicit package dirs that are not tests/
        name = norm_pip(str(rec.get("name") or "")).replace("-", "_")
        candidate = root / name
        if candidate.is_dir():
            roots.append(candidate)
        else:
            for child in sorted(root.iterdir()) if root.is_dir() else []:
                if child.is_dir() and child.name not in {
                    "tests",
                    "test",
                    "docs",
                    "scripts",
                    ".github",
                } and not child.name.startswith("."):
                    # only if it looks like a python package
                    if (child / "__init__.py").is_file() or any(child.glob("*.py")):
                        roots.append(child)
    # de-dup
    seen: set[str] = set()
    out: list[Path] = []
    for r in roots:
        key = str(r.resolve())
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def shippable_node_roots(rec: dict) -> list[Path]:
    root = REPO / rec["root"]
    roots: list[Path] = []
    files = rec.get("files")
    if isinstance(files, list) and files:
        for f in files:
            p = root / str(f)
            if p.is_dir():
                roots.append(p)
            elif p.is_file():
                roots.append(p.parent)
    else:
        main = rec.get("main")
        if isinstance(main, str) and main:
            p = root / main
            if p.is_file():
                roots.append(p.parent)
            elif (root / "src").is_dir():
                roots.append(root / "src")
            elif (root / "lib").is_dir():
                roots.append(root / "lib")
            else:
                roots.append(root)
        elif (root / "src").is_dir():
            roots.append(root / "src")
        elif (root / "dist").is_dir():
            roots.append(root / "dist")
        else:
            roots.append(root)
    seen: set[str] = set()
    out: list[Path] = []
    for r in roots:
        key = str(r.resolve())
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def is_test_path(path: Path, package_root: Path) -> bool:
    try:
        rel_parts = path.resolve().relative_to(package_root.resolve()).parts
    except ValueError:
        rel_parts = path.parts
    name = path.name.lower()
    if name.startswith("test_") or name.endswith("_test.py"):
        return True
    if name.endswith((".test.js", ".test.mjs", ".test.ts", ".test.tsx", ".spec.js", ".spec.ts", ".spec.mjs")):
        return True
    if name in {"conftest.py"}:
        return True
    for part in rel_parts:
        low = part.lower()
        if low in {"tests", "test", "__tests__", "spec", "specs"}:
            return True
    return False


def python_imports(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
    except SyntaxError:
        return []
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".", 1)[0]
                if top and top not in PY_STDLIB:
                    names.append(norm_pip(top))
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue  # relative
            if not node.module:
                continue
            top = node.module.split(".", 1)[0]
            if top and top not in PY_STDLIB:
                names.append(norm_pip(top))
    return sorted(set(names))


def js_imports(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    names: list[str] = []
    for rx in (JS_FROM, JS_REQUIRE):
        for m in rx.finditer(text):
            spec = m.group(1)
            if not spec or spec.startswith(".") or spec.startswith("/"):
                continue
            if spec.startswith("node:"):
                continue
            # scoped: @scope/name → keep full; else top-level
            if spec.startswith("@"):
                parts = spec.split("/")
                pkg = "/".join(parts[:2]) if len(parts) >= 2 else spec
            else:
                pkg = spec.split("/", 1)[0]
            names.append(norm_npm(pkg))
    return sorted(set(names))


def iter_shipped_modules(rec: dict) -> list[dict]:
    """Yield shippable and non-shippable (test) modules under a package root."""
    package_root = REPO / rec["root"]
    rows: list[dict] = []
    if rec["ecosystem"] == "pip":
        roots = shippable_python_roots(rec)
        # shippable
        for root in roots:
            if root.is_file():
                continue
            for path in sorted(root.rglob("*.py")):
                if any(should_skip_dir(p) for p in path.parts):
                    continue
                if is_test_path(path, package_root):
                    continue
                # must stay under a shippable root
                try:
                    path.resolve().relative_to(root.resolve())
                except ValueError:
                    continue
                rows.append(
                    {
                        "path": rel(path),
                        "shipped": True,
                        "imports": python_imports(path),
                    }
                )
        # test-only under package root (for control / negative)
        for path in sorted(package_root.rglob("*.py")):
            if any(should_skip_dir(p) for p in path.parts):
                continue
            if not is_test_path(path, package_root):
                continue
            rows.append(
                {
                    "path": rel(path),
                    "shipped": False,
                    "imports": python_imports(path),
                }
            )
    elif rec["ecosystem"] == "npm":
        roots = shippable_node_roots(rec)
        exts = {".js", ".mjs", ".cjs", ".ts", ".tsx"}
        for root in roots:
            paths = [root] if root.is_file() else sorted(
                p for p in root.rglob("*") if p.suffix in exts and p.is_file()
            )
            for path in paths:
                if any(should_skip_dir(p) for p in path.parts):
                    continue
                if is_test_path(path, package_root):
                    continue
                # if files: is set, don't treat package root dump as shipping tests/
                rows.append(
                    {
                        "path": rel(path),
                        "shipped": True,
                        "imports": js_imports(path),
                    }
                )
        for path in sorted(package_root.rglob("*")):
            if not path.is_file() or path.suffix not in exts:
                continue
            if any(should_skip_dir(p) for p in path.parts):
                continue
            if not is_test_path(path, package_root):
                continue
            rows.append(
                {
                    "path": rel(path),
                    "shipped": False,
                    "imports": js_imports(path),
                }
            )
    return rows


def map_import_to_declared(imp: str, declared: set[str], ecosystem: str) -> str | None:
    """Return the declared package name matching an import top-level, if any."""
    if ecosystem == "pip":
        # import name often uses underscores; declared uses hyphens
        candidates = {imp, imp.replace("_", "-"), imp.replace("-", "_")}
        for c in candidates:
            n = norm_pip(c)
            if n in declared:
                return n
        # also try without trailing
        return None
    n = norm_npm(imp)
    return n if n in declared else None


def find_defects(rec: dict) -> list[dict]:
    """Packaging defects: shipped module imports a declared-dev-only dependency."""
    if rec.get("error"):
        return []
    dev_only = set(rec.get("dev_only") or [])
    if not dev_only:
        return []
    defects: list[dict] = []
    for mod in iter_shipped_modules(rec):
        if not mod["shipped"]:
            continue
        for imp in mod["imports"]:
            hit = map_import_to_declared(imp, dev_only, rec["ecosystem"])
            if hit:
                defects.append(
                    {
                        "manifest": rec["manifest"],
                        "package": rec.get("name"),
                        "ecosystem": rec["ecosystem"],
                        "module": mod["path"],
                        "import_name": imp,
                        "declared_dev_only": hit,
                        "planted": is_our_fixture(rec["manifest"]),
                    }
                )
    return defects


def find_test_imports_of_dev(rec: dict) -> list[dict]:
    """Test-only imports of declared-dev-only deps (must NOT be flagged as defects)."""
    if rec.get("error"):
        return []
    dev_only = set(rec.get("dev_only") or [])
    if not dev_only:
        return []
    rows: list[dict] = []
    for mod in iter_shipped_modules(rec):
        if mod["shipped"]:
            continue
        for imp in mod["imports"]:
            hit = map_import_to_declared(imp, dev_only, rec["ecosystem"])
            if hit:
                rows.append(
                    {
                        "manifest": rec["manifest"],
                        "module": mod["path"],
                        "import_name": imp,
                        "declared_dev_only": hit,
                        "planted": is_our_fixture(rec["manifest"]),
                    }
                )
    return rows
