"""Isolated package client whose own resolution_order is the drill's SSOT.

Cache locations are consulted in order. First hit wins. A stale copy in any
earlier location masks the install tree. Refresh invalidates every reachable
cache location so execute() observes install-tree bytes.

Unreachable inventory rows (Windows live cache, owner HOME cache, missing
product module) are declared, never silently omitted.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from packages import OLD, PACKAGE_NAME, Package, behaviour_from_bytes

PRODUCT_CACHE_PY = Path("platform/plugin/cache.py")
WINDOWS_CACHE = r"%LOCALAPPDATA%\ast-integrate\plugin-cache"


class IsolationError(RuntimeError):
    pass


def owner_home() -> Path:
    return Path.home().resolve()


def assert_isolated(profile: Path) -> None:
    prof = profile.resolve()
    home = owner_home()
    if prof == home or home in prof.parents:
        raise IsolationError(
            f"profile {prof} resolves under owner home {home}; drill aborted"
        )
    # Refuse to use a profile that IS the real HOME even if HOME was redirected.
    real = Path(os.path.expanduser("~")).resolve()
    if prof == real:
        raise IsolationError(f"profile {prof} is the expanded user home")


@dataclass
class Location:
    id: str
    relpath: str
    reachable: bool
    reason: str
    kind: str  # bytecode | unpacked | http | cas | install | unreachable

    def path(self, profile: Path) -> Path:
        return (profile / self.relpath).resolve()


def inventory_template() -> list[Location]:
    product = Path("/opt/p2/ast-integrate") / PRODUCT_CACHE_PY
    product_present = product.is_file()
    return [
        Location(
            "bytecode",
            "cache/bytecode/" + PACKAGE_NAME + ".pyc",
            True,
            "reachable: isolated bytecode cache the client consults first",
            "bytecode",
        ),
        Location(
            "unpacked-user-cache",
            "cache/unpacked/" + PACKAGE_NAME + "/payload.json",
            True,
            "reachable: unpacked user cache copy consulted after bytecode",
            "unpacked",
        ),
        Location(
            "http-tarball-cache",
            "cache/http/" + PACKAGE_NAME + ".tar.json",
            True,
            "reachable: download cache of the previous package tarball",
            "http",
        ),
        Location(
            "cas-name-index",
            "cache/cas/index.json",
            True,
            "reachable: name-index pointer into the content-addressed blob store",
            "cas",
        ),
        Location(
            "install-tree",
            "install/" + PACKAGE_NAME + "/payload.json",
            True,
            "reachable: install tree written by the candidate install step",
            "install",
        ),
        Location(
            "product-platform-plugin-cache",
            PRODUCT_CACHE_PY.as_posix(),
            False,
            (
                "NOT-CHECKED: platform/plugin/cache.py "
                + ("present but not imported; drill stays in isolated replica" if product_present else "absent on this sparse worktree")
            ),
            "unreachable",
        ),
        Location(
            "windows-localappdata-plugin-cache",
            WINDOWS_CACHE,
            False,
            "NOT-CHECKED: Linux worktree; isolation forbids substituting the owner's live Windows profile",
            "unreachable",
        ),
        Location(
            "owner-live-home-cache",
            str(owner_home() / ".cache" / "ast-integrate"),
            False,
            "NOT-CHECKED: isolation assertion forbids seeding or reading the owner's live cache",
            "unreachable",
        ),
    ]


class Client:
    """Package client bound to one throwaway profile."""

    def __init__(self, profile: Path):
        assert_isolated(profile)
        self.profile = profile.resolve()
        self.profile.mkdir(parents=True, exist_ok=True)
        self._inventory = inventory_template()
        self._version_path = self.profile / "install" / PACKAGE_NAME / "VERSION"
        self._cas_dir = self.profile / "cache" / "cas" / "blobs"
        self._cas_dir.mkdir(parents=True, exist_ok=True)
        self._assert_paths_under_profile()

    def _assert_paths_under_profile(self) -> None:
        root = self.profile
        for loc in self._inventory:
            if not loc.reachable:
                continue
            p = loc.path(self.profile)
            if p != root and root not in p.parents:
                raise IsolationError(f"location {loc.id} path {p} escapes profile {root}")

    def inventory(self) -> list[Location]:
        return list(self._inventory)

    def resolution_order(self) -> list[Location]:
        """Runtime lookup order. Unreachable rows are not consulted."""
        order_ids = [
            "bytecode",
            "unpacked-user-cache",
            "http-tarball-cache",
            "cas-name-index",
            "install-tree",
        ]
        by_id = {loc.id: loc for loc in self._inventory if loc.reachable}
        return [by_id[i] for i in order_ids]

    def loc(self, loc_id: str) -> Location:
        for loc in self._inventory:
            if loc.id == loc_id:
                return loc
        raise KeyError(loc_id)

    def _index_path(self) -> Path:
        return self.loc("cas-name-index").path(self.profile)

    def _read_index(self) -> dict:
        p = self._index_path()
        if not p.is_file():
            return {}
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return doc if isinstance(doc, dict) else {}

    def _write_index(self, doc: dict) -> None:
        p = self._index_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )

    def _cas_put(self, payload: bytes) -> str:
        key = hashlib.sha256(payload).hexdigest()
        blob = self._cas_dir / key
        blob.write_bytes(payload)
        return key

    def _cas_get(self, key: str) -> bytes | None:
        blob = self._cas_dir / key
        if not blob.is_file():
            return None
        return blob.read_bytes()

    def _write_payload_file(self, path: Path, payload: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)

    def seed_poison(self, pkg: Package = OLD) -> list[str]:
        """Write stale previous-package bytes into every reachable cache location."""
        payload = pkg.payload()
        seeded: list[str] = []
        for loc in self.resolution_order():
            if loc.kind == "install":
                continue
            self._seed_one(loc, payload, pkg)
            seeded.append(loc.id)
        return seeded

    def _seed_one(self, loc: Location, payload: bytes, pkg: Package) -> None:
        if loc.kind == "bytecode":
            self._write_payload_file(loc.path(self.profile), b"PYC\0" + payload)
        elif loc.kind in {"unpacked", "http"}:
            self._write_payload_file(loc.path(self.profile), payload)
        elif loc.kind == "cas":
            key = self._cas_put(payload)
            idx = self._read_index()
            idx[pkg.name] = key
            self._write_index(idx)
        else:
            raise RuntimeError(f"cannot seed kind {loc.kind}")

    def install(self, pkg: Package, refresh: bool = False) -> None:
        """Write candidate bytes to the install tree. Caches stay unless refresh."""
        loc = self.loc("install-tree")
        self._write_payload_file(loc.path(self.profile), pkg.payload())
        self._version_path.parent.mkdir(parents=True, exist_ok=True)
        self._version_path.write_text(pkg.version + "\n", encoding="utf-8")
        if refresh:
            self.refresh()

    def refresh(self, layers: list[str] | None = None) -> list[str]:
        """Invalidate reachable cache locations, then re-index from install-tree.

        `layers` names a subset (mutation control). None means every cache layer.
        """
        cache_ids = [
            "bytecode",
            "unpacked-user-cache",
            "http-tarball-cache",
            "cas-name-index",
        ]
        chosen = cache_ids if layers is None else [i for i in cache_ids if i in layers]
        cleared: list[str] = []
        for loc_id in chosen:
            loc = self.loc(loc_id)
            path = loc.path(self.profile)
            if loc.kind == "cas":
                if path.is_file():
                    path.unlink()
                # Drop blobs so a leftover name-index cannot revive old bytes
                # if the index is also cleared. When mutating to skip cas,
                # blobs remain.
                if layers is None or "cas-name-index" in chosen:
                    for blob in self._cas_dir.glob("*"):
                        if blob.is_file():
                            blob.unlink()
            elif path.is_file():
                path.unlink()
            cleared.append(loc_id)
        if layers is None:
            self._reindex_from_install()
        return cleared

    def _reindex_from_install(self) -> None:
        raw = self.loc("install-tree").path(self.profile)
        if not raw.is_file():
            return
        payload = raw.read_bytes()
        key = self._cas_put(payload)
        self._write_index({PACKAGE_NAME: key})

    def _read_location(self, loc: Location) -> bytes | None:
        if loc.kind == "cas":
            idx = self._read_index()
            key = idx.get(PACKAGE_NAME)
            if not isinstance(key, str):
                return None
            return self._cas_get(key)
        path = loc.path(self.profile)
        if not path.is_file():
            return None
        return path.read_bytes()

    def execute(self) -> str | None:
        """Run the first payload found in the client's own resolution order."""
        for loc in self.resolution_order():
            raw = self._read_location(loc)
            behaviour = behaviour_from_bytes(raw)
            if behaviour:
                return behaviour
        return None

    def execute_from(self, loc_id: str) -> str | None:
        return behaviour_from_bytes(self._read_location(self.loc(loc_id)))

    def version(self) -> str | None:
        if not self._version_path.is_file():
            return None
        text = self._version_path.read_text(encoding="utf-8").strip()
        return text or None

    def hit_location(self) -> str | None:
        for loc in self.resolution_order():
            if behaviour_from_bytes(self._read_location(loc)):
                return loc.id
        return None


def with_fresh_profile(fn: Callable[[Client], object]) -> object:
    import tempfile

    with tempfile.TemporaryDirectory(prefix="rel0020-") as tmp:
        client = Client(Path(tmp) / "profile")
        return fn(client)
