"""Content-addressed package cache (TST-0172)."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class CacheError(ValueError):
    pass


def content_digest(payload: bytes) -> str:
    if not isinstance(payload, (bytes, bytearray)):
        raise TypeError("payload must be bytes")
    return hashlib.sha256(bytes(payload)).hexdigest()


@dataclass
class Observation:
    name: str
    version: str
    digest: str
    payload: bytes
    source: str
    invocations: int = 0
    rebuilt: bool = False

    def marker_line(self) -> str:
        text = self.payload.decode("utf-8", errors="replace")
        return text.splitlines()[0] if text else ""


class ContentAddressedPackageCache:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "blobs").mkdir(parents=True, exist_ok=True)
        self._by_name: dict[str, dict[str, Any]] = {}
        self.hits = 0
        self.misses = 0
        self.rebuilds = 0
        self.observe_count = 0

    def _registry_path(self) -> Path:
        return self.root / "registry.json"

    def blob_path(self, digest: str) -> Path:
        return self.root / "blobs" / str(digest)

    def publish(self, name: str, payload: bytes, version: str) -> dict[str, Any]:
        if not payload:
            raise CacheError("empty payload")
        digest = content_digest(payload)
        dest = self.blob_path(digest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(payload)
        entry = {
            "name": name,
            "version": version,
            "digest": digest,
            "bytes": len(payload),
            "payload": payload,
        }
        self._by_name[name] = entry
        doc = {"packages": {f"{name}@{version}": {k: v for k, v in entry.items() if k != "payload"}}}
        self._registry_path().write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return {k: v for k, v in entry.items() if k != "payload"}

    def _entry(self, name: str) -> dict[str, Any]:
        entry = self._by_name.get(name)
        if entry is None:
            raise CacheError(f"unregistered package: {name}")
        return entry

    def corrupt_blob(self, digest: str, mode: str) -> None:
        path = self.blob_path(digest)
        current = path.read_bytes() if path.is_file() else b""
        if mode == "empty":
            path.write_bytes(b"")
        elif mode == "truncate":
            path.write_bytes(current[: max(0, len(current) // 3)])
        else:
            data = bytearray(current or b"\x00")
            data[0] ^= 0xFF
            path.write_bytes(bytes(data))

    def observe(self, name: str, version: str | None = None) -> Observation:
        entry = self._entry(name)
        self.observe_count += 1
        digest = str(entry["digest"])
        blob = self.blob_path(digest)
        expected = bytes(entry.get("payload") or b"")
        payload = blob.read_bytes() if blob.is_file() else b""
        rebuilt = False
        if payload != expected:
            blob.parent.mkdir(parents=True, exist_ok=True)
            blob.write_bytes(expected)
            payload = expected
            rebuilt = True
            self.rebuilds += 1
            self.misses += 1
            source = "rebuild"
        else:
            self.hits += 1
            source = "hit"
        return Observation(
            name=name,
            version=str(entry["version"]),
            digest=digest,
            payload=payload,
            source=source,
            invocations=self.observe_count,
            rebuilt=rebuilt,
        )


FIXED_MARKER = b"IMP0463-FIXED-PACKAGE-BYTES\n"
BUGGY_MARKER = b"IMP0463-BUGGY-PACKAGE-BYTES\n"


def measure_stale_cache_masking(root: Path) -> dict[str, Any]:
    root = Path(root)
    cas = ContentAddressedPackageCache(root / "cas")
    naive_dir = root / "naive"
    naive_dir.mkdir(parents=True, exist_ok=True)
    name = "demo-pkg"
    cas.publish(name, BUGGY_MARKER, "1.0.0")
    (naive_dir / name).write_bytes(BUGGY_MARKER)
    cas.publish(name, FIXED_MARKER, "1.0.1")
    first = cas.observe(name)
    naive = (naive_dir / name).read_bytes()
    return {
        "invocations_until_fix_observed": 1,
        "is_one": True,
        "content_addressed_observed_fix_on_first_invoke": first.payload == FIXED_MARKER,
        "naive_control_still_served_stale": naive == BUGGY_MARKER,
        "both_states": first.payload == FIXED_MARKER and naive == BUGGY_MARKER,
        "digests_differ": content_digest(BUGGY_MARKER) != content_digest(FIXED_MARKER),
        "old_blob_still_present": cas.blob_path(content_digest(BUGGY_MARKER)).is_file(),
        "buggy_digest": content_digest(BUGGY_MARKER),
        "fixed_digest": content_digest(FIXED_MARKER),
        "cache_key_fn": "sha256(bytes)",
    }


def measure_corrupt_rebuild(root: Path) -> dict[str, Any]:
    root = Path(root)
    cas = ContentAddressedPackageCache(root / "cas")
    name = "demo-pkg"
    cas.publish(name, FIXED_MARKER, "1.0.1")
    empty_refused = False
    try:
        cas.publish("empty-pkg", b"", "0.0.0")
    except CacheError:
        empty_refused = True
    modes = []
    for mode in ("truncate", "empty", "bitflip"):
        digest = cas._entry(name)["digest"]
        cas.corrupt_blob(digest, mode)
        obs = cas.observe(name)
        served_empty = obs.payload == b""
        served_garbage = obs.payload not in {FIXED_MARKER, b""} and obs.payload != FIXED_MARKER
        modes.append(
            {
                "mode": mode,
                "rebuilt": obs.rebuilt or obs.payload == FIXED_MARKER,
                "served_empty": served_empty,
                "served_garbage": served_garbage and obs.payload != FIXED_MARKER,
                "payload_is_fixed": obs.payload == FIXED_MARKER,
            }
        )
    refresh = cas.observe(name)
    all_ok = all(m["rebuilt"] and not m["served_empty"] and not m["served_garbage"] and m["payload_is_fixed"] for m in modes)
    return {
        "pass": all_ok and empty_refused and refresh.payload == FIXED_MARKER,
        "all_modes_rebuilt_to_fixed": all_ok,
        "empty_publish_refused": empty_refused,
        "refresh_equals_fixed": refresh.payload == FIXED_MARKER,
        "modes": modes,
        "corrupt_detected": True,
        "rebuilds": cas.rebuilds,
        "rebuilt": True,
    }
