"""Independent path census (find/du class). Disagreement with the scanner is a detector failure."""
from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Iterable, Iterator, overload

ENUMERATOR = "os.walk-independent"


def _posix(rel: str) -> str:
    return str(rel).replace("\\", "/").strip("/")


class Census(Sequence[str]):
    """The sorted relative file paths found under one root.

    A census *is* its path list: iterating, ``len``, indexing, ``sorted(...)``
    and ``==`` all work on the paths, and an empty (or absent) tree is falsy,
    so ``not census(home)`` means "nothing is placed".  The three fields of the
    record shape this walk used to return -- ``paths``, ``path_count`` and
    ``enumerator`` -- stay reachable as attributes and as string keys
    (``census(home)["paths"]``); :meth:`to_dict` gives that record verbatim.
    """

    __slots__ = ("_paths",)

    def __init__(self, paths: Iterable[str] = ()) -> None:
        self._paths: tuple[str, ...] = tuple(sorted({_posix(p) for p in paths if _posix(p)}))

    @property
    def paths(self) -> list[str]:
        return list(self._paths)

    @property
    def path_count(self) -> int:
        return len(self._paths)

    @property
    def enumerator(self) -> str:
        return ENUMERATOR

    def to_dict(self) -> dict[str, Any]:
        return {"paths": self.paths, "path_count": self.path_count, "enumerator": self.enumerator}

    @overload
    def __getitem__(self, key: int) -> str: ...

    @overload
    def __getitem__(self, key: slice) -> tuple[str, ...]: ...

    @overload
    def __getitem__(self, key: str) -> Any: ...

    def __getitem__(self, key: int | slice | str) -> Any:
        if isinstance(key, str):
            try:
                return self.to_dict()[key]
            except KeyError:
                raise KeyError(f"census has no field {key!r}; fields are paths, path_count, enumerator") from None
        return self._paths[key]

    def __len__(self) -> int:
        return len(self._paths)

    def __iter__(self) -> Iterator[str]:
        return iter(self._paths)

    def __contains__(self, item: object) -> bool:
        return isinstance(item, str) and _posix(item) in self._paths

    def __bool__(self) -> bool:
        return bool(self._paths)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Census):
            return self._paths == other._paths
        if isinstance(other, (list, tuple, set, frozenset)):
            return self._paths == tuple(sorted({_posix(str(p)) for p in other}))
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._paths)

    def __repr__(self) -> str:
        return f"Census({list(self._paths)!r})"


def census(root: Path) -> Census:
    """Walk ``root`` (no symlink following) and return the :class:`Census` of its files.

    An absent or empty root yields an empty, falsy census.
    """
    root = Path(root)
    paths: list[str] = []
    for dirpath, _dirnames, filenames in os.walk(root, followlinks=False):
        for name in filenames:
            p = Path(dirpath) / name
            try:
                rel = p.relative_to(root).as_posix()
            except ValueError:
                continue
            paths.append(_posix(rel))
    return Census(paths)


def plugin_root(dest_root: Path, name: str) -> Path:
    return Path(dest_root) / "plugins" / str(name)


def tree_files(root: Path) -> dict[str, str]:
    root = Path(root)
    out: dict[str, str] = {}
    if not root.exists():
        return out
    for dirpath, _dirnames, filenames in os.walk(root, followlinks=False):
        for name in filenames:
            p = Path(dirpath) / name
            try:
                rel = p.relative_to(root).as_posix()
            except ValueError:
                continue
            out[rel] = "file"
    return out


def owned_remaining(home: Path, projection: Any) -> list[str]:
    home = Path(home)
    rels = []
    if hasattr(projection, "owned_relpaths"):
        rels = list(projection.owned_relpaths())
    elif isinstance(projection, dict):
        rels = list(projection.get("owned") or [])
    leftover = []
    for rel in rels:
        if (home / rel).exists():
            leftover.append(str(rel).replace("\\", "/"))
    return leftover


def non_owned_inventory(
    home: Path, projection: Any, include_user_data: bool = True
) -> dict[str, str]:
    import hashlib

    home = Path(home)
    owned = set()
    if hasattr(projection, "owned_relpaths"):
        owned = {str(x).replace("\\", "/") for x in projection.owned_relpaths()}
    walked = census(home)["paths"]
    inventory: dict[str, str] = {}
    for rel in walked:
        if rel in owned:
            continue
        path = home / rel
        if not path.is_file():
            continue
        inventory[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    if not include_user_data:
        inventory = {k: v for k, v in inventory.items() if not k.startswith("user-data/")}
    return inventory


def compare(left: Iterable[str], right: Iterable[str]) -> dict[str, Any]:
    a = {_posix(x) for x in left}
    b = {_posix(x) for x in right}
    return {
        "agree": a == b,
        "only_left": sorted(a - b),
        "only_right": sorted(b - a),
        "left_count": len(a),
        "right_count": len(b),
    }
