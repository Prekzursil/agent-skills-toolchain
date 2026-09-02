"""Per-gap-class census of shipped dependency manifests and lockfiles.

ADV-0058 plants an undeclared transitive for SBOM completeness; AUD-0020
inventories Python packages. This census covers pin, hash, SBOM, license
and advisory-query gaps across npm, PyPI and cargo shipped trees.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from classify import GAP_ORDER
from walk import (
    REPO,
    iter_shipped_manifests,
    nearest_npm_lock,
    rel,
    walk_cargo_lock,
    walk_npm_lock,
    walk_package_json,
    walk_pyproject,
    walk_requirements,
)

LICENSE_INV = REPO / "command-center" / "audit" / "AUD-0024-license-inventory.json"
PY_INV = REPO / "command-center" / "audit" / "AUD-0020-python-dep-inventory.json"


def load_sbom_keys() -> tuple[set[str], list[str]]:
    """Return (keys, sources). No shipped SBOM exists in tools/platform/release."""
    keys: set[str] = set()
    sources: list[str] = []
    candidates = [
        REPO / "sbom.json",
        REPO / "bom.json",
        REPO / "release" / "sbom.json",
        REPO / "platform" / "marketplace" / "sbom.json",
    ]
    for path in candidates:
        if not path.is_file():
            continue
        sources.append(rel(path))
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            continue
        comps = []
        if isinstance(data, dict):
            comps = data.get("components") or (data.get("packages") or [])
        for c in comps:
            if not isinstance(c, dict):
                continue
            name = c.get("name")
            version = c.get("version")
            purl = c.get("purl") or c.get("bom-ref")
            if isinstance(purl, str) and purl:
                keys.add(purl)
            if isinstance(name, str) and name:
                keys.add(name)
                if version:
                    keys.add(f"{name}@{version}")
    return keys, sources


def load_license_index() -> tuple[set[str], str | None]:
    if not LICENSE_INV.is_file():
        return set(), None
    try:
        data = json.loads(LICENSE_INV.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return set(), rel(LICENSE_INV)
    names: set[str] = set()
    for key in ("packages", "entries", "inventory", "rows"):
        block = data.get(key) if isinstance(data, dict) else None
        if not isinstance(block, list):
            continue
        for row in block:
            if isinstance(row, dict):
                n = row.get("name") or row.get("package")
                if isinstance(n, str) and n:
                    names.add(n.lower())
    report = data.get("report") if isinstance(data, dict) else None
    if isinstance(report, dict):
        for row in report.get("packages") or []:
            if isinstance(row, dict) and row.get("name"):
                names.add(str(row["name"]).lower())
    return names, rel(LICENSE_INV)


def _compact_row(row: dict[str, Any]) -> dict[str, Any]:
    keep = (
        "name",
        "version",
        "ecosystem",
        "spec",
        "kind",
        "depth",
        "direct",
        "origin",
        "gaps",
        "integrity",
        "resolved",
        "license",
    )
    out = {k: row[k] for k in keep if k in row and row[k] is not None}
    if not out.get("gaps"):
        out["gaps"] = []
    return out


def build_census(
    *,
    queried: set[str] | None = None,
) -> dict[str, Any]:
    sbom_keys, sbom_sources = load_sbom_keys()
    license_names, license_src = load_license_index()
    queried = queried or set()
    rows: list[dict[str, Any]] = []
    manifests: list[str] = []
    seen_origin_name: set[tuple[str, str, str]] = set()
    walked_locks: set[str] = set()

    for path in iter_shipped_manifests():
        manifests.append(rel(path))
        chunk: list[dict[str, Any]] = []
        if path.name == "package.json":
            lock = nearest_npm_lock(path)
            if lock is not None:
                lk = str(lock.resolve())
                if lk in walked_locks:
                    continue
                walked_locks.add(lk)
                chunk = walk_npm_lock(
                    lock, in_sbom=sbom_keys, queried=queried
                )
            else:
                chunk = walk_package_json(
                    path,
                    lock_path=None,
                    in_sbom=sbom_keys,
                    queried=queried,
                )
        elif path.name == "pyproject.toml":
            chunk = walk_pyproject(path, in_sbom=sbom_keys, queried=queried)
        elif path.name == "Cargo.lock":
            toml = path.parent / "Cargo.toml"
            chunk = walk_cargo_lock(
                path,
                toml if toml.is_file() else None,
                in_sbom=sbom_keys,
                queried=queried,
            )
        elif path.name.startswith("requirements"):
            chunk = walk_requirements(path, in_sbom=sbom_keys, queried=queried)
        for row in chunk:
            if license_names and str(row.get("name") or "").lower() in license_names:
                gaps = [g for g in row.get("gaps") or [] if g != "NO-LICENSE-RECORD"]
                row = dict(row)
                row["gaps"] = gaps
                row["license"] = row.get("license") or "AUD-0024"
            ident = (
                str(row.get("origin") or ""),
                str(row.get("ecosystem") or ""),
                f"{row.get('name')}@{row.get('version')}",
            )
            if ident in seen_origin_name:
                continue
            seen_origin_name.add(ident)
            rows.append(_compact_row(row))

    counts = Counter()
    for row in rows:
        for g in row.get("gaps") or []:
            counts[g] += 1
    by_class = {g: int(counts.get(g, 0)) for g in GAP_ORDER}
    with_any = sum(1 for r in rows if r.get("gaps"))
    clean = sum(1 for r in rows if not r.get("gaps"))
    citations = {
        "ADV-0058": "command-center/adversarial/ADV-0058-sbom-completeness-planted-transitive.json",
        "AUD-0020": rel(PY_INV) if PY_INV.is_file() else "ABSENT",
        "AUD-0024": license_src or "ABSENT",
    }
    return {
        "dependency_count": len(rows),
        "manifest_count": len(manifests),
        "manifests": manifests,
        "gap_class_counts": by_class,
        "with_any_gap": with_any,
        "with_no_gap": clean,
        "sbom_sources": sbom_sources,
        "sbom_entry_count": len(sbom_keys),
        "license_inventory": license_src,
        "scope_boundary": {
            "ADV-0058": (
                "plants an undeclared transitive to test SBOM completeness; "
                "this unit does not rebuild that plant"
            ),
            "AUD-0020": (
                "inventories Python dependencies; this unit adds pin/hash/"
                "SBOM/license/advisory classes across ALL shipped ecosystems"
            ),
        },
        "citations": citations,
        "dependencies": rows,
    }
