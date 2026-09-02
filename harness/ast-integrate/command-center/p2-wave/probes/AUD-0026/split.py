"""Runtime vs development dependency split detector for AUD-0026.

Probe 1 owns declared prod/dev classes. Probe 2 owns the shippable-module
import graph. A declared-dev name imported by a shipped module is a leak.
"""
from __future__ import annotations

import ast
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

SKIP_PARTS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "dist",
        "build",
        "vendor",
    }
)
PROBE_SKIP = ("command-center", "p2-wave", "probes")
DEV_GROUPS = frozenset(
    {
        "dev",
        "devel",
        "development",
        "test",
        "tests",
        "testing",
        "lint",
        "linter",
        "linters",
        "type",
        "types",
        "typing",
        "mypy",
        "pyright",
        "docs",
        "doc",
        "coverage",
        "cov",
        "qa",
        "style",
        "format",
        "fmt",
        "ruff",
        "black",
        "flake8",
    }
)
REQ_LINE = re.compile(
    r"^\s*(?P<name>[A-Za-z0-9._-]+)\s*(?P<extras>\[[^\]]*\])?\s*(?P<spec>.*)$"
)
IMPORT_TO_DIST = {
    "PIL": "pillow",
    "cv2": "opencv-python",
    "yaml": "pyyaml",
    "dateutil": "python-dateutil",
    "sklearn": "scikit-learn",
    "rest_framework": "djangorestframework",
    "bs4": "beautifulsoup4",
    "attr": "attrs",
    "serial": "pyserial",
    "jwt": "pyjwt",
    "dotenv": "python-dotenv",
    "skimage": "scikit-image",
    "OpenGL": "pyopengl",
    "gi": "pygobject",
    "cairo": "pycairo",
    "Magic": "python-magic",
    "git": "gitpython",
    "ruamel": "ruamel.yaml",
    "toml": "toml",
    "tomli": "tomli",
    "pkg_resources": "setuptools",
}
PLUGIN_ROOT = "tools/plugin"
PACKAGE_GATE_EXCLUSION = "tools/package_gate/exclusion_set.json"
STDLIB = set(getattr(sys, "stdlib_module_names", ())) | {
    "__future__",
    "builtins",
    "posix",
    "nt",
}


def norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", (name or "").strip()).lower()


def parse_spec(raw: str) -> str:
    spec = (raw or "").split("#")[0].split(";")[0].strip()
    if spec.startswith("(") and spec.endswith(")"):
        spec = spec[1:-1].strip()
    return spec or "*"


def add_req(bucket: dict[str, str], raw: str) -> None:
    line = str(raw).split("#")[0].strip()
    if not line or line.startswith("-"):
        return
    match = REQ_LINE.match(line)
    if not match:
        return
    bucket[norm(match.group("name"))] = parse_spec(match.group("spec"))


def as_req_map(value: Any) -> dict[str, str]:
    """Accept npm object maps, PEP 508 lists, and marketplace name/range lists."""
    bucket: dict[str, str] = {}
    if isinstance(value, dict):
        for key, spec in value.items():
            if isinstance(spec, dict):
                ver = spec.get("version") or spec.get("range") or spec.get("ver") or "*"
                bucket[norm(str(key))] = parse_spec(str(ver))
            else:
                bucket[norm(str(key))] = parse_spec(str(spec))
        return bucket
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                add_req(bucket, item)
            elif isinstance(item, dict):
                name = item.get("name") or item.get("package") or item.get("id")
                if not name:
                    continue
                ver = item.get("version") or item.get("range") or item.get("ver") or "*"
                bucket[norm(str(name))] = parse_spec(str(ver))
        return bucket
    return bucket


def skipped(path: Path) -> bool:
    return any(part in SKIP_PARTS for part in path.parts)


def in_probe_tree(path: Path) -> bool:
    parts = path.relative_to(REPO).parts
    return len(parts) >= 3 and parts[:3] == PROBE_SKIP


def rel(path: Path) -> str:
    return path.relative_to(REPO).as_posix()


