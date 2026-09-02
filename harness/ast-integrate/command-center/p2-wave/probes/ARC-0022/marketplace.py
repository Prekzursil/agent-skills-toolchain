"""Fixture marketplace and contracted A3 install state machine.

The registry index is the control plane. Every local capability arrives as an
installed, versioned, lockfile-pinned package. This module is the executable
fixture for ARC-0022; it does not write command-center/phase3/A3/DESIGN.json.
"""
from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass, field
from typing import Iterable

OWNER_HMAC = "fixture-owner-hmac-not-a-secret"
CHANNEL = "stable"

STATES = (
    "absent",
    "resolving",
    "fetching",
    "verifying",
    "staging",
    "active",
    "cache_corrupt",
    "quarantined",
    "failed",
)

EVENTS = (
    "install",
    "upgrade",
    "downgrade",
    "rollback",
    "uninstall",
    "offline_install",
    "resolved",
    "fetched",
    "verified",
    "committed",
    "malicious",
    "cache_corrupt",
    "recover",
    "abort",
    "export_found",
    "export_missing",
)

# Every (state, event) not listed here is explicitly REJECTED (no implicit self-loop).
DEFINED: dict[tuple[str, str], str] = {
    ("absent", "install"): "resolving",
    ("absent", "offline_install"): "resolving",
    ("absent", "abort"): "absent",
    ("resolving", "resolved"): "fetching",
    ("resolving", "export_found"): "fetching",
    ("resolving", "export_missing"): "failed",
    ("resolving", "abort"): "failed",
    ("fetching", "fetched"): "verifying",
    ("fetching", "cache_corrupt"): "cache_corrupt",
    ("fetching", "abort"): "failed",
    ("verifying", "verified"): "staging",
    ("verifying", "malicious"): "quarantined",
    ("verifying", "abort"): "failed",
    ("staging", "committed"): "active",
    ("staging", "abort"): "failed",
    ("active", "upgrade"): "resolving",
    ("active", "downgrade"): "resolving",
    ("active", "rollback"): "resolving",
    ("active", "uninstall"): "absent",
    ("active", "cache_corrupt"): "cache_corrupt",
    ("active", "abort"): "active",
    ("cache_corrupt", "recover"): "fetching",
    ("cache_corrupt", "uninstall"): "absent",
    ("cache_corrupt", "abort"): "failed",
    ("quarantined", "uninstall"): "absent",
    ("quarantined", "abort"): "quarantined",
    ("failed", "install"): "resolving",
    ("failed", "offline_install"): "resolving",
    ("failed", "recover"): "fetching",
    ("failed", "uninstall"): "absent",
    ("failed", "abort"): "absent",
}

