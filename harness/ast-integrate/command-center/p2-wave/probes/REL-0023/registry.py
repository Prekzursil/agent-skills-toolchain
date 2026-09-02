#!/usr/bin/env python3
"""Private file-backed registry with distinct deprecation and revocation."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CURRENT = "current"
DEPRECATED = "deprecated"
REVOKED = "revoked"
STATES = (CURRENT, DEPRECATED, REVOKED)
PKG = "harness.canary"


class RegistryError(Exception):
    pass


class PrivateRegistry:
    """JSON file store. Deprecation warns; revocation blocks resolve/move."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        if not self.path.is_file():
            self._write(
                {
                    "kind": "private-file-backed-registry",
                    "packages": {},
                }
            )

    def _read(self) -> dict[str, Any]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, doc: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(doc, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        tmp.replace(self.path)

    def publish(self, package: str, version: str, payload: str) -> None:
        doc = self._read()
        pkgs = doc.setdefault("packages", {})
        pkg = pkgs.setdefault(package, {"versions": {}})
        versions = pkg.setdefault("versions", {})
        if version in versions:
            raise RegistryError(f"already published {package}@{version}")
        versions[version] = {
            "payload": payload,
            "state": CURRENT,
            "deprecated": None,
            "revoked": None,
        }
        self._write(doc)

    def get(self, package: str, version: str) -> dict[str, Any]:
        doc = self._read()
        try:
            rec = doc["packages"][package]["versions"][version]
        except KeyError as exc:
            raise RegistryError(f"missing {package}@{version}") from exc
        return rec

    def list_versions(self, package: str) -> dict[str, dict[str, Any]]:
        doc = self._read()
        try:
            return dict(doc["packages"][package]["versions"])
        except KeyError as exc:
            raise RegistryError(f"missing package {package}") from exc

    def _set_version(self, package: str, version: str, rec: dict[str, Any]) -> None:
        doc = self._read()
        doc["packages"][package]["versions"][version] = rec
        self._write(doc)

    def deprecate(
        self,
        package: str,
        version: str,
        reason: str,
        successor: str,
        at_ns: int,
    ) -> None:
        rec = self.get(package, version)
        if rec["state"] == REVOKED:
            raise RegistryError("cannot deprecate a revoked version")
        if successor == version:
            raise RegistryError("successor must differ from the deprecated version")
        try:
            self.get(package, successor)
        except RegistryError as exc:
            raise RegistryError(
                f"successor {package}@{successor} does not exist"
            ) from exc
        rec["state"] = DEPRECATED
        rec["deprecated"] = {
            "reason": reason,
            "successor": successor,
            "at_ns": at_ns,
        }
        self._set_version(package, version, rec)

    def revoke(self, package: str, version: str, reason: str, at_ns: int) -> None:
        rec = self.get(package, version)
        rec["state"] = REVOKED
        rec["revoked"] = {"reason": reason, "at_ns": at_ns}
        self._set_version(package, version, rec)

    def highest_resolvable(self, package: str) -> str | None:
        versions = self.list_versions(package)
        live = [v for v, rec in versions.items() if rec["state"] != REVOKED]
        if not live:
            return None
        return sorted(live, key=_semver)[-1]


def _semver(ver: str) -> tuple[int, ...]:
    return tuple(int(p) for p in ver.split("."))