def is_test_path(relpath: str) -> bool:
    parts = Path(relpath).parts
    name = Path(relpath).name
    if any(p in {"tests", "test", "testdata", "testing"} for p in parts):
        return True
    if name.startswith("test_") or name.endswith("_test.py"):
        return True
    return name in {"conftest.py", "conftest.js", "conftest.cjs"}


def glob_match(relpath: str, pattern: str) -> bool:
    from fnmatch import fnmatch

    posix = relpath.replace("\\", "/")
    pat = pattern.replace("\\", "/").lstrip("/")
    if fnmatch(posix, pat) or fnmatch(posix, pat.rstrip("*")):
        return True
    if pat.endswith("*") and posix.startswith(pat.rstrip("*")):
        return True
    name = posix.rsplit("/", 1)[-1]
    return fnmatch(name, pat) or fnmatch(posix, f"*/{pat}")


def excluded_by_packaging(relpath: str, excludes: Iterable[str]) -> bool:
    posix = relpath.replace("\\", "/")
    for raw in excludes:
        pat = str(raw).replace("\\", "/").strip()
        if not pat:
            continue
        if glob_match(posix, pat):
            return True
        if pat.rstrip("*").rstrip("/") in posix.split("/"):
            return True
    return False


def is_shippable(relpath: str, excludes: Iterable[str]) -> bool:
    if is_test_path(relpath):
        return False
    return not excluded_by_packaging(relpath, excludes)


def parse_pyproject(path: Path) -> dict[str, Any]:
    runtime: dict[str, str] = {}
    dev: dict[str, str] = {}
    other: dict[str, dict[str, str]] = {}
    include: list[str] = []
    exclude: list[str] = []
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        return {
            "path": rel(path) if path.is_relative_to(REPO) else str(path),
            "kind": "pyproject.toml",
            "runtime": {},
            "dev": {},
            "optional_other": {},
            "include": [],
            "exclude": [],
            "error": f"{type(exc).__name__}: {exc}",
        }
    project = data.get("project") if isinstance(data.get("project"), dict) else {}
    for item in project.get("dependencies") or []:
        if isinstance(item, str):
            add_req(runtime, item)
        elif isinstance(item, dict):
            name = item.get("name")
            if name:
                runtime[norm(str(name))] = parse_spec(str(item.get("version") or "*"))
    opt_deps = project.get("optional-dependencies")
    if isinstance(opt_deps, dict):
        for group, items in opt_deps.items():
            parsed: dict[str, str] = {}
            for item in items or []:
                if isinstance(item, str):
                    add_req(parsed, item)
            is_dev = (
                norm(str(group)).replace("-", "")
                in {g.replace("-", "") for g in DEV_GROUPS}
                or norm(str(group)) in DEV_GROUPS
            )
            if is_dev:
                dev.update(parsed)
            else:
                other[str(group)] = parsed
    dep_groups = data.get("dependency-groups")
    if isinstance(dep_groups, dict):
        for group, items in dep_groups.items():
            parsed = {}
            for item in items or []:
                if isinstance(item, str):
                    add_req(parsed, item)
            # PEP 735 groups are not installed with the wheel.
            dev.update(parsed)
    tool = data.get("tool") if isinstance(data.get("tool"), dict) else {}
    poetry = tool.get("poetry") if isinstance(tool.get("poetry"), dict) else {}
    poetry_deps = poetry.get("dependencies")
    if isinstance(poetry_deps, dict):
        for name, spec in poetry_deps.items():
            if norm(str(name)) == "python":
                continue
            runtime.setdefault(
                norm(str(name)),
                parse_spec(
                    str(spec if not isinstance(spec, dict) else spec.get("version", "*"))
                ),
            )
    poetry_groups = poetry.get("group")
    if isinstance(poetry_groups, dict):
        for group, body in poetry_groups.items():
            parsed = {}
            deps = (body or {}).get("dependencies") if isinstance(body, dict) else {}
            if isinstance(deps, dict):
                for name, spec in deps.items():
                    parsed[norm(str(name))] = parse_spec(
                        str(
                            spec
                            if not isinstance(spec, dict)
                            else spec.get("version", "*")
                        )
                    )
            if norm(str(group)) in DEV_GROUPS:
                dev.update(parsed)
            else:
                other[str(group)] = parsed
    setuptools = tool.get("setuptools") if isinstance(tool.get("setuptools"), dict) else {}
    packages = setuptools.get("packages")
    find: dict[str, Any] = {}
    if isinstance(packages, dict):
        maybe_find = packages.get("find") or {}
        if isinstance(maybe_find, dict):
            find = maybe_find
    include.extend(str(x) for x in (find.get("include") or []) if x)
    exclude.extend(str(x) for x in (find.get("exclude") or []) if x)
    hatch_tool = tool.get("hatch") if isinstance(tool.get("hatch"), dict) else {}
    hatch_build = hatch_tool.get("build") if isinstance(hatch_tool.get("build"), dict) else {}
    hatch = hatch_build.get("targets") if isinstance(hatch_build.get("targets"), dict) else {}
    for target in hatch.values():
        if isinstance(target, dict):
            exclude.extend(str(x) for x in (target.get("exclude") or []) if x)
            include.extend(str(x) for x in (target.get("packages") or []) if x)
    uv = tool.get("uv") if isinstance(tool.get("uv"), dict) else {}
    for item in uv.get("dev-dependencies") or []:
        if isinstance(item, str):
            add_req(dev, item)
    path_s = rel(path) if path.is_relative_to(REPO) else str(path)
    return {
        "path": path_s,
        "kind": "pyproject.toml",
        "runtime": dict(sorted(runtime.items())),
        "dev": dict(sorted(dev.items())),
        "optional_other": {k: dict(sorted(v.items())) for k, v in sorted(other.items())},
        "include": include,
        "exclude": exclude,
        "error": None,
    }


