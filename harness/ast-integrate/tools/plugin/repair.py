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

__surface__ = 'plugin.repair'

def iter_rel_files(root, *args, **kwargs):
    from pathlib import Path

    root = Path(root)
    out = {}
    if root.is_dir():
        for p in root.rglob("*"):
            if p.is_file():
                out[p.relative_to(root).as_posix()] = p
    return out


def apply_repair(repo=None, live=None, one_directional=False, dry_run=True, *args, **kwargs):
    from pathlib import Path

    from plugin.drift import (
        DIVERGED,
        IDENTICAL_MODULO_EOL,
        LIVE_AHEAD,
        REPO_AHEAD,
        classify_pair,
    )

    if repo is None and args:
        repo = args[0]
    if live is None and len(args) > 1:
        live = args[1]
    repo_files = iter_rel_files(repo)
    live_files = iter_rel_files(live)
    keys = sorted(set(repo_files) | set(live_files))
    classifications = {}
    touch = []
    refused = []
    for rel in keys:
        rb = Path(repo_files[rel]).read_bytes() if rel in repo_files else b""
        lb = Path(live_files[rel]).read_bytes() if rel in live_files else b""
        klass = classify_pair(rb, lb, one_directional=bool(one_directional))
        classifications[rel] = klass
        if klass in {REPO_AHEAD, IDENTICAL_MODULO_EOL}:
            touch.append(rel)
        if klass in {DIVERGED, LIVE_AHEAD}:
            refused.append(rel)
    applied: list[str] = []
    if not dry_run:
        live_root = Path(live)
        for rel in touch:
            src = Path(repo_files[rel])
            dest = live_root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(src.read_bytes())
            applied.append(rel)
    return {
        "classifications": classifications,
        "touch_set": touch,
        "union_files": len(keys),
        "refused": refused,
        "applied": applied,
        "dry_run": bool(dry_run),
        "repo": str(repo),
        "live": str(live),
    }

def apply_corruption(*args, **kwargs):
    return _call('apply_corruption', *args, **kwargs)

def repair_install(*args, **kwargs):
    return _call('repair_install', *args, **kwargs)

def seed_install(*args, **kwargs):
    return _call('seed_install', *args, **kwargs)







def drop_payload_member(*args, **kwargs):
    return _call('drop_payload_member', *args, **kwargs)

def load_repair_source(*args, **kwargs):
    return _call('load_repair_source', *args, **kwargs)

__all__ = ['apply_repair', 'iter_rel_files', 'apply_corruption', 'repair_install', 'seed_install', 'COMPONENT_FOR_MODE', 'CORRUPTION_MODES', 'RED_JOURNEY', 'drop_payload_member', 'load_repair_source']

def __getattr__(name: str):
    if name.startswith('_'):
        raise AttributeError(name)
    val = _NS(name)
    globals()[name] = val
    return val



from plugin.payloadutil import PAYLOAD_FILES, SKILL_REL

CORRUPTION_MODES = ("missing_file", "truncated_skill", "missing_plugin_json")
COMPONENT_FOR_MODE = {
    "missing_file": SKILL_REL,
    "truncated_skill": SKILL_REL,
    "missing_plugin_json": "plugin.json",
}
RED_JOURNEY = {
    "missing_file": "skill_read",
    "truncated_skill": "skill_read",
    "missing_plugin_json": "plugin_json",
}


def seed_install(home, blob):
    from pathlib import Path
    import json
    home = Path(home)
    blob = Path(blob)
    live = home / "live"
    live.mkdir(parents=True, exist_ok=True)
    for rel, data in PAYLOAD_FILES.items():
        dest = live / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data if isinstance(data, bytes) else str(data).encode())
    plugin = {"name": "demo", "version": "1.0.0", "skills": [SKILL_REL]}
    (live / "plugin.json").write_text(json.dumps(plugin, indent=2) + "\n", encoding="utf-8")
    sidecar = home / "repair-source.json"
    payload = {rel: (live / rel).read_text(encoding="utf-8") for rel in list(PAYLOAD_FILES) + ["plugin.json"] if (live / rel).is_file()}
    sidecar.write_text(json.dumps({"plugin": "demo", "files": payload, "_sidecar_path": str(sidecar)}, indent=2), encoding="utf-8")
    blob.write_bytes(b"blob")
    return {"live_root": str(live), "home": str(home), "sidecar": str(sidecar)}


def apply_corruption(live, mode: str):
    from pathlib import Path
    live = Path(live)
    component = COMPONENT_FOR_MODE[mode]
    target = live / component
    if mode == "missing_file":
        if target.is_file():
            target.unlink()
    elif mode == "truncated_skill":
        target.write_bytes(b"#")
    elif mode == "missing_plugin_json":
        p = live / "plugin.json"
        if p.is_file():
            p.unlink()
    return {"mode": mode, "component": component, "path": str(target)}


def load_repair_source(home, name: str):
    from pathlib import Path
    import json
    sidecar = Path(home) / "repair-source.json"
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    data["_sidecar_path"] = str(sidecar)
    return data


def drop_payload_member(sidecar, rel: str):
    from pathlib import Path
    import json
    sidecar = Path(sidecar)
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    files = data.get("files") or {}
    files.pop(rel, None)
    data["files"] = files
    sidecar.write_text(json.dumps(data, indent=2), encoding="utf-8")


def repair_install(home):
    from pathlib import Path
    import json
    home = Path(home)
    live = home / "live"
    sidecar = home / "repair-source.json"
    restored = []
    unrepairable = []
    if not sidecar.is_file():
        return {"ok": False, "restored": restored, "unrepairable": ["sidecar"]}
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    files = data.get("files") or {}
    for rel, content in files.items():
        dest = live / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        restored.append({"path": rel})
    for rel in (SKILL_REL, "plugin.json"):
        if rel not in files and not (live / rel).is_file():
            unrepairable.append(rel)
    return {"ok": not unrepairable, "restored": restored, "unrepairable": unrepairable}
