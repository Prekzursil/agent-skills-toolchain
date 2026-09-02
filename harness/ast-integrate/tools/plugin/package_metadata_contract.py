"""Package metadata vs built artifact contract (TST-0035).

The contract: every declared package field -- ``name``, ``version``,
``entry_points``, ``engines`` and ``files`` -- must be consistent with what
the build actually emits, and a metadata/build mismatch must fail the gate.

Two package kinds are covered.

* **Python** -- the declaration is ``pyproject.toml`` (``[project]`` plus the
  ``[tool.setuptools] packages`` list).  The built artifact is a real sdist
  produced by ``setuptools.build_meta.build_sdist`` on a *copy* of the
  package (never in-tree), read back through ``PKG-INFO`` (``email.parser``),
  ``*.egg-info/entry_points.txt`` and the tar member list.
* **Node** -- the declaration is ``package.json`` (``name``/``version``/
  ``bin``/``engines``/``files``).  The built artifact is an ``npm pack``-shaped
  tarball (``package/`` prefix, ``package/package.json`` inside) built with
  :mod:`tarfile`; no ``npm`` binary is required.

:func:`compare_metadata` is the gate: one comparison row per rule with the
declared value, the built value, ``consistent`` and the ``missing``/``extra``
sets; ``gate_pass`` is true only when every row is consistent.

:func:`run_conformance_suite` is the executable conformance suite: a
conforming Python fixture and a conforming Node fixture must PASS, and for
every rule a deliberately non-conforming declaration (mutated metadata
compared against the *same* built artifact) must FAIL with exactly that
rule's row inconsistent.  ``both_states`` holds when both sides behave.

Nothing here reaches the network; the only subprocess is the interpreter
running the setuptools backend on the temporary copy.
"""
from __future__ import annotations

import configparser
import copy
import email.parser
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

try:
    import tomllib
except ImportError:  # pragma: no cover - Python < 3.11
    import tomli as tomllib  # type: ignore

__all__ = [
    "RULES",
    "RULE_IDS",
    "MetadataContractError",
    "parser_identity",
    "declared_python",
    "declared_node",
    "build_python_sdist",
    "build_node_tarball",
    "inspect_python_sdist",
    "inspect_node_tarball",
    "compare_metadata",
    "inspect_live_python",
    "live_npm_package_json",
    "make_python_fixture",
    "make_node_fixture",
    "mutate_declared",
    "run_conformance_suite",
]

RULES: list[str] = ["name", "version", "entry_points", "engines", "files"]
RULE_IDS: dict[str, str] = {
    "name": "PKG-NAME",
    "version": "PKG-VERSION",
    "entry_points": "PKG-ENTRY-POINTS",
    "engines": "PKG-ENGINES",
    "files": "PKG-FILES",
}

PYTHON_DECLARED_SOURCE = "pyproject.toml [project] + [tool.setuptools] packages"
NODE_DECLARED_SOURCE = "package.json name/version/bin/engines/files"
LIVE_PYTHON_PACKAGE = "tools/agentspec"
NPM_CANDIDATES = ("tools/agentspec/package.json", "tools/plugin/package.json")
_COPY_IGNORE = shutil.ignore_patterns(
    "__pycache__",
    "*.egg-info",
    "build",
    "dist",
    ".git",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "node_modules",
)
_NPM_ALWAYS_PACKED = ("package.json",)


class MetadataContractError(RuntimeError):
    """A declaration or artifact could not be read/built."""


def _python_version() -> str:
    v = sys.version_info
    return f"{v.major}.{v.minor}.{v.micro}"


def parser_identity() -> dict[str, Any]:
    """Identity of the parser stack the comparison is made with."""
    return {
        "name": "package-metadata-contract",
        "path": "tools/plugin/package_metadata_contract.py",
        "python": _python_version(),
        "version": f"python-{_python_version()}+setuptools.build_meta.build_sdist",
        "json_module": "json + tomllib + email.parser",
    }


