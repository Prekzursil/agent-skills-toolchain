"""Session-keyed vs project-keyed store (IMP-0430 bleed control)."""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

KEY_SHAPE_PROJECT = "project"
KEY_SHAPE_SESSION = "session"
KEY_TEMPLATE_PROJECT = "{store}/{project}"
KEY_TEMPLATE_SESSION = "{store}/{project}/{session}"


def make_key(store: str, project: str, session: str | None = None, *, mode: str = "session") -> str:
    if mode == "project" or session is None:
        return f"{store}/{project}"
    return f"{store}/{project}/{session}"


class SessionKeyedStore:
    def __init__(self, root: str | Path, mode: str = "session") -> None:
        self.root = Path(root)
        self.mode = str(mode or "session")
        self.root.mkdir(parents=True, exist_ok=True)
        self._mem: dict[tuple, Any] = {}
        self._lock = threading.Lock()

    def _tuple(self, store_name: str, project: str, sid: str) -> tuple:
        if self.mode == "project":
            return (store_name, project)
        return (store_name, project, sid)

    def put(self, store_name: str, project: str, sid: str, payload: Any) -> None:
        key = self._tuple(store_name, project, sid)
        path = self.root / make_key(store_name, project, sid, mode=self.mode)
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(payload, sort_keys=True)
        with self._lock:
            self._mem[key] = payload
            path.write_text(raw, encoding="utf-8")

    def get(self, store_name: str, project: str, sid: str) -> Any:
        key = self._tuple(store_name, project, sid)
        with self._lock:
            if key in self._mem:
                return self._mem[key]
        path = self.root / make_key(store_name, project, sid, mode=self.mode)
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
        return None


__all__ = [
    "KEY_SHAPE_PROJECT",
    "KEY_SHAPE_SESSION",
    "KEY_TEMPLATE_PROJECT",
    "KEY_TEMPLATE_SESSION",
    "SessionKeyedStore",
    "make_key",
]
