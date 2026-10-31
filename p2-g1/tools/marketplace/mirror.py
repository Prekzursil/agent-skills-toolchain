"""Private filesystem mirror: digest-preserving copy, owner-gated public bind."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

PUBLIC_BIND_HOSTS = frozenset({"0.0.0.0", "::", "[::]", "*"})


class DigestMismatchError(Exception):
    def __init__(self, name: str, claimed: str, computed: str) -> None:
        super().__init__(f"{name}: claimed {claimed} computed {computed}")
        self.name = name
        self.claimed = claimed
        self.computed = computed


class OwnerApprovalRequired(Exception):
    pass


def digest_of(payload: bytes | str | Path) -> str:
    if isinstance(payload, Path):
        data = payload.read_bytes()
    elif isinstance(payload, (bytes, bytearray)):
        data = bytes(payload)
    else:
        data = str(payload).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def parse_digest(raw: str) -> str:
    text = str(raw or "").strip().lower()
    if text.startswith("sha256:"):
        text = text[7:]
    if len(text) != 64 or any(c not in "0123456789abcdef" for c in text):
        raise ValueError(f"bad digest {raw!r}")
    return text


def require_private_or_approved(cfg: "MirrorConfig") -> str:
    host = str(cfg.bind_host or "")
    if host in PUBLIC_BIND_HOSTS or (cfg.bind_port and int(cfg.bind_port) in {80, 443}):
        if not cfg.owner_approved_public_mirror:
            raise OwnerApprovalRequired("public bind requires owner approval")
        return "owner-approved-public"
    return "filesystem-private"


def validate_reachability(cfg: "MirrorConfig") -> str:
    return require_private_or_approved(cfg)


@dataclass
class MirrorConfig:
    mirror_identity: str = "local-private-mirror"
    bind_host: str = "127.0.0.1"
    bind_port: int = 0
    owner_approved_public_mirror: bool = False


@dataclass
class PackageFilter:
    deny: frozenset[str] = field(default_factory=frozenset)

    def allows(self, name: str) -> bool:
        return name not in self.deny


class FileBackedRegistry:
    def __init__(self, root: Path, identity: str, role: str = "mirror") -> None:
        self.root = Path(root)
        self.identity = identity
        self.role = role
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "blobs").mkdir(parents=True, exist_ok=True)
        if not self.index_path.is_file():
            self.index_path.write_text(json.dumps({"packages": []}, indent=2) + "\n", encoding="utf-8")

    @property
    def index_path(self) -> Path:
        return self.root / "index.json"

    def _load(self) -> dict[str, Any]:
        return json.loads(self.index_path.read_text(encoding="utf-8"))

    def _save(self, doc: dict[str, Any]) -> None:
        self.index_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    def put_blob(self, payload: bytes) -> str:
        digest = digest_of(payload)
        dest = self.root / "blobs" / digest
        dest.write_bytes(payload)
        return digest

    def read_blob(self, digest: str) -> bytes | None:
        path = self.root / "blobs" / parse_digest(digest)
        if not path.is_file():
            return None
        return path.read_bytes()

    def get(self, name: str, version: str) -> dict[str, Any] | None:
        for row in self._load().get("packages") or []:
            if row.get("name") == name and row.get("version") == version:
                return dict(row)
        return None

    def package_names(self) -> list[str]:
        return sorted({str(r.get("name")) for r in (self._load().get("packages") or []) if r.get("name")})

    def census_blobs(self) -> dict[str, int]:
        out: dict[str, int] = {}
        blob_dir = self.root / "blobs"
        if not blob_dir.is_dir():
            return out
        for p in blob_dir.iterdir():
            if p.is_file():
                out[p.name] = p.stat().st_size
        return out

    def record(self, name: str, version: str, digest: str, provenance: dict[str, Any]) -> None:
        doc = self._load()
        rows = [r for r in (doc.get("packages") or []) if not (r.get("name") == name and r.get("version") == version)]
        rows.append(
            {
                "name": name,
                "version": version,
                "digest": digest,
                "provenance": provenance,
            }
        )
        doc["packages"] = rows
        self._save(doc)


def seed_package(
    registry: FileBackedRegistry,
    name: str,
    version: str,
    payload: bytes,
    *,
    source: str,
    commit: str = "",
    builder: str = "",
) -> str:
    digest = registry.put_blob(payload)
    registry.record(
        name,
        version,
        digest,
        {
            "source": source,
            "source_kind": "upstream",
            "commit": commit,
            "builder": builder,
            "transport": {},
        },
    )
    return digest


class UpstreamView:
    def __init__(self, registry: FileBackedRegistry, fetch_blob: Callable[[str], bytes] | None = None) -> None:
        self.registry = registry
        self._fetch_blob = fetch_blob

    def packages(self) -> list[dict[str, Any]]:
        return list(self.registry._load().get("packages") or [])

    def fetch(self, digest: str) -> bytes:
        if self._fetch_blob is not None:
            return self._fetch_blob(digest)
        data = self.registry.read_blob(digest)
        if data is None:
            raise FileNotFoundError(digest)
        return data


class MirrorSync:
    def __init__(
        self,
        upstream: UpstreamView,
        local: FileBackedRegistry,
        filt: PackageFilter,
        cfg: MirrorConfig,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self.upstream = upstream
        self.local = local
        self.filter = filt
        self.cfg = cfg
        self.sleep = sleep or (lambda _s: None)
        self.fetch_attempts: dict[str, int] = {}

    def sync(self) -> dict[str, Any]:
        mirrored: list[str] = []
        for row in self.upstream.packages():
            name = str(row.get("name") or "")
            version = str(row.get("version") or "")
            if not self.filter.allows(name):
                continue
            claimed = parse_digest(str(row.get("digest") or ""))
            self.fetch_attempts[claimed] = self.fetch_attempts.get(claimed, 0) + 1
            payload = self.upstream.fetch(claimed)
            computed = digest_of(payload)
            if computed != claimed:
                raise DigestMismatchError(name, claimed, computed)
            self.local.put_blob(payload)
            prov = dict(row.get("provenance") or {})
            prov["source"] = prov.get("source") or self.upstream.registry.identity
            prov["source_kind"] = "upstream"
            transport = dict(prov.get("transport") or {})
            transport["mirrored_by"] = self.cfg.mirror_identity
            prov["transport"] = transport
            self.local.record(name, version, claimed, prov)
            mirrored.append(f"{name}@{version}")
        return {"mirrored": mirrored, "ok": True}