def parse_requirements(path: Path) -> dict[str, Any]:
    runtime: dict[str, str] = {}
    dev: dict[str, str] = {}
    name = path.name.lower()
    bucket = (
        dev
        if any(tok in name for tok in ("dev", "test", "lint", "doc", "typing"))
        else runtime
    )
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return {
            "path": rel(path) if path.is_relative_to(REPO) else str(path),
            "kind": path.name,
            "runtime": {},
            "dev": {},
            "optional_other": {},
            "include": [],
            "exclude": [],
            "error": f"{type(exc).__name__}: {exc}",
        }
    for line in text.splitlines():
        add_req(bucket, line)
    path_s = rel(path) if path.is_relative_to(REPO) else str(path)
    return {
        "path": path_s,
        "kind": path.name,
        "runtime": dict(sorted(runtime.items())),
        "dev": dict(sorted(dev.items())),
        "optional_other": {},
        "include": [],
        "exclude": [],
        "error": None,
    }


def parse_package_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {
            "path": rel(path) if path.is_relative_to(REPO) else str(path),
            "kind": "package.json",
            "runtime": {},
            "dev": {},
            "optional_other": {},
            "include": [],
            "exclude": [],
            "error": f"{type(exc).__name__}: {exc}",
        }
    if not isinstance(data, dict):
        data = {}
    runtime = as_req_map(data.get("dependencies"))
    dev = as_req_map(data.get("devDependencies"))
    other = {
        "optionalDependencies": as_req_map(data.get("optionalDependencies")),
        "peerDependencies": as_req_map(data.get("peerDependencies")),
    }
    files = data.get("files") or []
    path_s = rel(path) if path.is_relative_to(REPO) else str(path)
    return {
        "path": path_s,
        "kind": "package.json",
        "runtime": dict(sorted(runtime.items())),
        "dev": dict(sorted(dev.items())),
        "optional_other": {k: v for k, v in other.items() if v},
        "include": [str(x) for x in files] if isinstance(files, list) else [],
        "exclude": [],
        "error": None,
        "name": data.get("name"),
    }


