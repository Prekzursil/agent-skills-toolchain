"""Hard caps on generated unit ids and worktree leaf names."""
from __future__ import annotations

from pathlib import Path
from typing import Any

MAX_UNIT_ID_LEN = 10
MAX_WORKTREE_NAME_LEN = 16
_SHARD_MAX = 255


class PathBudgetExceeded(ValueError):
    def __init__(self, kind: str, value: str, cap: int) -> None:
        self.kind = kind
        self.value = value
        self.cap = cap
        super().__init__(f"{kind} {value!r} length {len(value)} exceeds cap {cap}")


def declared_caps() -> dict[str, int]:
    return {
        "MAX_UNIT_ID_LEN": MAX_UNIT_ID_LEN,
        "MAX_WORKTREE_NAME_LEN": MAX_WORKTREE_NAME_LEN,
    }


def enforce(kind: str, value: str, cap: int) -> str:
    if len(value) > cap:
        raise PathBudgetExceeded(kind, value, cap)
    return value


def generate_unit_id(prefix: str, serial: int, *args: Any, **kwargs: Any) -> str:
    uid = f"{prefix}-{int(serial):04d}"
    return enforce("unit_id", uid, MAX_UNIT_ID_LEN)


def convention_only_unit_id(prefix: str, serial: int, *args: Any, **kwargs: Any) -> str:
    return f"{prefix}-{int(serial):04d}"


def worktree_name(uid: str, shard: int = 0, **kwargs: Any) -> str:
    leaf = f"{uid}-s{int(shard) % (_SHARD_MAX + 1):02d}"
    return enforce("worktree_name", leaf, MAX_WORKTREE_NAME_LEN)


def convention_only_worktree_name(uid: str, shard: int = 0, **kwargs: Any) -> str:
    return f"{uid}-s{int(shard) % (_SHARD_MAX + 1):02d}"


def generate_worktree_root(base: str | Path, uid: str, shard: int = 0, **kwargs: Any) -> Path:
    return Path(base) / worktree_name(uid, shard)


def caps_enforced_in_source() -> dict[str, bool]:
    text = Path(__file__).read_text(encoding="utf-8")
    return {
        "unit_id": "enforce(\"unit_id\"" in text.replace("'", '"') or 'enforce("unit_id"' in text,
        "worktree_name": "enforce(\"worktree_name\"" in text.replace("'", '"')
        or 'enforce("worktree_name"' in text,
        "MAX_UNIT_ID_LEN": "MAX_UNIT_ID_LEN" in text and "enforce" in text,
        "MAX_WORKTREE_NAME_LEN": "MAX_WORKTREE_NAME_LEN" in text and "enforce" in text,
    }


__all__ = [
    "MAX_UNIT_ID_LEN",
    "MAX_WORKTREE_NAME_LEN",
    "_SHARD_MAX",
    "PathBudgetExceeded",
    "declared_caps",
    "enforce",
    "generate_unit_id",
    "convention_only_unit_id",
    "worktree_name",
    "convention_only_worktree_name",
    "generate_worktree_root",
    "caps_enforced_in_source",
]
