"""Set-difference plugin rollback: restore owned_to, unlink owned_from-owned_to."""
from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping

from .trees import FOREIGN_PATHS, OWNED_V1, OWNED_V2


def _posix(path: str | Path) -> str:
    return str(path).replace("\\", "/").lstrip("./")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def census(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not root.is_dir():
        return out
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = _posix(path.relative_to(root).as_posix())
        out[rel] = _sha256(path.read_bytes())
    return out


def census_from_mapping(mapping: Mapping[str, str]) -> dict[str, str]:
    return { _posix(k): _sha256(str(v).encode("utf-8")) for k, v in mapping.items() }


def diff_census(pre: Mapping[str, str], post: Mapping[str, str]) -> dict[str, list[str]]:
    pre_keys = set(pre)
    post_keys = set(post)
    added = sorted(post_keys - pre_keys)
    removed = sorted(pre_keys - post_keys)
    changed = sorted(k for k in (pre_keys & post_keys) if pre[k] != post[k])
    return {"added": added, "removed": removed, "changed": changed}


def foreign_preserved(
    pre: Mapping[str, str],
    post: Mapping[str, str],
    foreign_paths: Iterable[str],
) -> bool:
    for rel in foreign_paths:
        key = _posix(rel)
        if key not in pre:
            continue
        if post.get(key) != pre[key]:
            return False
    return True


@dataclass
class RollbackReport:
    mode: str = "set-difference"
    error: str | None = None
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    foreign_preserved: bool = True

    def get(self, key: str, default=None):
        return getattr(self, key, default)


def rollback(
    live: Path,
    payload_v1: Path,
    owned_from: Iterable[str] = OWNED_V2,
    owned_to: Iterable[str] = OWNED_V1,
) -> RollbackReport:
    owned_from_set = { _posix(p) for p in owned_from }
    owned_to_set = { _posix(p) for p in owned_to }
    pre = census(live)
    live.mkdir(parents=True, exist_ok=True)

    for rel in sorted(owned_to_set):
        src = payload_v1 / rel
        dest = live / rel
        if rel not in owned_from_set and dest.exists() and rel in FOREIGN_PATHS:
            return RollbackReport(error=f"refuse overwrite foreign {rel}", foreign_preserved=False)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.is_file():
            dest.write_bytes(src.read_bytes())

    for rel in sorted(owned_from_set - owned_to_set):
        dest = live / rel
        if dest.is_file():
            dest.unlink()
            parent = dest.parent
            while parent != live and parent.is_dir() and not any(parent.iterdir()):
                parent.rmdir()
                parent = parent.parent

    post = census(live)
    delta = diff_census(pre, post)
    return RollbackReport(
        mode="set-difference",
        error=None,
        added=delta["added"],
        removed=delta["removed"],
        changed=delta["changed"],
        foreign_preserved=foreign_preserved(pre, post, FOREIGN_PATHS),
    )


def wholesale_snapshot_restore(live: Path, payload_v1: Path) -> None:
    if live.exists():
        shutil.rmtree(live)
    shutil.copytree(payload_v1, live)
