"""Shannon-entropy scanner for TST-0206. Independent of pattern_scan.py.

Does not know the canary prefix or the credential regex table. Extracts
high-entropy tokens from file bytes and one zip nesting level. Never prints
a token body.
"""
from __future__ import annotations

import math
import re
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

MAX_FILE_BYTES = 8 * 1024 * 1024
SKIP_SUFFIXES = {".pyc", ".pyo", ".so", ".o", ".a", ".png", ".jpg", ".jpeg", ".gif", ".webp"}
ARCHIVE_SUFFIXES = {".zip", ".whl", ".jar"}
TOKEN_RE = re.compile(rb"[A-Za-z0-9_+\/=-]{24,}")
ENTROPY_MIN = 4.2
WINDOW = 24


@dataclass
class Hit:
    path: str
    offset: int
    length: int
    entropy: float
    token: bytes | None = None
    rule_id: str = "high-entropy-token"


def public_hit(hit: Hit) -> dict:
    return {
        "path": hit.path,
        "offset": hit.offset,
        "length": hit.length,
        "entropy": round(hit.entropy, 3),
        "rule_id": hit.rule_id,
    }


def shannon(data: bytes) -> float:
    if not data:
        return 0.0
    n = len(data)
    counts = Counter(data)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def scan_bytes(data: bytes, *, path: str) -> list[Hit]:
    hits: list[Hit] = []
    for m in TOKEN_RE.finditer(data):
        token = m.group(0)
        ent = shannon(token)
        if ent < ENTROPY_MIN:
            best = 0.0
            if len(token) >= WINDOW:
                for i in range(0, len(token) - WINDOW + 1, 8):
                    best = max(best, shannon(token[i : i + WINDOW]))
            if best < ENTROPY_MIN:
                continue
            ent = best
        hits.append(
            Hit(
                path=path,
                offset=m.start(),
                length=len(token),
                entropy=ent,
                token=token,
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


def matching_canary(hits: list[Hit], full: str, *, prefix_len: int) -> list[Hit]:
    """True canary hits must include the random suffix, not the public PREFIX.

    PREFIX is named in receipts; matching on PREFIX alone would false-positive
    the produced-artifact scan after emit.
    """
    needle = full.encode("ascii")
    suffix = needle[prefix_len:]
    if not suffix:
        return []
    out: list[Hit] = []
    for h in hits:
        tok = h.token or b""
        if suffix in tok or (len(tok) >= WINDOW and tok[-WINDOW:] in suffix):
            out.append(h)
    return out
