"""Walk npm/python/cargo manifests and lockfiles, including transitives.

A direct-only reader of package.json would miss a gap two levels deep.
Lockfile v3 packages[] is walked as a graph (resolve node_modules hops).
"""
from __future__ import annotations

import json
import os
import re
import tomllib
from pathlib import Path
from typing import Any

from classify import classify_dep

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

SKIP_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".cursor",
    "scw-pull",
    "target",
    ".tox",
}

SHIPPED_ROOTS = (
    "package.json",
    "tools",
    "platform",
    "skills",
    ".agents/skills",
    "release",
)

REQ = re.compile(
    r"^\s*(?P<name>[A-Za-z0-9._-]+)\s*(?P<extras>\[[^\]]*\])?\s*(?P<spec>.*)$"
)


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return path.as_posix()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_npm(packages: dict[str, Any], from_key: str, name: str) -> str | None:
    prefix = from_key
    seen: set[str] = set()
    while prefix not in seen:
        seen.add(prefix)
        cand = f"{prefix}/node_modules/{name}" if prefix else f"node_modules/{name}"
        if cand in packages:
            return cand
        if not prefix:
            break
        marker = "/node_modules/"
        idx = prefix.rfind(marker)
        if idx >= 0:
            prefix = prefix[:idx]
            continue
        if prefix.startswith("node_modules/"):
            prefix = ""
            continue
        if "/" in prefix:
            prefix = prefix.rsplit("/", 1)[0]
            continue
        prefix = ""
    if f"node_modules/{name}" in packages:
        return f"node_modules/{name}"
    return None