# --------------------------------------------------------------------------
# declarations
# --------------------------------------------------------------------------
def _package_files(pkg_dir: Path, packages: list[str]) -> list[str]:
    """``*.py`` files of each declared package (non-recursive per package).

    Sub-packages must be declared themselves, exactly as setuptools treats an
    explicit ``packages`` list, so an undeclared sub-directory is *not* part
    of the declared file set.
    """
    out: set[str] = set()
    for pkg in packages:
        rel = PurePosixPath(*pkg.split("."))
        folder = pkg_dir / rel
        if not folder.is_dir():
            continue
        for p in folder.iterdir():
            if p.is_file() and p.suffix == ".py":
                out.add((rel / p.name).as_posix())
    return sorted(out)


def undeclared_python_files(pkg_dir: Path, packages: list[str]) -> list[str]:
    """``*.py`` files under a declared top-level package that no declared package covers."""
    declared = set(_package_files(pkg_dir, packages))
    roots = sorted({pkg.split(".")[0] for pkg in packages})
    found: list[str] = []
    for root in roots:
        folder = pkg_dir / root
        if not folder.is_dir():
            continue
        for p in folder.rglob("*.py"):
            if "__pycache__" in p.parts or not p.is_file():
                continue
            rel = p.relative_to(pkg_dir).as_posix()
            if rel not in declared:
                found.append(rel)
    return sorted(found)


def _pyproject_entry_points(project: dict[str, Any]) -> dict[str, dict[str, str]]:
    groups: dict[str, dict[str, str]] = {}
    scripts = project.get("scripts") or {}
    if scripts:
        groups["console_scripts"] = {str(k): str(v) for k, v in scripts.items()}
    gui = project.get("gui-scripts") or {}
    if gui:
        groups["gui_scripts"] = {str(k): str(v) for k, v in gui.items()}
    for group, table in (project.get("entry-points") or {}).items():
        if isinstance(table, dict) and table:
            groups[str(group)] = {str(k): str(v) for k, v in table.items()}
    return dict(sorted(groups.items()))


def declared_python(pkg_dir: Path | str) -> dict[str, Any]:
    """Read the Python declaration from ``<pkg_dir>/pyproject.toml``."""
    root = Path(pkg_dir)
    path = root / "pyproject.toml"
    if not path.is_file():
        raise MetadataContractError(f"pyproject.toml missing under {root}")
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise MetadataContractError(f"pyproject.toml unreadable: {exc}") from exc
    project = data.get("project") or {}
    if not isinstance(project, dict) or not project.get("name"):
        raise MetadataContractError("pyproject.toml has no [project].name")
    tool = (data.get("tool") or {}).get("setuptools") or {}
    packages = tool.get("packages")
    if not isinstance(packages, list) or not packages:
        # Explicit declaration absent: the package named by [project].name.
        packages = [str(project["name"]).replace("-", "_")]
    packages = [str(p) for p in packages]
    return {
        "kind": "python",
        "name": str(project["name"]),
        "version": str(project.get("version") or ""),
        "entry_points": _pyproject_entry_points(project),
        "engines": str(project.get("requires-python") or ""),
        "files": _package_files(root, packages),
        "packages": packages,
        "undeclared_files": undeclared_python_files(root, packages),
        "source": PYTHON_DECLARED_SOURCE,
    }


def _expand_node_files(root: Path, patterns: list[str]) -> list[str]:
    out: set[str] = set()
    for pat in patterns:
        pat = str(pat).strip().lstrip("./")
        if not pat:
            continue
        target = root / pat
        if target.is_file():
            out.add(PurePosixPath(pat).as_posix())
            continue
        if target.is_dir():
            for p in target.rglob("*"):
                if p.is_file():
                    out.add(p.relative_to(root).as_posix())
            continue
        matched = False
        for p in root.glob(pat):
            if p.is_file():
                out.add(p.relative_to(root).as_posix())
                matched = True
        if not matched:
            # Declared but absent on disk: keep the declaration so the
            # comparison reports it as missing from the built artifact.
            out.add(PurePosixPath(pat).as_posix())
    return sorted(out)


