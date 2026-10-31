"""Package download with digest check and quarantine of truncated remnants."""
from __future__ import annotations

import hashlib
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REASON_DIGEST_MISMATCH = "digest-mismatch"
CACHE_PAYLOAD_NAME = "payload.bin"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class DownloadResult:
    ok: bool
    classification: str
    message: str = ""
    received_bytes: int = 0
    claimed_bytes: int = 0
    received_digest: str = ""
    quarantine_path: str | None = None
    installed_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "classification": self.classification,
            "message": self.message,
            "received_bytes": self.received_bytes,
            "claimed_bytes": self.claimed_bytes,
            "received_digest": self.received_digest,
            "quarantine_path": self.quarantine_path,
            "installed_path": self.installed_path,
        }


def independent_cache_listing(cache: Path, package_id: str) -> list[str]:
    root = Path(cache)
    if not root.is_dir():
        return []
    hits = []
    for p in root.rglob("*"):
        if p.is_file() and package_id in p.as_posix():
            hits.append(p.name)
    pkg = root / package_id
    if pkg.exists():
        hits.append(package_id)
    return sorted(set(hits))


def naive_write_partial_into_cache(url: str, package_id: str, cache: Path) -> Path:
    dest_dir = Path(cache) / package_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / CACHE_PAYLOAD_NAME
    with urllib.request.urlopen(url, timeout=10) as resp:
        dest.write_bytes(resp.read())
    return dest


def download_package(
    url: str,
    package_id: str,
    expected_digest: str,
    cache: Path,
    quarantine: Path,
    install_root: Path | None = None,
) -> DownloadResult:
    cache = Path(cache)
    quarantine = Path(quarantine)
    cache.mkdir(parents=True, exist_ok=True)
    quarantine.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=10) as resp:
        claimed = int(resp.headers.get("Content-Length") or 0)
        body = resp.read()
    digest = sha256_hex(body)
    if digest != expected_digest:
        qpath = quarantine / f"{package_id}.partial"
        qpath.write_bytes(body)
        return DownloadResult(
            ok=False,
            classification=REASON_DIGEST_MISMATCH,
            message=f"digest-mismatch received={digest} expected={expected_digest}",
            received_bytes=len(body),
            claimed_bytes=claimed or len(body),
            received_digest=digest,
            quarantine_path=str(qpath),
        )
    pkg_dir = cache / package_id
    pkg_dir.mkdir(parents=True, exist_ok=True)
    payload = pkg_dir / CACHE_PAYLOAD_NAME
    payload.write_bytes(body)
    installed = payload
    if install_root is not None:
        install_root = Path(install_root)
        install_root.mkdir(parents=True, exist_ok=True)
        installed = install_root / package_id
        installed.write_bytes(body)
    return DownloadResult(
        ok=True,
        classification="ok",
        message="ok",
        received_bytes=len(body),
        claimed_bytes=claimed or len(body),
        received_digest=digest,
        installed_path=str(installed),
    )