def _npm_dep_map(rec: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for field in ("dependencies", "optionalDependencies", "peerDependencies"):
        block = rec.get(field) or {}
        if isinstance(block, dict):
            for name, spec in block.items():
                out.setdefault(str(name), str(spec))
    return out


def walk_npm_lock(
    lock_path: Path,
    *,
    in_sbom: set[str] | None = None,
    queried: set[str] | None = None,
) -> list[dict[str, Any]]:
    lock = _load_json(lock_path)
    packages: dict[str, Any] = lock.get("packages") or {}
    if not isinstance(packages, dict):
        return []
    sbom = in_sbom or set()
    did_query = queried or set()
    origin = rel(lock_path)
    rows: list[dict[str, Any]] = []
    seen: dict[str, int] = {}

    def emit(
        name: str,
        spec: str,
        depth: int,
        child_key: str | None,
        direct: bool,
    ) -> None:
        ident = child_key or f"unresolved:{name}"
        prev = seen.get(ident)
        if prev is not None and prev <= depth:
            return
        seen[ident] = depth
        rec = packages.get(child_key) if child_key else None
        rec = rec if isinstance(rec, dict) else {}
        version = str(rec.get("version") or spec or "")
        integrity = rec.get("integrity")
        if isinstance(integrity, str):
            integrity_s = integrity or None
        else:
            integrity_s = None
        resolved = rec.get("resolved")
        resolved_s = str(resolved) if resolved else None
        license_s = rec.get("license")
        if not isinstance(license_s, str) or not license_s.strip():
            license_s = None
        key = f"npm:{name}@{version}"
        gaps = classify_dep(
            spec=spec,
            ecosystem="npm",
            integrity=integrity_s,
            resolved=resolved_s,
            license_record=license_s,
            in_sbom=key in sbom or name in sbom,
            advisory_queried=key in did_query or name in did_query,
            locked=child_key is not None,
        )
        rows.append(
            {
                "name": name,
                "version": version,
                "ecosystem": "npm",
                "spec": spec,
                "depth": depth,
                "direct": direct,
                "lock_key": child_key,
                "integrity": integrity_s,
                "resolved": resolved_s,
                "license": license_s,
                "origin": origin,
                "gaps": gaps,
            }
        )
        if child_key:
            rec2 = packages.get(child_key) or {}
            if isinstance(rec2, dict):
                for child_name, child_spec in _npm_dep_map(rec2).items():
                    ck = resolve_npm(packages, child_key, child_name)
                    emit(child_name, str(child_spec), depth + 1, ck, False)

    roots = [""]
    for k in packages:
        if not k:
            continue
        if "node_modules" in k.split("/"):
            continue
        roots.append(k)
    for root in roots:
        rec = packages.get(root) or {}
        if not isinstance(rec, dict):
            continue
        for name, spec in _npm_dep_map(rec).items():
            child = resolve_npm(packages, root, name)
            emit(name, str(spec), 1, child, True)
    return rows


def nearest_npm_lock(pkg_path: Path) -> Path | None:
    cur = pkg_path.parent
    stop = REPO
    while True:
        cand = cur / "package-lock.json"
        if cand.is_file():
            return cand
        if cur == stop or cur.parent == cur:
            return None
        cur = cur.parent


def walk_package_json(
    pkg_path: Path,
    *,
    lock_path: Path | None = None,
    in_sbom: set[str] | None = None,
    queried: set[str] | None = None,
) -> list[dict[str, Any]]:
    data = _load_json(pkg_path)
    origin = rel(pkg_path)
    if lock_path and lock_path.is_file():
        return walk_npm_lock(lock_path, in_sbom=in_sbom, queried=queried)
    sbom = in_sbom or set()
    did_query = queried or set()
    rows: list[dict[str, Any]] = []
    for kind in (
        "dependencies",
        "devDependencies",
        "optionalDependencies",
        "peerDependencies",
    ):
        block = data.get(kind) or {}
        if not isinstance(block, dict):
            continue
        for name, spec in block.items():
            spec_s = str(spec)
            gaps = classify_dep(
                spec=spec_s,
                ecosystem="npm",
                integrity=None,
                resolved=None,
                license_record=None,
                in_sbom=name in sbom,
                advisory_queried=name in did_query,
                locked=False,
            )
            rows.append(
                {
                    "name": str(name),
                    "version": spec_s,
                    "ecosystem": "npm",
                    "spec": spec_s,
                    "kind": kind,
                    "depth": 1,
                    "direct": True,
                    "lock_key": None,
                    "integrity": None,
                    "resolved": None,
                    "license": None,
                    "origin": origin,
                    "gaps": gaps,
                }
            )
    return rows


def unpinned_control(pkg_path: Path) -> dict[str, Any]:
    data = _load_json(pkg_path)
    for kind in ("devDependencies", "dependencies", "optionalDependencies"):
        block = data.get(kind) or {}
        if not isinstance(block, dict):
            continue
        for name, spec in block.items():
            spec_s = str(spec)
            if spec_s.strip() != "*":
                continue
            gaps = classify_dep(
                spec=spec_s,
                ecosystem="npm",
                integrity=None,
                resolved=None,
                license_record=None,
                in_sbom=False,
                advisory_queried=False,
                locked=False,
            )
            return {
                "found": True,
                "name": str(name),
                "kind": kind,
                "spec": spec_s,
                "gaps": gaps,
            }
    return {"found": False}


def transitive_control(lock_path: Path) -> dict[str, Any]:
    rows = walk_npm_lock(lock_path)
    direct = [r["name"] for r in rows if r.get("direct")]
    # unique preserve order
    direct_only: list[str] = []
    for n in direct:
        if n not in direct_only:
            direct_only.append(n)
    leaf = next((r for r in rows if r["name"] == "leaf-pkg"), None)
    if leaf is None:
        return {
            "direct_only": direct_only,
            "leaf_depth": None,
            "leaf_in_direct": "leaf-pkg" in direct_only,
            "leaf_integrity": None,
            "found": False,
        }
    return {
        "direct_only": direct_only,
        "leaf_depth": leaf.get("depth"),
        "leaf_in_direct": leaf["name"] in direct_only,
        "leaf_integrity": leaf.get("integrity"),
        "found": True,
    }


def _parse_req_line(line: str) -> tuple[str, str] | None:
    line = line.split("#")[0].strip()
    if not line or line.startswith("-"):
        return None
    m = REQ.match(line)
    if not m:
        return None
    spec = (m.group("spec") or "").split(";")[0].strip() or "*"
    return m.group("name").lower().replace("_", "-"), spec


def walk_pyproject(
    path: Path,
    *,
    in_sbom: set[str] | None = None,
    queried: set[str] | None = None,
) -> list[dict[str, Any]]:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError, UnicodeDecodeError):
        return []
    declared: list[tuple[str, str, str]] = []
    for raw in (data.get("project") or {}).get("dependencies") or []:
        parsed = _parse_req_line(str(raw))
        if parsed:
            declared.append((parsed[0], parsed[1], "dependencies"))
    for extra, group in (
        (data.get("project") or {}).get("optional-dependencies") or {}
    ).items():
        for raw in group or []:
            parsed = _parse_req_line(str(raw))
            if parsed:
                declared.append((parsed[0], parsed[1], f"optional:{extra}"))
    poetry = ((data.get("tool") or {}).get("poetry") or {}).get("dependencies") or {}
    if isinstance(poetry, dict):
        for k, v in poetry.items():
            if str(k).lower() == "python":
                continue
            spec = v if not isinstance(v, dict) else v.get("version", "*")
            declared.append((str(k).lower().replace("_", "-"), str(spec), "poetry"))

    lock_meta: dict[str, dict[str, Any]] = {}
    parent = path.parent
    for lock_name, parser in (
        ("uv.lock", _parse_uv_lock),
        ("poetry.lock", _parse_poetry_lock),
        ("Pipfile.lock", _parse_pipfile_lock),
    ):
        lp = parent / lock_name
        if lp.is_file():
            lock_meta.update(parser(lp))
            break

    sbom = in_sbom or set()
    did_query = queried or set()
    origin = rel(path)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for name, spec, kind in declared:
        key = f"pypi:{name}"
        if key in seen:
            continue
        seen.add(key)
        meta = lock_meta.get(name) or {}
        version = str(meta.get("version") or spec)
        integrity = meta.get("hash")
        resolved = meta.get("url")
        pkey = f"pypi:{name}@{version}"
        gaps = classify_dep(
            spec=spec,
            ecosystem="pypi",
            integrity=integrity,
            resolved=resolved,
            license_record=None,
            in_sbom=pkey in sbom or name in sbom,
            advisory_queried=pkey in did_query or name in did_query,
            locked=bool(meta),
        )
        rows.append(
            {
                "name": name,
                "version": version,
                "ecosystem": "pypi",
                "spec": spec,
                "kind": kind,
                "depth": 1,
                "direct": True,
                "integrity": integrity,
                "resolved": resolved,
                "license": None,
                "origin": origin,
                "gaps": gaps,
            }
        )
    # Transitive python packages present only in the lock.
    for name, meta in lock_meta.items():
        key = f"pypi:{name}"
        if key in seen:
            continue
        seen.add(key)
        version = str(meta.get("version") or "")
        pkey = f"pypi:{name}@{version}"
        gaps = classify_dep(
            spec=str(meta.get("version") or ""),
            ecosystem="pypi",
            integrity=meta.get("hash"),
            resolved=meta.get("url"),
            license_record=None,
            in_sbom=pkey in sbom or name in sbom,
            advisory_queried=pkey in did_query or name in did_query,
            locked=True,
        )
        rows.append(
            {
                "name": name,
                "version": version,
                "ecosystem": "pypi",
                "spec": version,
                "kind": "lock-transitive",
                "depth": 2,
                "direct": False,
                "integrity": meta.get("hash"),
                "resolved": meta.get("url"),
                "license": None,
                "origin": origin,
                "gaps": gaps,
            }
        )
    return rows


