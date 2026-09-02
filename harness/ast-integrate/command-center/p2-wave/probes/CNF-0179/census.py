"""Worktree census: is there a production published bundle besides this fixture?

Bounded walk. A repo-wide rglob would treat every probe fixture .tar.gz as a
"published artifact" and can hang on this estate. Look only at release-shaped
roots and exact attestation filenames.
"""
from __future__ import annotations

from pathlib import Path

SEARCH_ROOTS = (
    "platform/marketplace",
    "dist",
    "release",
    "releases",
    "artifacts",
    "publish",
)

SKIP_DIR_NAMES = {
    ".git",
    "__pycache__",
    "node_modules",
    ".pytest_cache",
    "CNF-0179",
}

ATTESTATION_SUFFIXES = (
    ".intoto.json",
    ".intoto.json.sig",
    ".spdx.json",
    ".cdx.json",
)
ATTESTATION_NAMES = (
    "sbom.json",
    "bom.json",
    "provenance.json",
    "attestation.json",
)
PAYLOAD_SUFFIXES = (
    ".tar.gz",
    ".whl",
    ".sig",
)
MAX_HITS = 40


def _interesting(path: Path) -> bool:
    name = path.name.lower()
    if name in ATTESTATION_NAMES:
        return True
    if name.endswith(ATTESTATION_SUFFIXES):
        return True
    if name.endswith(PAYLOAD_SUFFIXES) and "schema" not in name:
        return True
    return False


def iter_hits(repo: Path) -> list[str]:
    hits: list[str] = []
    roots = [repo / rel for rel in SEARCH_ROOTS if (repo / rel).exists()]
    for root in roots:
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if set(path.parts) & SKIP_DIR_NAMES:
                continue
            rel = path.relative_to(repo).as_posix()
            if "/probes/CNF-0179/" in f"/{rel}":
                continue
            if not _interesting(path):
                continue
            hits.append(rel)
            if len(hits) >= MAX_HITS:
                return sorted(hits)
    return sorted(hits)


def census(repo: Path) -> dict:
    hits = iter_hits(repo)
    marketplace = (repo / "platform" / "marketplace").is_dir()
    receipts = (repo / "command-center" / "receipts").is_dir()
    signed_triple = False
    # A production bundle for this unit is a payload plus detached sig plus
    # SBOM plus provenance, not a marketplace *schema* tree.
    names = {Path(h).name.lower() for h in hits}
    has_payload = any(n.endswith(".tar.gz") or n.endswith(".whl") for n in names)
    has_sig = any(n.endswith(".sig") for n in names)
    has_sbom = any(
        n.endswith(".cdx.json") or n.endswith(".spdx.json") or n in {"sbom.json", "bom.json"}
        for n in names
    )
    has_prov = any(
        n.endswith(".intoto.json") or n in {"provenance.json", "attestation.json"}
        for n in names
    )
    signed_triple = bool(has_payload and has_sig and has_sbom and has_prov)
    return {
        "production_bundle_present": signed_triple,
        "marketplace_tree_present": marketplace,
        "hits": hits,
        "hit_count": len(hits),
        "note": (
            "No production payload+sig+SBOM+provenance triple outside the "
            "CNF-0179 fixture (marketplace tree holds schemas and unsigned "
            "package fixtures, not an independently signed release)."
            if not signed_triple
            else "Non-fixture signed/SBOM-like files found; listed in hits."
        ),
        "receipts_dir_exists_before_emit": receipts,
        "search_roots": [r for r in SEARCH_ROOTS if (repo / r).exists()],
    }
