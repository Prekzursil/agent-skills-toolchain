#!/usr/bin/env python3
"""Content-addressed cache with atomic publish and corruption recovery.

Production `tools/plugin-cache-reaper` is absent on this worktree. This module
is the live substrate TST-0097 measures: tmp + os.replace publish, integrity
on read, quarantine of corrupt entries, rebuild from source. Serving a corrupt
payload is a P0 and is never done by IntegrityCache.get.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
import time
import uuid
from pathlib import Path
from typing import Callable, Optional

PayloadBuilder = Callable[[bytes], bytes]

TRUNCATED = "truncated"
WRONG_HASH = "wrong_hash"
UNREADABLE = "unreadable_permissions"
LEFTOVER_TMP = "leftover_tmp"
INTACT = "intact"

DETECT_TRUNCATED = "meta-unparseable-or-payload-size-mismatch"
DETECT_WRONG_HASH = "payload-sha256-mismatch-against-meta"
DETECT_UNREADABLE = "st_mode-lacks-any-read-bit-or-EACCES"
DETECT_LEFTOVER_TMP = "orphan-tmp-part-not-on-publish-path"
DETECT_INTACT = "meta-parseable-size-match-sha256-match-readable"

PAYLOAD_NAME = "payload.bin"
META_NAME = "meta.json"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def render_payload(source: bytes) -> bytes:
    """Deterministic 'render' of a source blob (stand-in for a package/plugin)."""
    digest = sha256_bytes(source)
    return b"RENDERED\n" + digest.encode("ascii") + b"\n" + source


def cache_key(source: bytes, plugin_version: str = "1.0.0") -> str:
    return sha256_bytes(plugin_version.encode("utf-8") + b"\n" + sha256_bytes(source).encode("ascii"))


def _mode_grants_read(mode: int) -> bool:
    return bool(stat.S_IMODE(mode) & 0o444)


def _fsync_dir(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write_atomic_file(dest: Path, data: bytes, tmp_dir: Path, stem: str) -> Path:
    """Write data to a unique tmp file, fsync, os.replace onto dest. Returns dest."""
    tmp_dir.mkdir(parents=True, exist_ok=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    token = f"{os.getpid()}.{uuid.uuid4().hex}"
    tmp = tmp_dir / f"{stem}.{token}.part"
    with open(tmp, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(str(tmp), str(dest))
    _fsync_dir(dest.parent)
    return dest


class CacheError(RuntimeError):
    def __init__(self, reason: str, detection: str, detail: str = ""):
        super().__init__(f"{reason}:{detection}:{detail}")
        self.reason = reason
        self.detection = detection
        self.detail = detail


class IntegrityCache:
    """Published entries live under entries/<key>/. Tmp files never occupy that path."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.entries = self.root / "entries"
        self.tmp = self.root / "tmp"
        self.quarantine = self.root / "quarantine"
        self.entries.mkdir(parents=True, exist_ok=True)
        self.tmp.mkdir(parents=True, exist_ok=True)
        self.quarantine.mkdir(parents=True, exist_ok=True)
        self.events: list[dict] = []

    def entry_dir(self, key: str) -> Path:
        return self.entries / key

    def payload_path(self, key: str) -> Path:
        return self.entry_dir(key) / PAYLOAD_NAME

    def meta_path(self, key: str) -> Path:
        return self.entry_dir(key) / META_NAME

    def _record(self, **event: object) -> None:
        self.events.append(event)

    def put(
        self,
        source: bytes,
        payload: Optional[bytes] = None,
        plugin_version: str = "1.0.0",
        interrupt_before_replace: bool = False,
    ) -> dict:
        """Atomically publish payload + meta. interrupt_before_replace leaves only a tmp part."""
        key = cache_key(source, plugin_version)
        if payload is None:
            payload = render_payload(source)
        meta = {
            "key": key,
            "plugin_version": plugin_version,
            "source_sha256": sha256_bytes(source),
            "payload_sha256": sha256_bytes(payload),
            "payload_bytes": len(payload),
        }
        meta_raw = (json.dumps(meta, indent=2, sort_keys=True) + "\n").encode("utf-8")
        if interrupt_before_replace:
            token = f"{os.getpid()}.{uuid.uuid4().hex}"
            leftover = self.tmp / f"{key}.{token}.payload.part"
            leftover.write_bytes(payload[: max(1, len(payload) // 2)])
            self._record(
                op="put_interrupted",
                key=key,
                leftover=str(leftover.relative_to(self.root)),
            )
            return {
                "key": key,
                "published": False,
                "interrupted": True,
                "leftover_tmp": leftover.as_posix(),
            }
        dest_dir = self.entry_dir(key)
        dest_dir.mkdir(parents=True, exist_ok=True)
        _write_atomic_file(self.payload_path(key), payload, self.tmp, f"{key}.payload")
        _write_atomic_file(self.meta_path(key), meta_raw, self.tmp, f"{key}.meta")
        self._record(op="put", key=key, payload_sha256=meta["payload_sha256"])
        return {"key": key, "published": True, "interrupted": False, **meta}

    def list_orphans(self) -> list[Path]:
        if not self.tmp.is_dir():
            return []
        return sorted(p for p in self.tmp.iterdir() if p.is_file() and p.name.endswith(".part"))

    def sweep_orphans(self) -> list[dict]:
        moved = []
        for part in self.list_orphans():
            dest = self._quarantine_dir("orphan-tmp", part.stem)
            dest.mkdir(parents=True, exist_ok=True)
            target = dest / part.name
            os.replace(str(part), str(target))
            (dest / "reason.txt").write_text(
                f"{LEFTOVER_TMP}\n{DETECT_LEFTOVER_TMP}\n{part.name}\n",
                encoding="utf-8",
            )
            rec = {
                "corruption_mode": LEFTOVER_TMP,
                "detection_mechanism": DETECT_LEFTOVER_TMP,
                "quarantined": True,
                "from": part.as_posix(),
                "to": target.as_posix(),
            }
            moved.append(rec)
            self._record(op="sweep_orphan", **rec)
        return moved

    def _quarantine_dir(self, reason: str, key: str) -> Path:
        stamp = time.strftime("%Y%m%dT%H%M%S")
        return self.quarantine / f"{key}.{reason}.{stamp}.{uuid.uuid4().hex[:8]}"

    def quarantine_entry(self, key: str, reason: str, detection: str, detail: str = "") -> Path:
        src = self.entry_dir(key)
        dest = self._quarantine_dir(reason, key)
        dest.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            for child in src.iterdir():
                os.replace(str(child), str(dest / child.name))
            try:
                src.rmdir()
            except OSError:
                pass
        (dest / "reason.txt").write_text(
            f"{reason}\n{detection}\n{detail}\n", encoding="utf-8"
        )
        self._record(
            op="quarantine",
            key=key,
            reason=reason,
            detection=detection,
            dest=dest.as_posix(),
        )
        return dest

    def inspect(self, key: str) -> dict:
        """Classify a published entry. Never returns payload bytes on a failed check."""
        payload_p = self.payload_path(key)
        meta_p = self.meta_path(key)
        if not payload_p.exists() and not meta_p.exists():
            return {
                "ok": False,
                "present": False,
                "corruption_mode": None,
                "detection_mechanism": None,
                "detail": "absent",
            }
        for path in (payload_p, meta_p):
            if not path.exists():
                return {
                    "ok": False,
                    "present": True,
                    "corruption_mode": TRUNCATED,
                    "detection_mechanism": DETECT_TRUNCATED,
                    "detail": f"missing:{path.name}",
                }
            try:
                st = path.stat()
            except OSError as exc:
                return {
                    "ok": False,
                    "present": True,
                    "corruption_mode": UNREADABLE,
                    "detection_mechanism": DETECT_UNREADABLE,
                    "detail": f"stat:{type(exc).__name__}",
                }
            if not _mode_grants_read(st.st_mode):
                return {
                    "ok": False,
                    "present": True,
                    "corruption_mode": UNREADABLE,
                    "detection_mechanism": DETECT_UNREADABLE,
                    "detail": f"mode:{stat.S_IMODE(st.st_mode):o}:{path.name}",
                }
        try:
            meta_raw = meta_p.read_bytes()
            meta = json.loads(meta_raw.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            return {
                "ok": False,
                "present": True,
                "corruption_mode": TRUNCATED,
                "detection_mechanism": DETECT_TRUNCATED,
                "detail": f"meta:{type(exc).__name__}",
            }
        try:
            payload = payload_p.read_bytes()
        except OSError as exc:
            return {
                "ok": False,
                "present": True,
                "corruption_mode": UNREADABLE,
                "detection_mechanism": DETECT_UNREADABLE,
                "detail": f"read:{type(exc).__name__}",
            }
        expected_len = meta.get("payload_bytes")
        if not isinstance(expected_len, int) or len(payload) != expected_len:
            return {
                "ok": False,
                "present": True,
                "corruption_mode": TRUNCATED,
                "detection_mechanism": DETECT_TRUNCATED,
                "detail": f"size:{len(payload)}!={expected_len}",
            }
        actual = sha256_bytes(payload)
        expected = meta.get("payload_sha256")
        if actual != expected:
            return {
                "ok": False,
                "present": True,
                "corruption_mode": WRONG_HASH,
                "detection_mechanism": DETECT_WRONG_HASH,
                "detail": f"{actual}!={expected}",
            }
        return {
            "ok": True,
            "present": True,
            "corruption_mode": INTACT,
            "detection_mechanism": DETECT_INTACT,
            "payload": payload,
            "meta": meta,
            "payload_sha256": actual,
        }

    def get(
        self,
        source: bytes,
        plugin_version: str = "1.0.0",
        rebuild: Optional[PayloadBuilder] = None,
    ) -> dict:
        """Serve an intact entry or detect+quarantine+rebuild. Never serves corrupt bytes."""
        orphans = self.sweep_orphans()
        key = cache_key(source, plugin_version)
        builder = rebuild or render_payload
        inspected = self.inspect(key)
        if inspected.get("ok"):
            payload = inspected["payload"]
            self._record(op="hit", key=key, payload_sha256=inspected["payload_sha256"])
            return {
                "key": key,
                "served": payload,
                "served_corrupt": False,
                "rebuilt": False,
                "hit": True,
                "corruption_mode": INTACT,
                "detection_mechanism": DETECT_INTACT,
                "quarantined": False,
                "orphans_swept": orphans,
                "payload_sha256": inspected["payload_sha256"],
            }
        quarantined_path = None
        mode = inspected.get("corruption_mode")
        detection = inspected.get("detection_mechanism")
        if inspected.get("present"):
            quarantined_path = self.quarantine_entry(
                key, str(mode), str(detection), str(inspected.get("detail") or "")
            )
        fresh = builder(source)
        self.put(source, fresh, plugin_version=plugin_version)
        rebuilt_sha = sha256_bytes(fresh)
        self._record(op="rebuild", key=key, payload_sha256=rebuilt_sha, from_mode=mode)
        return {
            "key": key,
            "served": fresh,
            "served_corrupt": False,
            "rebuilt": True,
            "hit": False,
            "corruption_mode": mode,
            "detection_mechanism": detection,
            "quarantined": quarantined_path is not None,
            "quarantine_path": None if quarantined_path is None else quarantined_path.as_posix(),
            "orphans_swept": orphans,
            "payload_sha256": rebuilt_sha,
            "inspect_detail": inspected.get("detail"),
        }


class SilentServeCache(IntegrityCache):
    """P0 mutant: returns on-disk bytes without integrity checks."""

    def get(
        self,
        source: bytes,
        plugin_version: str = "1.0.0",
        rebuild: Optional[PayloadBuilder] = None,
    ) -> dict:
        key = cache_key(source, plugin_version)
        path = self.payload_path(key)
        payload = path.read_bytes() if path.is_file() else b""
        return {
            "key": key,
            "served": payload,
            "served_corrupt": True,
            "rebuilt": False,
            "hit": path.is_file(),
            "corruption_mode": None,
            "detection_mechanism": None,
            "quarantined": False,
            "payload_sha256": sha256_bytes(payload) if payload else None,
            "mutant": "silent-serve",
        }


class InPlaceWriteCache(IntegrityCache):
    """Mutant: in-place write to the publish path (no tmp+replace)."""

    def put_inplace_partial(self, source: bytes, plugin_version: str = "1.0.0") -> dict:
        key = cache_key(source, plugin_version)
        payload = render_payload(source)
        dest_dir = self.entry_dir(key)
        dest_dir.mkdir(parents=True, exist_ok=True)
        path = self.payload_path(key)
        with open(path, "wb") as fh:
            fh.write(payload[: max(1, len(payload) // 3)])
            fh.flush()
            os.fsync(fh.fileno())
        meta = {
            "key": key,
            "plugin_version": plugin_version,
            "source_sha256": sha256_bytes(source),
            "payload_sha256": sha256_bytes(payload),
            "payload_bytes": len(payload),
        }
        self.meta_path(key).write_text(json.dumps(meta) + "\n", encoding="utf-8")
        return {
            "key": key,
            "published_partial": True,
            "on_disk_bytes": path.stat().st_size,
            "declared_bytes": len(payload),
        }
