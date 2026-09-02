"""Live license inventory for this worktree's dependency closure.

AUD-0022's transitive graph is consumed when present. When it is absent this
detector walks first-party tools packages, AST imports, and Requires-Dist.
That is a mechanically different detector, not a reuse of a missing graph.
"""
from __future__ import annotations

import ast
import hashlib
import importlib.metadata as im
import json
import sys
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import classify as C  # noqa: E402

UNIT = "AUD-0024"
AUD0022 = REPO / "command-center/audit/AUD-0022-transitive-dep-graph.json"
OUT_REL = "command-center/audit/AUD-0024-license-inventory.json"
SCHEMA_REL = "command-center/schema/audit-inventory.schema.json"
SKIP_DIRS = frozenset(
    {
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "dist",
        "build",
    }
)
STDLIB = set(getattr(sys, "stdlib_module_names", ())) | set(sys.builtin_module_names)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def intended_distribution_license() -> dict[str, Any]:
    """Plugin outbound license as declared on this worktree. Absence is reported."""
    roots = [
        REPO,
        REPO / "tools" / "plugin",
        REPO / ".claude-plugin",
    ]
    files: list[dict[str, Any]] = []
    for root in roots:
        if not root.is_dir():
            continue
        for name in ("LICENSE", "LICENSE.txt", "LICENSE.md", "COPYING", "UNLICENSE"):
            p = root / name
            if p.is_file():
                blob = C.read_text(p)
                cls = C.classify_license_blob(blob)
                files.append(
                    {
                        "path": p.relative_to(REPO).as_posix(),
                        "spdx": cls["spdx"],
                        "bytes": p.stat().st_size,
                    }
                )
        for meta_name in ("plugin.json", "package.json"):
            p = root / meta_name
            if not p.is_file():
                continue
            doc = load_json(p)
            if isinstance(doc, dict) and doc.get("license"):
                declared = C.declared_to_spdx(
                    doc["license"] if isinstance(doc["license"], str) else str(doc["license"])
                )
                files.append(
                    {
                        "path": p.relative_to(REPO).as_posix(),
                        "spdx": declared["spdx"],
                        "raw": declared["raw"],
                        "source": "metadata",
                    }
                )
    if files:
        spdx_ids = {f.get("spdx") for f in files}
        if len(spdx_ids) == 1:
            only = next(iter(spdx_ids))
            return {
                "spdx": only,
                "raw_sources": files,
                "status": "DECLARED" if only not in {C.UNKNOWN, C.AMBIGUOUS} else C.UNRESOLVED,
            }
        return {
            "spdx": C.AMBIGUOUS,
            "raw_sources": files,
            "status": C.AMBIGUOUS,
        }
    return {
        "spdx": C.LICENSE_ABSENT,
        "raw_sources": [],
        "status": C.LICENSE_ABSENT,
        "note": "No LICENSE file and no plugin.json/package.json license field at plugin roots on this worktree.",
    }


def aud0022_packages() -> tuple[bool, list[dict[str, Any]], str]:
    if not AUD0022.is_file() or AUD0022.stat().st_size <= 0:
        return False, [], "ABSENT"
    doc = load_json(AUD0022)
    if not isinstance(doc, dict):
        return False, [], "UNPARSEABLE"
    names: list[dict[str, Any]] = []
    for key in ("packages", "nodes", "closure", "dependencies"):
        rows = doc.get(key)
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, str) and row.strip():
                    names.append({"name": row.strip(), "source": "aud-0022"})
                elif isinstance(row, dict):
                    n = row.get("name") or row.get("package") or row.get("id")
                    if isinstance(n, str) and n.strip():
                        names.append(
                            {
                                "name": n.strip(),
                                "version": row.get("version"),
                                "source": "aud-0022",
                            }
                        )
    return True, names, "PRESENT"


