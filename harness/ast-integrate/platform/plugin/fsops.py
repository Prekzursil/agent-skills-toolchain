"""Filesystem layer: containment, reserved names, long paths, atomic writes, EOL-stable hashing.

Four hard-won rules are enforced here rather than left to callers:

1. **Containment.** Every relative path is resolved against a root and re-checked for
   containment, so a ``..`` segment, a drive-absolute path, or a UNC path can never escape a
   staging or install prefix (``E_IO``).
2. **Reserved device names.** Windows resolves ``CON``, ``NUL``, ``COM1`` … as devices at any
   path depth, so a payload entry named ``nul`` silently becomes a black hole. Rejected.
3. **Long paths.** Windows APIs cap at 260 chars unless the path carries the ``\\\\?\\`` prefix.
4. **EOL-normalised hashing.** Git stores LF, Windows checks out CRLF, so hashing working-tree
   bytes reports drift that does not exist. Every content comparison in this package uses
   ``content_hash`` (LF-normalised); ``raw_hash`` exists only where the exact bytes matter
   (archive determinism).
"""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path, PurePosixPath

from .errors import PluginError

#: Windows device names, matched case-insensitively against the stem of every segment.
RESERVED_STEMS = frozenset(
    {"con", "prn", "aux", "nul", "clock$"}
    | {f"com{i}" for i in range(1, 10)}
    | {f"lpt{i}" for i in range(1, 10)}
)

#: Conservative ceiling; beyond this a Windows path needs the extended prefix.
LONG_PATH_THRESHOLD = 240


def is_reserved_segment(segment: str) -> bool:
    """True if ``segment`` resolves to a Windows device regardless of extension."""
    stem = segment.split(".", 1)[0].strip().lower()
    return stem in RESERVED_STEMS


def check_relpath(rel: str) -> PurePosixPath:
    """Validate a payload-relative path. Raises ``E_IO`` rather than returning a sentinel."""
    if not rel or rel != rel.strip():
        raise PluginError("E_IO", f"empty or space-padded relative path: {rel!r}")
    unified = rel.replace("\\", "/")
    if unified.startswith("/") or unified.startswith("//"):
        raise PluginError(
            "E_IO", f"absolute or UNC path is not payload-relative: {rel!r}"
        )
    if len(unified) > 1 and unified[1] == ":":
        raise PluginError(
            "E_IO", f"drive-absolute path is not payload-relative: {rel!r}"
        )
    parts = [p for p in unified.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        raise PluginError("E_IO", f"parent-directory segment escapes the root: {rel!r}")
    for p in parts:
        if is_reserved_segment(p):
            raise PluginError(
                "E_IO", f"reserved device name in path: {rel!r} (segment {p!r})"
            )
    if not parts:
        raise PluginError("E_IO", f"path resolves to the root itself: {rel!r}")
    return PurePosixPath("/".join(parts))


def safe_join(root: Path, rel: str) -> Path:
    """Join and prove containment. The only sanctioned way to turn a manifest path into a file."""
    checked = check_relpath(rel)
    root_res = Path(os.path.abspath(root))
    target = Path(os.path.abspath(root_res / Path(str(checked))))
    try:
        target.relative_to(root_res)
    except ValueError as exc:  # pragma: no cover - defence in depth
        raise PluginError(
            "E_IO", f"path escaped its root: {rel!r} -> {target}"
        ) from exc
    return target


def extended(path: Path) -> Path:
    """Add the Windows extended-length prefix when the path is long enough to need it."""
    if os.name != "nt":
        return path
    s = str(path)
    if len(s) < LONG_PATH_THRESHOLD or s.startswith("\\\\?\\"):
        return path
    if s.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + s.lstrip("\\"))
    return Path("\\\\?\\" + s)


def _read(path: Path) -> bytes:
    try:
        return extended(path).read_bytes()
    except OSError as exc:
        raise PluginError("E_IO", f"cannot read {path}: {exc}") from exc


def normalise_eol(data: bytes) -> bytes:
    """CRLF and lone CR -> LF. Applied to text-shaped bytes only."""
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def looks_binary(data: bytes) -> bool:
    """A NUL byte in the first 8 KiB is the standard binary tell; git uses the same heuristic."""
    return b"\x00" in data[:8192]


def content_hash(path: Path) -> str:
    """sha256 over LF-normalised bytes for text, raw bytes for binary. Platform-stable."""
    data = _read(path)
    if not looks_binary(data):
        data = normalise_eol(data)
    return hashlib.sha256(data).hexdigest()


def hash_bytes(data: bytes) -> str:
    if not looks_binary(data):
        data = normalise_eol(data)
    return hashlib.sha256(data).hexdigest()


