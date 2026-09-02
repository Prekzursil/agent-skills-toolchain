#!/usr/bin/env python3
"""Public half of withdrawal under PR-ONLY: revert is a pull request, not a direct write."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from clock import NamedClock
from registry import PKG, PrivateRegistry


class DirectIndexWriteRefused(Exception):
    pass


class PublicIndex:
    """Public index mutated only by merging a pull request."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        if not self.path.is_file():
            self._write({"kind": "public-index", "packages": {}})

    def _read(self) -> dict[str, Any]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, doc: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(doc, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    def seed_from_registry(self, registry: PrivateRegistry, package: str = PKG) -> None:
        versions = {
            ver: {"state": rec["state"]}
            for ver, rec in registry.list_versions(package).items()
        }
        doc = self._read()
        doc["packages"][package] = {"versions": versions}
        self._write(doc)

    def apply_merged_pr(self, pr: "PullRequest") -> None:
        doc = self._read()
        pkg = doc.setdefault("packages", {}).setdefault(pr.package, {"versions": {}})
        versions = pkg.setdefault("versions", {})
        if pr.kind != "revert-withdraw":
            raise ValueError(f"unsupported pr kind {pr.kind}")
        rec = versions.get(pr.version)
        if rec is None:
            rec = {}
        rec["state"] = "withdrawn-pending-registry-reflect"
        rec["revert_pr"] = pr.id
        versions[pr.version] = rec
        doc.setdefault("merged_prs", []).append(pr.id)
        self._write(doc)

    def direct_write(self, *_a: Any, **_k: Any) -> None:
        raise DirectIndexWriteRefused(
            "PR-ONLY: public index mutates only via merged pull request"
        )


class PullRequest:
    def __init__(self, pr_id: str, package: str, version: str, kind: str) -> None:
        self.id = pr_id
        self.package = package
        self.version = version
        self.kind = kind
        self.merged = False
        self.merge_ns: int | None = None

    def merge(self, index: PublicIndex, clock: NamedClock) -> int:
        if self.merged:
            raise RuntimeError("pr already merged")
        self.merge_ns = clock.now_ns()
        index.apply_merged_pr(self)
        self.merged = True
        return self.merge_ns


class RegistryReflector:
    """Copies a merged revert into the private registry. That copy is the exposure close."""

    def __init__(self, registry: PrivateRegistry, package: str = PKG) -> None:
        self.registry = registry
        self.package = package

    def reflect_revoke(
        self,
        version: str,
        reason: str,
        clock: NamedClock,
    ) -> int:
        at = clock.now_ns()
        self.registry.revoke(self.package, version, reason, at)
        return at