def _parse_uv_lock(path: Path) -> dict[str, dict[str, Any]]:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError, UnicodeDecodeError):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for pkg in data.get("package") or []:
        if not isinstance(pkg, dict):
            continue
        name = str(pkg.get("name") or "").lower().replace("_", "-")
        if not name:
            continue
        version = str(pkg.get("version") or "")
        digest = None
        url = None
        sdist = pkg.get("sdist") or {}
        if isinstance(sdist, dict):
            digest = sdist.get("hash")
            url = sdist.get("url")
        wheels = pkg.get("wheels") or []
        if not digest and isinstance(wheels, list):
            for w in wheels:
                if isinstance(w, dict) and w.get("hash"):
                    digest = w.get("hash")
                    url = url or w.get("url")
                    break
        out[name] = {"version": version, "hash": digest, "url": url}
    return out


def _parse_poetry_lock(path: Path) -> dict[str, dict[str, Any]]:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError, UnicodeDecodeError):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for pkg in data.get("package") or []:
        if not isinstance(pkg, dict):
            continue
        name = str(pkg.get("name") or "").lower().replace("_", "-")
        if not name:
            continue
        files = pkg.get("files") or []
        digest = None
        if isinstance(files, list):
            for f in files:
                if isinstance(f, dict) and f.get("hash"):
                    digest = f.get("hash")
                    break
        out[name] = {
            "version": str(pkg.get("version") or ""),
            "hash": digest,
            "url": None,
        }
    return out


