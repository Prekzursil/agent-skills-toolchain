"""Test collector whose printed listing is the source of collected ids.

Does not grep source. Ids are emitted only after a loader or inspect walk of
an imported module, or after pytest --collect-only stdout is parsed. A module
that cannot import is COLLECTION_ERROR and contributes no collected id.
"""
from __future__ import annotations

import importlib.util
import inspect
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

LIVE_ROOTS = (
    REPO / "tools" / "command-center" / "tests",
    REPO / "tools" / "plugin" / "tests",
    REPO / "tools" / "marketplace" / "tests",
)

HEADER = "TST-0123-COLLECT v1"


def relposix(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def _iter_tests(suite: unittest.TestSuite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _iter_tests(item)
        else:
            yield item


def _load_module(path: Path):
    name = f"tst0123_{path.stem}_{abs(hash(str(path.resolve()))) % 10_000_000}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"no spec for {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def collect_file_stdlib(path: Path, id_root: Path) -> tuple[list[str], list[str]]:
    """Import path and collect unittest cases plus module-level test_* functions."""
    collected: list[str] = []
    errors: list[str] = []
    rel = relposix(path, id_root)
    try:
        mod = _load_module(path)
    except Exception as exc:  # noqa: BLE001 — collection must record import failure
        errors.append(f"COLLECTION_ERROR {rel} {type(exc).__name__}: {exc}")
        return collected, errors
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(mod)
    seen_methods: set[str] = set()
    for test in _iter_tests(suite):
        parts = test.id().split(".")
        if len(parts) >= 2:
            cls, method = parts[-2], parts[-1]
            nid = f"{rel}::{cls}::{method}"
            seen_methods.add(method)
        else:
            nid = f"{rel}::{test.id()}"
        collected.append(nid)
    for name, obj in inspect.getmembers(mod, inspect.isfunction):
        if not name.startswith("test_"):
            continue
        if name in seen_methods:
            continue
        if getattr(obj, "__module__", None) != mod.__name__:
            continue
        collected.append(f"{rel}::{name}")
    return collected, errors


def collect_tree_stdlib(root: Path, *, id_root: Path | None = None) -> dict[str, Any]:
    id_root = id_root or root
    files = sorted(p for p in root.rglob("test_*.py") if p.is_file())
    collected: list[str] = []
    errors: list[str] = []
    for path in files:
        ids, errs = collect_file_stdlib(path, id_root)
        collected.extend(ids)
        errors.extend(errs)
    collected = sorted(set(collected))
    return {
        "runner": "stdlib-unittest-loader+inspect",
        "root": str(root),
        "id_root": str(id_root),
        "files": [relposix(p, id_root) for p in files],
        "collected": collected,
        "errors": errors,
    }


def attempt_pytest(root: Path) -> dict[str, Any]:
    cmd = [
        sys.executable,
        "-B",
        "-m",
        "pytest",
        "--collect-only",
        "-q",
        str(root),
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=90,
        )
    except subprocess.TimeoutExpired:
        return {
            "available": False,
            "command": " ".join(cmd),
            "returncode": 124,
            "raw": "TIMEOUT",
            "collected": [],
        }
    raw = ((proc.stdout or "") + (proc.stderr or "")).strip()
    if proc.returncode != 0 or "ModuleNotFoundError" in raw or "No module named pytest" in raw:
        return {
            "available": False,
            "command": " ".join(cmd),
            "returncode": proc.returncode,
            "raw": raw[-4000:],
            "collected": [],
        }
    ids: list[str] = []
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if "::" in line and not line.startswith("=") and "error" not in line.lower():
            ids.append(line)
    return {
        "available": True,
        "command": " ".join(cmd),
        "returncode": proc.returncode,
        "raw": raw[-4000:],
        "collected": sorted(set(ids)),
    }


def format_listing(blob: dict[str, Any]) -> str:
    lines = [
        HEADER,
        f"# runner={blob.get('runner')}",
        f"# root={blob.get('root')}",
        f"# id_root={blob.get('id_root')}",
        f"# files={len(blob.get('files') or [])}",
    ]
    for nid in blob.get("collected") or []:
        lines.append(f"COLLECTED {nid}")
    for err in blob.get("errors") or []:
        lines.append(err if str(err).startswith("COLLECTION_ERROR ") else f"COLLECTION_ERROR {err}")
    n = len(blob.get("collected") or [])
    e = len(blob.get("errors") or [])
    lines.append(f"# END collected={n} errors={e}")
    return "\n".join(lines) + "\n"


def parse_listing(text: str) -> list[str]:
    """Collected ids come only from COLLECTED lines of runner output."""
    if HEADER not in text:
        raise ValueError("collection listing missing TST-0123-COLLECT header")
    ids: list[str] = []
    for line in text.splitlines():
        if line.startswith("COLLECTED "):
            nid = line[len("COLLECTED ") :].strip()
            if nid:
                ids.append(nid)
    return sorted(set(ids))


def collect_live() -> dict[str, Any]:
    # Package dirs for `import catalog` / `from marketplace...`. Do not put
    # REPO on sys.path: repo-root `platform/` shadows stdlib platform.
    for root in LIVE_ROOTS:
        pkg = str(root.parent.resolve())
        if pkg not in sys.path:
            sys.path.insert(0, pkg)
    tools_dir = str((REPO / "tools").resolve())
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)
    pytest_meta = []
    collected: list[str] = []
    errors: list[str] = []
    files: list[str] = []
    for root in LIVE_ROOTS:
        py = attempt_pytest(root)
        pytest_meta.append(
            {
                "root": relposix(root, REPO),
                "available": py["available"],
                "returncode": py["returncode"],
                "command": py["command"],
            }
        )
        if py["available"] and py["collected"]:
            collected.extend(py["collected"])
            continue
        blob = collect_tree_stdlib(root, id_root=REPO)
        collected.extend(blob["collected"])
        errors.extend(blob["errors"])
        files.extend(blob["files"])
    collected = sorted(set(collected))
    return {
        "runner": "pytest-or-stdlib",
        "root": str(REPO),
        "id_root": str(REPO),
        "files": files,
        "collected": collected,
        "errors": errors,
        "pytest": pytest_meta,
        "live_roots": [relposix(p, REPO) for p in LIVE_ROOTS],
    }


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "--live":
        blob = collect_live()
    elif argv:
        root = Path(argv[0])
        if not root.is_absolute():
            root = (REPO / root).resolve()
        blob = collect_tree_stdlib(root, id_root=root)
    else:
        blob = collect_tree_stdlib(HERE / "fixtures" / "suite")
    sys.stdout.write(format_listing(blob))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
