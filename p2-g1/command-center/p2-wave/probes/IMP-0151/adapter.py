"""IMP-0151 adapter: enumerate workflow-shaped capabilities (skills/commands/
agents/hooks) under two roots, READ-ONLY, recording divergence per artifact
without treating either side as authoritative.

Recovered 2026-10-25 by builder shard 11 wave 2 from the delivery receipt
`command-center/receipts/IMP-0151.json`. The live fixture tree is never
written: the adapter only walks and hashes. Shared (name+content equal) is the
only reconciled class; repo_only / live_only are REPORTED, never silently
promoted or demoted."""
from __future__ import annotations

import hashlib
from pathlib import Path


def _snapshot(root: Path) -> dict[str, str]:
    """rel-path -> sha256 (CRLF-normalized) of every file under root."""
    out: dict[str, str] = {}
    if not Path(root).is_dir():
        return out
    for p in sorted(Path(root).rglob("*")):
        if p.is_file():
            rel = p.relative_to(root).as_posix()
            out[rel] = hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    return out


def discover(repo_root: str | Path, live_root: str | Path) -> dict:
    """Classify every artifact: shared / repo_only / live_only. Read-only."""
    repo = _snapshot(Path(repo_root))
    live = _snapshot(Path(live_root))
    repo_names, live_names = set(repo), set(live)
    shared = sorted(
        n for n in repo_names & live_names if repo[n] == live[n]
    )
    diverged = sorted(
        n for n in repo_names & live_names if repo[n] != live[n]
    )
    return {
        "read_only": True,
        "repo_only": sorted(repo_names - live_names),
        "live_only": sorted(live_names - repo_names),
        "shared": shared,
        "diverged": diverged,
        "counts": {
            "repo": len(repo_names),
            "live": len(live_names),
            "shared": len(shared),
            "repo_only": len(repo_names - live_names),
            "live_only": len(live_names - repo_names),
        },
    }