def parse_manifest(path: Path) -> dict[str, Any]:
    try:
        if path.name == "pyproject.toml":
            return parse_pyproject(path)
        if path.name == "package.json":
            return parse_package_json(path)
        if path.name.startswith("requirements"):
            return parse_requirements(path)
        return {
            "path": str(path),
            "kind": path.name,
            "runtime": {},
            "dev": {},
            "optional_other": {},
            "include": [],
            "exclude": [],
            "error": "unsupported-manifest",
        }
    except Exception as exc:  # noqa: BLE001 — census must not die on one fixture
        return {
            "path": rel(path) if path.is_relative_to(REPO) else str(path),
            "kind": path.name,
            "runtime": {},
            "dev": {},
            "optional_other": {},
            "include": [],
            "exclude": [],
            "error": f"{type(exc).__name__}: {exc}",
        }


def find_manifests(root: Path, *, skip_probes: bool = True) -> list[Path]:
    found: list[Path] = []
    for dirpath, dirnames, filenames in root.walk() if hasattr(root, "walk") else _walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_PARTS]
        current = Path(dirpath)
        if skipped(current):
            continue
        if skip_probes and current.is_relative_to(REPO) and in_probe_tree(current):
            dirnames[:] = []
            continue
        for name in filenames:
            if name == "pyproject.toml" or name == "package.json" or (
                name.startswith("requirements") and name.endswith(".txt")
            ):
                found.append(current / name)
    return sorted(found)


def _walk(root: Path):
    import os

    for dirpath, dirnames, filenames in os.walk(root):
        yield dirpath, dirnames, filenames


def dist_for_import(top: str) -> str:
    if top in IMPORT_TO_DIST:
        return norm(IMPORT_TO_DIST[top])
    return norm(top)


def extract_imports(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        return [
            {
                "module": "<unparseable>",
                "top": "<unparseable>",
                "kind": "error",
                "detail": f"{type(exc).__name__}: {exc}",
            }
        ]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = (alias.name or "").split(".")[0]
                rows.append({"module": alias.name, "top": top, "kind": "import"})
        elif isinstance(node, ast.ImportFrom):
            if node.level and not node.module:
                continue
            if node.level:
                continue
            if not node.module:
                continue
            top = node.module.split(".")[0]
            rows.append({"module": node.module, "top": top, "kind": "from"})
    return rows


def repo_python_package_names() -> set[str]:
    """Importable top-level names under tools/ (hyphen dirs map to underscores)."""
    names: set[str] = set()
    tools = REPO / "tools"
    if not tools.is_dir():
        return names
    for child in tools.iterdir():
        if not child.is_dir() or child.name.startswith("."):
            continue
        py_ok = (child / "__init__.py").is_file() or any(child.glob("*.py"))
        if not py_ok:
            continue
        names.add(child.name.replace("-", "_"))
    return names


def classify_top(
    top: str, first_party: set[str], repo_first_party: set[str] | None = None
) -> str:
    if not top or top == "<unparseable>":
        return "error"
    if top in STDLIB:
        return "stdlib"
    if top in first_party or norm(top) in {norm(x) for x in first_party}:
        return "first-party"
    repo = repo_first_party or set()
    if top in repo or top.replace("-", "_") in repo:
        return "repo-first-party"
    return "third-party"


def load_exclusion_rules() -> dict[str, Any]:
    path = REPO / PACKAGE_GATE_EXCLUSION
    if not path.is_file():
        return {"path": PACKAGE_GATE_EXCLUSION, "present": False, "patterns": []}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {
            "path": PACKAGE_GATE_EXCLUSION,
            "present": True,
            "error": f"{type(exc).__name__}: {exc}",
            "patterns": [],
        }
    patterns = doc.get("patterns") if isinstance(doc, dict) else []
    ids = [
        str(p.get("id"))
        for p in (patterns or [])
        if isinstance(p, dict) and p.get("id")
    ]
    excludes_tests = any(
        "test" in str(p.get("value") or "").lower()
        or "test" in str(p.get("id") or "").lower()
        for p in (patterns or [])
        if isinstance(p, dict)
    )
    return {
        "path": PACKAGE_GATE_EXCLUSION,
        "present": True,
        "pattern_ids": ids,
        "excludes_tests": excludes_tests,
        "size_ceiling_bytes": doc.get("size_ceiling_bytes") if isinstance(doc, dict) else None,
    }


def write_control_fixture(root: Path) -> dict[str, Any]:
    """Shipped module imports pytest (dev); test module imports pytest too."""
    src = root / "src" / "aud0026fix"
    tests = root / "tests"
    src.mkdir(parents=True, exist_ok=True)
    tests.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "aud0026fix"',
                'version = "0.0.1"',
                "dependencies = [",
                '  "rich>=13",',
                "]",
                "[project.optional-dependencies]",
                "dev = [",
                '  "pytest>=8",',
                "]",
                "[tool.setuptools.packages.find]",
                'where = ["src"]',
                'exclude = ["tests*"]',
                "",
            ]
        ),
        encoding="utf-8",
    )
    (src / "__init__.py").write_text("", encoding="utf-8")
    (src / "leaky.py").write_text("import pytest\n", encoding="utf-8")
    (src / "ok.py").write_text("import rich\n", encoding="utf-8")
    (tests / "test_harness.py").write_text("import pytest\n", encoding="utf-8")
    return {
        "root": str(root),
        "shipped_leaky": "src/aud0026fix/leaky.py",
        "shipped_ok": "src/aud0026fix/ok.py",
        "test_only": "tests/test_harness.py",
        "runtime": ["rich"],
        "dev": ["pytest"],
    }


