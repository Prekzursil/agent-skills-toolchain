#!/usr/bin/env python3
"""TST-0175 measured layer: explicit cache-path ownership manifest + upgrade simulator.

The unit question: `update` / `install --repair` must invalidate exactly the
caches it OWNS and leave user data untouched. The measured layer binds the
PRODUCTION invalidation primitive (platform/plugin/cache.py Cache.invalidate /
Cache.refresh) to an explicit ownership manifest: only manifest-listed derived
paths are touched; anything not listed is never opened for write.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

def _cache_cls():
    from prodimport import load_cache_module
    return load_cache_module().Cache

# --- explicit ownership manifest: the ONLY derived paths an upgrade may clear ---
OWNERSHIP_MANIFEST = {
    "owned_derived": [
        "state/cache",        # content-addressed blob cache (platform Cache root)
        "state/quarantine",   # cache's quarantine side-dir (derived evidence, re-derivable)
        "state/derived-index",
    ],
    "user_data": [
        "state/notes",
        "state/profiles",
        "state/user-settings.json",
        "commands.json",
    ],
}

OWNED = [Path(p) for p in OWNERSHIP_MANIFEST["owned_derived"]]
USER = [Path(p) for p in OWNERSHIP_MANIFEST["user_data"]]


def is_owned(rel: Path) -> bool:
    """True iff rel (relative to install root) is on the owned-derived list."""
    rel = Path(rel)
    return any(rel == o or o in rel.parents for o in OWNED)


def tree_hash(root: Path, rels: list[Path]) -> dict[str, str]:
    """sha256 per file under the given relative dirs, keyed rel-path (sorted). Empty dirs -> {} entry marker."""
    out: dict[str, str] = {}
    for rel in rels:
        base = root / rel
        if base.is_file():
            out[rel.as_posix()] = hashlib.sha256(base.read_bytes()).hexdigest()
        elif base.is_dir():
            files = sorted(p for p in base.rglob("*") if p.is_file())
            out[rel.as_posix() + "/"] = ",".join(
                f"{p.relative_to(root).as_posix()}:{hashlib.sha256(p.read_bytes()).hexdigest()}" for p in files
            )
        else:
            out[rel.as_posix()] = "<absent>"
    return out


def upgrade_install_repair(root: Path) -> dict:
    """Upgrade / install --repair: clear EXACTLY the owned derived paths via the
    production invalidation primitive; never write anywhere else."""
    Cache = _cache_cls()

    cleared: dict[str, int] = {}
    for rel in OWNED:
        target = root / rel
        target.mkdir(parents=True, exist_ok=True)
        if rel.as_posix() == "state/cache":
            c = Cache(target.parent / "cache")
            cleared[rel.as_posix()] = c.invalidate()  # production: never touches quarantine
        else:
            n = 0
            if target.exists():
                for f in sorted(target.rglob("*")):
                    if f.is_file():
                        f.unlink()
                        n += 1
            cleared[rel.as_posix()] = n
    return {"cleared": cleared, "manifest": OWNERSHIP_MANIFEST}


def rollback_buggy(root: Path) -> None:
    """KNOWN-BROKEN rollback (regression seed _USER-PROMPTS.md:11347): wipes the
    whole state dir including user data. Detector fuel only -- never shipped."""
    import shutil

    shutil.rmtree(root / "state", ignore_errors=True)


def rollback_correct(root: Path) -> None:
    """Correct rollback: restores previous version's derived state, keeps user data."""
    for rel in OWNED:
        target = root / rel
        if rel.as_posix() == "state/cache":
            Cache = _cache_cls()

            Cache(target.parent / "cache").invalidate()
        elif target.exists():
            import shutil

            shutil.rmtree(target, ignore_errors=True)
