"""SBOM completeness: artifact-derived closure versus a declared-manifest SBOM.

Closure is computed by unpacking the shipped wheel and reading dist-info METADATA
plus runtime import statements. The lockfile that the SBOM generator consumed is
never opened on that path (circular-derivation would hide an unregenerated plant).
"""
from __future__ import annotations

import ast
import io
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

APP = ("cnf0109-plugin", "1.0.0")
DIRECT = ("declared-direct", "1.2.0")
TRANSITIVE = ("declared-transitive", "3.4.5")
PLANTED = ("planted-unregen", "0.0.1")
PHANTOM = ("phantom-listed", "9.9.9")

IMPORT_TO_DIST = {
    "cnf0109_plugin": APP[0],
    "declared_direct": DIRECT[0],
    "declared_transitive": TRANSITIVE[0],
    "planted_unregen": PLANTED[0],
}

META_NAME = re.compile(r"^Name:\s*(.+)\s*$", re.M)
META_VERSION = re.compile(r"^Version:\s*(.+)\s*$", re.M)
META_REQ = re.compile(r"^Requires-Dist:\s*([^;]+)", re.M)
REQ_NAME = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)")


def normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name.strip().lower())


def key(name: str, version: str) -> tuple[str, str]:
    return normalize(name), str(version).strip()


def as_comp(pair: tuple[str, str]) -> dict:
    return {"name": pair[0], "version": pair[1], "purl": f"pkg:pypi/{pair[0]}@{pair[1]}"}


def dist_import(name: str) -> str:
    return normalize(name).replace("-", "_")


def metadata_blob(name: str, version: str, requires: Iterable[str] = ()) -> str:
    lines = [
        "Metadata-Version: 2.1",
        f"Name: {name}",
        f"Version: {version}",
        "Summary: CNF-0109 fixture component",
    ]
    for req in requires:
        lines.append(f"Requires-Dist: {req}")
    return "\n".join(lines) + "\n"


def _add_dist(zf: zipfile.ZipFile, name: str, version: str, body: str, requires: Iterable[str] = ()) -> None:
    dist = f"{dist_import(name)}-{version}.dist-info"
    pkg = dist_import(name)
    init = f"{pkg}/__init__.py"
    meta = f"{dist}/METADATA"
    rec = f"{dist}/RECORD"
    zf.writestr(init, body)
    zf.writestr(meta, metadata_blob(name, version, requires))
    zf.writestr(rec, f"{init},,\n{meta},,\n{rec},,\n")


def write_wheel(path: Path, *, include_planted: bool) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        _add_dist(
            zf,
            APP[0],
            APP[1],
            "from declared_direct import ping\n\ndef run():\n    return ping()\n",
            requires=[f"{DIRECT[0]}=={DIRECT[1]}"],
        )
        _add_dist(
            zf,
            DIRECT[0],
            DIRECT[1],
            "from declared_transitive import helper\n\ndef ping():\n    return helper()\n",
            requires=[f"{TRANSITIVE[0]}=={TRANSITIVE[1]}"],
        )
        _add_dist(
            zf,
            TRANSITIVE[0],
            TRANSITIVE[1],
            "def helper():\n    return 'transitive-live'\n",
        )
        if include_planted:
            _add_dist(
                zf,
                PLANTED[0],
                PLANTED[1],
                "def marker():\n    return 'planted-without-sbom-regen'\n",
            )
    path.write_bytes(buf.getvalue())
    return path


def plant_into_wheel(path: Path) -> None:
    with zipfile.ZipFile(path, "a", compression=zipfile.ZIP_DEFLATED) as zf:
        names = set(zf.namelist())
        planted_meta = f"{dist_import(PLANTED[0])}-{PLANTED[1]}.dist-info/METADATA"
        if planted_meta in names:
            return
        _add_dist(
            zf,
            PLANTED[0],
            PLANTED[1],
            "def marker():\n    return 'planted-without-sbom-regen'\n",
        )


