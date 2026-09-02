"""Deprecated vs revoked install states (IMP-0101)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from marketplace.warning_channel import CHANNEL, USER_CHANNEL_SOURCE

PKG = "wf.example.pack"
DEPRECATED_VER = "1.2.0"
REVOKED_VER = "1.0.0"
SUCCESSOR_VER = "1.3.0"


class SuccessorDoesNotExist(ValueError):
    """Successor package is not in the registry."""


class DeprecationRegistry:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "registry.json"
        if self.path.is_file():
            self.doc = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self.doc = {"packages": {}}
            self._save()

    def _save(self) -> None:
        self.path.write_text(json.dumps(self.doc, indent=2) + "\n", encoding="utf-8")

    def _pkg(self, name: str) -> dict[str, Any]:
        packages = self.doc.setdefault("packages", {})
        return packages.setdefault(name, {"versions": {}})

    def publish(self, name: str, version: str, payload: str = "") -> None:
        rec = self._pkg(name)["versions"].setdefault(version, {})
        rec["state"] = "current"
        rec["payload"] = payload
        self._save()

    def get(self, name: str, version: str) -> dict[str, Any]:
        return dict(self._pkg(name)["versions"].get(version) or {})

    def deprecate(self, name: str, version: str, reason: str, successor: str) -> None:
        pkg_name, _, suc_ver = successor.partition("@")
        if suc_ver:
            suc = self._pkg(pkg_name)["versions"].get(suc_ver)
            if not suc:
                raise SuccessorDoesNotExist(successor)
        else:
            if pkg_name not in self.doc.get("packages", {}):
                raise SuccessorDoesNotExist(successor)
        rec = self._pkg(name)["versions"].setdefault(version, {})
        rec["state"] = "deprecated"
        rec["reason"] = reason
        rec["successor"] = successor if "@" in successor else f"{successor}@{SUCCESSOR_VER}"
        self._save()
        self._write_user_warning(name, version, rec["successor"])

    def _write_user_warning(self, name: str, version: str, successor: str) -> None:
        warning = {
            "channel": CHANNEL,
            "visible": True,
            "source": USER_CHANNEL_SOURCE,
            "message": f"{name}@{version} is deprecated; install {successor}",
            "successor": successor,
        }
        path = self.root / "user-warnings.jsonl"
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(warning) + "\n")

    def install(self, name: str, version: str) -> dict[str, Any]:
        rec = self.get(name, version)
        state = rec.get("state") or "current"
        if state == "revoked":
            return {"ok": False, "installed": False, "state": state, "version": version}
        dest = self.root / "installed" / f"{name}@{version}"
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "VERSION").write_text(version + "\n", encoding="utf-8")
        warning = {}
        if state == "deprecated":
            successor = rec.get("successor") or f"{name}@{SUCCESSOR_VER}"
            if "@" not in str(successor):
                successor = f"{name}@{successor}"
            warning = {
                "successor": successor,
                "message": f"{name}@{version} is deprecated; install {successor}",
            }
            self._write_user_warning(name, version, successor)
        return {
            "ok": True,
            "installed": True,
            "state": state,
            "version": version,
            "warning": warning,
        }

    def health_check(self) -> dict[str, Any]:
        path = self.root / "user-warnings.jsonl"
        messages = []
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                messages.append(json.loads(line))
        return {
            "source": USER_CHANNEL_SOURCE,
            "degraded": bool(messages),
            "warning_count": len(messages),
            "messages": messages,
        }


def seed_catalog_registry(root: Path) -> DeprecationRegistry:
    reg = DeprecationRegistry(root)
    reg.publish(PKG, SUCCESSOR_VER, payload="successor")
    reg.publish(PKG, DEPRECATED_VER, payload="old")
    reg.publish(PKG, REVOKED_VER, payload="revoked")
    rec = reg._pkg(PKG)["versions"][REVOKED_VER]
    rec["state"] = "revoked"
    reg.deprecate(PKG, DEPRECATED_VER, reason="superseded", successor=f"{PKG}@{SUCCESSOR_VER}")
    return reg


def run_catalog_evidence(root: Path) -> dict[str, Any]:
    root = Path(root)
    reg = seed_catalog_registry(root)
    dep = reg.install(PKG, DEPRECATED_VER)
    rev = reg.install(PKG, REVOKED_VER)
    listed = sorted(reg._pkg(PKG)["versions"])
    warnings = root / "user-warnings.jsonl"
    return {
        "deprecated_install": dep,
        "revoked": rev,
        "warning_persisted": warnings.is_file() and warnings.stat().st_size > 0,
        "still_listed": DEPRECATED_VER in listed,
        "states_are_aliases": dep.get("ok") == rev.get("ok"),
    }
