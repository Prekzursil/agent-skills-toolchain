"""Build the candidate shipped payload and the deliberate-violation payload."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from constants import (
    EXTRA_MEMBER,
    HERE,
    PLANTED_CREDENTIAL_BODY,
    PLANTED_ENV,
    PLANTED_GIT,
    PLANTED_OVERSIZE,
    REPO,
)
from pack import append_member, write_zip

GEN_DIR = HERE.parent / "ARC-0010"
sys.path.insert(0, str(GEN_DIR))
import generator as G  # noqa: E402


def candidate_files() -> dict[str, bytes]:
    """Plugin files that would ship from the typed registry generator."""
    registry = G.load_json(G.DEFAULT_REGISTRY)
    return G.generate(registry)


def git_config_bytes() -> bytes:
    return b"[core]\n\trepositoryformatversion = 0\n\tfilemode = true\n"


def oversize_bytes(ceiling: int) -> bytes:
    return b"\0" * (ceiling + 1)


def write_candidate_zip(dest: Path) -> dict[str, bytes]:
    files = candidate_files()
    write_zip(files, dest)
    return files


def write_polluted_zip(dest: Path, single_file_ceiling: int) -> dict[str, bytes]:
    files = dict(candidate_files())
    files[PLANTED_GIT] = git_config_bytes()
    files[PLANTED_ENV] = PLANTED_CREDENTIAL_BODY.encode("utf-8")
    files[PLANTED_OVERSIZE] = oversize_bytes(single_file_ceiling)
    write_zip(files, dest)
    return files


def write_enumeration_proof_zip(clean_zip: Path, dest: Path) -> None:
    dest.write_bytes(clean_zip.read_bytes())
    append_member(dest, EXTRA_MEMBER, b"this path is not on the allowlist\n")


def production_surface(repo: Path | None = None) -> dict[str, Any]:
    root = repo or REPO
    found: list[str] = []
    search_roots = (
        root / "dist",
        root / "build",
        root / "tools" / "plugin",
        root / ".claude-plugin",
        root / "packaging",
    )
    for base in search_roots:
        if not base.is_dir():
            continue
        for pat in ("*.whl", "*.tar.gz", "*.tgz", "*.zip"):
            for p in base.rglob(pat):
                rel = p.relative_to(root).as_posix()
                if "probes/CNF-0102/" in rel:
                    continue
                found.append(rel)
    packer = (root / "tools/plugin/pack.py").is_file()
    allow = (root / "tools/plugin/payload-allowlist.json").is_file()
    plugin = (root / ".claude-plugin/plugin.json").is_file()
    if found:
        source = (
            "ARC-0010 generate() plugin payload packed by CNF-0102 pack.py; "
            f"also found {len(found)} distributable(s) in production search roots"
        )
    else:
        source = (
            "ARC-0010 generate() plugin payload packed by CNF-0102 pack.py; "
            "no production wheel/sdist/plugin zip in dist/build/tools/plugin/"
            ".claude-plugin/packaging"
        )
    return {
        "production_packer_present": packer,
        "production_allowlist_present": allow,
        "plugin_manifest_present": plugin,
        "existing_distributables": sorted(found),
        "candidate_source": source,
    }
