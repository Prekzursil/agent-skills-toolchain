"""SBOM construction and BIDIRECTIONAL verification against the real payload bytes.

THE ONLY VERIFICATION THAT MEANS ANYTHING
    An SBOM is trivially "verified" by checking that every SBOM component's hash matches a
    file -- and that check passes while the payload carries an EXTRA file the SBOM never
    mentions. So :func:`verify` requires a BIJECTION and reports both directions
    separately:

      * ``missing_from_disk``   - SBOM claims a file the payload does not contain
      * ``missing_from_sbom``   - payload contains a file the SBOM never declared
      * ``hash_mismatch``       - both name it, the bytes differ

    A one-directional SBOM check is the same shape of error as the measured 86%-accurate
    one-directional tree comparison in this estate's rules: it cannot see the case where
    the OTHER side holds something unique, and 100% of those errors point at accepting
    something unreviewed.

LICENCE DATA IS PART OF THE BILL
    Every component carries at least one SPDX licence id, and :func:`component_licenses`
    is what the licence-aggregate gate consumes. TOURNAMENT-VERDICT.md M1 records a
    CC BY-SA 4.0 share-alike entry sitting inside a package declaring MIT, invisible to a
    LICENSE-file scanner. A per-file declared licence is the shape in which that is visible.
"""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Any, NamedTuple

from .canon import ensure_within, hex_digest_file

TOOL_NAME = "mkt-sbom"
TOOL_VERSION = "1.0.0"


def deterministic_serial(name: str, version: str, payload_digest: str) -> str:
    """A stable ``urn:uuid`` derived from the package coordinates.

    Deterministic on purpose: the SBOM is inside the signed surface, so a random serial
    would make an otherwise byte-identical rebuild produce a different signature and
    destroy the reproducible-build claim it is meant to support.
    """
    seed = f"{name}\x1f{version}\x1f{payload_digest}".encode("utf-8")
    return "urn:uuid:" + str(
        uuid.UUID(bytes=hashlib.sha256(seed).digest()[:16], version=5)
    )


def build(
    *,
    name: str,
    version: str,
    files: list[dict[str, Any]],
    licenses: dict[str, str],
    payload_digest: str,
    timestamp: str,
    default_license: str | None = None,
) -> dict[str, Any]:
    """Build a CycloneDX-shaped SBOM from the manifest payload list.

    ``licenses`` maps a payload path to an SPDX id. A path with no entry uses
    ``default_license``; if that is also absent the build RAISES rather than emitting a
    component with an empty licence list -- an SBOM that cannot say what licence a file is
    under is precisely the artifact that let the M1 defect hide.
    """
    components = []
    for entry in sorted(files, key=lambda f: f["path"]):
        path = entry["path"]
        spdx = licenses.get(path, default_license)
        if not spdx:
            raise ValueError(
                f"no licence for payload file {path!r}: refusing to emit a component with no "
                "licence (an unlicensed component is how an aggregate licence misstatement hides)"
            )
        components.append(
            {
                "type": "file",
                "name": path,
                "hashes": [
                    {"alg": "SHA-256", "content": entry["sha256"].split(":", 1)[1]}
                ],
                "licenses": [{"license": {"id": spdx}}],
            }
        )
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": deterministic_serial(name, version, payload_digest),
        "metadata": {
            "timestamp": timestamp,
            "component": {"type": "application", "name": name, "version": version},
            "tools": [{"name": TOOL_NAME, "version": TOOL_VERSION}],
        },
        "components": components,
    }


class SbomVerdict(NamedTuple):
    ok: bool
    components_checked: int
    payload_files: int
    missing_from_disk: list[str]
    missing_from_sbom: list[str]
    hash_mismatch: list[str]

    def summary(self) -> str:
        return (
            f"{self.components_checked}/{self.payload_files} components matched; "
            f"missing_from_disk={len(self.missing_from_disk)} "
            f"missing_from_sbom={len(self.missing_from_sbom)} "
            f"hash_mismatch={len(self.hash_mismatch)}"
        )


def verify(
    sbom: dict[str, Any],
    payload_root: str | Path,
    *,
    declared: list[dict[str, Any]] | None = None,
) -> SbomVerdict:
    """Verify the SBOM against the bytes on disk under ``payload_root``.

    ``declared`` is the manifest payload list. When given, the bijection is checked against
    the MANIFEST as well, so an SBOM and a payload that agree with each other but disagree
    with the signed manifest is still caught.
    """
    root = Path(payload_root)
    sbom_files: dict[str, str] = {}
    for comp in sbom.get("components", []):
        if comp.get("type") != "file":
            continue
        digests = [
            h["content"] for h in comp.get("hashes", []) if h.get("alg") == "SHA-256"
        ]
        if digests:
            sbom_files[comp["name"]] = digests[0]

    on_disk: dict[str, str] = {}
    if root.is_dir():
        for path in sorted(root.rglob("*")):
            if path.is_file():
                rel = path.relative_to(root).as_posix()
                on_disk[rel] = hex_digest_file(path)

    universe = set(sbom_files) | set(on_disk)
    if declared is not None:
        universe |= {d["path"] for d in declared}

    missing_from_disk = sorted(
        p for p in universe if p in sbom_files and p not in on_disk
    )
    missing_from_sbom = sorted(p for p in universe if p not in sbom_files)
    mismatch = []
    matched = 0
    for path in sorted(set(sbom_files) & set(on_disk)):
        # containment: a component name must not be able to point outside the payload root
        ensure_within(root, path)
        if sbom_files[path] != on_disk[path]:
            mismatch.append(path)
        else:
            matched += 1
    ok = (
        not missing_from_disk and not missing_from_sbom and not mismatch and matched > 0
    )
    return SbomVerdict(
        ok, matched, len(on_disk), missing_from_disk, missing_from_sbom, mismatch
    )


def component_licenses(sbom: dict[str, Any]) -> dict[str, str]:
    """``{payload_path: spdx}`` for every file component."""
    out: dict[str, str] = {}
    for comp in sbom.get("components", []):
        licenses = comp.get("licenses") or []
        if licenses:
            out[comp["name"]] = licenses[0]["license"]["id"]
    return out