def scan_tree_imports(
    root: Path,
    *,
    first_party: set[str],
    excludes: Iterable[str],
    package_rel: str | None = None,
    repo_first_party: set[str] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    repo_fp = repo_first_party or set()
    for path in sorted(root.rglob("*.py")):
        if skipped(path):
            continue
        if package_rel:
            relpath = path.relative_to(root).as_posix()
        else:
            relpath = path.relative_to(REPO).as_posix() if path.is_relative_to(REPO) else str(path)
        shipped = is_shippable(relpath, excludes)
        for item in extract_imports(path):
            top = item.get("top") or ""
            kind = classify_top(top, first_party, repo_fp)
            needs_dist = kind in {"third-party", "repo-first-party"}
            dist = dist_for_import(top) if needs_dist else ""
            rows.append(
                {
                    "path": relpath,
                    "shipped": shipped,
                    "module": item.get("module"),
                    "top": top,
                    "import_kind": item.get("kind"),
                    "class": kind,
                    "dist": dist,
                }
            )
    return rows


def leaks_from_imports(
    imports: list[dict[str, Any]], runtime: dict[str, str], dev: dict[str, str]
) -> list[dict[str, Any]]:
    runtime_n = set(runtime)
    dev_n = set(dev)
    leaks: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in imports:
        if not row.get("shipped"):
            continue
        if row.get("class") not in {"third-party", "repo-first-party"}:
            continue
        dist = str(row.get("dist") or "")
        if not dist:
            continue
        key = (str(row.get("path")), dist)
        if key in seen:
            continue
        seen.add(key)
        if dist in dev_n and dist not in runtime_n:
            kind = "declared-dev-imported-by-shipped"
        elif dist not in runtime_n:
            if row.get("class") == "repo-first-party":
                kind = "undeclared-repo-sibling-imported-by-shipped"
            else:
                kind = "undeclared-third-party-imported-by-shipped"
        else:
            continue
        leaks.append(
            {
                "path": row["path"],
                "dist": dist,
                "top": row.get("top"),
                "class": row.get("class"),
                "kind": kind,
            }
        )
    return leaks


def run_control(root: Path) -> dict[str, Any]:
    meta = write_control_fixture(root)
    parsed = parse_pyproject(root / "pyproject.toml")
    runtime = parsed["runtime"]
    dev = parsed["dev"]
    split_ok = (
        "rich" in runtime
        and "pytest" in dev
        and "pytest" not in runtime
        and "rich" not in dev
        and parsed["error"] is None
    )
    imports = scan_tree_imports(
        root,
        first_party={"aud0026fix"},
        excludes=parsed.get("exclude") or ["tests*"],
        package_rel="fixture",
    )
    leaks = leaks_from_imports(imports, runtime, dev)
    flagged_leaky = any(
        x["path"].endswith("leaky.py") and x["dist"] == "pytest" for x in leaks
    )
    flagged_ok = any(x["path"].endswith("ok.py") for x in leaks)
    flagged_test = any("tests/" in x["path"] or x["path"].startswith("tests") for x in leaks)
    mutant_imports = []
    for row in imports:
        clone = dict(row)
        clone["shipped"] = True
        mutant_imports.append(clone)
    mutant_leaks = leaks_from_imports(mutant_imports, runtime, dev)
    mutant_flags_test = any(
        "test_harness.py" in x["path"] and x["dist"] == "pytest" for x in mutant_leaks
    )
    return {
        "fixture": meta,
        "declared_runtime": runtime,
        "declared_dev": dev,
        "packaging_exclude": parsed.get("exclude") or [],
        "split_parser_ok": split_ok,
        "imports": imports,
        "leaks": leaks,
        "shipped_dev_import_flagged": flagged_leaky,
        "shipped_runtime_import_silent": not flagged_ok,
        "test_dev_import_silent": not flagged_test,
        "mutant_no_test_filter_flags_test_import": mutant_flags_test,
        "pass": bool(
            split_ok
            and flagged_leaky
            and not flagged_ok
            and not flagged_test
            and mutant_flags_test
        ),
    }


def plugin_first_party() -> set[str]:
    names = {"plugin"}
    root = REPO / PLUGIN_ROOT
    if root.is_dir():
        for child in root.iterdir():
            if child.suffix == ".py" and child.stem != "__init__":
                names.add(child.stem)
    return names


def live_plugin_scan() -> dict[str, Any]:
    root = REPO / PLUGIN_ROOT
    manifests = find_manifests(root, skip_probes=False) if root.is_dir() else []
    parsed = [parse_manifest(p) for p in manifests]
    runtime: dict[str, str] = {}
    dev: dict[str, str] = {}
    excludes: list[str] = ["tests*"]
    for item in parsed:
        runtime.update(item.get("runtime") or {})
        dev.update(item.get("dev") or {})
        excludes.extend(item.get("exclude") or [])
    repo_fp = repo_python_package_names() - plugin_first_party()
    imports = (
        scan_tree_imports(
            root,
            first_party=plugin_first_party(),
            excludes=excludes,
            repo_first_party=repo_fp,
        )
        if root.is_dir()
        else []
    )
    leaks = leaks_from_imports(imports, runtime, dev)
    shipped = [r for r in imports if r.get("shipped")]
    third = [
        r
        for r in shipped
        if r.get("class") in {"third-party", "repo-first-party"}
    ]
    return {
        "plugin_root": PLUGIN_ROOT,
        "plugin_root_exists": root.is_dir(),
        "manifests": parsed,
        "manifest_count": len(parsed),
        "manifest_absent": len(parsed) == 0,
        "runtime": dict(sorted(runtime.items())),
        "dev": dict(sorted(dev.items())),
        "consumer_forced": sorted(runtime),
        "dev_only": sorted(d for d in dev if d not in runtime),
        "packaging_exclude": excludes,
        "import_rows": imports,
        "shipped_import_count": len(shipped),
        "shipped_third_party": third,
        "leaks": leaks,
        "py_file_count": (
            sum(1 for p in root.rglob("*.py") if not skipped(p)) if root.is_dir() else 0
        ),
    }


def repo_manifest_census() -> list[dict[str, Any]]:
    out = []
    for path in find_manifests(REPO, skip_probes=True):
        out.append(parse_manifest(path))
    return out