def raw_hash(path: Path) -> str:
    """sha256 over exact bytes. Only for archive determinism, never for drift."""
    return hashlib.sha256(_read(path)).hexdigest()


def normalised_size(path: Path) -> int:
    """Byte length of the content AS SHIPPED (LF-normalised for text).

    ``stat().st_size`` is the wrong number for any artifact that records what a package contains:
    a CRLF working-tree copy of the same file is 1 byte per line larger, so recording ``st_size``
    made two builds of identical content produce different inventories — and therefore different
    archives. Measured: a 2-line file gave 12 vs 10 and broke reproducibility.
    """
    data = _read(path)
    if not looks_binary(data):
        data = normalise_eol(data)
    return len(data)


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Write via a sibling temp file + ``os.replace``. A killed run cannot leave a half file."""
    target = extended(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(target.parent), prefix=".tmp-", suffix=".part")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, str(target))
    except OSError as exc:
        with contextlib_suppress():
            os.unlink(tmp)
        raise PluginError("E_IO", f"atomic write failed for {path}: {exc}") from exc


def atomic_write_text(path: Path, text: str, *, eol: str = "\n") -> None:
    """Write text with an explicitly chosen line ending (never the platform default)."""
    body = normalise_eol(text.encode("utf-8"))
    if eol != "\n":
        body = body.replace(b"\n", eol.encode("ascii"))
    atomic_write_bytes(path, body)


class contextlib_suppress:
    """Tiny local suppressor; avoids importing contextlib just for one unlink."""

    def __enter__(self) -> None:
        return None

    def __exit__(self, *exc: object) -> bool:
        return True


#: Retry budget for a directory rename on Windows. MEASURED in this package's own test suite:
#: ``os.replace`` of a freshly written staging directory onto a non-existent destination raised
#: ``PermissionError: [WinError 5] Access is denied`` on 1 of 30 runs, while the same code path
#: succeeded on the other 29 — a transient handle held by the indexer/AV, not a logic error. A
#: bare ``os.replace`` therefore makes install FLAKY on Windows.
DIR_MOVE_ATTEMPTS = 6
DIR_MOVE_BACKOFF = 0.15


def move_dir(src: Path, dest: Path) -> str:
    """Move a directory, atomically when the OS lets us. Returns the strategy actually used.

    ``rename`` is preferred and is atomic. If Windows refuses it transiently, we retry with a
    short backoff; only if every retry fails do we fall back to copy-then-delete, which is not
    atomic but IS safe here because the caller registers ``rmtree(dest)`` as the transaction's
    inverse before this runs.
    """
    import time

    last: OSError | None = None
    for attempt in range(DIR_MOVE_ATTEMPTS):
        try:
            os.replace(str(extended(src)), str(extended(dest)))
            return "rename" if attempt == 0 else f"rename-after-{attempt}-retries"
        except OSError as exc:
            last = exc
            time.sleep(DIR_MOVE_BACKOFF * (attempt + 1))
    try:
        shutil.copytree(str(extended(src)), str(extended(dest)), dirs_exist_ok=True)
    except OSError as exc:
        raise PluginError(
            "E_IO",
            f"cannot move {src} -> {dest}: rename failed {DIR_MOVE_ATTEMPTS}x ({last}) and the "
            f"copy fallback also failed ({exc})",
        ) from exc
    rmtree(src)
    return "copy-fallback"


def iter_files(root: Path) -> Iterator[Path]:
    """Every regular file under ``root``, deterministic order, symlinks not followed."""
    if not root.exists():
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            p = Path(dirpath) / name
            if p.is_symlink() or not p.is_file():
                continue
            yield p


def relposix(root: Path, path: Path) -> str:
    """Repo-relative POSIX path. The single canonical spelling used in every artifact."""
    return path.relative_to(root).as_posix()


def case_collisions(relpaths: list[str]) -> list[list[str]]:
    """Groups of paths that differ only by case: fatal on macOS/Windows, invisible on Linux."""
    buckets: dict[str, list[str]] = {}
    for rel in relpaths:
        buckets.setdefault(rel.lower(), []).append(rel)
    return [sorted(v) for v in buckets.values() if len(v) > 1]


def rmtree(path: Path) -> None:
    """Best-effort recursive delete that tolerates read-only files on Windows."""

    def _onerror(func, target, exc_info):  # type: ignore[no-untyped-def]
        with contextlib_suppress():
            os.chmod(target, 0o700)
            func(target)

    if path.exists():
        shutil.rmtree(extended(path), onexc=lambda f, t, e: _onerror(f, t, e))


def dir_size(root: Path) -> tuple[int, int]:
    """(total bytes, file count) under ``root``."""
    total = 0
    count = 0
    for p in iter_files(root):
        total += p.stat().st_size
        count += 1
    return total, count
