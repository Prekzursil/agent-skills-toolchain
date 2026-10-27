"""Build a CycloneDX 1.5 SBOM from lockfiles + vendored trees."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent


def _pkg(name: str, version: str, *, source: str, purl_kind: str = "pypi") -> dict[str, Any]:
    return {
        "type": "library",
        "name": name,
        "version": version,
        "bom-ref": f"{source}:{name}@{version}",
        "purl": f"pkg:{purl_kind}/{name}@{version}",
        "properties": [{"name": "source", "value": source}],
    }


def _from_package_lock(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    out: list[dict[str, Any]] = []
    packages = data.get("packages")
    if isinstance(packages, dict):
        for rel, meta in packages.items():
            if not rel or rel == "":
                continue
            if not isinstance(meta, dict):
                continue
            name = str(meta.get("name") or rel.rsplit("node_modules/", 1)[-1])
            ver = str(meta.get("version") or "")
            if name and ver:
                out.append(_pkg(name, ver, source="lockfile", purl_kind="npm"))
        return out
    deps = data.get("dependencies")
    if isinstance(deps, dict):
        def walk(tree: dict, acc: list[dict[str, Any]]) -> None:
            for name, meta in tree.items():
                if not isinstance(meta, dict):
                    continue
                ver = str(meta.get("version") or "")
                if ver:
                    acc.append(_pkg(str(name), ver, source="lockfile", purl_kind="npm"))
                nested = meta.get("dependencies")
                if isinstance(nested, dict):
                    walk(nested, acc)
        walk(deps, out)
    return out


def _from_requirements_lock(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "==" in line:
            name, ver = line.split("==", 1)
            out.append(_pkg(name.strip(), ver.strip().split(";")[0].strip(), source="lockfile"))
    return out


def _from_poetry_lock(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    name = ""
    version = ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line == "[[package]]":
            if name and version:
                out.append(_pkg(name, version, source="lockfile"))
            name, version = "", ""
            continue
        if line.startswith("name ="):
            name = line.split("=", 1)[1].strip().strip('"').strip("'")
        elif line.startswith("version ="):
            version = line.split("=", 1)[1].strip().strip('"').strip("'")
    if name and version:
        out.append(_pkg(name, version, source="lockfile"))
    return out


def _from_vendor(root: Path) -> list[dict[str, Any]]:
    vendor = root / "vendor"
    if not vendor.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for child in sorted(vendor.iterdir()):
        if child.is_dir():
            ver = "unpinned"
            meta = child / "METADATA"
            if meta.is_file():
                for line in meta.read_text(encoding="utf-8").splitlines():
                    if line.lower().startswith("version:"):
                        parsed = line.split(":", 1)[1].strip()
                        if parsed:
                            ver = parsed
            out.append(_pkg(child.name, ver, source="vendored"))
    return out


def build_bom(fixture: Path, timestamp: str = "2026-08-24T18:00:00Z") -> dict[str, Any]:
    root = Path(fixture)
    components: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in (
        *_from_package_lock(root / "package-lock.json"),
        *_from_requirements_lock(root / "requirements.lock"),
        *_from_poetry_lock(root / "poetry.lock"),
        *_from_vendor(root),
    ):
        key = (row["name"], row["version"], row["properties"][0]["value"])
        if key in seen:
            continue
        seen.add(key)
        components.append(row)
    if not components:
        components.append(_pkg("plugin-closure-placeholder", "0.0.0", source="lockfile"))
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "serialNumber": "urn:uuid:00000000-0000-4000-8000-000000000062",
        "metadata": {
            "timestamp": timestamp,
            "component": {"type": "application", "name": "plugin-closure", "version": "1.0.0"},
        },
        "components": components,
    }


def identities_from_bom(bom: dict[str, Any], source: str | None = None) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for row in bom.get("components") or []:
        if not isinstance(row, dict):
            continue
        props = {p.get("name"): p.get("value") for p in (row.get("properties") or []) if isinstance(p, dict)}
        if source and props.get("source") != source:
            continue
        name = str(row.get("name") or "")
        ver = str(row.get("version") or "")
        if name:
            out.add((name, ver))
    return out


def write_bom(bom: dict[str, Any], dest: Path) -> Path:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(bom, indent=2) + "\n", encoding="utf-8")
    return dest
