#!/usr/bin/env python3
"""Isolated canary-profile client that resolves against the private registry."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from registry import CURRENT, DEPRECATED, PKG, REVOKED, PrivateRegistry, _semver


class IsolationError(Exception):
    pass


class CanaryClient:
    """Install/resolve inside a throwaway profile. Never uses the owner HOME."""

    def __init__(
        self,
        profile: Path,
        registry: PrivateRegistry,
        owner_home: Path,
        package: str = PKG,
    ) -> None:
        self.profile = Path(profile).resolve()
        self.registry = registry
        self.owner_home = Path(owner_home).resolve()
        self.package = package
        self._assert_isolated()
        (self.profile / ".rel0023-isolated").write_text(
            "isolated\n", encoding="utf-8", newline="\n"
        )
        (self.profile / "warnings.log").touch()

    def _assert_isolated(self) -> None:
        prof = self.profile
        home = self.owner_home
        if prof == home:
            raise IsolationError("canary profile resolved to owner HOME")
        if home in prof.parents:
            raise IsolationError("canary profile is inside owner HOME")
        self.profile.mkdir(parents=True, exist_ok=True)

    def _installed_path(self) -> Path:
        return self.profile / "installed.json"

    def _payload_path(self) -> Path:
        return self.profile / "payload.txt"

    def installed(self) -> dict[str, Any] | None:
        p = self._installed_path()
        if not p.is_file():
            return None
        return json.loads(p.read_text(encoding="utf-8"))

    def execute(self) -> str:
        rec = self.installed()
        if rec is None:
            raise IsolationError("nothing installed")
        return self._payload_path().read_text(encoding="utf-8")

    def _persist_install(self, version: str, rec: dict[str, Any], warning: str | None) -> None:
        body = rec["payload"]
        self._payload_path().write_text(body, encoding="utf-8", newline="\n")
        doc = {
            "package": self.package,
            "version": version,
            "state_at_install": rec["state"],
            "warning": warning,
        }
        self._installed_path().write_text(
            json.dumps(doc, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        if warning:
            with (self.profile / "warnings.log").open("a", encoding="utf-8", newline="\n") as fh:
                fh.write(warning + "\n")

    def _warning_for(self, version: str, rec: dict[str, Any]) -> str | None:
        if rec["state"] != DEPRECATED:
            return None
        dep = rec["deprecated"] or {}
        successor = dep.get("successor") or ""
        reason = dep.get("reason") or ""
        return (
            f"DEPRECATED {self.package}@{version}: {reason}; "
            f"successor={self.package}@{successor}"
        )

    def fresh_install(self) -> dict[str, Any]:
        """Fresh resolve: revoked versions are not candidates."""
        versions = self.registry.list_versions(self.package)
        live = [v for v, rec in versions.items() if rec["state"] != REVOKED]
        if not live:
            return {
                "action": "NO_RESOLVE",
                "version": None,
                "warning": None,
                "reason": "no-non-revoked-version",
            }
        version = sorted(live, key=_semver)[-1]
        rec = versions[version]
        warning = self._warning_for(version, rec)
        self._persist_install(version, rec, warning)
        return {
            "action": "INSTALL_OK",
            "version": version,
            "warning": warning,
            "reason": "fresh-highest-non-revoked",
            "executed": self.execute(),
        }

    def move_to(self, target: str) -> dict[str, Any]:
        """Installed client offered a specific version (upgrade/move)."""
        rec = self.registry.get(self.package, target)
        if rec["state"] == REVOKED:
            return {
                "action": "REFUSE_MOVE",
                "version": self.installed()["version"] if self.installed() else None,
                "offered": target,
                "warning": None,
                "reason": "offered-version-revoked",
            }
        warning = self._warning_for(target, rec)
        self._persist_install(target, rec, warning)
        return {
            "action": "MOVE_OK",
            "version": target,
            "offered": target,
            "warning": warning,
            "reason": "move-accepted",
            "executed": self.execute(),
        }

    def next_resolve(self) -> dict[str, Any]:
        """What an already-installed client does at its next resolve."""
        inst = self.installed()
        if inst is None:
            return self.fresh_install()
        rec = self.registry.get(self.package, inst["version"])
        if rec["state"] == REVOKED:
            # Bytes already on disk are not uninstalled. The client keeps
            # running them unaware of a withdrawal of the installed copy.
            return {
                "action": "KEEP_RUNNING_UNAWARE",
                "version": inst["version"],
                "warning": None,
                "reason": "already-installed-revoked-copy-not-withdrawn",
                "executed": self.execute(),
                "bytes_unchanged": self.execute() == rec["payload"],
            }
        if rec["state"] == DEPRECATED:
            warning = self._warning_for(inst["version"], rec)
            with (self.profile / "warnings.log").open(
                "a", encoding="utf-8", newline="\n"
            ) as fh:
                fh.write(warning + "\n")
            return {
                "action": "WARN_STAY",
                "version": inst["version"],
                "warning": warning,
                "reason": "installed-version-deprecated",
                "executed": self.execute(),
            }
        return {
            "action": "STAY_CURRENT",
            "version": inst["version"],
            "warning": None,
            "reason": "installed-version-current",
            "executed": self.execute(),
        }

    def isolation_record(self) -> dict[str, Any]:
        return {
            "profile": str(self.profile),
            "owner_home": str(self.owner_home),
            "isolated": True,
            "owner_home_untouched": not _touches(self.profile, self.owner_home),
        }


def _touches(profile: Path, owner_home: Path) -> bool:
    try:
        profile.relative_to(owner_home)
        return True
    except ValueError:
        return False