ALL_GUARDS = frozenset(
    {
        "G_PIN",
        "G_VERIFY",
        "G_DOWNGRADE_WINDOW",
        "G_ROLLBACK_PREV",
        "G_UNINSTALL_CLEAN",
        "G_OFFLINE_EXPORT",
        "G_CACHE_REVALIDATE",
        "G_MALICE",
    }
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sign_digest(digest: str) -> str:
    return hashlib.sha256(f"{OWNER_HMAC}:{digest}".encode("utf-8")).hexdigest()


def vtuple(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for p in version.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    return tuple(parts)


@dataclass(frozen=True)
class Package:
    package_id: str
    version: str
    channel: str
    payload: bytes
    sha256: str
    signature: str
    malicious: bool = False

    def as_index_row(self) -> dict:
        return {
            "id": self.package_id,
            "version": self.version,
            "channel": self.channel,
            "sha256": self.sha256,
            "signature": self.signature,
            "malicious": self.malicious,
            "bytes": len(self.payload),
        }


def make_package(
    package_id: str,
    version: str,
    body: str,
    *,
    malicious: bool = False,
    strip_sig: bool = False,
    channel: str = CHANNEL,
) -> Package:
    payload = body.encode("utf-8")
    digest = sha256_bytes(payload)
    sig = "STRIPPED" if strip_sig else sign_digest(digest)
    return Package(
        package_id=package_id,
        version=version,
        channel=channel,
        payload=payload,
        sha256=digest,
        signature=sig,
        malicious=malicious,
    )


def fixture_packages() -> dict[tuple[str, str], Package]:
    """What the fixture registry must contain to exercise every named branch."""
    core100 = make_package("pkg.core", "1.0.0", "core-payload-1.0.0-clean")
    core110 = make_package("pkg.core", "1.1.0", "core-payload-1.1.0-upgrade")
    core090 = make_package("pkg.core", "0.9.0", "core-payload-0.9.0-downgrade")
    core120 = make_package("pkg.core", "1.2.0", "core-payload-1.2.0-latest-trap")
    evil = make_package(
        "pkg.evil",
        "1.0.0",
        "evil-payload-do-not-execute",
        malicious=True,
        strip_sig=True,
    )
    ghost = make_package("pkg.core", "0.8.0", "ghost-not-in-honest-index")
    stale110 = make_package("pkg.core", "1.1.0", "core-payload-1.1.0-BUGGY-stale-cache")
    return {
        ("pkg.core", "1.0.0"): core100,
        ("pkg.core", "1.1.0"): core110,
        ("pkg.core", "0.9.0"): core090,
        ("pkg.core", "1.2.0"): core120,
        ("pkg.evil", "1.0.0"): evil,
        ("pkg.core", "0.8.0"): ghost,
        ("pkg.core", "1.1.0-stale"): stale110,
    }


def disposition(state: str, event: str) -> dict:
    nxt = DEFINED.get((state, event))
    if nxt is None:
        return {
            "kind": "rejected",
            "next": None,
            "reason": f"{event} is not legal in {state}; no implicit self-loop",
        }
    return {"kind": "defined", "next": nxt, "reason": None}


def all_pairs() -> list[tuple[str, str]]:
    return [(s, e) for s in STATES for e in EVENTS]


def defined_pairs() -> list[tuple[str, str]]:
    return sorted(DEFINED.keys())


@dataclass
class World:
    state: str = "absent"
    guards: frozenset[str] = field(default_factory=lambda: frozenset(ALL_GUARDS))
    network: bool = True
    index: dict[tuple[str, str], Package] = field(default_factory=dict)
    cache: dict[str, dict] = field(default_factory=dict)
    exports: dict[tuple[str, str], bytes] = field(default_factory=dict)
    lockfile: dict[str, dict] = field(default_factory=dict)
    installed: dict[str, dict] = field(default_factory=dict)
    trace: list[tuple[str, str, str]] = field(default_factory=list)
    last_error: str | None = None
    abort_at: str | None = None

    def clone(self, *, guards: Iterable[str] | None = None) -> "World":
        w = copy.deepcopy(self)
        if guards is not None:
            w.guards = frozenset(guards)
        return w

    def fire(self, event: str) -> str:
        src = self.state
        nxt = DEFINED.get((src, event))
        if nxt is None:
            self.trace.append((src, event, "REJECTED"))
            self.last_error = f"rejected:{src}+{event}"
            return "REJECTED"
        self.trace.append((src, event, nxt))
        self.state = nxt
        return nxt

    def index_pkg(self, package_id: str, version: str) -> Package | None:
        return self.index.get((package_id, version))

    def cache_key(self, package_id: str, version: str) -> str:
        return f"{package_id}@{version}"

    def _corrupt(self, entry: dict | None) -> bool:
        return bool(entry) and entry.get("corrupt") is True

    def obtain_bytes(self, pkg: Package, *, offline: bool) -> bytes | None:
        cached = self.cache.get(self.cache_key(pkg.package_id, pkg.version))
        if self.state == "resolving":
            if offline:
                export = self.exports.get((pkg.package_id, pkg.version))
                if export is None:
                    self.fire("export_missing")
                    self.last_error = "export-missing"
                    return None
                self.fire("export_found")
            else:
                self.fire("resolved")
        if self._maybe_abort("fetching"):
            return None
        if offline and self.state == "fetching":
            export = self.exports.get((pkg.package_id, pkg.version))
            if "G_OFFLINE_EXPORT" not in self.guards and cached and not self._corrupt(cached):
                self.fire("fetched")
                return cached["bytes"]
            if self._corrupt(cached) and "G_OFFLINE_EXPORT" not in self.guards:
                self.fire("cache_corrupt")
                self.last_error = "cache-corrupt"
                return None
            if export is None:
                self.fire("abort")
                self.last_error = "export-missing-mid-fetch"
                return None
            self.fire("fetched")
            return export

        if cached and self._corrupt(cached):
            self.fire("cache_corrupt")
            self.last_error = "cache-corrupt"
            return None
        if cached and cached.get("sha256") != pkg.sha256:
            if "G_CACHE_REVALIDATE" in self.guards:
                if not self.network:
                    self.fire("abort")
                    self.last_error = "stale-cache-offline"
                    return None
                self.fire("fetched")
                return pkg.payload
            self.fire("fetched")
            return cached["bytes"]
        if cached and cached.get("sha256") == pkg.sha256:
            self.fire("fetched")
            return cached["bytes"]
        if not self.network:
            self.fire("abort")
            self.last_error = "network-required"
            return None
        self.fire("fetched")
        return pkg.payload

    def verify(self, pkg: Package, data: bytes) -> bool:
        if self._maybe_abort("verifying"):
            return False
        digest = sha256_bytes(data)
        sig_ok = pkg.signature == sign_digest(pkg.sha256) and not pkg.malicious
        hash_ok = digest == pkg.sha256
        if "G_MALICE" in self.guards and not sig_ok:
            self.fire("malicious")
            self.last_error = "malicious-or-unsigned"
            return False
        if "G_VERIFY" in self.guards and not hash_ok:
            self.fire("malicious")
            self.last_error = "hash-mismatch"
            return False
        self.fire("verified")
        return True

    def commit(self, pkg: Package, data: bytes) -> None:
        if self._maybe_abort("staging"):
            return
        rec = {
            "version": pkg.version,
            "bytes": data,
            "sha256": sha256_bytes(data),
            "channel": pkg.channel,
        }
        self.installed[pkg.package_id] = rec
        if "G_PIN" in self.guards:
            prev = self.lockfile.get(pkg.package_id)
            previous = None
            if prev:
                previous = {"version": prev["version"], "sha256": prev["sha256"]}
            self.lockfile[pkg.package_id] = {
                "version": pkg.version,
                "sha256": rec["sha256"],
                "channel": pkg.channel,
                "previous": previous,
            }
        self.fire("committed")

    def _maybe_abort(self, when: str) -> bool:
        if self.abort_at == when:
            self.fire("abort")
            self.last_error = f"aborted-at-{when}"
            return True
        return False

    def abort_now(self) -> str:
        return self.fire("abort")

    def _begin(self, package_id: str, version: str, event: str) -> Package | None:
        pkg = self.index_pkg(package_id, version)
        if pkg is None:
            self.last_error = f"not-in-index:{package_id}@{version}"
            if self.state in {"absent", "failed"} and event in {"install", "offline_install"}:
                self.fire(event)
                self.fire("export_missing" if event == "offline_install" else "abort")
            return None
        return pkg

    def install(
        self,
        package_id: str,
        version: str,
        *,
        offline: bool = False,
        abort_at: str | None = None,
    ) -> str:
        pkg = self.index_pkg(package_id, version)
        if pkg is None:
            self.last_error = f"not-in-index:{package_id}@{version}"
            return "failed"
        start = "offline_install" if offline else "install"
        got = self.fire(start)
        if got == "REJECTED":
            return "rejected"
        self.abort_at = abort_at
        try:
            return self._finish(pkg, offline=offline)
        finally:
            self.abort_at = None

    def upgrade(self, package_id: str, version: str, *, abort_at: str | None = None) -> str:
        pkg = self.index_pkg(package_id, version)
        if pkg is None:
            self.last_error = f"not-in-index:{package_id}@{version}"
            return "failed"
        got = self.fire("upgrade")
        if got == "REJECTED":
            return "rejected"
        self.abort_at = abort_at
        try:
            return self._finish(pkg, offline=False)
        finally:
            self.abort_at = None

    def downgrade(self, package_id: str, version: str) -> str:
        current = self.installed.get(package_id)
        pkg = self.index_pkg(package_id, version)
        if "G_DOWNGRADE_WINDOW" in self.guards:
            if current is None:
                self.last_error = "downgrade-without-install"
                if self.state == "active":
                    self.fire("abort")
                return "failed"
            if pkg is None or vtuple(version) >= vtuple(current["version"]):
                self.last_error = "downgrade-window-rejected"
                got = self.fire("downgrade")
                if got != "REJECTED":
                    self.fire("abort")
                return "failed"
        elif pkg is None:
            ghost = make_package(package_id, version, f"ghost-{version}")
            cached = self.cache.get(self.cache_key(package_id, version))
            if cached and not self._corrupt(cached):
                ghost = Package(
                    package_id=package_id,
                    version=version,
                    channel=CHANNEL,
                    payload=cached["bytes"],
                    sha256=cached["sha256"],
                    signature=sign_digest(cached["sha256"]),
                    malicious=False,
                )
            self.index[(package_id, version)] = ghost
            pkg = ghost
        got = self.fire("downgrade")
        if got == "REJECTED":
            return "rejected"
        assert pkg is not None
        return self._finish(pkg, offline=False)

    def rollback(self, package_id: str) -> str:
        pin = self.lockfile.get(package_id)
        prev = (pin or {}).get("previous") if "G_ROLLBACK_PREV" in self.guards else None
        if "G_ROLLBACK_PREV" not in self.guards:
            latest = None
            for (pid, ver), pkg in self.index.items():
                if pid != package_id:
                    continue
                if latest is None or vtuple(ver) > vtuple(latest.version):
                    latest = pkg
            if latest is None:
                self.last_error = "rollback-no-latest"
                return "failed"
            got = self.fire("rollback")
            if got == "REJECTED":
                return "rejected"
            return self._finish(latest, offline=False)
        if not prev:
            self.last_error = "rollback-no-previous-pin"
            got = self.fire("rollback")
            if got != "REJECTED":
                self.fire("abort")
            return "failed"
        pkg = self.index_pkg(package_id, prev["version"])
        if pkg is None:
            self.last_error = "rollback-previous-not-in-index"
            return "failed"
        got = self.fire("rollback")
        if got == "REJECTED":
            return "rejected"
        return self._finish(pkg, offline=False)

    def uninstall(self, package_id: str) -> str:
        got = self.fire("uninstall")
        if got == "REJECTED":
            return "rejected"
        if "G_UNINSTALL_CLEAN" in self.guards:
            self.installed.pop(package_id, None)
            self.lockfile.pop(package_id, None)
        return self.state

    def recover(self, package_id: str, version: str) -> str:
        pkg = self.index_pkg(package_id, version)
        if pkg is None:
            self.last_error = "recover-not-in-index"
            return "failed"
        got = self.fire("recover")
        if got == "REJECTED":
            return "rejected"
        self.cache.pop(self.cache_key(package_id, version), None)
        return self._finish(pkg, offline=False, skip_begin=True)

    def _finish(
        self,
        pkg: Package,
        *,
        offline: bool,
        skip_begin: bool = False,
    ) -> str:
        if not skip_begin and self.abort_at == "resolving":
            if self._maybe_abort("resolving"):
                return self.state
        data = self.obtain_bytes(pkg, offline=offline)
        if data is None:
            return self.state
        if not self.verify(pkg, data):
            return self.state
        self.commit(pkg, data)
        return self.state


def fresh_world(*, guards: Iterable[str] | None = None, network: bool = True) -> World:
    pkgs = fixture_packages()
    index = {
        k: v
        for k, v in pkgs.items()
        if k[1] != "1.1.0-stale" and k != ("pkg.core", "0.8.0")
    }
    w = World(
        state="absent",
        guards=frozenset(ALL_GUARDS if guards is None else guards),
        network=network,
        index=index,
    )
    core100 = pkgs[("pkg.core", "1.0.0")]
    w.exports[("pkg.core", "1.0.0")] = core100.payload
    return w


def seed_stale_cache(world: World) -> Package:
    stale = fixture_packages()[("pkg.core", "1.1.0-stale")]
    honest = world.index[("pkg.core", "1.1.0")]
    world.cache[world.cache_key("pkg.core", "1.1.0")] = {
        "sha256": stale.sha256,
        "bytes": stale.payload,
        "corrupt": False,
    }
    assert stale.sha256 != honest.sha256
    return stale


def seed_corrupt_cache(world: World) -> None:
    world.cache[world.cache_key("pkg.core", "1.1.0")] = {
        "sha256": "00" * 32,
        "bytes": b"\x00truncated",
        "corrupt": True,
    }


def seed_ghost_cache(world: World) -> Package:
    ghost = fixture_packages()[("pkg.core", "0.8.0")]
    world.cache[world.cache_key("pkg.core", "0.8.0")] = {
        "sha256": ghost.sha256,
        "bytes": ghost.payload,
        "corrupt": False,
    }
    return ghost