def declared_node(pkg_dir: Path | str) -> dict[str, Any]:
    """Read the Node declaration from ``<pkg_dir>/package.json``."""
    root = Path(pkg_dir)
    path = root / "package.json"
    if not path.is_file():
        raise MetadataContractError(f"package.json missing under {root}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MetadataContractError(f"package.json unreadable: {exc}") from exc
    if not isinstance(data, dict) or not data.get("name"):
        raise MetadataContractError("package.json has no name")
    bin_field = data.get("bin")
    if isinstance(bin_field, str):
        bin_map = {str(data["name"]).split("/")[-1]: bin_field}
    elif isinstance(bin_field, dict):
        bin_map = {str(k): str(v) for k, v in bin_field.items()}
    else:
        bin_map = {}
    engines = data.get("engines") if isinstance(data.get("engines"), dict) else {}
    files = data.get("files") if isinstance(data.get("files"), list) else []
    return {
        "kind": "node",
        "name": str(data["name"]),
        "version": str(data.get("version") or ""),
        "entry_points": {"bin": dict(sorted(bin_map.items()))} if bin_map else {},
        "engines": {str(k): str(v) for k, v in sorted(engines.items())},
        "files": _expand_node_files(root, [str(f) for f in files]),
        "source": NODE_DECLARED_SOURCE,
    }


# --------------------------------------------------------------------------
# builds
# --------------------------------------------------------------------------
def _hermetic_env() -> dict[str, str]:
    env = {
        k: v
        for k, v in os.environ.items()
        if k in ("PATH", "HOME", "TMPDIR", "TEMP", "TMP", "SYSTEMROOT", "LANG", "LC_ALL")
    }
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["SOURCE_DATE_EPOCH"] = "315532800"
    return env


def build_python_sdist(pkg_dir: Path | str, out_dir: Path | str) -> Path:
    """Build an sdist of a *copy* of ``pkg_dir`` with ``setuptools.build_meta``.

    The copy keeps the tree under test pristine (no ``*.egg-info`` or
    ``dist/`` lands in the repo).  The backend runs in a fresh, isolated
    interpreter so nothing imported by the caller leaks into the build.
    """
    src = Path(pkg_dir)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pkgmeta-src-") as tmp:
        work = Path(tmp) / src.name
        shutil.copytree(src, work, ignore=_COPY_IGNORE, symlinks=False)
        code = (
            "import sys\n"
            "from setuptools import build_meta\n"
            "print(build_meta.build_sdist(sys.argv[1]))\n"
        )
        proc = subprocess.run(
            [sys.executable, "-I", "-B", "-c", code, str(out.resolve())],
            cwd=str(work),
            capture_output=True,
            text=True,
            timeout=240,
            env=_hermetic_env(),
            check=False,
        )
    if proc.returncode != 0:
        tail = ((proc.stdout or "") + (proc.stderr or ""))[-2000:]
        raise MetadataContractError(f"build_sdist failed rc={proc.returncode}: {tail}")
    name = (proc.stdout or "").strip().splitlines()[-1].strip()
    artifact = out / name
    if not artifact.is_file():
        raise MetadataContractError(f"build_sdist reported {name!r} but it is absent")
    return artifact


def build_node_tarball(pkg_dir: Path | str, out_dir: Path | str) -> Path:
    """Pack ``pkg_dir`` the way ``npm pack`` does: ``package/`` prefix, ``files`` honoured."""
    root = Path(pkg_dir)
    decl = declared_node(root)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    base = decl["name"].replace("@", "").replace("/", "-")
    artifact = out / f"{base}-{decl['version']}.tgz"
    members: list[str] = list(_NPM_ALWAYS_PACKED)
    for rel in decl["files"]:
        if (root / rel).is_file() and rel not in members:
            members.append(rel)
    for target in (decl["entry_points"].get("bin") or {}).values():
        rel = str(target).lstrip("./")
        if (root / rel).is_file() and rel not in members:
            members.append(rel)
    with tarfile.open(artifact, "w:gz") as tf:
        for rel in sorted(members):
            info = tf.gettarinfo(str(root / rel), arcname=f"package/{rel}")
            info.mtime = 315532800
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            with open(root / rel, "rb") as fh:
                tf.addfile(info, fh)
    return artifact


# --------------------------------------------------------------------------
# artifact inspection
# --------------------------------------------------------------------------
def _read_member(tf: tarfile.TarFile, name: str) -> str:
    fh = tf.extractfile(name)
    if fh is None:
        raise MetadataContractError(f"{name} is not a regular member")
    return fh.read().decode("utf-8", errors="replace")


def inspect_python_sdist(artifact: Path | str, packages: list[str] | None = None) -> dict[str, Any]:
    """Read name/version/entry points/Requires-Python/py members out of an sdist."""
    path = Path(artifact)
    if not tarfile.is_tarfile(path):
        raise MetadataContractError(f"{path.name} is not a tar archive")
    with tarfile.open(path) as tf:
        names = tf.getnames()
        files = [m for m in tf.getmembers() if m.isfile()]
        roots = sorted({n.split("/", 1)[0] for n in names if "/" in n})
        if len(roots) != 1:
            raise MetadataContractError(f"sdist has {len(roots)} top-level dirs: {roots}")
        prefix = roots[0] + "/"
        pkg_info = next((n for n in names if n == prefix + "PKG-INFO"), None)
        if pkg_info is None:
            raise MetadataContractError("sdist has no PKG-INFO")
        meta = email.parser.Parser().parsestr(_read_member(tf, pkg_info))
        ep_member = next(
            (n for n in names if n.startswith(prefix) and n.endswith(".egg-info/entry_points.txt")),
            None,
        )
        entry_points: dict[str, dict[str, str]] = {}
        if ep_member:
            cp = configparser.ConfigParser(interpolation=None, delimiters=("=",))
            cp.optionxform = str  # type: ignore[assignment]
            cp.read_string(_read_member(tf, ep_member))
            for section in cp.sections():
                entry_points[section] = {k: v.strip() for k, v in cp.items(section)}
    members = sorted(m.name[len(prefix):] for m in files if m.name.startswith(prefix))
    py_members = [m for m in members if m.endswith(".py")]
    roots_wanted = {p.split(".")[0] for p in (packages or [])}
    if roots_wanted:
        built_files = [m for m in py_members if m.split("/", 1)[0] in roots_wanted]
    else:
        built_files = py_members
    return {
        "kind": "python",
        "artifact": path.name,
        "artifact_bytes": path.stat().st_size,
        "name": str(meta.get("Name") or ""),
        "version": str(meta.get("Version") or ""),
        "entry_points": dict(sorted(entry_points.items())),
        "engines": str(meta.get("Requires-Python") or ""),
        "files": sorted(built_files),
        "members": members,
        "source": f"sdist {path.name} PKG-INFO + member list",
    }


def inspect_node_tarball(artifact: Path | str) -> dict[str, Any]:
    """Read name/version/bin/engines/files out of an npm-pack-shaped tarball."""
    path = Path(artifact)
    if not tarfile.is_tarfile(path):
        raise MetadataContractError(f"{path.name} is not a tar archive")
    with tarfile.open(path) as tf:
        files = [m for m in tf.getmembers() if m.isfile()]
        names = [m.name for m in files]
        if "package/package.json" not in names:
            raise MetadataContractError("tarball has no package/package.json")
        try:
            data = json.loads(_read_member(tf, "package/package.json"))
        except json.JSONDecodeError as exc:
            raise MetadataContractError(f"packed package.json unreadable: {exc}") from exc
    members = sorted(n[len("package/"):] for n in names if n.startswith("package/"))
    bin_field = data.get("bin")
    if isinstance(bin_field, str):
        bin_map = {str(data.get("name", "")).split("/")[-1]: bin_field}
    elif isinstance(bin_field, dict):
        bin_map = {str(k): str(v) for k, v in bin_field.items()}
    else:
        bin_map = {}
    # A bin entry only counts as built when its target is actually packed.
    packed_bin = {
        k: v for k, v in bin_map.items() if str(v).lstrip("./") in members
    }
    engines = data.get("engines") if isinstance(data.get("engines"), dict) else {}
    return {
        "kind": "node",
        "artifact": path.name,
        "artifact_bytes": path.stat().st_size,
        "name": str(data.get("name") or ""),
        "version": str(data.get("version") or ""),
        "entry_points": {"bin": dict(sorted(packed_bin.items()))} if packed_bin else {},
        "engines": {str(k): str(v) for k, v in sorted(engines.items())},
        "files": [m for m in members if m not in _NPM_ALWAYS_PACKED],
        "members": members,
        "source": f"npm-pack-shaped tarball {path.name}",
    }


# --------------------------------------------------------------------------
# the gate
# --------------------------------------------------------------------------
def _flatten_entry_points(groups: dict[str, dict[str, str]]) -> dict[str, str]:
    return {f"{g}:{n}": str(t) for g, table in groups.items() for n, t in table.items()}


def compare_metadata(
    declared: dict[str, Any],
    built: dict[str, Any],
    *,
    package: str | None = None,
) -> dict[str, Any]:
    """Compare a declaration with a built artifact, one row per rule."""
    kind = str(declared.get("kind") or built.get("kind") or "python")
    rows: list[dict[str, Any]] = []
    for field in RULES:
        d_val = declared.get(field)
        b_val = built.get(field)
        missing: list[str] = []
        extra: list[str] = []
        if field == "entry_points":
            d_flat = _flatten_entry_points(d_val or {})
            b_flat = _flatten_entry_points(b_val or {})
            missing = sorted(k for k, t in d_flat.items() if b_flat.get(k) != t)
            extra = sorted(k for k in b_flat if k not in d_flat)
            consistent = not missing and not extra
            shown_built: Any = {
                "present": sorted(b_flat),
                "missing": missing,
                "extra": extra,
            }
        elif field == "files":
            d_set = set(d_val or [])
            b_set = set(b_val or [])
            missing = sorted(d_set - b_set)
            extra = sorted(b_set - d_set)
            consistent = not missing and not extra
            shown_built = sorted(b_set)
        else:
            consistent = d_val == b_val
            shown_built = b_val
        row = {
            "field": field,
            "kind": kind,
            "rule_id": RULE_IDS[field],
            "declared": d_val,
            "built": shown_built,
            "consistent": bool(consistent),
            "declared_source": declared.get("source"),
            "built_source": built.get("source"),
            "missing": missing,
            "extra": extra,
        }
        if package is not None:
            row["package"] = package
        rows.append(row)
    mismatches = [r["field"] for r in rows if not r["consistent"]]
    return {
        "kind": kind,
        "artifact": built.get("artifact"),
        "artifact_bytes": built.get("artifact_bytes"),
        "gate_pass": not mismatches,
        "mismatches": mismatches,
        "comparison_table": rows,
    }


# --------------------------------------------------------------------------
# live tree
# --------------------------------------------------------------------------
def inspect_live_python(repo: Path | str, package: str = LIVE_PYTHON_PACKAGE) -> dict[str, Any] | None:
    """Re-pack the live Python package and compare it with its declaration.

    Returns ``None`` when the package has no ``pyproject.toml``.
    """
    root = Path(repo)
    pkg_dir = root / package
    if not (pkg_dir / "pyproject.toml").is_file():
        return None
    declared = declared_python(pkg_dir)
    with tempfile.TemporaryDirectory(prefix="pkgmeta-dist-") as tmp:
        artifact = build_python_sdist(pkg_dir, tmp)
        built = inspect_python_sdist(artifact, declared["packages"])
    result = compare_metadata(declared, built, package=package)
    result.update(
        {
            "package": package,
            "method": "copy-then-setuptools.build_meta.build_sdist",
            "declared_packages": declared["packages"],
            "undeclared_files": declared["undeclared_files"],
            "sdist_member_count": len(built["members"]),
        }
    )
    return result


def live_npm_package_json(repo: Path | str) -> dict[str, Any]:
    """Census of ``package.json`` beside the primary-tree packages."""
    root = Path(repo)
    found = [rel for rel in NPM_CANDIDATES if (root / rel).is_file()]
    if found:
        note = (
            f"package.json present at {', '.join(found)}; Node contract coverage "
            "applies to the live tree as well as the fixtures."
        )
    else:
        note = (
            "No package.json beside tools/agentspec or tools/plugin; Node contract "
            "coverage is fixture-only. Repo-root package.json is the private monorepo "
            "workspace file, not the agentspec distribution."
        )
    return {
        "candidates": list(NPM_CANDIDATES),
        "found": found,
        "present": bool(found),
        "note": note,
    }


# --------------------------------------------------------------------------
# conformance suite
# --------------------------------------------------------------------------
PYTHON_FIXTURE_NAME = "tst0035fix"
NODE_FIXTURE_NAME = "tst0035-node"


def make_python_fixture(root: Path | str) -> Path:
    """Write a minimal, fully declared Python package under ``root``."""
    pkg = Path(root) / PYTHON_FIXTURE_NAME
    (pkg / PYTHON_FIXTURE_NAME).mkdir(parents=True, exist_ok=True)
    (pkg / "pyproject.toml").write_text(
        "[build-system]\n"
        'requires = ["setuptools>=61"]\n'
        'build-backend = "setuptools.build_meta"\n\n'
        "[project]\n"
        f'name = "{PYTHON_FIXTURE_NAME}"\n'
        'version = "1.0.0"\n'
        'description = "TST-0035 conforming Python fixture"\n'
        'requires-python = ">=3.10"\n\n'
        "[project.scripts]\n"
        f'{PYTHON_FIXTURE_NAME} = "{PYTHON_FIXTURE_NAME}:main"\n\n'
        "[tool.setuptools]\n"
        f'packages = ["{PYTHON_FIXTURE_NAME}"]\n',
        encoding="utf-8",
    )
    (pkg / PYTHON_FIXTURE_NAME / "__init__.py").write_text(
        '"""TST-0035 conforming fixture package."""\n\n\n'
        "def main() -> int:\n"
        "    return 0\n",
        encoding="utf-8",
    )
    return pkg


def make_node_fixture(root: Path | str) -> Path:
    """Write a minimal, fully declared Node package under ``root``."""
    pkg = Path(root) / NODE_FIXTURE_NAME
    (pkg / "bin").mkdir(parents=True, exist_ok=True)
    (pkg / "lib").mkdir(parents=True, exist_ok=True)
    (pkg / "package.json").write_text(
        json.dumps(
            {
                "name": NODE_FIXTURE_NAME,
                "version": "1.2.3",
                "description": "TST-0035 conforming Node fixture",
                "bin": {NODE_FIXTURE_NAME: "./bin/cli.js"},
                "engines": {"node": ">=18"},
                "files": ["bin/cli.js", "lib/index.js"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (pkg / "bin" / "cli.js").write_text(
        "#!/usr/bin/env node\nrequire('../lib/index.js').main();\n", encoding="utf-8"
    )
    (pkg / "lib" / "index.js").write_text(
        "exports.main = function main() { return 0; };\n", encoding="utf-8"
    )
    return pkg


def mutate_declared(declared: dict[str, Any], field: str) -> dict[str, Any]:
    """Return a copy of ``declared`` whose ``field`` no longer matches the build."""
    if field not in RULES:
        raise ValueError(f"unknown rule {field!r}")
    mutated = copy.deepcopy(declared)
    kind = mutated.get("kind")
    if field == "name":
        mutated["name"] = f"{mutated['name']}-renamed"
    elif field == "version":
        mutated["version"] = "9.9.9"
    elif field == "entry_points":
        group = "bin" if kind == "node" else "console_scripts"
        table = dict(mutated.get("entry_points", {}).get(group) or {})
        phantom = f"{mutated['name']}-extra"
        table[phantom] = "./bin/extra.js" if kind == "node" else f"{mutated['name']}:extra"
        eps = dict(mutated.get("entry_points") or {})
        eps[group] = table
        mutated["entry_points"] = eps
    elif field == "engines":
        if kind == "node":
            engines = dict(mutated.get("engines") or {})
            engines["node"] = ">=20"
            mutated["engines"] = engines
        else:
            mutated["engines"] = ">=3.12"
    elif field == "files":
        phantom = "lib/phantom.js" if kind == "node" else f"{mutated['name']}/phantom.py"
        mutated["files"] = sorted(set(mutated.get("files") or []) | {phantom})
    return mutated


def _case(
    case_id: str,
    kind: str,
    state: str,
    target_field: str | None,
    result: dict[str, Any],
) -> dict[str, Any]:
    rows = {r["field"]: r for r in result["comparison_table"]}
    target_inconsistent = (
        bool(target_field) and not rows[target_field]["consistent"]  # type: ignore[index]
    )
    return {
        "id": case_id,
        "kind": kind,
        "state": state,
        "target_field": target_field,
        "gate_pass": bool(result["gate_pass"]),
        "mismatches": list(result["mismatches"]),
        "target_field_inconsistent": bool(target_inconsistent),
        "artifact": result.get("artifact"),
        "comparison_table": result["comparison_table"],
    }


def run_conformance_suite() -> dict[str, Any]:
    """Run the executable conformance suite on fresh fixtures.

    Both conforming fixtures are built for real; every negative case mutates
    the *declaration* and re-runs the gate against the unchanged artifact, so
    a negative that still passes would mean the rule is not enforced.
    """
    cases: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="pkgmeta-suite-") as tmp:
        root = Path(tmp)
        py_pkg = make_python_fixture(root / "python")
        py_decl = declared_python(py_pkg)
        py_art = build_python_sdist(py_pkg, root / "python-dist")
        py_built = inspect_python_sdist(py_art, py_decl["packages"])
        cases.append(
            _case("python-conforming", "python", "conforming", None, compare_metadata(py_decl, py_built))
        )
        node_pkg = make_node_fixture(root / "node")
        node_decl = declared_node(node_pkg)
        node_art = build_node_tarball(node_pkg, root / "node-dist")
        node_built = inspect_node_tarball(node_art)
        cases.append(
            _case("node-conforming", "node", "conforming", None, compare_metadata(node_decl, node_built))
        )
        for field in RULES:
            cases.append(
                _case(
                    f"python-neg-{field}",
                    "python",
                    "nonconforming",
                    field,
                    compare_metadata(mutate_declared(py_decl, field), py_built),
                )
            )
        for field in RULES:
            cases.append(
                _case(
                    f"node-neg-{field}",
                    "node",
                    "nonconforming",
                    field,
                    compare_metadata(mutate_declared(node_decl, field), node_built),
                )
            )
    conforming = [c for c in cases if c["state"] == "conforming"]
    negatives = [c for c in cases if c["state"] == "nonconforming"]
    conforming_pass = bool(conforming) and all(c["gate_pass"] for c in conforming)
    per_rule: dict[str, dict[str, Any]] = {}
    for field in RULES:
        mine = [c for c in negatives if c["target_field"] == field]
        per_rule[field] = {
            "negatives": [c["id"] for c in mine],
            "ok": bool(mine)
            and all((not c["gate_pass"]) and c["target_field_inconsistent"] for c in mine),
        }
    negatives_fail = bool(negatives) and all(not c["gate_pass"] for c in negatives)
    both_states = conforming_pass and negatives_fail
    suite_ok = both_states and all(info["ok"] for info in per_rule.values())
    return {
        "suite_ok": suite_ok,
        "both_states": both_states,
        "conforming_pass": conforming_pass,
        "negatives_fail": negatives_fail,
        "per_rule": per_rule,
        "cases": cases,
        "rules": list(RULES),
        "parser": parser_identity(),
    }


def main(argv: list[str] | None = None) -> int:
    """CLI: run the suite (and the live check when a repo root is given)."""
    args = list(sys.argv[1:] if argv is None else argv)
    suite = run_conformance_suite()
    out: dict[str, Any] = {
        "suite_ok": suite["suite_ok"],
        "both_states": suite["both_states"],
        "conforming_pass": suite["conforming_pass"],
        "per_rule": suite["per_rule"],
    }
    if args:
        live = inspect_live_python(args[0])
        out["live"] = None if live is None else {
            "artifact": live["artifact"],
            "gate_pass": live["gate_pass"],
            "mismatches": live["mismatches"],
        }
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0 if suite["suite_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
