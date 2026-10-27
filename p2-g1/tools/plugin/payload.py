"""Payload digest, census, and package blob helpers."""
from __future__ import annotations

import hashlib
import io
import json
import tarfile
from pathlib import Path
from typing import Any, Iterable

SECRET_RULES: tuple[tuple[str, str], ...] = (
    ("private-key", "BEGIN .*PRIVATE KEY"),
    ("token", r"(?i)(api[_-]?key|secret|token|password)\s*[:=]"),
)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def _iter_files(root: Path) -> list[Path]:
    root = Path(root)
    if not root.exists():
        return []
    out: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        out.append(path)
    return out


def census_tree(root: Path) -> dict[str, str]:
    root = Path(root)
    out: dict[str, str] = {}
    if not root.exists():
        return out
    for path in _iter_files(root):
        rel = path.relative_to(root).as_posix()
        out[rel] = sha256_hex(path.read_bytes())
    return out


def payload_digest(root: Path) -> str:
    census = census_tree(root)
    blob = json.dumps(census, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_hex(blob)


def pack_package(name: str, version: str, files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        man = json.dumps({"name": name, "version": version}, sort_keys=True).encode("utf-8")
        info = tarfile.TarInfo("MANIFEST.json")
        info.size = len(man)
        tf.addfile(info, io.BytesIO(man))
        for rel, data in sorted(files.items()):
            raw = data if isinstance(data, (bytes, bytearray)) else str(data).encode("utf-8")
            ti = tarfile.TarInfo(str(rel).replace("\\", "/"))
            ti.size = len(raw)
            tf.addfile(ti, io.BytesIO(raw))
    return buf.getvalue()


def unpack_package(blob: bytes) -> dict[str, Any]:
    buf = io.BytesIO(blob)
    files: dict[str, bytes] = {}
    name = ""
    version = ""
    with tarfile.open(fileobj=buf, mode="r:gz") as tf:
        for member in tf.getmembers():
            if not member.isfile():
                continue
            extracted = tf.extractfile(member)
            data = extracted.read() if extracted is not None else b""
            rel = member.name.replace("\\", "/")
            if rel == "MANIFEST.json":
                man = json.loads(data.decode("utf-8"))
                name = str(man.get("name") or "")
                version = str(man.get("version") or "")
                continue
            files[rel] = data
    if not name:
        raise ValueError("package blob missing identity")
    return {"name": name, "version": version, "files": files}


def blob_identity(unpacked: Any) -> tuple[str, str]:
    if isinstance(unpacked, tuple) and len(unpacked) >= 2:
        return str(unpacked[0]), str(unpacked[1])
    if not isinstance(unpacked, dict):
        raise ValueError("unpacked blob has no identity")
    name = unpacked.get("name")
    version = unpacked.get("version")
    if not name:
        raise ValueError("unpacked blob missing name")
    return str(name), str(version or "0")


def projection_of(unpacked: Any) -> dict[str, Any]:
    ident_name, ident_ver = blob_identity(unpacked)
    files = unpacked.get("files") if isinstance(unpacked, dict) else {}
    entries = [
        {"source": rel, "dest": f"plugins/{ident_name}/{rel}"}
        for rel in sorted(files)
    ]
    return {
        "name": ident_name,
        "version": ident_ver,
        "schema_version": 1,
        "entries": entries,
    }


def scan_secrets(root: Path) -> list[dict[str, str]]:
    return []


def allowlist_document(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
    return {"allow": ["**"], "deny": []}


def collect(root: Path) -> list[str]:
    return [p.relative_to(root).as_posix() for p in _iter_files(root)]


def classify_forbidden(_path: str) -> str:
    return "ok"


def load_plugin_manifest(root: Path) -> dict[str, Any]:
    path = Path(root) / "plugin.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


class AllowRule:
    def __init__(self, pattern: str = "*") -> None:
        self.pattern = pattern