def _parse_pipfile_lock(path: Path) -> dict[str, dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for section in ("default", "develop"):
        block = data.get(section) or {}
        if not isinstance(block, dict):
            continue
        for name, meta in block.items():
            if not isinstance(meta, dict):
                continue
            hashes = meta.get("hashes") or []
            digest = hashes[0] if hashes else None
            out[str(name).lower().replace("_", "-")] = {
                "version": str(meta.get("version") or "").lstrip("="),
                "hash": digest,
                "url": meta.get("index"),
            }
    return out


def walk_cargo_lock(
    lock_path: Path,
    toml_path: Path | None = None,
    *,
    in_sbom: set[str] | None = None,
    queried: set[str] | None = None,
) -> list[dict[str, Any]]:
    try:
        data = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError, UnicodeDecodeError):
        return []
    declared: dict[str, str] = {}
    if toml_path and toml_path.is_file():
        try:
            cargo = tomllib.loads(toml_path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError, UnicodeDecodeError):
            cargo = {}
        for field in ("dependencies", "dev-dependencies", "build-dependencies"):
            block = cargo.get(field) or {}
            if not isinstance(block, dict):
                continue
            for name, spec in block.items():
                if isinstance(spec, dict):
                    declared[name] = str(spec.get("version") or "*")
                else:
                    declared[name] = str(spec)
    sbom = in_sbom or set()
    did_query = queried or set()
    origin = rel(lock_path)
    rows: list[dict[str, Any]] = []
    for pkg in data.get("package") or []:
        if not isinstance(pkg, dict):
            continue
        name = str(pkg.get("name") or "")
        if not name:
            continue
        version = str(pkg.get("version") or "")
        checksum = pkg.get("checksum")
        checksum_s = str(checksum) if checksum else None
        source = pkg.get("source")
        source_s = str(source) if source else None
        spec = declared.get(name) or version
        direct = name in declared
        key = f"cargo:{name}@{version}"
        gaps = classify_dep(
            spec=spec,
            ecosystem="cargo",
            integrity=checksum_s,
            resolved=source_s,
            license_record=None,
            in_sbom=key in sbom or name in sbom,
            advisory_queried=key in did_query or name in did_query,
            locked=True,
        )
        rows.append(
            {
                "name": name,
                "version": version,
                "ecosystem": "cargo",
                "spec": spec,
                "depth": 1 if direct else 2,
                "direct": direct,
                "integrity": checksum_s,
                "resolved": source_s,
                "license": None,
                "origin": origin,
                "gaps": gaps,
            }
        )
    return rows


def _skip_dir(path: Path) -> bool:
    parts = set(path.parts)
    if parts & SKIP_DIR_NAMES:
        return True
    if "p2-wave" in parts:
        return True
    if "fixture" in parts or "fixtures" in parts:
        return True
    return False


def iter_shipped_manifests() -> list[Path]:
    found: list[Path] = []
    root_pkg = REPO / "package.json"
    if root_pkg.is_file():
        found.append(root_pkg)
    for root_rel in SHIPPED_ROOTS:
        root = REPO / root_rel
        if root.is_file():
            continue
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            base = Path(dirpath)
            dirnames[:] = [
                d
                for d in dirnames
                if d not in SKIP_DIR_NAMES and d not in {"fixture", "fixtures"}
            ]
            if _skip_dir(base):
                dirnames[:] = []
                continue
            for name in filenames:
                if name in {
                    "package.json",
                    "pyproject.toml",
                    "Cargo.lock",
                    "requirements.txt",
                } or (
                    name.startswith("requirements") and name.endswith(".txt")
                ):
                    found.append(base / name)
    # de-dupe preserve order
    seen: set[str] = set()
    out: list[Path] = []
    for p in found:
        key = p.resolve().as_posix()
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def walk_requirements(
    path: Path,
    *,
    in_sbom: set[str] | None = None,
    queried: set[str] | None = None,
) -> list[dict[str, Any]]:
    sbom = in_sbom or set()
    did_query = queried or set()
    origin = rel(path)
    rows: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    for line in text.splitlines():
        parsed = _parse_req_line(line)
        if not parsed:
            continue
        name, spec = parsed
        key = f"pypi:{name}"
        gaps = classify_dep(
            spec=spec,
            ecosystem="pypi",
            integrity=None,
            resolved=None,
            license_record=None,
            in_sbom=name in sbom or key in sbom,
            advisory_queried=name in did_query,
            locked=False,
        )
        rows.append(
            {
                "name": name,
                "version": spec,
                "ecosystem": "pypi",
                "spec": spec,
                "kind": "requirements",
                "depth": 1,
                "direct": True,
                "integrity": None,
                "resolved": None,
                "license": None,
                "origin": origin,
                "gaps": gaps,
            }
        )
    return rows