def first_party_packages() -> list[dict[str, Any]]:
    tools = REPO / "tools"
    out: list[dict[str, Any]] = []
    if not tools.is_dir():
        return out
    for child in sorted(tools.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        py = list(child.glob("*.py")) + list(child.glob("*/__init__.py"))
        if not py:
            continue
        out.append(
            {
                "name": child.name,
                "version": None,
                "ecosystem": "python-first-party",
                "path": child.relative_to(REPO).as_posix(),
                "source": "first-party-tools",
                "root": child,
            }
        )
    out.append(
        {
            "name": "ast-integrate-plugin",
            "version": None,
            "ecosystem": "plugin",
            "path": "tools/plugin",
            "source": "plugin-root",
            "root": REPO / "tools" / "plugin",
        }
    )
    return out


def _iter_py(root: Path) -> Iterable[Path]:
    for path in root.rglob("*.py"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        yield path


def imported_top_levels(root: Path) -> set[str]:
    names: set[str] = set()
    for path in _iter_py(root):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = (alias.name or "").split(".")[0]
                    if top:
                        names.add(top)
            elif isinstance(node, ast.ImportFrom):
                if node.level and not node.module:
                    continue
                if node.module:
                    top = node.module.split(".")[0]
                    if top:
                        names.add(top)
    first_party = {p.name for p in (REPO / "tools").iterdir() if p.is_dir()} if (REPO / "tools").is_dir() else set()
    names -= STDLIB
    names -= first_party
    names -= {"__future__"}
    return names


def _dist_for_module(mod: str, index: dict[str, list[str]]) -> str | None:
    hits = index.get(mod)
    if hits:
        return sorted(hits)[0]
    return None


def requires_dist_names(dist: im.Distribution) -> list[str]:
    reqs = dist.metadata.get_all("Requires-Dist") or []
    names: list[str] = []
    for raw in reqs:
        text = str(raw)
        if "extra ==" in text.replace("extra==", "extra =="):
            continue
        name = text.split(";", 1)[0].strip()
        for sep in ("[", " ", "<", ">", "=", "~", "!"):
            if sep in name:
                name = name.split(sep, 1)[0].strip()
        if name:
            names.append(name)
    return names


def installed_record(name: str, *, source: str) -> dict[str, Any] | None:
    try:
        dist = im.distribution(name)
    except im.PackageNotFoundError:
        return {
            "name": name,
            "version": None,
            "ecosystem": "python",
            "source": source,
            "installed": False,
            "root": None,
            "declared_raw": None,
            "classifiers": [],
            "dist_info": None,
        }
    meta = dist.metadata
    classifiers = [c for c in (meta.get_all("Classifier") or []) if isinstance(c, str)]
    license_expr = meta.get("License-Expression")
    license_field = meta.get("License")
    info = getattr(dist, "_path", None)
    return {
        "name": meta.get("Name") or name,
        "version": dist.version,
        "ecosystem": "python",
        "source": source,
        "installed": True,
        "root": Path(str(info)) if info else None,
        "declared_raw": license_expr or license_field,
        "license_expression": license_expr,
        "license_field": license_field,
        "classifiers": classifiers,
        "requires": requires_dist_names(dist),
        "dist_info": Path(str(info)) if info else None,
    }


def expand_installed(seed_names: Iterable[str], *, source: str) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    queue = [s for s in seed_names]
    while queue:
        raw = queue.pop(0)
        key = raw.replace("_", "-").lower()
        if key in seen:
            continue
        seen.add(key)
        rec = installed_record(raw, source=source)
        if rec is None:
            continue
        out.append(rec)
        if rec.get("installed") and rec.get("requires"):
            for dep in rec["requires"]:
                dk = dep.replace("_", "-").lower()
                if dk not in seen:
                    queue.append(dep)
                    rec.setdefault("source", source)
    return out


def declared_from_record(rec: dict[str, Any]) -> dict[str, Any]:
    if rec.get("declared_raw"):
        got = C.declared_to_spdx(rec["declared_raw"])
        got["source"] = "metadata-license-field"
        return got
    clf = C.classifier_to_spdx(rec.get("classifiers") or [])
    if clf:
        return clf
    root = rec.get("root")
    if isinstance(root, Path):
        for meta_name in ("package.json", "pyproject.toml", "Cargo.toml"):
            p = root / meta_name if root.is_dir() else None
            if p and p.is_file():
                if meta_name == "package.json":
                    doc = load_json(p)
                    if isinstance(doc, dict) and doc.get("license"):
                        lic = doc["license"]
                        raw = lic if isinstance(lic, str) else json.dumps(lic)
                        got = C.declared_to_spdx(raw)
                        got["source"] = "package.json"
                        return got
                text = C.read_text(p)
                m = __import__("re").search(
                    r"(?im)^license\s*=\s*(?:\{[^}]*text\s*=\s*)?[\"']([^\"']+)[\"']",
                    text,
                )
                if m:
                    got = C.declared_to_spdx(m.group(1))
                    got["source"] = meta_name
                    return got
    return {
        "raw": None,
        "spdx": C.LICENSE_ABSENT,
        "code": C.LICENSE_ABSENT,
        "ambiguous": False,
        "source": "none",
    }


def actual_from_record(rec: dict[str, Any]) -> dict[str, Any]:
    roots: list[Path] = []
    root = rec.get("root")
    if isinstance(root, Path) and root.is_dir():
        roots.append(root)
        # dist-info only: do not walk all of dist-packages
        if root.name.endswith(".dist-info") or root.name.endswith(".egg-info"):
            pass
        else:
            pass
    files: list[Path] = []
    for r in roots:
        try:
            for p in r.iterdir():
                if p.is_file() and C.is_license_filename(p.name):
                    files.append(p)
                elif p.is_dir() and p.name.lower() in {"licenses", "license"}:
                    for q in p.rglob("*"):
                        if q.is_file() and C.is_license_filename(q.name):
                            files.append(q)
        except OSError:
            continue
    files.sort(key=lambda p: (len(p.parts), p.as_posix().lower()))
    if not files:
        return {
            "spdx": C.ABSENT,
            "code": C.ABSENT,
            "method": "license-file",
            "path": None,
            "present": False,
        }
    path = files[0]
    blob = C.read_text(path)
    cls = C.classify_license_blob(blob)
    try:
        rel = path.relative_to(REPO).as_posix()
    except ValueError:
        rel = str(path)
    return {
        **cls,
        "path": rel,
        "present": True,
        "sha256": sha256_text(blob),
        "bytes": min(len(blob.encode("utf-8")), 256_000),
    }


def package_row(rec: dict[str, Any], intended: dict[str, Any]) -> dict[str, Any]:
    declared = declared_from_record(rec)
    actual = actual_from_record(rec)
    resolved = C.resolve_declared_versus_actual(
        declared.get("spdx"),
        actual.get("spdx"),
        license_file_present=bool(actual.get("present")),
    )
    market = C.marketplace_flag(
        intended_spdx=str(intended.get("spdx") or C.LICENSE_ABSENT),
        resolved_spdx=str(resolved["resolved_spdx"]),
        conflict=bool(resolved["conflict"]),
    )
    root = rec.get("root")
    path = rec.get("path")
    if not path and isinstance(root, Path):
        try:
            path = root.relative_to(REPO).as_posix()
        except ValueError:
            path = str(root)
    return {
        "name": rec["name"],
        "version": rec.get("version"),
        "ecosystem": rec.get("ecosystem") or "python",
        "source": rec.get("source"),
        "installed": rec.get("installed"),
        "path": path,
        "declared_raw": declared.get("raw"),
        "declared_spdx": declared.get("spdx") or C.LICENSE_ABSENT,
        "declared_code": declared.get("code"),
        "declared_source": declared.get("source"),
        "actual_spdx": actual.get("spdx") or C.ABSENT,
        "actual_code": actual.get("code"),
        "actual_path": actual.get("path"),
        "actual_present": bool(actual.get("present")),
        "resolved_spdx": resolved["resolved_spdx"],
        "conflict": bool(resolved["conflict"]),
        "unresolved": bool(resolved["unresolved"]),
        "ambiguous": bool(resolved["ambiguous"]),
        "resolve_reason": resolved["reason"],
        "marketplace": market,
        "legal_advice": False,
    }


def build_inventory() -> dict[str, Any]:
    intended = intended_distribution_license()
    aud_ok, aud_rows, aud_status = aud0022_packages()
    first = first_party_packages()
    import_index = im.packages_distributions()
    imported_mods = imported_top_levels(REPO / "tools") if (REPO / "tools").is_dir() else set()
    imported_dists = []
    unresolved_imports = []
    for mod in sorted(imported_mods):
        dist = _dist_for_module(mod, import_index)
        if dist:
            imported_dists.append(dist)
        else:
            unresolved_imports.append(mod)
    installed = expand_installed(imported_dists, source="import-graph+requires-dist")
    aud_installed = []
    if aud_ok:
        aud_installed = expand_installed(
            [r["name"] for r in aud_rows],
            source="aud-0022",
        )

    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def add(rec: dict[str, Any]) -> None:
        key = (str(rec.get("name")).lower(), str(rec.get("source")))
        # de-dupe by name across sources, prefer installed metadata
        name_key = str(rec.get("name")).lower()
        if any(str(r["name"]).lower() == name_key for r in rows):
            return
        seen.add(key)
        rows.append(package_row(rec, intended))

    for rec in first:
        add(rec)
    for rec in installed:
        add(rec)
    for rec in aud_installed:
        add(rec)

    rows.sort(key=lambda r: (str(r.get("source") or ""), str(r["name"]).lower()))
    conflicts = [r for r in rows if r["conflict"]]
    unresolved = [r for r in rows if r["unresolved"] or r["resolved_spdx"] in {C.UNRESOLVED, C.AMBIGUOUS}]
    incompatible = [
        r
        for r in rows
        if r.get("marketplace", {}).get("incompatible_with_public_marketplace")
        and r.get("marketplace", {}).get("verdict") == "INCOMPATIBLE"
    ]
    needs_review = [
        r
        for r in rows
        if r.get("marketplace", {}).get("verdict") == "UNKNOWN-NEEDS-REVIEW"
    ]
    file_absent = [r for r in rows if not r.get("actual_present")]
    return {
        "intended_distribution_license": intended,
        "aud0022": {
            "path": "command-center/audit/AUD-0022-transitive-dep-graph.json",
            "present": aud_ok,
            "status": aud_status,
            "named_packages": len(aud_rows),
        },
        "closure_method": (
            "aud-0022-union-import-graph"
            if aud_ok
            else "import-graph+requires-dist+first-party (AUD-0022 absent; pivoted detector)"
        ),
        "imported_modules": sorted(imported_mods),
        "unresolved_imports": unresolved_imports,
        "packages": rows,
        "counts": {
            "packages": len(rows),
            "first_party": sum(1 for r in rows if r.get("source") in {"first-party-tools", "plugin-root"}),
            "installed_third_party": sum(1 for r in rows if r.get("installed")),
            "conflicts": len(conflicts),
            "unresolved_or_ambiguous": len(unresolved),
            "marketplace_incompatible": len(incompatible),
            "marketplace_needs_review": len(needs_review),
            "license_file_absent": len(file_absent),
        },
        "declared_vs_actual_conflicts": [
            {
                "name": r["name"],
                "declared_spdx": r["declared_spdx"],
                "actual_spdx": r["actual_spdx"],
                "resolved_spdx": r["resolved_spdx"],
            }
            for r in conflicts
        ],
        "unresolved_or_ambiguous": [
            {
                "name": r["name"],
                "resolved_spdx": r["resolved_spdx"],
                "declared_spdx": r["declared_spdx"],
                "actual_spdx": r["actual_spdx"],
            }
            for r in unresolved
        ],
        "marketplace_incompatible": [
            {
                "name": r["name"],
                "resolved_spdx": r["resolved_spdx"],
                "verdict": r["marketplace"]["verdict"],
                "reason": r["marketplace"]["reason"],
            }
            for r in incompatible
        ],
        "legal_advice": False,
        "disclaimer": C.LEGAL_DISCLAIMER,
    }


MIT_BLOB = (
    "Permission is hereby granted, free of charge, to any person obtaining a copy\n"
    'THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\n'
    "without limitation the rights to use, copy, modify, merge, publish, distribute\n"
)

AGPL_BLOB = (
    "GNU Affero General Public License\n"
    "Version 3, 19 November 2007\n"
    "Copyright (C) 2007 Free Software Foundation, Inc.\n"
)


def write_fixture(root: Path, *, declared: str, license_text: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "package.json").write_text(
        json.dumps({"name": "aud0024-fixture", "license": declared}, indent=2) + "\n",
        encoding="utf-8",
    )
    (root / "LICENSE").write_text(license_text, encoding="utf-8")
    return root


def scan_tree(root: Path, *, source: str = "fixture") -> dict[str, Any]:
    rec = {
        "name": "aud0024-fixture",
        "version": "0.0.0",
        "ecosystem": "fixture",
        "source": source,
        "installed": False,
        "root": root,
        "declared_raw": None,
        "classifiers": [],
    }
    pkg = load_json(root / "package.json")
    if isinstance(pkg, dict):
        rec["declared_raw"] = pkg.get("license")
        rec["name"] = pkg.get("name") or rec["name"]
    intended = intended_distribution_license()
    return package_row(rec, intended)


def control_mit_agpl_conflict(tmp: Path) -> dict[str, Any]:
    bad = write_fixture(tmp / "bad", declared="MIT", license_text=AGPL_BLOB)
    good = write_fixture(tmp / "good", declared="MIT", license_text=MIT_BLOB)
    bad_row = scan_tree(bad, source="control-bad")
    good_row = scan_tree(good, source="control-good")
    fired = (
        bad_row["conflict"] is True
        and bad_row["resolved_spdx"] == C.CONFLICT
        and bad_row["declared_spdx"] == "MIT"
        and bad_row["actual_spdx"] == "AGPL-3.0-only"
        and bad_row["resolved_spdx"] not in {"MIT", "AGPL-3.0-only"}
    )
    silent = (
        good_row["conflict"] is False
        and good_row["resolved_spdx"] == "MIT"
        and good_row["declared_spdx"] == "MIT"
        and good_row["actual_spdx"] == "MIT"
    )
    return {
        "fired_on_bad_state": fired,
        "silent_on_good_state": silent,
        "both_states": fired and silent,
        "bad": {
            "declared_spdx": bad_row["declared_spdx"],
            "actual_spdx": bad_row["actual_spdx"],
            "resolved_spdx": bad_row["resolved_spdx"],
            "conflict": bad_row["conflict"],
        },
        "good": {
            "declared_spdx": good_row["declared_spdx"],
            "actual_spdx": good_row["actual_spdx"],
            "resolved_spdx": good_row["resolved_spdx"],
            "conflict": good_row["conflict"],
        },
        "pass": fired and silent,
    }
