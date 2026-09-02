"""Projection-scoped snapshot/restore with owner-only perms (IMP-0030)."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from plugin.projection import expand_touch_paths, load_projection


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def _blake2b(data: bytes) -> str:
    return hashlib.blake2b(data.replace(b"\r\n", b"\n"), digest_size=16).hexdigest()


def census_tree(root: Path) -> dict[str, dict[str, str]]:
    root = Path(root)
    out: dict[str, dict[str, str]] = {}
    if not root.exists():
        return out
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        raw = p.read_bytes()
        out[rel] = {"sha256": _sha256(raw), "blake2b": _blake2b(raw)}
    return out


def censuses_equal(left: dict, right: dict) -> dict[str, Any]:
    a = {k: dict(v) for k, v in (left or {}).items()}
    b = {k: dict(v) for k, v in (right or {}).items()}
    return {
        "equal": a == b,
        "only_left": sorted(set(a) - set(b)),
        "only_right": sorted(set(b) - set(a)),
    }


def _secretish(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    upper = path.name.upper()
    if path.suffix.lower() in {".env", ".pem", ".key"} or upper in {"ENV", ".ENV"}:
        if "=" in text and any(
            tok in text.upper() for tok in ("KEY", "TOKEN", "SECRET", "PASSWORD")
        ):
            return True
    for line in text.splitlines():
        if "=" not in line:
            continue
        name, _, val = line.partition("=")
        n = name.strip().upper()
        if n.endswith(("KEY", "TOKEN", "SECRET", "PASSWORD", "PAT")) and val.strip():
            return True
    return False


def _chmod_owner_only(path: Path) -> None:
    if os.name == "nt":
        return
    mode = stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR
    try:
        os.chmod(path, mode)
        for p in path.rglob("*"):
            try:
                os.chmod(p, mode if p.is_dir() else (stat.S_IRUSR | stat.S_IWUSR))
            except OSError:
                continue
    except OSError:
        pass


@dataclass
class Snapshot:
    snapshot_dir: Path
    included_census: dict = field(default_factory=dict)
    manifest: dict = field(default_factory=dict)


def snapshot(
    live: Path,
    store: Path,
    projection: Any,
    keep: int = 3,
    op: str = "snapshot",
) -> Snapshot:
    live = Path(live)
    store = Path(store)
    store.mkdir(parents=True, exist_ok=True)
    dest = store / f"{op}-1"
    if dest.exists():
        shutil.rmtree(dest)
    tree = dest / "tree"
    tree.mkdir(parents=True, exist_ok=True)
    proj = load_projection(projection)
    touch = expand_touch_paths(live, proj)
    excluded: list[str] = []
    copied: list[str] = []
    for rel in touch:
        src = live / rel
        if not src.is_file():
            continue
        if _secretish(src):
            excluded.append(rel)
            continue
        target = tree / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        copied.append(rel)
    manifest = {
        "op": op,
        "keep": keep,
        "copied_paths": copied,
        "excluded_paths": excluded,
        "projection_id": proj.get("id"),
    }
    (dest / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _chmod_owner_only(dest)
    included = census_tree(tree)
    return Snapshot(snapshot_dir=dest, included_census=included, manifest=manifest)


def restore(snapshot_dir: Path, dest: Path) -> dict[str, dict[str, str]]:
    snapshot_dir = Path(snapshot_dir)
    dest = Path(dest)
    src = snapshot_dir / "tree"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    return census_tree(dest)


def verify_snapshot_permissions(snapshot_dir: Path) -> dict[str, Any]:
    snapshot_dir = Path(snapshot_dir)
    if os.name == "nt":
        return {"owner_only": True, "platform": "nt"}
    try:
        mode = stat.S_IMODE(snapshot_dir.stat().st_mode)
    except OSError:
        return {"owner_only": False}
    return {"owner_only": (mode & 0o077) == 0, "mode": oct(mode)}