def write_lockfile(path: Path) -> Path:
    """Declared dependency manifest the SBOM generator is allowed to read."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"{APP[0]}=={APP[1]}",
        f"{DIRECT[0]}=={DIRECT[1]}",
        f"{TRANSITIVE[0]}=={TRANSITIVE[1]}",
        f"{PHANTOM[0]}=={PHANTOM[1]}",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def parse_lockfile(path: Path) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "==" not in line:
            raise ValueError(f"lockfile line is not name==version: {line!r}")
        name, version = line.split("==", 1)
        out.add(key(name, version))
    return out


def generate_sbom_from_lockfile(lock: Path, dest: Path) -> Path:
    """SBOM generator: lockfile only. Never opens the wheel."""
    comps = []
    for name, version in sorted(parse_lockfile(lock)):
        comps.append(
            {
                "type": "library",
                "name": name,
                "version": version,
                "purl": f"pkg:pypi/{name}@{version}",
            }
        )
    doc = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": "urn:uuid:cnf-0109-unregenerated-control",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": APP[0],
                "version": APP[1],
            }
        },
        "components": comps,
    }
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return dest


def parse_sbom(path: Path) -> set[tuple[str, str]]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    out: set[tuple[str, str]] = set()
    for comp in doc.get("components") or []:
        if not isinstance(comp, dict):
            continue
        name = comp.get("name")
        version = comp.get("version")
        if name and version:
            out.add(key(str(name), str(version)))
    return out


def _parse_metadata(text: str) -> tuple[str, str, list[str]]:
    nm = META_NAME.search(text)
    ver = META_VERSION.search(text)
    if not nm or not ver:
        raise ValueError("METADATA missing Name or Version")
    reqs = []
    for m in META_REQ.finditer(text):
        token = m.group(1).strip()
        rm = REQ_NAME.match(token)
        if rm:
            reqs.append(normalize(rm.group(1)))
    return normalize(nm.group(1)), ver.group(1).strip(), reqs


def _imported_names(source: str) -> set[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


@dataclass(frozen=True)
class Closure:
    components: set[tuple[str, str]]
    metadata_names: set[str]
    imported_dists: set[str]
    intra_artifact_requires: list[tuple[str, str]]
    method: str


def closure_from_wheel(path: Path) -> Closure:
    """Inspect the built artifact. Does not take a lockfile path on purpose."""
    comps: dict[str, str] = {}
    requires: list[tuple[str, str]] = []
    imported: set[str] = set()
    with zipfile.ZipFile(path) as zf:
        for info in zf.infolist():
            name = info.filename.replace("\\", "/")
            if name.endswith(".dist-info/METADATA"):
                text = zf.read(info).decode("utf-8")
                dist, version, reqs = _parse_metadata(text)
                comps[dist] = version
                for req in reqs:
                    requires.append((dist, req))
            if name.endswith(".py") and not info.is_dir():
                src = zf.read(info).decode("utf-8")
                for mod in _imported_names(src):
                    dist = IMPORT_TO_DIST.get(mod)
                    if dist:
                        imported.add(dist)
    if not comps:
        raise ValueError(f"no dist-info METADATA in {path}")
    present = set(comps)
    intra = [(src, dst) for src, dst in requires if dst in present]
    return Closure(
        components={(n, comps[n]) for n in comps},
        metadata_names=present,
        imported_dists=imported,
        intra_artifact_requires=intra,
        method=(
            "Unpacked the wheel zip; parsed Name/Version from each "
            "*.dist-info/METADATA; recorded Requires-Dist edges that resolve to "
            "another dist present in the same zip; parsed import/from-import "
            "names in bundled .py files and mapped them to those dists. The "
            "declared lockfile used to generate the SBOM was not opened."
        ),
    )


@dataclass(frozen=True)
class Diff:
    ships_but_absent: list[dict]
    listed_but_does_not_ship: list[dict]
    in_both: list[dict]
    artifact_only: set[tuple[str, str]]
    sbom_only: set[tuple[str, str]]
    both: set[tuple[str, str]]


def diff_sets(artifact: set[tuple[str, str]], sbom: set[tuple[str, str]]) -> Diff:
    only_art = artifact - sbom
    only_sbom = sbom - artifact
    both = artifact & sbom
    return Diff(
        ships_but_absent=[as_comp(p) for p in sorted(only_art)],
        listed_but_does_not_ship=[as_comp(p) for p in sorted(only_sbom)],
        in_both=[as_comp(p) for p in sorted(both)],
        artifact_only=only_art,
        sbom_only=only_sbom,
        both=both,
    )


def estate_scan(repo: Path) -> dict:
    """Honest census of this worktree: generated SBOMs and built distributables."""
    import os

    skip_dirs = {
        ".git",
        "__pycache__",
        "p2-wave",
        "confirmation",
        "node_modules",
        ".venv",
        "venv",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        "site-packages",
        ".agents",
    }
    sbom_hits: list[str] = []
    wheel_hits: list[str] = []
    root = str(repo)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for fname in filenames:
            low = fname.lower()
            rel = Path(dirpath, fname).relative_to(repo).as_posix()
            if low.endswith((".whl", ".egg")):
                wheel_hits.append(rel)
            if low.endswith(".schema.json"):
                continue
            if low.endswith((".cdx.json", ".spdx.json", ".spdx")) or low in {
                "bom.json",
                "cyclonedx.json",
                "sbom.json",
            }:
                sbom_hits.append(rel)
            elif low.endswith(".json") and low.startswith("sbom"):
                sbom_hits.append(rel)
    return {
        "worktree_generated_sbom_paths": sorted(sbom_hits),
        "worktree_wheel_paths": sorted(wheel_hits),
        "has_project_generated_sbom": bool(sbom_hits),
        "has_project_built_wheel": bool(wheel_hits),
        "note": (
            "This Linux worktree is sparse (command-center + tools). Absence of a "
            "project SBOM is recorded; it is not treated as a zero-difference pass. "
            "The confirmation procedure runs against a constructed shipped wheel "
            "and a lockfile-derived CycloneDX SBOM so the required control can fire."
        ),
    }
