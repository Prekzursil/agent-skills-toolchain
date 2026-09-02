#!/usr/bin/env python3
"""snapshot_ring.py -- bounded save-snapshot ring + auto-rollback (HGT-safe-restore)
for a LIVE Battle Cats EN (jp.co.ponos.battlecatsen) save on rooted BlueStacks.

Rides the ``bcsfe-save-roundtrip`` bus (do NOT reinvent the save I/O discipline):
  * SAVE_DATA at /data/data/<pkg>/files/SAVE_DATA (~539 KB primary).
  * PULL byte-exact AFTER a KEYCODE_HOME flush -- backgrounding flushes BC's RAM
    copy to disk; ``force-stop`` does NOT flush.
  * PUSH in place via ``cat >`` so the inode + owner (uid 10065) + SELinux
    app_data_file context survive; ``am force-stop`` FIRST so autosave cannot
    clobber the restore; ``md5sum`` verify device == snapshot afterwards.
  * The MSYS empty-wipe trap: a 0-byte / short file must NEVER be stored as a good
    snapshot NOR pushed back -- that is exactly how a save gets wiped
    (md5 d41d8cd98f00b204e9800998ecf8427e). Size + md5 are gated here.

HGT-safe-restore -- the discipline this module automates:
  keep a rotating ring of known-good PRE-EDIT snapshots so ANY broken / suspect
  state can be rolled back to the last verified save. On a broken state: kill hooks
  + restart BC first, then restore the newest verified snapshot.

SAFETY / shadow-mode (council C5): a ``snapshot`` (read-only pull) and an EXPLICIT
operator ``rollback`` are always real. AUTOMATIC rollback (triggered by a health
guard) defaults to SHADOW -- it LOGS "would restore <snap>" and does NOT mutate the
live save unless armed with ``enforce=True``. It never blocks and never nags.

CLI:
  python snapshot_ring.py snap [label]          # flush+pull a byte-exact snapshot
  python snapshot_ring.py list                  # show the ring (newest first)
  python snapshot_ring.py rollback [index]      # EXPLICIT restore (index in `list`)
  python snapshot_ring.py verify                # md5 device vs newest snapshot
  python snapshot_ring.py prune                 # enforce capacity + drop orphans
Env: BC_ADB (default adb), BC_SERIAL (default 127.0.0.1:5555),
     BC_RING_DIR (default <skill>/.save-ring), BC_RING_CAP (default 10).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from typing import Callable, Optional, Protocol, runtime_checkable

PKG = "jp.co.ponos.battlecatsen"
SAVE_PATH = f"/data/data/{PKG}/files/SAVE_DATA"
# A real primary save is ~539 KB; the empty-wipe was 0 bytes. Anything below this
# is treated as corrupt: never stored as good, never pushed back.
MIN_SAVE_BYTES = 4096
DEFAULT_CAPACITY = 10
MANIFEST_NAME = "ring.json"

log = logging.getLogger("bc.snapshot_ring")


def md5_hex(data: bytes) -> str:
    """md5 of a byte blob (matches on-device ``md5sum`` for integrity checks)."""
    return hashlib.md5(  # noqa: S324 (integrity check, not crypto)
        data, usedforsecurity=False
    ).hexdigest()


@dataclass(frozen=True)
class Snapshot:
    """One immutable pre-edit save snapshot on the host."""

    ts: float
    path: str
    md5: str
    size: int
    label: str = ""
    verified: bool = False

    @property
    def ok(self) -> bool:
        """A snapshot is restorable only if it is verified and large enough."""
        return self.verified and self.size >= MIN_SAVE_BYTES

    def to_json(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_json(d: dict) -> "Snapshot":
        return Snapshot(
            ts=float(d["ts"]),
            path=str(d["path"]),
            md5=str(d["md5"]),
            size=int(d["size"]),
            label=str(d.get("label", "")),
            verified=bool(d.get("verified", False)),
        )


@runtime_checkable
class SaveIO(Protocol):
    """Injectable save-I/O seam. The default :class:`AdbSaveIO` shells to adb; tests
    inject a fake. Keeps all device coupling out of the ring logic."""

    def flush(self) -> None:
        """Background BC (KEYCODE_HOME) so its RAM save is flushed to disk."""

    def pull(self) -> bytes:
        """Return the live SAVE_DATA bytes (byte-exact)."""

    def force_stop(self) -> None:
        """``am force-stop`` the package so autosave cannot race a restore."""

    def push(self, data: bytes) -> None:
        """Restore ``data`` in place (inode/uid/SELinux-context-preserving)."""

    def device_md5(self) -> str:
        """md5sum of the live SAVE_DATA on device (post-restore verification)."""


class AdbSaveIO:
    """Real adb-backed save I/O. Encodes the bcsfe-save-roundtrip discipline:
    HOME-flush pull, force-stop-first + in-place ``cat >`` restore, md5 verify."""

    def __init__(
        self,
        adb: Optional[str] = None,
        serial: Optional[str] = None,
        flush_wait_s: float = 3.0,
    ) -> None:
        self.adb = adb or os.environ.get("BC_ADB", "adb")
        self.serial = serial or os.environ.get("BC_SERIAL", "127.0.0.1:5555")
        self.flush_wait_s = flush_wait_s

    def _run(
        self, *args: str, binary: bool = False, want_input: Optional[bytes] = None
    ):
        cmd = [self.adb, "-s", self.serial, *args]
        if binary:
            return subprocess.run(
                cmd, stdout=subprocess.PIPE, input=want_input, check=True
            ).stdout
        return subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=True
        ).stdout.strip()

    def flush(self) -> None:
        self._run("shell", "input", "keyevent", "KEYCODE_HOME")
        time.sleep(self.flush_wait_s)

    def pull(self) -> bytes:
        # exec-out cat streams the file byte-exact (no /sdcard hop, no MSYS mangling).
        return self._run("exec-out", "su", "-c", f"cat {SAVE_PATH}", binary=True)

    def force_stop(self) -> None:
        self._run("shell", "am", "force-stop", PKG)

    def push(self, data: bytes) -> None:
        # In-place cat> reuses the existing inode so owner + SELinux context survive.
        # A fresh cp/push as root lands root:root + wrong context and BC rejects it.
        script = (
            f"cat > {SAVE_PATH}; chown 10065:10065 {SAVE_PATH}; "
            f"chmod 660 {SAVE_PATH}; restorecon {SAVE_PATH}"
        )
        self._run("exec-out", "su", "-c", script, binary=True, want_input=data)

    def device_md5(self) -> str:
        out = self._run("exec-out", "su", "-c", f"md5sum {SAVE_PATH}")
        return out.split()[0] if out else ""


class SnapshotRing:
    """Bounded ring of pre-edit save snapshots + HGT-safe auto-rollback.

    All device coupling is behind :class:`SaveIO`; the ring/rotation/rollback-decision
    logic is pure and unit-testable with a fake IO.
    """

    def __init__(
        self,
        io: SaveIO,
        ring_dir: str,
        capacity: int = DEFAULT_CAPACITY,
        min_bytes: int = MIN_SAVE_BYTES,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self.io = io
        self.ring_dir = ring_dir
        self.capacity = capacity
        self.min_bytes = min_bytes
        self.log = logger or log
        os.makedirs(self.ring_dir, exist_ok=True)
        self._snaps: list[Snapshot] = self._load_manifest()

    # -- persistence -------------------------------------------------------
    @property
    def _manifest_path(self) -> str:
        return os.path.join(self.ring_dir, MANIFEST_NAME)

    def _load_manifest(self) -> list[Snapshot]:
        if not os.path.exists(self._manifest_path):
            return []
        try:
            with open(self._manifest_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            return [Snapshot.from_json(d) for d in raw.get("snapshots", [])]
        except (OSError, ValueError, KeyError) as e:  # fail-open: empty ring
            self.log.warning("manifest unreadable (%s); starting empty ring", e)
            return []

    def _save_manifest(self) -> None:
        tmp = self._manifest_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"snapshots": [s.to_json() for s in self._snaps]}, f, indent=2)
        os.replace(tmp, self._manifest_path)

    # -- ring ops ----------------------------------------------------------
    def snapshot(self, label: str = "") -> Snapshot:
        """Flush + pull a byte-exact snapshot into the ring; rotate the oldest out.

        Raises ValueError if the live save reads back short/empty (corruption guard)
        so a bad read can never masquerade as a good restore point.
        """
        self.io.flush()
        data = self.io.pull()
        if len(data) < self.min_bytes:
            raise ValueError(
                f"refusing to store snapshot: live save is {len(data)} bytes "
                f"(< {self.min_bytes}); looks empty/corrupt -- not a valid restore point"
            )
        ts = time.time()
        digest = md5_hex(data)
        # Unique filename: two snapshots with identical content in the same second
        # must NOT collide (else rotating the oldest deletes the shared file).
        fname = f"save-{int(ts)}-{digest[:8]}-{os.urandom(4).hex()}.bin"
        fpath = os.path.join(self.ring_dir, fname)
        with open(fpath, "wb") as f:
            f.write(data)
        snap = Snapshot(
            ts=ts, path=fpath, md5=digest, size=len(data), label=label, verified=True
        )
        self._snaps.append(snap)
        self._rotate()
        self._save_manifest()
        self.log.info(
            "snapshot stored: %s (%d bytes, md5 %s)", fname, snap.size, digest
        )
        return snap

    def _rotate(self) -> None:
        while len(self._snaps) > self.capacity:
            old = self._snaps.pop(0)
            self._unlink(old.path)

    @staticmethod
    def _unlink(path: str) -> None:
        try:
            os.remove(path)
        except OSError:
            pass

    def list(self) -> list[Snapshot]:
        """Snapshots newest-first."""
        return sorted(self._snaps, key=lambda s: s.ts, reverse=True)

    def latest_good(self) -> Optional[Snapshot]:
        """Newest snapshot that is verified and still on disk at the recorded size."""
        for s in self.list():
            if (
                s.ok
                and os.path.exists(s.path)
                and os.path.getsize(s.path) >= self.min_bytes
            ):
                return s
        return None

    def _resolve_target(self, target) -> Optional[Snapshot]:
        if target is None:
            return self.latest_good()
        if isinstance(target, Snapshot):
            return target
        if isinstance(target, int):
            ordered = self.list()
            if 0 <= target < len(ordered):
                return ordered[target]
            return None
        raise TypeError("target must be None, an int index, or a Snapshot")

    def _read_snapshot_bytes(self, snap: Snapshot) -> bytes:
        with open(snap.path, "rb") as f:
            return f.read()

    # -- rollback ----------------------------------------------------------
    def rollback(self, target=None, *, enforce: bool = True) -> dict:
        """Restore a snapshot (default: newest known-good).

        ``enforce=False`` = SHADOW: log the decision, mutate nothing. Guards:
        target must exist, be >= min_bytes, and its on-disk md5 must match the
        recorded md5 (never push a corrupted backup over a live save).
        """
        snap = self._resolve_target(target)
        if snap is None:
            return {"result": "FAILED:snapshot-ring-rollback no known-good snapshot"}
        if not (snap.ok and os.path.exists(snap.path)):
            return {
                "result": f"FAILED:snapshot-ring-rollback snapshot unusable ({snap.path})"
            }
        data = self._read_snapshot_bytes(snap)
        if len(data) < self.min_bytes or md5_hex(data) != snap.md5:
            return {
                "result": "FAILED:snapshot-ring-rollback backup integrity check failed",
                "expected_md5": snap.md5,
                "actual_md5": md5_hex(data),
                "size": len(data),
            }
        if not enforce:
            msg = f"SHADOW would restore {os.path.basename(snap.path)} (md5 {snap.md5})"
            self.log.info(msg)
            return {
                "result": "SHADOW:snapshot-ring-rollback",
                "would_restore": snap.to_json(),
                "pushed": False,
            }
        # ENFORCE: force-stop first (block autosave), in-place restore, md5 verify.
        self.io.force_stop()
        self.io.push(data)
        dev_md5 = self.io.device_md5()
        verified = dev_md5 == snap.md5
        result = (
            "SUCCESS:snapshot-ring-rollback"
            if verified
            else "FAILED:snapshot-ring-rollback md5 mismatch after restore"
        )
        self.log.info("%s dev_md5=%s snap_md5=%s", result, dev_md5, snap.md5)
        return {
            "result": result,
            "restored": snap.to_json(),
            "pushed": True,
            "device_md5": dev_md5,
            "verified": verified,
        }

    def auto_rollback(
        self, is_broken: Callable[[], bool], *, enforce: bool = False
    ) -> dict:
        """HGT-safe auto-rollback. SHADOW by default (enforce=False): if ``is_broken()``
        returns True, LOG which snapshot WOULD be restored and mutate nothing. Only
        with ``enforce=True`` does it actually restore. Never blocks/nags."""
        try:
            broken = bool(is_broken())
        except Exception as e:  # a flaky health probe must not itself trigger a restore
            self.log.warning("health probe raised (%s); treating as not-broken", e)
            broken = False
        if not broken:
            return {"result": "ok", "broken": False, "action": "none"}
        target = self.latest_good()
        if target is None:
            return {
                "result": "FAILED:snapshot-ring-auto-rollback broken but no known-good snapshot",
                "broken": True,
                "action": "none",
            }
        if not enforce:
            self.log.warning(
                "SHADOW auto-rollback: state broken; would restore %s",
                os.path.basename(target.path),
            )
            return {
                "result": "SHADOW:snapshot-ring-auto-rollback",
                "broken": True,
                "would_restore": target.to_json(),
                "action": "shadow-log",
                "pushed": False,
            }
        return {
            **self.rollback(target, enforce=True),
            "broken": True,
            "action": "restore",
        }

    def prune(self) -> dict:
        """Enforce capacity and drop manifest entries whose files vanished."""
        self._snaps = [s for s in self._snaps if os.path.exists(s.path)]
        self._rotate()
        self._save_manifest()
        # Remove orphan .bin files not referenced by the manifest.
        keep = {os.path.basename(s.path) for s in self._snaps}
        removed = 0
        for name in os.listdir(self.ring_dir):
            if name.endswith(".bin") and name not in keep:
                self._unlink(os.path.join(self.ring_dir, name))
                removed += 1
        return {
            "result": "SUCCESS:snapshot-ring-prune",
            "kept": len(self._snaps),
            "orphans_removed": removed,
        }


# -- CLI -------------------------------------------------------------------
def _default_ring_dir() -> str:
    return os.environ.get(
        "BC_RING_DIR",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".save-ring"),
    )


def _default_ring() -> SnapshotRing:
    cap = int(os.environ.get("BC_RING_CAP", str(DEFAULT_CAPACITY)))
    return SnapshotRing(AdbSaveIO(), _default_ring_dir(), capacity=cap)


def _emit(obj: object) -> None:
    sys.stdout.write(json.dumps(obj, indent=2, default=str) + "\n")


def main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        sys.stdout.write(__doc__ or "")
        return 0
    cmd, rest = args[0], args[1:]
    ring = _default_ring()
    if cmd == "snap":
        _emit(ring.snapshot(rest[0] if rest else "").to_json())
    elif cmd == "list":
        _emit(
            {
                "ring_dir": ring.ring_dir,
                "capacity": ring.capacity,
                "snapshots": [s.to_json() for s in ring.list()],
            }
        )
    elif cmd == "rollback":
        idx = int(rest[0]) if rest else None
        _emit(ring.rollback(idx, enforce=True))
    elif cmd == "verify":
        good = ring.latest_good()
        if not good:
            _emit({"result": "FAILED:verify no known-good snapshot"})
            return 1
        dev = ring.io.device_md5()
        _emit(
            {
                "result": "match" if dev == good.md5 else "differ",
                "device_md5": dev,
                "snapshot_md5": good.md5,
                "snapshot": good.to_json(),
            }
        )
    elif cmd == "prune":
        _emit(ring.prune())
    else:
        sys.stdout.write(__doc__ or "")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
