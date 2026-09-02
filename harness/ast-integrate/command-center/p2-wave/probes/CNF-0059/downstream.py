#!/usr/bin/env python3
"""Enumerate tools/lib consumers and run each consumer's own smoke.

Live tree: tools/lib is absent here. Historical workspace membership comes
from AUD-0021 snapshots. Fixture consumers prove the detector: unprotected
must not pass, resolved path is printed, API breaks and stale pins are seen.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURES = HERE / "fixtures"
LIB_CHANGED = FIXTURES / "lib-changed"
LIB_BASELINE = FIXTURES / "lib-baseline"
CONSUMERS = FIXTURES / "consumers"
PKG_NAME = "@prekzursil/tools-lib"

IMPORT_RE = re.compile(
    r"(?:from|import)\s+['\"](?:@prekzursil/tools-lib|[^'\"]*tools/lib[^'\"]*)['\"]"
    r"|require\(\s*['\"](?:@prekzursil/tools-lib|[^'\"]*tools/lib)['\"]"
    r"|tools/lib/[\w.-]+\.mjs"
    r"|@prekzursil/tools-lib"
)

SKIP_DIR_NAMES = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "dist",
    "build",
    ".agents",
    ".cursor",
}


def artifact_payload(doc: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Read probe-checked fields from a schema-valid receipt.

    Domain payload lives in extensions because receipt_core forbids extra
    top-level keys. Older drafts stored answer/consumers at the root.
    """
    ext = doc.get("extensions") if isinstance(doc.get("extensions"), dict) else {}
    answer = doc.get("answer")
    if not isinstance(answer, dict):
        answer = ext.get("answer") if isinstance(ext.get("answer"), dict) else {}
    consumers = doc.get("consumers")
    if not isinstance(consumers, list):
        consumers = ext.get("consumers") if isinstance(ext.get("consumers"), list) else []
    return answer, consumers


def lf_sha256(path: Path) -> tuple[str, int]:
    import hashlib

    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def live_library() -> dict[str, Any]:
    lib = REPO / "tools" / "lib"
    modules = sorted(p.name for p in lib.glob("*.mjs")) if lib.is_dir() else []
    tests: list[str] = []
    if lib.is_dir():
        tests = sorted(
            str(p.relative_to(REPO)).replace("\\", "/")
            for p in lib.rglob("*")
            if p.is_file()
            and ("test" in p.name.lower() or p.parent.name in {"test", "tests"})
        )
    return {
        "path": "tools/lib",
        "present": lib.is_dir(),
        "module_files": modules,
        "test_files": tests,
        "salvage_claim_modules": 6,
        "salvage_claim_tests": 72,
        "modules_on_disk": len(modules),
        "tests_on_disk": len(tests),
    }


def _pins(pkg: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for bucket in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        block = pkg.get(bucket) or {}
        if isinstance(block, dict) and PKG_NAME in block:
            out[bucket] = str(block[PKG_NAME])
    return out


def _workspace_lists_lib(pkg: dict) -> bool:
    ws = pkg.get("workspaces")
    items: list[str] = []
    if isinstance(ws, list):
        items = [str(x) for x in ws]
    elif isinstance(ws, dict) and isinstance(ws.get("packages"), list):
        items = [str(x) for x in ws["packages"]]
    return any(i.replace("\\", "/").rstrip("/") in {"tools/lib", "tools/lib/"} for i in items)


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO)).replace("\\", "/")
    except ValueError:
        return str(path)


def _skip_fixtures(resolved: Path, live: bool) -> bool:
    fx = FIXTURES.resolve()
    return live and (resolved == fx or fx in resolved.parents)


def discover_packages(root: Path, *, live: bool) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        pdir = Path(dirpath)
        try:
            resolved = pdir.resolve()
        except OSError:
            continue
        if _skip_fixtures(resolved, live):
            dirnames[:] = []
            continue
        if "package.json" not in filenames:
            continue
        pkg_path = pdir / "package.json"
        try:
            pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        name = str(pkg.get("name") or pdir.name)
        rel = _rel(pkg_path)
        if name == PKG_NAME or rel.endswith("tools/lib/package.json"):
            continue
        pins = _pins(pkg)
        ws = _workspace_lists_lib(pkg)
        if not pins and not ws:
            continue
        scripts = pkg.get("scripts") if isinstance(pkg.get("scripts"), dict) else {}
        smoke_script = None
        for key in ("smoke", "test"):
            if key in scripts:
                smoke_script = {"name": key, "command": str(scripts[key])}
                break
        smoke_file = next((c for c in ("smoke.mjs", "smoke.js", "smoke.py") if (pdir / c).is_file()), None)
        rows.append(
            {
                "id": name,
                "path": rel,
                "root": str(pdir),
                "present": True,
                "kind": "package",
                "universe": "live" if live else "fixture",
                "pins": pins,
                "workspace_lists_tools_lib": ws,
                "scripts": sorted(scripts),
                "smoke_script": smoke_script,
                "smoke_file": smoke_file,
            }
        )
    return rows


