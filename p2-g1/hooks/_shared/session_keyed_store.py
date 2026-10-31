"""Session-keyed harness state store (IMP-0430).

Every harness state store is keyed by the template
{store}|{project_id}|{session_id}. A project-only key bleeds one session's
goal/state into a concurrent sibling; ProjectKeyedMutant reproduces that
defect for the bleed probe. Filesystem names slug the separators.
"""
from __future__ import annotations

import json as _json
from pathlib import Path

KEY_TEMPLATE = "{store}|{project_id}|{session_id}"
PROJECT_MUTANT_TEMPLATE = "{store}|{project_id}"


def state_key(store: str, project_id: str, session_id: str) -> str:
    return KEY_TEMPLATE.format(store=store, project_id=project_id, session_id=session_id)


def _slug(key: str) -> str:
    return key.replace("|", "__").replace("/", "-").replace(chr(92), "-")


class SessionKeyedStore:
    def __init__(self, store: str, root: Path) -> None:
        self.store = store
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.root / (_slug(key) + ".json")

    def write(self, project_id: str, session_id: str, body: dict) -> Path:
        p = self._path(state_key(self.store, project_id, session_id))
        p.write_text(_json.dumps(body, indent=2, sort_keys=True), encoding="utf-8")
        return p

    def read(self, project_id: str, session_id: str) -> dict:
        p = self._path(state_key(self.store, project_id, session_id))
        if not p.is_file():
            return {}
        return _json.loads(p.read_text(encoding="utf-8"))


class ProjectKeyedMutant(SessionKeyedStore):
    """Defect replica: two sessions in one project share a single key."""

    @staticmethod
    def mutant_key(store: str, project_id: str) -> str:
        return PROJECT_MUTANT_TEMPLATE.format(store=store, project_id=project_id)

    def write(self, project_id: str, session_id: str, body: dict) -> Path:
        p = self._path(self.mutant_key(self.store, project_id))
        p.write_text(_json.dumps(body, indent=2, sort_keys=True), encoding="utf-8")
        return p

    def read(self, project_id: str, session_id: str) -> dict:
        p = self._path(self.mutant_key(self.store, project_id))
        if not p.is_file():
            return {}
        return _json.loads(p.read_text(encoding="utf-8"))


__all__ = ["KEY_TEMPLATE", "PROJECT_MUTANT_TEMPLATE", "ProjectKeyedMutant",
           "SessionKeyedStore", "state_key"]
