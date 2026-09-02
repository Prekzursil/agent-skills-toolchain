"""Mirror conflict policy: record both digests, refuse install until explicit resolve (IMP-0107)."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

FORBIDDEN_PREFER_KEYS = (
    "prefer_upstream",
    "prefer_mirror",
    "preferred_source",
    "authoritative",
    "authoritative_side",
    "winner",
    "auto_resolve",
)


class SilentPreferenceRefused(Exception):
    pass


class UnresolvedMirrorConflict(Exception):
    pass


def sha256_digest(data: bytes | str | Path) -> str:
    if isinstance(data, Path):
        raw = data.read_bytes()
    elif isinstance(data, (bytes, bytearray)):
        raw = bytes(data)
    else:
        raw = str(data).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def census(dest: Path) -> dict[str, str]:
    dest = Path(dest)
    out: dict[str, str] = {}
    if not dest.exists():
        return out
    for path in dest.rglob("*"):
        if path.is_file():
            rel = path.relative_to(dest).as_posix()
            out[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def load_conflict_file(path: Path) -> list[dict[str, Any]]:
    text = Path(path).read_text(encoding="utf-8")
    doc = json.loads(text)
    if isinstance(doc, list):
        return doc
    if isinstance(doc, dict):
        recs = doc.get("conflicts") or doc.get("records") or []
        if isinstance(recs, list):
            return recs
    return []


@dataclass
class InstallResult:
    ok: bool
    reason: str = ""
    written: list[str] | None = None


class MirrorConflictPolicy:
    def __init__(self, store: str | Path, config: dict[str, Any] | None = None) -> None:
        self.store = Path(store)
        if config:
            for key in FORBIDDEN_PREFER_KEYS:
                if key in config:
                    raise SilentPreferenceRefused(key)
        self._load()

    def _load(self) -> list[dict[str, Any]]:
        if not self.store.is_file():
            self._records: list[dict[str, Any]] = []
            return self._records
        self._records = load_conflict_file(self.store)
        return self._records

    def _save(self) -> None:
        self.store.parent.mkdir(parents=True, exist_ok=True)
        self.store.write_text(
            json.dumps(self._records, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _key(self, package: str, version: str) -> tuple[str, str]:
        return (package, version)

    def _find(self, package: str, version: str) -> dict[str, Any] | None:
        for rec in self._records:
            if rec.get("package") == package and rec.get("version") == version:
                return rec
        return None

    def compare_and_record(
        self,
        package: str,
        version: str,
        *,
        upstream_url: str,
        upstream_digest: str,
        mirror_url: str,
        mirror_digest: str,
    ) -> dict[str, Any] | None:
        existing = self._find(package, version)
        if existing is not None and existing.get("status") == "unresolved":
            return existing
        if upstream_digest == mirror_digest:
            return None
        rec = {
            "package": package,
            "version": version,
            "upstream_digest": upstream_digest,
            "mirror_digest": mirror_digest,
            "status": "unresolved",
            "sources": [
                {"name": "upstream", "url": upstream_url, "digest": upstream_digest},
                {"name": "mirror", "url": mirror_url, "digest": mirror_digest},
            ],
        }
        self._records.append(rec)
        self._save()
        return rec

    def unresolved(self, package: str, version: str) -> dict[str, Any] | None:
        rec = self._find(package, version)
        if rec is None or rec.get("status") != "unresolved":
            return None
        return rec

    def chosen_digest(self, package: str, version: str) -> str:
        rec = self._find(package, version)
        if rec is None or rec.get("status") == "unresolved":
            raise UnresolvedMirrorConflict(f"{package}@{version}")
        digest = rec.get("chosen_digest")
        if not digest:
            raise UnresolvedMirrorConflict(f"{package}@{version}")
        return str(digest)

    def resolve(
        self,
        package: str,
        version: str,
        *,
        actor: str,
        note: str,
        chosen_digest: str | None = None,
    ) -> dict[str, Any]:
        rec = self._find(package, version)
        if rec is None:
            raise UnresolvedMirrorConflict(f"{package}@{version} missing")
        rec["status"] = "resolved"
        rec["resolved_by"] = actor
        rec["note"] = note
        rec["chosen_digest"] = chosen_digest or rec.get("upstream_digest")
        self._save()
        return rec

    def install(self, package: str, version: str, dest: Path, blob: bytes) -> InstallResult:
        dest = Path(dest)
        rec = self._find(package, version)
        if rec is not None and rec.get("status") == "unresolved":
            return InstallResult(ok=False, reason="unresolved-mirror-conflict", written=[])
        dest.mkdir(parents=True, exist_ok=True)
        payload = dest / package / version / "payload.bin"
        payload.parent.mkdir(parents=True, exist_ok=True)
        payload.write_bytes(blob)
        return InstallResult(ok=True, reason="installed", written=[payload.as_posix()])