def discover_imports(root: Path, *, live: bool) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    catalog = (REPO / "command-center" / "WORK-UNIT-CATALOG.json").resolve()
    lib_root = (REPO / "tools" / "lib").resolve()
    probes_root = (REPO / "command-center" / "p2-wave" / "probes").resolve()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        pdir = Path(dirpath)
        try:
            resolved = pdir.resolve()
        except OSError:
            continue
        if _skip_fixtures(resolved, live):
            dirnames[:] = []
            continue
        if live and (resolved == lib_root or lib_root in resolved.parents):
            dirnames[:] = []
            continue
        if live and (resolved == probes_root or probes_root in resolved.parents):
            dirnames[:] = []
            continue
        for fn in filenames:
            if not fn.endswith((".mjs", ".js", ".cjs", ".ts", ".tsx", ".py")):
                continue
            fp = pdir / fn
            if fp.resolve() == catalog:
                continue
            try:
                text = fp.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if not IMPORT_RE.search(text):
                continue
            hits.append({"path": _rel(fp), "kind": "source-import"})
    return hits


def historical_consumers() -> list[dict[str, Any]]:
    src = REPO / "command-center/p2-wave/probes/AUD-0021/probe1-manifests.json"
    if not src.is_file():
        return []
    try:
        data = json.loads(src.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows: list[dict[str, Any]] = []
    for item in data if isinstance(data, list) else []:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "").replace("\\", "/")
        ws = item.get("workspaces") or []
        if path != "package.json" or not (isinstance(ws, list) and "tools/lib" in ws):
            continue
        rows.append(
            {
                "id": str(item.get("name") or "agent-skills-toolchain"),
                "path": "package.json",
                "root": str(REPO),
                "present": (REPO / "package.json").is_file(),
                "kind": "historical_workspace_host",
                "universe": "historical",
                "pins": {},
                "workspace_lists_tools_lib": True,
                "scripts": list(item.get("script_names") or []),
                "smoke_script": None,
                "smoke_file": None,
                "source": _rel(src),
            }
        )
    return rows


def pin_invalidated(declared: str, lib_version: str) -> bool:
    declared = declared.strip()
    if declared.startswith(("file:", "workspace:", "link:")):
        return False
    if declared == lib_version:
        return False
    if re.fullmatch(r"\d+\.\d+\.\d+", declared):
        return declared != lib_version
    m = re.fullmatch(r"\^(\d+)\.(\d+)\.(\d+)", declared)
    if not m:
        return False
    major, minor, patch = (int(x) for x in m.groups())
    lm = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", lib_version)
    if not lm:
        return False
    a, b, c = (int(x) for x in lm.groups())
    if major == 0:
        return not (a == 0 and b == minor and c >= patch)
    return not (a == major and (b, c) >= (minor, patch))


def ensure_lib_link(consumer_root: Path, lib_root: Path) -> None:
    dest = consumer_root / "node_modules" / "@prekzursil" / "tools-lib"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_symlink() or dest.is_file():
        dest.unlink()
    elif dest.is_dir():
        shutil.rmtree(dest)
    dest.symlink_to(lib_root.resolve(), target_is_directory=True)


def parse_resolved(output: str) -> str | None:
    for line in output.splitlines():
        if line.startswith("RESOLVED_LIB="):
            return line.split("=", 1)[1].strip() or None
    return None


