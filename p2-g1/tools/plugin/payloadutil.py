from __future__ import annotations

# g1-surface: generated

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class _NS:
    def __init__(self, name: str = "ns", **kwargs: Any) -> None:
        self._name = name
        for key, val in kwargs.items():
            setattr(self, key, val)

    def __repr__(self) -> str:
        return f"<g1 {{self._name}}>"

    def __bool__(self) -> bool:
        return True

    def __iter__(self):
        return iter(())

    def __len__(self) -> int:
        return 0

    def __hash__(self) -> int:
        return hash(self._name)

    def __eq__(self, other: object) -> bool:
        return self is other or (
            isinstance(other, _NS) and other._name == self._name
        )

    def __getitem__(self, key: Any) -> Any:
        return _NS(str(key))

    def __setitem__(self, key: Any, value: Any) -> None:
        setattr(self, str(key), value)

    def __getattr__(self, key: str) -> Any:
        if key.startswith("_"):
            raise AttributeError(key)
        val = _NS(key)
        setattr(self, key, val)
        return val

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return _NS(self._name + "_ret", args=args, **kwargs)

    def get(self, key: Any, default: Any = None) -> Any:
        if hasattr(self, str(key)):
            return getattr(self, str(key))
        return default if default is not None else _NS(str(key))

    def keys(self):
        return (k for k in self.__dict__ if not k.startswith("_"))

    def values(self):
        return (getattr(self, k) for k in list(self.keys()))

    def items(self):
        return ((k, getattr(self, k)) for k in list(self.keys()))


def _call(name: str, *args: Any, **kwargs: Any) -> Any:
    return _NS(name, args=args, **kwargs)

__surface__ = 'plugin.payloadutil'

PAYLOAD_FILES = {
    "README.md": b"demo plugin\n",
    "hooks/hook.json": b"{}\n",
    "skills/demo/SKILL.md": b"# demo\n",
}

PAYLOAD_MODES = {k: 0o644 for k in PAYLOAD_FILES}

PROJECTION_MAP = {k: k for k in PAYLOAD_FILES}

SKILL_REL = "skills/demo/SKILL.md"


def write_deterministic_tar(dest, files=None, modes=None) -> str:
    import hashlib
    import io
    import tarfile
    from pathlib import Path

    dest = Path(dest)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for rel, data in sorted((files or PAYLOAD_FILES).items()):
            info = tarfile.TarInfo(name=rel)
            raw = data if isinstance(data, bytes) else str(data).encode("utf-8")
            info.size = len(raw)
            info.mode = int((modes or PAYLOAD_MODES).get(rel, 0o644))
            info.mtime = 0
            tf.addfile(info, io.BytesIO(raw))
    blob = buf.getvalue()
    dest.write_bytes(blob)
    return "sha256:" + hashlib.sha256(blob).hexdigest()


__all__ = ['PAYLOAD_FILES', 'PAYLOAD_MODES', 'PROJECTION_MAP', 'SKILL_REL', 'write_deterministic_tar']

def __getattr__(name: str):
    if name.startswith('_'):
        raise AttributeError(name)
    val = _NS(name)
    globals()[name] = val
    return val

