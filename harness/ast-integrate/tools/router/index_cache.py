"""Capability-index cache with safe invalidation (IMP-0402).

The router answers from an index of the installed capabilities (skills'
``SKILL.md`` front matter, plugin manifests). That index is cached on disk so a
query does not re-read every capability, which creates the classic staleness
bug: edit a description, keep getting the old answer. This module makes the
cache safe:

* :func:`fingerprint_tree` hashes every file under the capability roots twice:
  a *content hash* (bytes) and an *mtime token* (size + mtime_ns). Either one
  changing invalidates the cache, so a touch without a byte change rebuilds
  too (``stale-mtime``) and an edit rebuilds as ``stale-hash``.
* :func:`diagnose_cache` names what is wrong with a cache file (``missing``,
  ``zero-byte``, ``truncated``, ``malformed-json``, ``wrong-schema``,
  ``empty-index`` or ``ok``) so recovery is typed instead of a bare except.
* :func:`load_or_rebuild` serves a hit only when the file is ``ok`` *and* both
  fingerprints match; anything else rebuilds from the sources and rewrites the
  cache atomically. An index with zero capabilities is never served or written:
  it raises :class:`EmptyIndexError` every time (no two-strikes softening).
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

CACHE_SCHEMA = "ast.capability-index-cache/v1"

ACTION_HIT = "cache-hit"
ACTION_REBUILT = "rebuilt"

REASON_OK = "ok"
REASON_MISSING = "missing"
REASON_ZERO_BYTE = "zero-byte"
REASON_TRUNCATED = "truncated"
REASON_MALFORMED = "malformed-json"
REASON_WRONG_SCHEMA = "wrong-schema"
REASON_EMPTY_INDEX = "empty-index"
REASON_STALE_HASH = "stale-hash"
REASON_STALE_MTIME = "stale-mtime"

SKILL_FILE = "SKILL.md"
MANIFEST_SUFFIX = ".json"
_EXCLUDED_DIRS = {".git", "__pycache__", "node_modules"}


class IndexCacheError(RuntimeError):
    """Base class for typed cache failures."""


class EmptyIndexError(IndexCacheError):
    """A capability index with zero capabilities: a failure, never OK."""


class CacheSchemaError(IndexCacheError):
    """The cache document is not a ``CACHE_SCHEMA`` capability index."""


@dataclass(frozen=True)
class TreeFingerprint:
    """Two independent staleness signals over a set of capability roots."""

    content_hash: str
    mtime_token: str
    file_count: int
    max_mtime_ns: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CacheLoad:
    """Result of :func:`load_or_rebuild`."""

    action: str
    reason: str
    index: dict[str, Any]
    fingerprint: TreeFingerprint
    cache_path: str
    capabilities: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "reason": self.reason,
            "cache_path": self.cache_path,
            "fingerprint": self.fingerprint.to_dict(),
            "capability_count": len(self.capabilities),
        }


# --------------------------------------------------------------------------- files


def _iter_files(root: Path) -> Iterable[Path]:
    root = Path(root)
    if not root.is_dir():
        return
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = sorted(current.iterdir(), key=lambda p: p.name)
        except OSError:
            continue
        for entry in entries:
            if entry.is_symlink():
                continue
            if entry.is_dir():
                if entry.name not in _EXCLUDED_DIRS:
                    stack.append(entry)
            elif entry.is_file():
                yield entry


def _source_path(root: Path, file: Path) -> str:
    rel = file.relative_to(root).as_posix()
    return f"{root.name}/{rel}"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fingerprint_tree(roots: Sequence[Path | str]) -> TreeFingerprint:
    """Hash the bytes and the (size, mtime_ns) of every file under ``roots``.

    Roots that do not exist contribute nothing; an empty forest has a defined
    fingerprint (the hash of nothing) so a later rebuild can still compare.
    """
    content_rows: list[str] = []
    mtime_rows: list[str] = []
    count = 0
    max_mtime = 0
    for raw_root in roots:
        root = Path(raw_root).resolve()
        for file in _iter_files(root):
            try:
                data = file.read_bytes()
                st = file.stat()
            except OSError:
                continue
            rel = _source_path(root, file)
            content_rows.append(f"{rel}\0{_sha256_bytes(data)}")
            mtime_rows.append(f"{rel}\0{st.st_size}\0{st.st_mtime_ns}")
            count += 1
            max_mtime = max(max_mtime, int(st.st_mtime_ns))
    content_rows.sort()
    mtime_rows.sort()
    content_hash = _sha256_bytes("\n".join(content_rows).encode("utf-8"))
    mtime_token = _sha256_bytes("\n".join(mtime_rows).encode("utf-8"))
    return TreeFingerprint(
        content_hash=content_hash,
        mtime_token=mtime_token,
        file_count=count,
        max_mtime_ns=max_mtime,
    )


# --------------------------------------------------------------------- front matter


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _parse_frontmatter(text: str) -> dict[str, str]:
    """Parse a ``---`` delimited YAML-ish front-matter block into flat strings.

    Only ``key: value`` scalars are recognised; nested structures are kept as
    their raw text. CRLF and LF input parse identically. Text without a front
    matter block yields an empty dict rather than raising.
    """
    if not isinstance(text, str):
        raise TypeError(f"_parse_frontmatter expects str, got {type(text).__name__}")
    normalised = text.replace("\r\n", "\n").replace("\r", "\n")
    if normalised.startswith("\ufeff"):
        normalised = normalised[1:]
    lines = normalised.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}
    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return fields
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith((" ", "\t")):
            # continuation of the previous scalar (folded value)
            if fields:
                last = next(reversed(fields))
                fields[last] = (fields[last] + " " + line.strip()).strip()
            continue
        key, sep, value = line.partition(":")
        if not sep or not key.strip():
            continue
        fields[key.strip()] = _unquote(value)
    # unterminated block: treat as no front matter
    return {}


# ------------------------------------------------------------------- index build


def _capability_from_skill(
    root: Path, file: Path, data: bytes
) -> dict[str, Any] | None:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    fields = _parse_frontmatter(text)
    name = fields.get("name") or file.parent.name
    if not name:
        return None
    return {
        "capability_id": name,
        "kind": "skill",
        "name": name,
        "description": fields.get("description", ""),
        "source_path": _source_path(root, file),
        "sha256": _sha256_bytes(data),
    }


def _capability_from_manifest(
    root: Path, file: Path, data: bytes
) -> dict[str, Any] | None:
    try:
        doc = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(doc, dict):
        return None
    name = doc.get("name") or doc.get("capability_id") or doc.get("id")
    if not isinstance(name, str) or not name or "description" not in doc:
        return None
    return {
        "capability_id": name,
        "kind": "plugin",
        "name": name,
        "description": str(doc.get("description") or ""),
        "source_path": _source_path(root, file),
        "sha256": _sha256_bytes(data),
    }


def scan_capabilities(roots: Sequence[Path | str]) -> list[dict[str, Any]]:
    """Read every capability source under ``roots`` into index rows."""
    rows: list[dict[str, Any]] = []
    for raw_root in roots:
        root = Path(raw_root).resolve()
        for file in _iter_files(root):
            try:
                data = file.read_bytes()
            except OSError:
                continue
            row: dict[str, Any] | None = None
            if file.name == SKILL_FILE:
                row = _capability_from_skill(root, file, data)
            elif file.suffix == MANIFEST_SUFFIX:
                row = _capability_from_manifest(root, file, data)
            if row is not None:
                rows.append(row)
    rows.sort(key=lambda r: (r["capability_id"], r["source_path"]))
    return rows


def build_index(
    roots: Sequence[Path | str], fingerprint: TreeFingerprint | None = None
) -> dict[str, Any]:
    """Build a fresh index document from sources (never from a cache)."""
    fp = fingerprint or fingerprint_tree(roots)
    return {
        "schema": CACHE_SCHEMA,
        "content_hash": fp.content_hash,
        "mtime_token": fp.mtime_token,
        "file_count": fp.file_count,
        "max_mtime_ns": fp.max_mtime_ns,
        "roots": [Path(r).resolve().name for r in roots],
        "capabilities": scan_capabilities(roots),
    }


def assert_index_usable(doc: Any) -> dict[str, Any]:
    """Raise unless ``doc`` is a well-formed, non-empty capability index."""
    if not isinstance(doc, dict):
        raise CacheSchemaError(f"index document is {type(doc).__name__}, not an object")
    if doc.get("schema") != CACHE_SCHEMA:
        raise CacheSchemaError(
            f"index schema {doc.get('schema')!r} != {CACHE_SCHEMA!r}"
        )
    for key in ("content_hash", "mtime_token"):
        if not isinstance(doc.get(key), str) or not doc.get(key):
            raise CacheSchemaError(f"index lacks {key}")
    caps = doc.get("capabilities")
    if not isinstance(caps, list):
        raise CacheSchemaError("index capabilities is not a list")
    if len(caps) == 0:
        raise EmptyIndexError("empty rebuilt index is a failure, not OK")
    for i, row in enumerate(caps):
        if not isinstance(row, dict) or not row.get("capability_id"):
            raise CacheSchemaError(f"capability row #{i} lacks capability_id")
    return doc


# ------------------------------------------------------------------- cache file


def _looks_truncated(text: str) -> bool:
    """True when the JSON text ends inside an open string/array/object."""
    depth = 0
    in_string = False
    escape = False
    for ch in text:
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
    return in_string or depth > 0


def read_cache_document(path: Path | str) -> tuple[str, dict[str, Any] | None]:
    """Return ``(diagnosis, document)``; ``document`` is only set for ``ok``."""
    p = Path(path)
    if not p.is_file():
        return REASON_MISSING, None
    try:
        data = p.read_bytes()
    except OSError:
        return REASON_MISSING, None
    if len(data) == 0:
        return REASON_ZERO_BYTE, None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return REASON_MALFORMED, None
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return (REASON_TRUNCATED if _looks_truncated(text) else REASON_MALFORMED), None
    try:
        assert_index_usable(doc)
    except EmptyIndexError:
        return REASON_EMPTY_INDEX, None
    except CacheSchemaError:
        return REASON_WRONG_SCHEMA, None
    return REASON_OK, doc


def diagnose_cache(path: Path | str) -> str:
    """Name the state of a cache file without loading it into service."""
    return read_cache_document(path)[0]


def write_cache_atomic(path: Path | str, doc: dict[str, Any]) -> Path:
    """Write ``doc`` as canonical JSON via temp file + ``os.replace``.

    Readers never observe a half-written cache: they see the old bytes or the
    new ones.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    fd, tmp_name = tempfile.mkstemp(
        prefix=target.name + ".", suffix=".tmp", dir=str(target.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, target)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return target


def load_or_rebuild(cache_path: Path | str, roots: Sequence[Path | str]) -> CacheLoad:
    """Serve the cache only when it is intact and both fingerprints match.

    Raises :class:`EmptyIndexError` when the sources yield no capability; the
    empty index is neither served nor written, so the next call fails the same
    way instead of being softened into a hit.
    """
    cache = Path(cache_path)
    fp = fingerprint_tree(roots)
    diagnosis, doc = read_cache_document(cache)
    if diagnosis == REASON_OK and doc is not None:
        if doc.get("content_hash") != fp.content_hash:
            reason = REASON_STALE_HASH
        elif doc.get("mtime_token") != fp.mtime_token:
            reason = REASON_STALE_MTIME
        else:
            return CacheLoad(
                action=ACTION_HIT,
                reason=REASON_OK,
                index=doc,
                fingerprint=fp,
                cache_path=str(cache),
                capabilities=list(doc.get("capabilities") or []),
            )
    else:
        reason = diagnosis
    fresh = build_index(roots, fp)
    assert_index_usable(fresh)
    write_cache_atomic(cache, fresh)
    return CacheLoad(
        action=ACTION_REBUILT,
        reason=reason,
        index=fresh,
        fingerprint=fp,
        cache_path=str(cache),
        capabilities=list(fresh["capabilities"]),
    )


__all__ = [
    "ACTION_HIT",
    "ACTION_REBUILT",
    "CACHE_SCHEMA",
    "CacheLoad",
    "CacheSchemaError",
    "EmptyIndexError",
    "IndexCacheError",
    "TreeFingerprint",
    "assert_index_usable",
    "build_index",
    "diagnose_cache",
    "fingerprint_tree",
    "load_or_rebuild",
    "read_cache_document",
    "scan_capabilities",
    "write_cache_atomic",
]