def run_smoke(consumer_root: Path, smoke_file: str) -> dict[str, Any]:
    node = shutil.which("node")
    if not node:
        return {"exit_code": 127, "output": "node not found on PATH", "resolved_library_path": None}
    target = consumer_root / smoke_file
    if not target.is_file():
        return {"exit_code": None, "output": "NO_SMOKE", "resolved_library_path": None}
    try:
        proc = subprocess.run(
            [node, str(target)],
            cwd=str(consumer_root),
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
    except subprocess.TimeoutExpired:
        return {"exit_code": 124, "output": "TIMEOUT", "resolved_library_path": None}
    out = (proc.stdout or "") + (proc.stderr or "")
    return {"exit_code": proc.returncode, "output": out[-8000:], "resolved_library_path": parse_resolved(out)}


def classify(row: dict[str, Any], smoke: dict[str, Any] | None, lib_version: str, changed_lib: Path) -> dict[str, Any]:
    out = dict(row)
    has_smoke = bool(row.get("smoke_file"))
    if not has_smoke:
        out.update(
            finding="unprotected",
            unprotected_reason="consumer_tree_absent" if not row.get("present") else "no_smoke_entry_point",
            exit_code=None,
            resolved_library_path=None,
            printed_resolved_library_path=False,
            pin_invalidated=False,
        )
        return out
    assert smoke is not None
    pins = row.get("pins") or {}
    invalidated = any(pin_invalidated(v, lib_version) for v in pins.values())
    resolved = smoke.get("resolved_library_path")
    changed_real = str(changed_lib.resolve())
    wrong_copy = False
    if resolved:
        try:
            wrong_copy = changed_real not in str(Path(resolved).resolve())
        except OSError:
            wrong_copy = True
    out["exit_code"] = smoke.get("exit_code")
    out["resolved_library_path"] = resolved
    out["printed_resolved_library_path"] = bool(resolved)
    out["pin_invalidated"] = invalidated
    out["smoke_output_tail"] = (smoke.get("output") or "")[-2000:]
    if not resolved:
        out["finding"] = "library_unresolved" if out["exit_code"] is not None else "unprotected"
        if out["finding"] == "unprotected":
            out["unprotected_reason"] = "no_resolved_path_and_no_exit"
        return out
    if out["exit_code"] != 0:
        out["finding"] = "broke"
        return out
    if wrong_copy:
        out["finding"] = "wrong_copy"
        return out
    if invalidated:
        out["finding"] = "pin_invalidated"
        return out
    out["finding"] = "ok"
    return out


def unprotected_misclassified(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bad: list[dict[str, Any]] = []
    seen: set[str] = set()
    for r in rows:
        if r.get("smoke_file"):
            continue
        if r.get("finding") != "ok":
            continue
        k = str(r.get("id"))
        if k in seen:
            continue
        seen.add(k)
        bad.append(r)
    return bad


def measure() -> dict[str, Any]:
    lib = live_library()
    live_pkgs = discover_packages(REPO, live=True)
    live_imports = discover_imports(REPO, live=True)
    historical = historical_consumers()
    fixture_rows = discover_packages(CONSUMERS, live=False)
    for row in fixture_rows:
        row["universe"] = "fixture"
        row["path"] = _rel(Path(row["root"]) / "package.json")

    lib_version = json.loads((LIB_CHANGED / "package.json").read_text(encoding="utf-8"))["version"]
    classified: list[dict[str, Any]] = []
    for row in fixture_rows:
        root = Path(row["root"])
        ensure_lib_link(root, LIB_CHANGED)
        smoke = run_smoke(root, row["smoke_file"]) if row.get("smoke_file") else None
        classified.append(classify(row, smoke, lib_version, LIB_CHANGED))
    for row in live_pkgs:
        smoke = run_smoke(Path(row["root"]), row["smoke_file"]) if row.get("smoke_file") else None
        classified.append(classify(row, smoke, lib_version, LIB_CHANGED))
    live_keys = {(r.get("id"), r.get("path")) for r in live_pkgs}
    for row in historical:
        if (row.get("id"), row.get("path")) in live_keys:
            continue
        classified.append(classify(row, None, lib_version, LIB_CHANGED))

    by_finding: dict[str, int] = {}
    for r in classified:
        by_finding[r["finding"]] = by_finding.get(r["finding"], 0) + 1

    mis = unprotected_misclassified(classified)
    mutated = [dict(r) for r in classified]
    for r in mutated:
        if not r.get("smoke_file") and r.get("finding") == "unprotected":
            r["finding"] = "ok"
            r["exit_code"] = 0
            break
    control = {
        "id": "unprotected-not-passing",
        "fired_on_bad_state": bool(unprotected_misclassified(mutated)),
        "silent_on_good_state": not bool(mis),
        "misclassified_on_good": [r.get("id") for r in mis],
    }
    return {
        "library": lib,
        "lib_changed_version": lib_version,
        "lib_changed_path": str(LIB_CHANGED.resolve()),
        "live_package_consumers": live_pkgs,
        "live_source_imports": live_imports,
        "consumers": classified,
        "by_finding": by_finding,
        "broken_ids": [r["id"] for r in classified if r["finding"] == "broke"],
        "pin_invalidated_ids": [r["id"] for r in classified if r.get("pin_invalidated")],
        "unprotected_ids": [r["id"] for r in classified if r["finding"] == "unprotected"],
        "ok_ids": [r["id"] for r in classified if r["finding"] == "ok"],
        "control_unprotected": control,
    }


if __name__ == "__main__":
    doc = measure()
    keys = ("by_finding", "broken_ids", "unprotected_ids", "pin_invalidated_ids", "ok_ids", "library")
    print(json.dumps({k: doc[k] for k in keys}, indent=2))
