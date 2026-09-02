"""SBOM-versus-artifact set difference in both directions.

Signal is tar-member paths vs CycloneDX cnf0179:path properties.
listed_but_absent = SBOM paths with no matching tar member.
present_but_unlisted = tar members with no matching SBOM path (supply-chain risk).
"""
from __future__ import annotations

import copy
import gzip
import io
import json
import tarfile
from pathlib import Path

from bundle import PATH_PROP, PHANTOM_PURL, PKG, VENDOR_HELPER_PURL

REGULAR = tarfile.REGTYPE


def tar_member_paths(artifact: Path) -> list[str]:
    raw = gzip.decompress(artifact.read_bytes())
    paths: list[str] = []
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as tf:
        for info in tf.getmembers():
            if info.type != REGULAR and not info.isreg():
                continue
            name = info.name.replace("\\", "/").lstrip("./")
            if name:
                paths.append(name)
    return sorted(set(paths))


def sbom_path_map(sbom: dict) -> dict[str, str]:
    """path -> purl"""
    out: dict[str, str] = {}
    for comp in sbom.get("components") or []:
        if not isinstance(comp, dict):
            continue
        purl = str(comp.get("purl") or "")
        path = ""
        for prop in comp.get("properties") or []:
            if isinstance(prop, dict) and prop.get("name") == PATH_PROP:
                path = str(prop.get("value") or "").replace("\\", "/").lstrip("./")
                break
        if path:
            out[path] = purl
    return out


def load_sbom(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def differ(artifact: Path, sbom: dict) -> dict:
    present = set(tar_member_paths(artifact))
    listed = sbom_path_map(sbom)
    listed_paths = set(listed)
    listed_but_absent = sorted(
        listed[p] or p for p in (listed_paths - present)
    )
    present_but_unlisted = sorted(present - listed_paths)
    return {
        "tar_members": sorted(present),
        "sbom_paths": sorted(listed_paths),
        "listed_but_absent": listed_but_absent,
        "present_but_unlisted": present_but_unlisted,
        "healthy": not listed_but_absent and not present_but_unlisted,
    }


def remove_component(sbom: dict, purl: str) -> dict:
    mutant = copy.deepcopy(sbom)
    comps = [
        c
        for c in (mutant.get("components") or [])
        if not (isinstance(c, dict) and c.get("purl") == purl)
    ]
    mutant["components"] = comps
    return mutant


def add_phantom(sbom: dict, purl: str = PHANTOM_PURL) -> dict:
    mutant = copy.deepcopy(sbom)
    comps = list(mutant.get("components") or [])
    comps.append(
        {
            "type": "library",
            "name": "ghost-lib",
            "version": "0.0.1",
            "purl": purl,
            "properties": [
                {"name": PATH_PROP, "value": f"{PKG}/lib/ghost-lib.so"}
            ],
        }
    )
    mutant["components"] = comps
    return mutant


def vendor_helper_arcname() -> str:
    return f"{PKG}/vendor/helper.py"


__all__ = [
    "PHANTOM_PURL",
    "VENDOR_HELPER_PURL",
    "add_phantom",
    "differ",
    "load_sbom",
    "remove_component",
    "tar_member_paths",
    "vendor_helper_arcname",
]
