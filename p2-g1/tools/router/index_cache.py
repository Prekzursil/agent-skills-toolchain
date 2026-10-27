"""Capability-index cache with content-hash + mtime dual invalidation.

Unit IMP-0402 (rebuilt 2026-10-25, wave2 shard14 resume completion). The tree
carried a generated import-stub at this path; the certified implementation was
re-derived from the receipt contract and the two named probes.

Cache schema: ast.capability-index-cache/v1
Invalidation axes:
  content_hash  - pure content digest; byte-identical touch does NOT change it
  mtime_token   - stat digest (path,size,mtime_ns); any mtime change flips it

Recovery classes (diagnose_cache): missing / ok / truncated / zero-byte /
wrong-schema. A truncated, zero-byte, wrong-schema, stale-hash, or stale-mtime
cache rebuilds from the live source tree and never serves stale payload.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CACHE_SCHEMA = "ast.capability-index-cache/v1"

_DIAG_MISSING = "missing"
_DIAG_OK = "ok"
_DIAG_TRUNCATED = "truncated"
_DIAG_ZERO_BYTE = "zero-byte"
_DIAG_WRONG_SCHEMA = "wrong-schema"
_DIAG_EMPTY_INDEX = "empty-index"


class EmptyIndexError(RuntimeError):
    """Raised when an index document carries no capabilities (failure, not OK)."""


@dataclass(frozen=True)
class TreeFingerprint:
    content_hash: str
    mtime_token: str
    file_count: int
    max_mtime_ns: int


@dataclass
class CacheOutcome:
    action: str  # "rebuilt" | "cache-hit"
    reason: str
    fingerprint: TreeFingerprint
    index: dict


def _iter_source_files(roots: list[Path]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        root = Path(root)
        if root.is_file():
            files.append(root)
        elif root.is_dir():
            files.extend(p for p in sorted(root.rglob("*")) if p.is_file())
    seen: set = set()
    uniq = []
    for f in files:
        r = str(f).lower()
        if r not in seen:
            seen.add(r)
            uniq.append(f)
    return sorted(uniq, key=lambda p: str(p).lower())


def fingerprint_tree(roots: list[Path]) -> TreeFingerprint:
    """Content digest + stat token over every file under roots."""
    files = _iter_source_files(roots)
    content = hashlib.sha256()
    stat_tok = hashlib.sha256()
    max_mtime = 0
    for f in files:
        rel = str(f).lower()
        try:
            raw = f.read_bytes()
            st = f.stat()
        except OSError:
            continue
        content.update(rel.encode("utf-8"))
        content.update(b"\0")
        content.update(raw)
        content.update(b"\0")
        stat_tok.update(rel.encode("utf-8"))
        stat_tok.update(f"{st.st_size}:{st.st_mtime_ns}".encode("utf-8"))
        stat_tok.update(b"\0")
        max_mtime = max(max_mtime, st.st_mtime_ns)
    return TreeFingerprint(
        content_hash=content.hexdigest(),
        mtime_token=stat_tok.hexdigest(),
        file_count=len(files),
        max_mtime_ns=max_mtime,
    )


def _index_capabilities(roots: list[Path]) -> list[dict[str, Any]]:
    """Index SKILL.md frontmatter skills and {name,description} JSON docs."""
    caps: list[dict[str, Any]] = []
    for f in _iter_source_files(roots):
        lower = f.name.lower()
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        name: str | None = None
        desc: str | None = None
        if lower.endswith(".md"):
            if text.startswith("---"):
                lines = text.splitlines()[1:]
                for line in lines:
                    if line.strip() == "---":
                        break
                    if ":" not in line:
                        continue
                    key, _, val = line.partition(":")
                    key = key.strip().lower()
                    val = val.strip()
                    if key == "name" and not name:
                        name = val
                    elif key == "description" and not desc:
                        desc = val
        elif lower.endswith(".json"):
            try:
                doc = json.loads(text)
            except json.JSONDecodeError:
                doc = None
            if isinstance(doc, dict):
                name = str(doc.get("name") or "") or None
                desc = str(doc.get("description") or "") or None
        if name and desc:
            caps.append(
                {
                    "capability_id": name,
                    "description": desc,
                    "source_path": str(f).replace("\\", "/"),
                }
            )
    return caps


def _build_index(roots: list[Path]) -> tuple[dict[str, Any], TreeFingerprint]:
    fp = fingerprint_tree(roots)
    caps = _index_capabilities(roots)
    index = {
        "schema": CACHE_SCHEMA,
        "content_hash": fp.content_hash,
        "mtime_token": fp.mtime_token,
        "file_count": fp.file_count,
        "max_mtime_ns": fp.max_mtime_ns,
        "capabilities": caps,
    }
    return index, fp


def write_cache_atomic(cache_path: Path, doc: dict[str, Any]) -> None:
    """Tmp + os.replace publish of a cache document."""
    cache_path = Path(cache_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    fd, tmp_name = tempfile.mkstemp(
        dir=str(cache_path.parent), prefix=".cache-", suffix=".tmp"
    )
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, cache_path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def diagnose_cache(cache_path: Path) -> str:
    """Recovery class of an on-disk cache document."""
    cache_path = Path(cache_path)
    if not cache_path.is_file():
        return _DIAG_MISSING
    try:
        size = cache_path.stat().st_size
    except OSError:
        return _DIAG_MISSING
    if size == 0:
        return _DIAG_ZERO_BYTE
    try:
        doc = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return _DIAG_TRUNCATED
    if not isinstance(doc, dict) or doc.get("schema") != CACHE_SCHEMA:
        return _DIAG_WRONG_SCHEMA
    if not doc.get("capabilities"):
        return _DIAG_EMPTY_INDEX
    return _DIAG_OK


def assert_index_usable(doc: Any) -> None:
    """An index with no capabilities is a failure, never an OK."""
    if not isinstance(doc, dict):
        raise EmptyIndexError("index document is not an object")
    if doc.get("schema") != CACHE_SCHEMA:
        raise EmptyIndexError(f"index schema is not {CACHE_SCHEMA}")
    if not doc.get("capabilities"):
        raise EmptyIndexError("index carries zero capabilities - not usable")


def load_or_rebuild(cache_path: Path, roots: list[Path]) -> CacheOutcome:
    """Serve the cached index when it matches the live tree; else rebuild.

    Rebuild reasons carry the diagnosed cause: missing / truncated /
    zero-byte / wrong-schema / stale-hash / stale-mtime.
    """
    cache_path = Path(cache_path)
    fp = fingerprint_tree(roots)
    diag = diagnose_cache(cache_path)

    if diag == _DIAG_OK:
        try:
            doc = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            doc = None
        if isinstance(doc, dict):
            if doc.get("content_hash") != fp.content_hash:
                return _rebuild(cache_path, roots, fp, "stale-hash")
            if doc.get("mtime_token") != fp.mtime_token:
                return _rebuild(cache_path, roots, fp, "stale-mtime")
            try:
                assert_index_usable(doc)
            except EmptyIndexError:
                return _rebuild(cache_path, roots, fp, "empty-index")
            return CacheOutcome(
                action="cache-hit", reason="ok", fingerprint=fp, index=doc
            )
    reason_map = {
        _DIAG_MISSING: "missing",
        _DIAG_TRUNCATED: "truncated",
        _DIAG_ZERO_BYTE: "zero-byte",
        _DIAG_WRONG_SCHEMA: "wrong-schema",
        _DIAG_EMPTY_INDEX: "empty-index",
    }
    return _rebuild(cache_path, roots, fp, reason_map.get(diag, "missing"))


def _rebuild(
    cache_path: Path, roots: list[Path], fp: TreeFingerprint, reason: str
) -> CacheOutcome:
    index, live_fp = _build_index(roots)
    if not index["capabilities"]:
        # Fail closed: a rebuild that finds nothing is a defect, never an OK.
        raise EmptyIndexError(
            f"rebuild over sources produced zero capabilities ({reason})"
        )
    write_cache_atomic(cache_path, index)
    return CacheOutcome(
        action="rebuilt", reason=reason, fingerprint=live_fp, index=index
    )
