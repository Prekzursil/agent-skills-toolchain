#!/usr/bin/env python3
"""Path resolution for the G-1 tools, native-Linux aware (cloud worker 02.09).

The 28.08-02.09 tools hard-coded the owner's WSL layout: Windows tree at
``/mnt/c/Users/Prekzursil/source/ast-integrate`` (state of record: ovh-monitor,
catalog) and a rsync mirror at ``~/p2-g1`` (where probes execute). On the cloud
Linux worker the checked-out ``harness/ast-integrate`` tree IS the workspace:
there is no mirror, no rsync, and the ovh-monitor ledger lives in the same tree.

Resolution order (each tool imports ``ROOT``/``WIN``/``MON``/``LOG`` from here):
  1. ``AST_INTEGRATE_ROOT`` env, when set and it holds the catalog.
  2. The Windows mirror layout, when ``/mnt/c/...`` exists (owner's box).
  3. The tree this file lives in (``seed-stage`` -> ``p2-wave`` -> ``command-center``
     -> repo root).
``WIN == ROOT`` on Linux, so copy-back steps become no-ops.
"""
from __future__ import annotations

import os
from pathlib import Path

_HERE = Path(__file__).resolve()
_REPO_FROM_FILE = _HERE.parents[3]
_WIN_LEGACY = Path("/mnt/c/Users/Prekzursil/source/ast-integrate")
_MIRROR_LEGACY = Path.home() / "p2-g1"


def _has_catalog(p: Path) -> bool:
    return (p / "command-center" / "WORK-UNIT-CATALOG.json").is_file()


def _resolve_root() -> Path:
    env = os.environ.get("AST_INTEGRATE_ROOT")
    if env and _has_catalog(Path(env)):
        return Path(env).resolve()
    if _WIN_LEGACY.is_dir() and _has_catalog(_MIRROR_LEGACY):
        return _MIRROR_LEGACY
    return _REPO_FROM_FILE


def _resolve_win(root: Path) -> Path:
    if _WIN_LEGACY.is_dir() and _has_catalog(_WIN_LEGACY) and root != _REPO_FROM_FILE:
        return _WIN_LEGACY
    return root


ROOT: Path = _resolve_root()
WIN: Path = _resolve_win(ROOT)
MON: Path = WIN / "command-center" / "p2-wave" / "ovh-monitor"
REPAIR: Path = MON / "repair-claude"
LOG: Path = MON / "g1-repair-claude_2026-08-27.log"
CATALOG: Path = WIN / "command-center" / "WORK-UNIT-CATALOG.json"
MEASURE: Path = ROOT / "command-center" / "p2-wave" / "_measure_one_delivered.py"
NATIVE: bool = WIN == ROOT


# Legacy waves in the order they ran (ledger P2-REPAIR-PROGRESS_2026-08-27.md). In a git
# checkout every file carries the checkout mtime, so mtime ordering is arbitrary there
# (measured 02.09: mtime order gave 692 fails, chronology gives 668 -- 24 units flipped).
LEGACY_ORDER: tuple[str, ...] = (
    "mod-pass1.jsonl",           # 28.08 ~04:30  mod class 16/16
    "timeout-pass1.jsonl",       # 28.08         81-ID timeout retry
    "batch6-predicate.jsonl",    # 28.08 ~04:55  predicate class 3/3
    "wave-regen-listget.jsonl",  # 28.08 ~06:00  regen pilot (19)
    "wave-regen-full.jsonl",     # 28.08 06:05-07:01 (died at 143)
    "wave-regen-0209.jsonl",     # 02.09 02:34-  893-ID regen+measure (owner's box)
)


def overlay_sources() -> list[Path]:
    """Census + rerun + every repair-claude wave, chronological (latest row wins).

    Legacy waves follow LEGACY_ORDER; anything newer (cloud waves named
    ``w0902-NN-*``) sorts after them by name, then by mtime for stragglers.
    """
    srcs = [MON / "g1-local-full.jsonl", MON / "g1-fails-rerun.jsonl"]
    if REPAIR.is_dir():
        present = {p.name: p for p in REPAIR.glob("*.jsonl")}
        for name in LEGACY_ORDER:
            if name in present:
                srcs.append(present.pop(name))
        cloud = sorted((p for p in present.values() if p.name.startswith("w0902-")), key=lambda p: p.name)
        rest = sorted((p for p in present.values() if not p.name.startswith("w0902-")), key=lambda p: (p.stat().st_mtime, p.name))
        srcs.extend(rest)
        srcs.extend(cloud)
    return [p for p in srcs if p.is_file()]


def latest_rows() -> dict[str, dict]:
    """Latest record per unit id across every overlay source."""
    import json

    latest: dict[str, dict] = {}
    for src in overlay_sources():
        for line in src.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            uid = rec.get("id")
            if uid:
                latest[uid] = rec
    return latest


if __name__ == "__main__":
    print(f"ROOT={ROOT}\nWIN={WIN}\nMON={MON}\nNATIVE={NATIVE}\ncatalog={CATALOG.is_file()}")
