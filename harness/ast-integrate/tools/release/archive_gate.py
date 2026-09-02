"""Distributable content allowlist + byte ceiling (REL-0009)."""
from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Entry:
    path: str
    size: int = 0
    sha256: str = ""


@dataclass
class ArchiveResult:
    ok: bool
    entry_count: int
    total_bytes: int
    byte_headroom: int
    file_count_headroom: int
    allowlist_violations: list[dict[str, str]] = field(default_factory=list)
    evaluation_surface: str = "archive-entry-list"

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "entry_count": self.entry_count,
            "total_bytes": self.total_bytes,
            "byte_headroom": self.byte_headroom,
            "file_count_headroom": self.file_count_headroom,
            "allowlist_violations": list(self.allowlist_violations),
            "evaluation_surface": self.evaluation_surface,
        }


def load_policy(path: Path | None = None) -> dict[str, Any]:
    path = Path(path) if path else Path(__file__).with_name("payload-allowlist.json")
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "max_bytes": 1_000_000,
        "max_files": 500,
        "deny_prefixes": [".git/", ".git"],
        "deny_names": [".git", ".gitignore"],
        "allow_suffixes": [".py", ".md", ".json", ".txt", ".toml"],
    }


def evaluate(archive: Path, policy: dict[str, Any] | None = None) -> ArchiveResult:
    return evaluate_archive(archive, policy)


def pack_tree(src: Path, dest: Path, policy: dict[str, Any] | None = None) -> Path:
    import zipfile as _zf
    src = Path(src)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with _zf.ZipFile(dest, "w") as zf:
        for p in src.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(src).as_posix())
    return dest


def append_zero_blob(archive: Path, name: str = "zero.bin", size: int = 0) -> Path:
    import zipfile as _zf
    archive = Path(archive)
    with _zf.ZipFile(archive, "a") as zf:
        zf.writestr(name, b"\x00" * int(size))
    return archive


def evaluate_archive(archive: Path, policy: dict[str, Any] | None = None) -> ArchiveResult:
    policy = policy or load_policy()
    archive = Path(archive)
    deny_prefixes = list(policy.get("deny_prefixes") or [".git/"])
    max_bytes = int(policy.get("max_bytes") or 1_000_000)
    max_files = int(policy.get("max_files") or 500)
    violations: list[dict[str, str]] = []
    n = 0
    total = 0
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            name = info.filename.replace("\\", "/")
            n += 1
            total += int(info.file_size)
            if name.rstrip("/").endswith(".git") or name.startswith(".git/") or name == ".git/HEAD":
                violations.append({"path": name, "reason": "deny-prefix"})
            for pfx in deny_prefixes:
                if name == pfx or name.startswith(str(pfx).rstrip("/") + "/"):
                    violations.append({"path": name, "reason": "deny-prefix"})
            if int(info.file_size) > max_bytes:
                violations.append({"path": name, "reason": "blob-ceiling"})
    uniq = []
    seen = set()
    for v in violations:
        key = (v["path"], v["reason"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(v)
    ok = not uniq and n <= max_files and total <= max_bytes
    return ArchiveResult(
        ok=ok,
        entry_count=n,
        total_bytes=total,
        byte_headroom=max_bytes - total,
        file_count_headroom=max_files - n,
        allowlist_violations=uniq,
    )
