"""Pattern scanner for TST-0206. Independent of entropy_scan.py.

Looks for the planted canary shape and a small credential-shaped table
(PEM, AKIA, JSON secret fields). Does not import entropy_scan. Does not
echo a matched body.
"""
from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from canary import PREFIX

MAX_FILE_BYTES = 8 * 1024 * 1024
SKIP_SUFFIXES = {".pyc", ".pyo", ".so", ".o", ".a", ".png", ".jpg", ".jpeg", ".gif", ".webp"}
ARCHIVE_SUFFIXES = {".zip", ".whl", ".jar"}

RULES: tuple[tuple[str, re.Pattern[bytes]], ...] = (
    ("tst0206-canary", re.compile(PREFIX.encode("ascii") + rb"[A-Za-z0-9_-]{16,}")),
    ("pem-private-key", re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("akia-shaped", re.compile(rb"AKIA[0-9A-Z]{16}")),
    ("json-password", re.compile(rb'(?i)"password"\s*:\s*"[^"\\]{12,}"')),
    ("json-secret-field", re.compile(
        rb'(?i)"(?:api[_-]?token|api[_-]?key|secret|decrypted_secret)"\s*:\s*"[^"\\]{12,}"'
    )),
)


@dataclass
class Hit:
    path: str
    offset: int
    length: int
    rule_id: str
    token: bytes | None = None


def public_hit(hit: Hit) -> dict:
    return {
        "path": hit.path,
        "offset": hit.offset,
        "length": hit.length,
        "rule_id": hit.rule_id,
    }


def scan_bytes(data: bytes, *, path: str) -> list[Hit]:
    hits: list[Hit] = []
    for rule_id, pat in RULES:
        for m in pat.finditer(data):
            hits.append(
                Hit(
                    path=path,
                    offset=m.start(),
                    length=m.end() - m.start(),
                    rule_id=rule_id,
                    token=m.group(0),
                )
            )
    return hits


def _read_capped(path: Path) -> bytes | None:
    try:
        size = path.stat().st_size
    except OSError:
        return None
    if size <= 0 or size > MAX_FILE_BYTES:
        return None
    if path.suffix.lower() in SKIP_SUFFIXES:
        return None
    try:
        return path.read_bytes()
    except OSError:
        return None


def scan_archive(path: Path, rel: str) -> list[Hit]:
    hits: list[Hit] = []
    try:
        with zipfile.ZipFile(path) as zf:
            for info in zf.infolist():
                if info.is_dir() or info.file_size > MAX_FILE_BYTES:
                    continue
                try:
                    data = zf.read(info)
                except (OSError, zipfile.BadZipFile, RuntimeError):
                    continue
                hits.extend(scan_bytes(data, path=f"{rel}!{info.filename}"))
    except (OSError, zipfile.BadZipFile, RuntimeError):
        return hits
    return hits


def scan_path(path: Path, *, rel: str | None = None) -> list[Hit]:
    path = Path(path)
    label = rel if rel is not None else path.as_posix()
    if path.suffix.lower() in ARCHIVE_SUFFIXES:
        return scan_archive(path, label)
    data = _read_capped(path)
    if data is None:
        return []
    return scan_bytes(data, path=label)


def scan_tree(root: Path, *, origin: str | None = None) -> list[Hit]:
    root = Path(root)
    if root.is_file():
        return scan_path(root, rel=origin or root.name)
    hits: list[Hit] = []
    if not root.is_dir():
        return hits
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if origin:
            rel = f"{origin}/{rel}"
        hits.extend(scan_path(p, rel=rel))
    return hits


def canary_hits(hits: list[Hit]) -> list[Hit]:
    return [h for h in hits if h.rule_id == "tst0206-canary"]
