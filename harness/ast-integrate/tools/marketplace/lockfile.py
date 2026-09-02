"""Verified lockfile install with digest mismatch refusal (IMP-0084)."""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

CURRENT_RESOLVER_VERSION = "1"
LOCKFILE_VERSION = 1
DIGEST_ALGORITHM = "sha256"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pinned_digest_hex(pkg: dict[str, Any]) -> str:
    """Return the pinned hex digest of a lockfile row.

    Rows carry the digest as {"algorithm": "sha256", "hex": ...} (schema
    $defs/package.digest); the flat "sha256" mirror is accepted for rows
    written before the digest object existed.
    """
    digest = pkg.get("digest")
    if isinstance(digest, dict) and digest.get("hex"):
        algorithm = str(digest.get("algorithm") or DIGEST_ALGORITHM)
        if algorithm != DIGEST_ALGORITHM:
            raise ValueError(f"unsupported lockfile digest algorithm {algorithm}")
        return str(digest["hex"])
    flat = pkg.get("sha256")
    if not flat:
        raise KeyError("digest")
    return str(flat)


@dataclass
class ResolvedPackage:
    name: str
    version: str
    source_url: str
    blob: bytes
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def digest_hex(self) -> str:
        return sha256_hex(self.blob)


class DigestMismatch(Exception):
    def __init__(self, expected_hex: str, actual_hex: str, *, dest: Path | None = None):
        self.expected_hex = expected_hex
        self.actual_hex = actual_hex
        self.dest = dest
        super().__init__(
            f"digest mismatch expected={expected_hex} actual={actual_hex}"
        )

    def dest_unchanged(self) -> bool:
        return True


class MissingLockfileEntry(Exception):
    def __init__(self, name: str, version: str | None = None, fetch_count: int = 0):
        self.name = name
        self.version = version
        self.fetch_count = fetch_count
        super().__init__(f"missing lockfile entry {name}@{version}")


def filesystem_census(root: Path) -> dict[str, str]:
    root = Path(root)
    out: dict[str, str] = {}
    if not root.is_dir():
        return out
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            out[rel] = sha256_hex(path.read_bytes())
    return out


def generate_lockfile(
    packages: list[ResolvedPackage], resolver_version: str | None = None
) -> bytes:
    rows = sorted(
        (
            {
                "name": p.name,
                "version": p.version,
                "source_url": p.source_url,
                "digest": {"algorithm": DIGEST_ALGORITHM, "hex": sha256_hex(p.blob)},
                "sha256": sha256_hex(p.blob),
                "bytes": len(p.blob),
            }
            for p in packages
        ),
        key=lambda r: (r["name"], r["version"]),
    )
    doc = {
        "lockfile_version": LOCKFILE_VERSION,
        "resolver_version": resolver_version or CURRENT_RESOLVER_VERSION,
        "packages": rows,
    }
    return json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")


def load_lockfile(data: bytes) -> dict[str, Any]:
    return json.loads(data.decode("utf-8"))


@dataclass
class InstallResult:
    name: str
    version: str
    digest_hex: str
    dest: str
    warnings: list[str] = field(default_factory=list)


def install_verified(
    lock_bytes: bytes,
    *,
    name: str,
    dest: Path,
    fetch: Callable[[str], bytes],
    version: str | None = None,
    current_resolver_version: str | None = None,
) -> InstallResult:
    doc = load_lockfile(lock_bytes)
    entries = [p for p in doc.get("packages") or [] if p.get("name") == name]
    if version is not None:
        entries = [p for p in entries if p.get("version") == version]
    if not entries:
        raise MissingLockfileEntry(name, version, fetch_count=0)
    pkg = entries[0]
    blob = fetch(pkg["source_url"])
    actual = sha256_hex(blob)
    expected = pinned_digest_hex(pkg)
    if actual != expected:
        raise DigestMismatch(expected, actual, dest=Path(dest))
    dest = Path(dest)
    payload = dest / pkg["name"] / pkg["version"] / "payload"
    payload.parent.mkdir(parents=True, exist_ok=True)
    payload.write_bytes(blob)
    warnings: list[str] = []
    recorded = str(doc.get("resolver_version") or "")
    current = current_resolver_version or CURRENT_RESOLVER_VERSION
    if recorded and recorded != current:
        warnings.append(
            f"stale resolver version recorded={recorded} current={current}"
        )
    return InstallResult(
        name=pkg["name"],
        version=pkg["version"],
        digest_hex=actual,
        dest=str(payload),
        warnings=warnings,
    )
