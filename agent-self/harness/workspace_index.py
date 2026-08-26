from __future__ import annotations

import ctypes
import hashlib
import json
import os
import re
import shutil
import sqlite3
import stat
import subprocess
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterator, Sequence
from ctypes import wintypes


SCHEMA_VERSION = 3
STATE_DIRNAME = "workspace-integrity"
DB_FILENAME = "index.sqlite3"
ASSERT_FRESH_DEADLINE_SEC = 0.9
DEFAULT_GIT_TIMEOUT_SEC = 10.0
SQLITE_PROGRESS_STEPS = 1_000
MAX_RELEVANT_FILE_BYTES = 512 * 1024
MAX_POSTIMAGE_BYTES = 512 * 1024
MAX_PLAN_POSTIMAGE_BYTES = 1024 * 1024
MAX_OP_FILES = 16
MAX_OP_DIRS = 4
MAX_OP_DEPTH = 3
MAX_SESSION_FILES = 64
MAX_SESSION_DIRS = 16
MAX_UNRESOLVED = 8
SOURCE_EXTENSIONS = frozenset(
    {
        ".py",
        ".pyi",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".c",
        ".cc",
        ".cpp",
        ".cxx",
        ".h",
        ".hpp",
        ".cs",
        ".go",
        ".java",
        ".kt",
        ".rs",
        ".rb",
        ".php",
        ".swift",
    }
)
DOC_EXTENSIONS = frozenset({".md", ".rst", ".txt", ".adoc"})
RECURRING_BASENAMES = frozenset(
    {"__init__.py", "index.js", "index.jsx", "index.ts", "index.tsx"}
)
SKIP_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".cache",
        ".mypy_cache",
        ".nox",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        "artifacts",
        "dist",
        "build",
        "coverage",
        "gen",
        "generated",
        "out",
        "target",
        "temp",
        "tmp",
        "vendor",
        "vendors",
    }
)
WINDOWS_DEVICE_PREFIX = ("\\\\.\\", "\\\\?\\", "//./", "//?/")
WINDOWS_WILDCARDS = frozenset({"*", "?"})
WINDOWS_RESERVED_NAMES = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "COM6",
        "COM7",
        "COM8",
        "COM9",
        "LPT1",
        "LPT2",
        "LPT3",
        "LPT4",
        "LPT5",
        "LPT6",
        "LPT7",
        "LPT8",
        "LPT9",
    }
)
SYMBOL_PATTERNS = (
    re.compile(
        r"^(?:async[ \t]+def|def|class)[ \t]+([A-Za-z_][A-Za-z0-9_]*)\b",
        re.MULTILINE,
    ),
    re.compile(
        r"^(?:export[ \t]+)?(?:(?:async[ \t]+)?function|class|interface|type)[ \t]+([A-Za-z_][A-Za-z0-9_]*)\b",
        re.MULTILINE,
    ),
    re.compile(r"^(?:func|type)[ \t]+([A-Za-z_][A-Za-z0-9_]*)\b", re.MULTILINE),
    re.compile(
        r"^(?:pub[ \t]+)?(?:fn|struct|enum|trait|type)[ \t]+([A-Za-z_][A-Za-z0-9_]*)\b",
        re.MULTILINE,
    ),
    re.compile(
        r"^(?:public|private|protected|internal)?[ \t]*(?:class|interface|enum)[ \t]+([A-Za-z_][A-Za-z0-9_]*)\b",
        re.MULTILINE,
    ),
)
EXPECTED_TABLES = frozenset(
    {
        "meta",
        "watch_entries",
        "directories",
        "files",
        "doc_families",
        "source_basenames",
        "symbols",
        "reservations",
        "reservation_claims",
    }
)
EXPECTED_COLUMNS = {
    "meta": ("key", "value"),
    "watch_entries": (
        "path",
        "entry_kind",
        "top_level",
        "mtime_ns",
        "ctime_ns",
        "size",
        "inode",
        "device",
        "child_count",
        "child_signature",
    ),
    "directories": ("path", "top_level"),
    "files": ("path", "dir_path", "basename", "top_level", "kind"),
    "doc_families": ("family", "path"),
    "source_basenames": ("basename", "path"),
    "symbols": ("symbol", "path"),
    "reservations": (
        "owner",
        "operation_id",
        "payload_hash",
        "postimage_hash",
        "generation",
        "created_at",
        "status",
        "plan_json",
    ),
    "reservation_claims": (
        "owner",
        "operation_id",
        "claim_kind",
        "claim_key",
        "claim_path",
    ),
}
SCHEMA_DDL = (
    "CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)",
    """
    CREATE TABLE watch_entries(
        path TEXT PRIMARY KEY,
        entry_kind TEXT NOT NULL,
        top_level TEXT NOT NULL,
        mtime_ns INTEGER NOT NULL,
        ctime_ns INTEGER NOT NULL,
        size INTEGER,
        inode TEXT NOT NULL,
        device TEXT NOT NULL,
        child_count INTEGER,
        child_signature TEXT
    )
    """,
    """
    CREATE TABLE directories(
        path TEXT PRIMARY KEY,
        top_level TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE files(
        path TEXT PRIMARY KEY,
        dir_path TEXT NOT NULL,
        basename TEXT NOT NULL,
        top_level TEXT NOT NULL,
        kind TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE doc_families(
        family TEXT NOT NULL,
        path TEXT NOT NULL,
        PRIMARY KEY(family, path)
    )
    """,
    """
    CREATE TABLE source_basenames(
        basename TEXT NOT NULL,
        path TEXT NOT NULL,
        PRIMARY KEY(basename, path)
    )
    """,
    """
    CREATE TABLE symbols(
        symbol TEXT NOT NULL,
        path TEXT NOT NULL,
        PRIMARY KEY(symbol, path)
    )
    """,
    """
    CREATE TABLE reservations(
        owner TEXT NOT NULL,
        operation_id TEXT NOT NULL,
        payload_hash TEXT NOT NULL,
        postimage_hash TEXT NOT NULL,
        generation TEXT NOT NULL,
        created_at TEXT NOT NULL,
        status TEXT NOT NULL,
        plan_json TEXT NOT NULL,
        PRIMARY KEY(owner, operation_id)
    )
    """,
    """
    CREATE TABLE reservation_claims(
        owner TEXT NOT NULL,
        operation_id TEXT NOT NULL,
        claim_kind TEXT NOT NULL,
        claim_key TEXT NOT NULL,
        claim_path TEXT NOT NULL,
        PRIMARY KEY(owner, operation_id, claim_kind, claim_key),
        FOREIGN KEY(owner, operation_id) REFERENCES reservations(owner, operation_id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX reservation_claim_lookup ON reservation_claims(claim_kind, claim_key)",
)

if os.name == "nt":
    _FILE_READ_ATTRIBUTES = 0x0080
    _FILE_SHARE_ALL = 0x00000007
    _OPEN_EXISTING = 3
    _FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
    _INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value

    class _BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("dwFileAttributes", wintypes.DWORD),
            ("ftCreationTime", wintypes.FILETIME),
            ("ftLastAccessTime", wintypes.FILETIME),
            ("ftLastWriteTime", wintypes.FILETIME),
            ("dwVolumeSerialNumber", wintypes.DWORD),
            ("nFileSizeHigh", wintypes.DWORD),
            ("nFileSizeLow", wintypes.DWORD),
            ("nNumberOfLinks", wintypes.DWORD),
            ("nFileIndexHigh", wintypes.DWORD),
            ("nFileIndexLow", wintypes.DWORD),
        ]

    _KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _CREATE_FILE_W = _KERNEL32.CreateFileW
    _CREATE_FILE_W.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    _CREATE_FILE_W.restype = wintypes.HANDLE
    _GET_FILE_INFORMATION_BY_HANDLE = _KERNEL32.GetFileInformationByHandle
    _GET_FILE_INFORMATION_BY_HANDLE.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_BY_HANDLE_FILE_INFORMATION),
    ]
    _GET_FILE_INFORMATION_BY_HANDLE.restype = wintypes.BOOL
    _CLOSE_HANDLE = _KERNEL32.CloseHandle
    _CLOSE_HANDLE.argtypes = [wintypes.HANDLE]
    _CLOSE_HANDLE.restype = wintypes.BOOL


class WorkspaceIndexFailure(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class RepoIdentity:
    repo_root: Path
    git_dir: Path
    common_dir: Path
    key: str


@dataclass(frozen=True)
class MutationOp:
    kind: str
    path: str
    postimage: str | None = None
    source_path: str | None = None

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "path": self.path,
            "source_path": self.source_path,
            "has_postimage": self.postimage is not None,
        }

    def canonical_postimage(self) -> dict[str, Any]:
        return {"path": self.path, "postimage": self.postimage}


@dataclass(frozen=True)
class MutationPlan:
    owner: str
    operation_id: str
    operations: tuple[MutationOp, ...]

    def __post_init__(self) -> None:
        if not self.owner.strip():
            raise ValueError("owner is required")
        if not self.operation_id.strip():
            raise ValueError("operation_id is required")
        if not self.operations:
            raise ValueError("operations are required")

    @property
    def payload_hash(self) -> str:
        return _hash_json([op.canonical_payload() for op in self.operations])

    @property
    def postimage_hash(self) -> str:
        return _hash_json([op.canonical_postimage() for op in self.operations])


@dataclass(frozen=True)
class RefreshReceipt:
    file_count: int
    directory_count: int
    doc_family_count: int
    source_basename_count: int
    symbol_count: int
    watch_entry_count: int
    generation: str


@dataclass(frozen=True)
class ReservationReceipt:
    status: str
    payload_hash: str
    postimage_hash: str
    generation: str


def _hash_json(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_repo_key(path: Path) -> str:
    return hashlib.sha256(str(path).encode("utf-8", "replace")).hexdigest()[:16]


def _normalize_doc_family(path: PurePosixPath) -> str:
    stem = re.sub(r"(?i)(?:[-_ ]v?\d+)+$", "", path.stem.strip())
    normalized = re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")
    return normalized or path.stem.lower()


def _is_doc_path(path: PurePosixPath) -> bool:
    if path.suffix.lower() not in DOC_EXTENSIONS:
        return False
    if len(path.parts) >= 2 and path.parts[0].lower() == "docs":
        return True
    return len(path.parts) == 1 and path.stem.lower().startswith("readme")


def _is_source_path(path: PurePosixPath) -> bool:
    return bool(path.parts) and path.suffix.lower() in SOURCE_EXTENSIONS


def _extract_symbols(text: str) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for pattern in SYMBOL_PATTERNS:
        for match in pattern.finditer(text):
            symbol = match.group(1)
            if symbol not in seen:
                seen.add(symbol)
                ordered.append(symbol)
    return tuple(ordered)


def _contains(base: Path, candidate: Path) -> bool:
    try:
        return os.path.commonpath([str(base), str(candidate)]) == str(base)
    except ValueError:
        return False


def _is_reparse_point(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        attrs = path.lstat().st_file_attributes
    except (AttributeError, OSError):
        return False
    return bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def _file_identity(path: Path, stats: os.stat_result) -> tuple[str, str]:
    if os.name == "nt":
        flags = _FILE_FLAG_BACKUP_SEMANTICS if path.is_dir() else 0
        handle = _CREATE_FILE_W(
            str(path),
            _FILE_READ_ATTRIBUTES,
            _FILE_SHARE_ALL,
            None,
            _OPEN_EXISTING,
            flags,
            None,
        )
        if handle != _INVALID_HANDLE_VALUE:
            try:
                info = _BY_HANDLE_FILE_INFORMATION()
                ok = _GET_FILE_INFORMATION_BY_HANDLE(handle, ctypes.byref(info))
                if ok:
                    return (
                        f"vol:{int(info.dwVolumeSerialNumber):08x}",
                        f"idx:{int(info.nFileIndexHigh):08x}{int(info.nFileIndexLow):08x}",
                    )
            finally:
                _CLOSE_HANDLE(handle)
    return (
        f"dev:{int(getattr(stats, 'st_dev', 0))}",
        f"ino:{int(getattr(stats, 'st_ino', 0))}",
    )


def _file_link_count(path: Path, stats: os.stat_result) -> int:
    if os.name == "nt":
        flags = _FILE_FLAG_BACKUP_SEMANTICS if path.is_dir() else 0
        handle = _CREATE_FILE_W(
            str(path),
            _FILE_READ_ATTRIBUTES,
            _FILE_SHARE_ALL,
            None,
            _OPEN_EXISTING,
            flags,
            None,
        )
        if handle != _INVALID_HANDLE_VALUE:
            try:
                info = _BY_HANDLE_FILE_INFORMATION()
                ok = _GET_FILE_INFORMATION_BY_HANDLE(handle, ctypes.byref(info))
                if ok:
                    return int(info.nNumberOfLinks)
            finally:
                _CLOSE_HANDLE(handle)
    return int(getattr(stats, "st_nlink", 1))


def _ensure_single_link(path: Path, stats: os.stat_result, *, label: str) -> None:
    if _file_link_count(path, stats) != 1:
        raise WorkspaceIndexFailure(
            "workspace_index_uncertain",
            f"hard-link count must be 1: {label}",
        )


def _has_ads(raw: str) -> bool:
    if raw.startswith(("\\\\", "//")):
        return ":" in raw[2:]
    if re.match(r"^[A-Za-z]:[\\/]", raw):
        return ":" in raw[3:]
    return ":" in raw


def _has_reserved_device_component(raw: str) -> bool:
    for component in re.split(r"[\\/]+", raw):
        stem = component.rstrip(" .").split(".", 1)[0]
        if stem and stem.upper() in WINDOWS_RESERVED_NAMES:
            return True
    return False


def _sanitize_relative_path(raw_path: str) -> PurePosixPath:
    raw_text = str(raw_path)
    if raw_text != raw_text.strip():
        raise WorkspaceIndexFailure(
            "workspace_index_uncertain", "path padding is not allowed"
        )
    text = raw_text.replace("\\", "/")
    if not text:
        raise WorkspaceIndexFailure("workspace_index_uncertain", "blank path")
    if text.startswith("/") or re.match(r"^[A-Za-z]:", text):
        raise WorkspaceIndexFailure("workspace_index_uncertain", "absolute path")
    if any(char in text for char in WINDOWS_WILDCARDS):
        raise WorkspaceIndexFailure("workspace_index_uncertain", "wildcard path")
    if "\x00" in text or text.startswith(WINDOWS_DEVICE_PREFIX):
        raise WorkspaceIndexFailure("workspace_index_uncertain", "device path")
    if _has_ads(text) or _has_reserved_device_component(text):
        raise WorkspaceIndexFailure("workspace_index_uncertain", "unsafe path")
    path = PurePosixPath(text)
    if any(part in ("", ".", "..") for part in path.parts):
        raise WorkspaceIndexFailure("workspace_index_uncertain", "relative traversal")
    for part in path.parts:
        if part.endswith((" ", ".")):
            raise WorkspaceIndexFailure(
                "workspace_index_uncertain", "trailing dot/space alias"
            )
        if part.lower() in {".git", ".hg", ".svn"}:
            raise WorkspaceIndexFailure(
                "workspace_index_uncertain", "vcs metadata path"
            )
    return path


def _existing_anchor(path: Path) -> Path:
    current = path.resolve(strict=False)
    if current.exists():
        return current if current.is_dir() else current.parent
    probe = current.parent
    while probe != probe.parent and not probe.exists():
        probe = probe.parent
    if not probe.exists():
        raise WorkspaceIndexFailure(
            "workspace_repo_unavailable",
            f"missing anchor for {path}",
        )
    return probe if probe.is_dir() else probe.parent


def _trusted_git_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for key in ("SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "TEMP", "TMP"):
        value = os.environ.get(key)
        if value:
            env[key] = value
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    env["HOME"] = str(Path.home())
    env["USERPROFILE"] = str(Path.home())
    return env


def _candidate_is_trusted(candidate: Path, *, disallowed_roots: Sequence[Path]) -> bool:
    if not candidate.is_absolute() or not candidate.exists():
        return False
    try:
        resolved = candidate.resolve(strict=True)
    except OSError:
        return False
    for root in disallowed_roots:
        try:
            if _contains(root.resolve(strict=True), resolved):
                return False
        except OSError:
            continue
    home = Path.home()
    try:
        if _contains(home.resolve(strict=True), resolved):
            return False
    except OSError:
        pass
    return True


def _validated_trusted_git(
    candidate: Path | str,
    *,
    disallowed_roots: Sequence[Path],
) -> Path:
    path = Path(candidate)
    if not _candidate_is_trusted(path, disallowed_roots=disallowed_roots):
        raise WorkspaceIndexFailure(
            "workspace_repo_unavailable",
            f"untrusted git executable: {path}",
        )
    return path.resolve(strict=True)


def _remaining_timeout_sec(deadline_monotonic: float | None, cap: float) -> float:
    if deadline_monotonic is None:
        return cap
    remaining = deadline_monotonic - time.monotonic()
    if remaining <= 0:
        raise WorkspaceIndexFailure(
            "workspace_index_deadline",
            "deadline exceeded",
        )
    return min(cap, remaining)


def _require_before_deadline(
    deadline_monotonic: float | None,
    *,
    message: str = "deadline exceeded",
) -> None:
    if deadline_monotonic is not None and time.monotonic() >= deadline_monotonic:
        raise WorkspaceIndexFailure("workspace_index_deadline", message)


def _trusted_git_executable(
    *,
    disallowed_roots: Sequence[Path],
    deadline_monotonic: float | None = None,
) -> Path:
    configured = os.environ.get("HARNESS_TRUSTED_GIT_EXE")
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured))
    try:
        completed = subprocess.run(
            ["where.exe", "git"],
            capture_output=True,
            text=True,
            check=False,
            timeout=_remaining_timeout_sec(deadline_monotonic, DEFAULT_GIT_TIMEOUT_SEC),
            cwd=str(Path.home()),
            env=_trusted_git_env(),
        )
        if completed.returncode == 0:
            candidates.extend(
                Path(line.strip())
                for line in completed.stdout.splitlines()
                if line.strip()
            )
    except subprocess.TimeoutExpired as exc:
        raise WorkspaceIndexFailure("workspace_index_deadline", str(exc)) from exc
    except (FileNotFoundError, OSError):
        pass
    fallback = shutil.which("git")
    if fallback:
        candidates.append(Path(fallback))
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        if _candidate_is_trusted(candidate, disallowed_roots=disallowed_roots):
            return candidate.resolve(strict=True)
    raise WorkspaceIndexFailure(
        "workspace_repo_unavailable",
        "trusted absolute git executable not found",
    )


def resolve_repo_identity(
    repo_path: Path | str,
    *,
    git_executable: Path | str | None = None,
    deadline_monotonic: float | None = None,
) -> RepoIdentity:
    _require_before_deadline(
        deadline_monotonic,
        message="deadline exceeded before repo identity probe",
    )
    anchor = _existing_anchor(Path(repo_path))
    trusted_git = (
        _validated_trusted_git(git_executable, disallowed_roots=(anchor,))
        if git_executable is not None
        else _trusted_git_executable(
            disallowed_roots=(anchor,),
            deadline_monotonic=deadline_monotonic,
        )
    )
    try:
        completed = subprocess.run(
            [
                str(trusted_git),
                "-C",
                str(anchor),
                "rev-parse",
                "--show-toplevel",
                "--absolute-git-dir",
                "--git-common-dir",
                "--is-inside-work-tree",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=_remaining_timeout_sec(deadline_monotonic, DEFAULT_GIT_TIMEOUT_SEC),
            cwd=str(Path.home()),
            env=_trusted_git_env(),
        )
    except subprocess.TimeoutExpired as exc:
        raise WorkspaceIndexFailure("workspace_index_deadline", str(exc)) from exc
    except (FileNotFoundError, OSError) as exc:
        raise WorkspaceIndexFailure("workspace_repo_unavailable", str(exc)) from exc
    if completed.returncode != 0:
        raise WorkspaceIndexFailure(
            "workspace_repo_unavailable",
            completed.stderr.strip()
            or completed.stdout.strip()
            or "git rev-parse failed",
        )
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    if len(lines) != 4 or lines[3].lower() != "true":
        raise WorkspaceIndexFailure(
            "workspace_repo_unavailable",
            "not a real git worktree",
        )
    repo_root = Path(lines[0]).resolve(strict=True)
    git_dir = _resolve_git_path(anchor, lines[1])
    common_dir = _resolve_git_path(anchor, lines[2])
    physical_anchor = anchor.resolve(strict=True)
    if not _contains(repo_root, physical_anchor):
        raise WorkspaceIndexFailure(
            "workspace_repo_unavailable",
            "anchor escaped repo root",
        )
    if _is_reparse_point(repo_root):
        raise WorkspaceIndexFailure(
            "workspace_repo_unavailable",
            "repo root is a reparse point",
        )
    return RepoIdentity(
        repo_root=repo_root,
        git_dir=git_dir,
        common_dir=common_dir,
        key=_canonical_repo_key(repo_root),
    )


def _resolve_git_path(anchor: Path, value: str) -> Path:
    candidate = Path(value)
    target = candidate if candidate.is_absolute() else anchor / candidate
    return target.resolve(strict=True)


def _walk_onerror(exc: OSError) -> None:
    raise WorkspaceIndexFailure("workspace_index_uncertain", str(exc)) from exc


def _iter_repo(
    repo_root: Path,
    *,
    deadline_monotonic: float | None = None,
) -> Iterator[tuple[PurePosixPath, Path, list[str], list[str]]]:
    _require_before_deadline(
        deadline_monotonic,
        message="deadline exceeded before repo traversal",
    )
    for current_root, dirs, files in os.walk(
        repo_root,
        topdown=True,
        onerror=_walk_onerror,
    ):
        _require_before_deadline(
            deadline_monotonic,
            message="deadline exceeded during repo traversal",
        )
        dirs[:] = sorted(
            [name for name in dirs if name.lower() not in SKIP_DIRS],
            key=str.lower,
        )
        files.sort(key=str.lower)
        current = Path(current_root)
        relative = (
            PurePosixPath(".")
            if current == repo_root
            else PurePosixPath(current.relative_to(repo_root).as_posix())
        )
        yield relative, current, list(dirs), list(files)


def _child_listing_signature(path: Path) -> tuple[int, str]:
    entries = _directory_entries(path)
    return len(entries), _hash_json(entries)


def _directory_entries(path: Path) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    try:
        with os.scandir(path) as it:
            for entry in it:
                if (
                    entry.is_dir(follow_symlinks=False)
                    and entry.name.lower() in SKIP_DIRS
                ):
                    continue
                kind = "dir" if entry.is_dir(follow_symlinks=False) else "file"
                entries.append((kind, entry.name))
    except OSError as exc:
        raise WorkspaceIndexFailure("workspace_index_uncertain", str(exc)) from exc
    entries.sort(key=lambda item: (item[0], item[1].lower(), item[1]))
    return entries


def _strict_read_relevant_text(path: Path) -> str:
    return _read_bounded_stable_text(path, MAX_RELEVANT_FILE_BYTES)


def _strict_read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="strict")
    except (OSError, UnicodeDecodeError) as exc:
        raise WorkspaceIndexFailure("workspace_index_uncertain", str(exc)) from exc


def _content_signature(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _utf8_size(text: str) -> int:
    return len(text.encode("utf-8"))


def _is_sqlite_busy_message(exc: sqlite3.OperationalError) -> bool:
    message = str(exc).lower()
    return "locked" in message or "busy" in message


def _stat_signature(stats: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        int(getattr(stats, "st_size", 0)),
        int(getattr(stats, "st_mtime_ns", 0)),
        int(getattr(stats, "st_ctime_ns", 0)),
        int(getattr(stats, "st_dev", 0)),
        int(getattr(stats, "st_ino", 0)),
    )


def _read_bounded_stable_bytes(path: Path, limit: int) -> bytes:
    if not path.is_file():
        raise WorkspaceIndexFailure("workspace_index_uncertain", f"not a file: {path}")
    try:
        with path.open("rb") as fh:
            before = os.fstat(fh.fileno())
            before_sig = _stat_signature(before)
            data = fh.read(limit + 1)
            after = os.fstat(fh.fileno())
    except OSError as exc:
        raise WorkspaceIndexFailure("workspace_index_uncertain", str(exc)) from exc
    after_sig = _stat_signature(after)
    if before_sig != after_sig:
        raise WorkspaceIndexFailure(
            "workspace_index_uncertain",
            f"unstable read while sampling {path}",
        )
    if len(data) > limit:
        raise WorkspaceIndexFailure(
            "workspace_index_uncertain",
            f"relevant file exceeds {limit} bytes: {path}",
        )
    return data


def _read_bounded_stable_text(path: Path, limit: int) -> str:
    data = _read_bounded_stable_bytes(path, limit)
    try:
        return data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise WorkspaceIndexFailure("workspace_index_uncertain", str(exc)) from exc


def _read_prefix_bytes(path: Path, limit: int) -> bytes:
    try:
        with path.open("rb") as fh:
            return fh.read(limit)
    except OSError as exc:
        raise WorkspaceIndexFailure("workspace_index_uncertain", str(exc)) from exc


def _bounded_content_signature(path: Path, limit: int) -> str:
    return hashlib.sha256(_read_bounded_stable_bytes(path, limit)).hexdigest()


class WorkspaceIndex:
    def __init__(
        self,
        *,
        state_root: Path | str,
        repo_path: Path | str,
        git_executable: Path | str | None = None,
        deadline_monotonic: float | None = None,
    ):
        self.state_root = Path(state_root)
        self.deadline_monotonic = deadline_monotonic
        self.git_executable = (
            _validated_trusted_git(git_executable, disallowed_roots=(self.state_root,))
            if git_executable is not None
            else _trusted_git_executable(disallowed_roots=(self.state_root,))
        )
        self.repo = resolve_repo_identity(
            repo_path,
            git_executable=self.git_executable,
            deadline_monotonic=self.deadline_monotonic,
        )
        self.root = self.state_root / STATE_DIRNAME / self.repo.key
        self.db_path = self.root / DB_FILENAME

    def refresh(self) -> RefreshReceipt:
        _require_before_deadline(
            self.deadline_monotonic,
            message="deadline exceeded before refresh",
        )
        self.root.mkdir(parents=True, exist_ok=True)
        watch_rows: list[tuple[Any, ...]] = []
        directory_rows: list[tuple[str, str]] = []
        file_rows: list[tuple[str, str, str, str, str]] = []
        doc_family_rows: list[tuple[str, str]] = []
        basename_rows: list[tuple[str, str]] = []
        symbol_rows: list[tuple[str, str]] = []
        with self._open_connection(require_existing=self.db_path.exists()) as conn:
            self._begin_immediate(conn)
            self._create_schema_if_missing(conn)
            rebuild_reason = self._schema_rebuild_reason(conn)
            if rebuild_reason is not None:
                self._assert_no_active_reservations_locked(conn)
                self._rebuild_schema_locked(conn)
            self._verify_schema(conn)
            self._assert_no_active_reservations_locked(conn)
            for relative_dir, current, child_dirs, child_files in _iter_repo(
                self.repo.repo_root,
                deadline_monotonic=self.deadline_monotonic,
            ):
                _require_before_deadline(
                    self.deadline_monotonic,
                    message="deadline exceeded during refresh traversal",
                )
                if current != self.repo.repo_root and _is_reparse_point(current):
                    raise WorkspaceIndexFailure(
                        "workspace_index_uncertain",
                        f"reparse point detected during refresh: {current}",
                    )
                watch_rows.append(self._directory_watch_row(relative_dir, current))
                dir_path = (
                    ""
                    if relative_dir == PurePosixPath(".")
                    else relative_dir.as_posix()
                )
                if dir_path:
                    directory_rows.append((dir_path, relative_dir.parts[0]))
                for dirname in child_dirs:
                    if _is_reparse_point(current / dirname):
                        raise WorkspaceIndexFailure(
                            "workspace_index_uncertain",
                            f"reparse point detected during refresh: {current / dirname}",
                        )
                for filename in child_files:
                    physical = current / filename
                    if _is_reparse_point(physical):
                        raise WorkspaceIndexFailure(
                            "workspace_index_uncertain",
                            f"reparse point detected during refresh: {physical}",
                        )
                    relative_file = (
                        PurePosixPath(filename)
                        if relative_dir == PurePosixPath(".")
                        else relative_dir / filename
                    )
                    file_entry = self._file_index_rows(relative_file, physical)
                    watch_rows.append(file_entry["watch"])
                    file_rows.append(file_entry["file"])
                    doc_family_rows.extend(file_entry["doc_families"])
                    basename_rows.extend(file_entry["basenames"])
                    symbol_rows.extend(file_entry["symbols"])
            generation = _hash_json(
                {
                    "watch_rows": watch_rows,
                    "directories": directory_rows,
                    "files": file_rows,
                    "doc_families": doc_family_rows,
                    "basenames": basename_rows,
                    "symbols": symbol_rows,
                }
            )
            self._clear_index_state(conn)
            conn.executemany(
                """
                INSERT INTO watch_entries(
                    path, entry_kind, top_level, mtime_ns, ctime_ns, size, inode, device, child_count, child_signature
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                watch_rows,
            )
            conn.executemany(
                "INSERT INTO directories(path, top_level) VALUES(?, ?)",
                directory_rows,
            )
            conn.executemany(
                "INSERT INTO files(path, dir_path, basename, top_level, kind) VALUES(?, ?, ?, ?, ?)",
                file_rows,
            )
            conn.executemany(
                "INSERT INTO doc_families(family, path) VALUES(?, ?)",
                doc_family_rows,
            )
            conn.executemany(
                "INSERT INTO source_basenames(basename, path) VALUES(?, ?)",
                basename_rows,
            )
            conn.executemany(
                "INSERT INTO symbols(symbol, path) VALUES(?, ?)",
                symbol_rows,
            )
            conn.executemany(
                "INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)",
                [
                    ("schema_version", str(SCHEMA_VERSION)),
                    ("repo_root", str(self.repo.repo_root)),
                    ("git_dir", str(self.repo.git_dir)),
                    ("common_dir", str(self.repo.common_dir)),
                    ("refreshed_at", _utc_now()),
                    ("generation", generation),
                    ("health_status", "ok"),
                    ("health_reason", ""),
                    ("health_updated_at", _utc_now()),
                ],
            )
            conn.commit()
        return RefreshReceipt(
            file_count=len(file_rows),
            directory_count=len(directory_rows),
            doc_family_count=len(doc_family_rows),
            source_basename_count=len(basename_rows),
            symbol_count=len(symbol_rows),
            watch_entry_count=len(watch_rows),
            generation=generation,
        )

    def assert_fresh(self) -> None:
        _require_before_deadline(
            self.deadline_monotonic,
            message="deadline exceeded before assert_fresh",
        )
        with self._open_connection(require_existing=True) as conn:
            self._verify_schema(conn)
            self._require_healthy_locked(conn)
            self._assert_fresh_locked(conn, deadline_monotonic=self.deadline_monotonic)

    def reserve(self, plan: MutationPlan) -> ReservationReceipt:
        _require_before_deadline(
            self.deadline_monotonic,
            message="deadline exceeded before reserve",
        )
        with self._open_connection(require_existing=True) as conn:
            self._verify_schema(conn)
            self._begin_immediate(conn)
            self._require_healthy_locked(conn)
            top_levels = self._top_levels(conn)
            normalized_ops = tuple(
                self._normalize_operation(op, top_levels=top_levels)
                for op in plan.operations
            )
            total_postimage_bytes = sum(
                int(op["postimage_bytes"]) for op in normalized_ops
            )
            if total_postimage_bytes > MAX_PLAN_POSTIMAGE_BYTES:
                raise WorkspaceIndexFailure(
                    "workspace_op_limit",
                    "aggregate postimage bytes exceeded",
                )
            self._assert_fresh_locked(conn, deadline_monotonic=self.deadline_monotonic)
            generation = self._generation(conn)
            plan_summary = self._summarize_plan(normalized_ops)
            existing = conn.execute(
                """
                SELECT payload_hash, postimage_hash, generation
                FROM reservations
                WHERE owner = ? AND operation_id = ? AND status = 'reserved'
                """,
                (plan.owner, plan.operation_id),
            ).fetchone()
            if existing is not None:
                payload_hash = str(existing["payload_hash"])
                postimage_hash = str(existing["postimage_hash"])
                existing_generation = str(existing["generation"])
                if (
                    payload_hash == plan.payload_hash
                    and postimage_hash == plan.postimage_hash
                    and existing_generation == generation
                ):
                    conn.rollback()
                    return ReservationReceipt(
                        "idempotent",
                        payload_hash,
                        postimage_hash,
                        existing_generation,
                    )
                raise WorkspaceIndexFailure(
                    "workspace_retry_mismatch",
                    "operation id reused with different reservation state",
                )
            unresolved = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM reservations
                WHERE owner = ? AND status = 'reserved'
                """,
                (plan.owner,),
            ).fetchone()
            if unresolved is None or int(unresolved["count"]) >= MAX_UNRESOLVED:
                raise WorkspaceIndexFailure(
                    "workspace_session_limit",
                    "unresolved limit exceeded",
                )
            outstanding = conn.execute(
                """
                SELECT claim_kind, COUNT(*) AS count
                FROM reservation_claims
                WHERE owner = ?
                GROUP BY claim_kind
                """,
                (plan.owner,),
            ).fetchall()
            session_files = sum(
                int(row["count"]) for row in outstanding if row["claim_kind"] == "file"
            )
            session_dirs = sum(
                int(row["count"]) for row in outstanding if row["claim_kind"] == "dir"
            )
            planned_file_claims = sum(
                1
                for claim_kind, _claim_key, _claim_path in plan_summary["claims"]
                if claim_kind == "file"
            )
            if session_files + planned_file_claims > MAX_SESSION_FILES:
                raise WorkspaceIndexFailure(
                    "workspace_session_limit",
                    "session file slop exceeded",
                )
            if session_dirs + plan_summary["new_dir_count"] > MAX_SESSION_DIRS:
                raise WorkspaceIndexFailure(
                    "workspace_session_limit",
                    "session dir slop exceeded",
                )
            self._check_conflicts(conn, normalized_ops)
            self._assert_fresh_locked(conn, deadline_monotonic=self.deadline_monotonic)
            try:
                conn.execute(
                    """
                    INSERT INTO reservations(
                        owner, operation_id, payload_hash, postimage_hash, generation, created_at, status, plan_json
                    ) VALUES(?, ?, ?, ?, ?, ?, 'reserved', ?)
                    """,
                    (
                        plan.owner,
                        plan.operation_id,
                        plan.payload_hash,
                        plan.postimage_hash,
                        generation,
                        _utc_now(),
                        self._reservation_plan_json(normalized_ops),
                    ),
                )
                conn.executemany(
                    """
                    INSERT INTO reservation_claims(
                        owner, operation_id, claim_kind, claim_key, claim_path
                    ) VALUES(?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            plan.owner,
                            plan.operation_id,
                            claim_kind,
                            claim_key,
                            claim_path,
                        )
                        for claim_kind, claim_key, claim_path in plan_summary["claims"]
                    ],
                )
            except sqlite3.IntegrityError as exc:
                raise WorkspaceIndexFailure(
                    "workspace_index_conflict",
                    str(exc),
                ) from exc
            conn.commit()
            return ReservationReceipt(
                "reserved",
                plan.payload_hash,
                plan.postimage_hash,
                generation,
            )

    def resolve(self, *, owner: str, operation_id: str) -> bool:
        _require_before_deadline(
            self.deadline_monotonic,
            message="deadline exceeded before resolve",
        )
        with self._open_connection(require_existing=True) as conn:
            self._verify_schema(conn)
            self._begin_immediate(conn)
            row = conn.execute(
                """
                SELECT status
                FROM reservations
                WHERE owner = ? AND operation_id = ?
                """,
                (owner, operation_id),
            ).fetchone()
            if row is None:
                conn.rollback()
                return False
            status = str(row["status"])
            if status == "resolved":
                conn.rollback()
                return True
            if status != "reserved":
                conn.rollback()
                return False
            conn.execute(
                "DELETE FROM reservation_claims WHERE owner = ? AND operation_id = ?",
                (owner, operation_id),
            )
            conn.execute(
                """
                UPDATE reservations
                SET status = 'resolved'
                WHERE owner = ? AND operation_id = ?
                """,
                (owner, operation_id),
            )
            conn.commit()
            return True

    def invalidate(self, *, reason: str) -> bool:
        _require_before_deadline(
            self.deadline_monotonic,
            message="deadline exceeded before invalidate",
        )
        with self._open_connection(require_existing=True) as conn:
            self._verify_schema(conn)
            self._begin_immediate(conn)
            self._mark_repo_needs_refresh_locked(conn, reason=reason)
            conn.commit()
            return True

    def abandon_owner(self, *, owner: str) -> bool:
        _require_before_deadline(
            self.deadline_monotonic,
            message="deadline exceeded before abandon_owner",
        )
        with self._open_connection(require_existing=True) as conn:
            self._verify_schema(conn)
            self._begin_immediate(conn)
            rows = conn.execute(
                """
                SELECT operation_id
                FROM reservations
                WHERE owner = ? AND status = 'reserved'
                """,
                (owner,),
            ).fetchall()
            if not rows:
                conn.rollback()
                return False
            try:
                self._assert_fresh_locked(
                    conn,
                    deadline_monotonic=self.deadline_monotonic,
                )
            except WorkspaceIndexFailure as exc:
                self._mark_repo_needs_refresh_locked(
                    conn,
                    reason=f"abandon_owner invalidated: {exc.code}: {exc}",
                )
                conn.commit()
                return False
            operation_ids = [str(row["operation_id"]) for row in rows]
            conn.executemany(
                "DELETE FROM reservation_claims WHERE owner = ? AND operation_id = ?",
                [(owner, operation_id) for operation_id in operation_ids],
            )
            conn.execute(
                """
                UPDATE reservations
                SET status = 'abandoned'
                WHERE owner = ? AND status = 'reserved'
                """,
                (owner,),
            )
            conn.commit()
            return True

    def mark_needs_refresh(
        self,
        *,
        owner: str,
        operation_id: str,
        reason: str,
    ) -> bool:
        _require_before_deadline(
            self.deadline_monotonic,
            message="deadline exceeded before mark_needs_refresh",
        )
        with self._open_connection(require_existing=True) as conn:
            self._verify_schema(conn)
            self._begin_immediate(conn)
            row = conn.execute(
                """
                SELECT status
                FROM reservations
                WHERE owner = ? AND operation_id = ?
                """,
                (owner, operation_id),
            ).fetchone()
            if row is None:
                conn.rollback()
                return False
            status = str(row["status"])
            if status == "needs_refresh":
                conn.rollback()
                return True
            if status != "reserved":
                conn.rollback()
                return False
            self._mark_repo_needs_refresh_locked(
                conn,
                reason=reason,
            )
            conn.commit()
            return True

    def finalize_success(self, *, owner: str, operation_id: str) -> bool:
        _require_before_deadline(
            self.deadline_monotonic,
            message="deadline exceeded before finalize_success",
        )
        with self._open_connection(require_existing=True) as conn:
            self._verify_schema(conn)
            self._begin_immediate(conn)
            row = conn.execute(
                """
                SELECT plan_json, generation, status
                FROM reservations
                WHERE owner = ? AND operation_id = ?
                """,
                (owner, operation_id),
            ).fetchone()
            if row is None:
                conn.rollback()
                return False
            status = str(row["status"])
            if status == "completed":
                conn.rollback()
                return True
            self._require_healthy_locked(conn)
            if status != "reserved":
                conn.rollback()
                return False
            payload = self._load_reservation_plan(str(row["plan_json"]))
            if str(row["generation"]) != self._generation(conn):
                self._mark_repo_needs_refresh_locked(
                    conn,
                    reason="generation changed before finalize",
                )
                conn.commit()
                return False
            for stored_op in payload["operations"]:
                if not self._postimage_matches(stored_op):
                    self._mark_repo_needs_refresh_locked(
                        conn,
                        reason=f"postimage mismatch: {stored_op['path']}",
                    )
                    conn.commit()
                    return False
            try:
                self._assert_expected_directory_state_locked(
                    conn,
                    payload["operations"],
                )
            except WorkspaceIndexFailure as exc:
                self._mark_repo_needs_refresh_locked(
                    conn,
                    reason=f"unexpected directory state: {exc.code}: {exc}",
                )
                conn.commit()
                return False
            self._apply_finalized_operations_locked(
                conn,
                operations=payload["operations"],
            )
            conn.execute(
                """
                UPDATE reservations
                SET status = 'completed'
                WHERE owner = ? AND operation_id = ?
                """,
                (owner, operation_id),
            )
            conn.execute(
                "DELETE FROM reservation_claims WHERE owner = ? AND operation_id = ?",
                (owner, operation_id),
            )
            generation = self._recompute_generation_locked(conn)
            self._set_meta_locked(
                conn,
                generation=generation,
                refreshed_at=_utc_now(),
                health_status="ok",
                health_reason="",
                health_updated_at=_utc_now(),
            )
            self._rebase_active_reservations_locked(
                conn,
                completed_owner=owner,
                completed_operation_id=operation_id,
                generation=generation,
                changed_paths=self._changed_paths(payload["operations"]),
            )
            conn.commit()
            return True

    @contextmanager
    def _open_connection(
        self, *, require_existing: bool
    ) -> Iterator[sqlite3.Connection]:
        if require_existing and not self.db_path.exists():
            raise WorkspaceIndexFailure(
                "workspace_index_missing",
                "index database missing",
            )
        if self.db_path.exists():
            header = _read_prefix_bytes(self.db_path, 16)
            if header and header != b"SQLite format 3\x00":
                raise WorkspaceIndexFailure(
                    "workspace_index_corrupt",
                    "invalid sqlite header",
                )
        try:
            conn = sqlite3.connect(self.db_path, timeout=0, isolation_level=None)
        except sqlite3.OperationalError as exc:
            if _is_sqlite_busy_message(exc):
                raise WorkspaceIndexFailure("workspace_index_busy", str(exc)) from exc
            raise WorkspaceIndexFailure("workspace_index_corrupt", str(exc)) from exc
        except sqlite3.Error as exc:
            raise WorkspaceIndexFailure("workspace_index_corrupt", str(exc)) from exc
        conn.row_factory = sqlite3.Row
        deadline_interrupted = False

        def _deadline_progress_handler() -> int:
            nonlocal deadline_interrupted
            if (
                self.deadline_monotonic is not None
                and time.monotonic() >= self.deadline_monotonic
            ):
                deadline_interrupted = True
                return 1
            return 0

        try:
            if self.deadline_monotonic is not None:
                conn.set_progress_handler(
                    _deadline_progress_handler,
                    SQLITE_PROGRESS_STEPS,
                )
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL").fetchone()
            self._run_integrity_checks(conn)
            yield conn
        except sqlite3.OperationalError as exc:
            if deadline_interrupted or (
                "interrupted" in str(exc).lower()
                and self.deadline_monotonic is not None
                and time.monotonic() >= self.deadline_monotonic
            ):
                raise WorkspaceIndexFailure(
                    "workspace_index_deadline", str(exc)
                ) from exc
            if _is_sqlite_busy_message(exc):
                raise WorkspaceIndexFailure("workspace_index_busy", str(exc)) from exc
            raise WorkspaceIndexFailure("workspace_index_corrupt", str(exc)) from exc
        except sqlite3.DatabaseError as exc:
            raise WorkspaceIndexFailure("workspace_index_corrupt", str(exc)) from exc
        finally:
            try:
                conn.set_progress_handler(None, 0)
            except sqlite3.Error:
                pass
            conn.close()

    def _run_integrity_checks(self, conn: sqlite3.Connection) -> None:
        quick_rows = conn.execute("PRAGMA quick_check").fetchall()
        if len(quick_rows) != 1 or str(quick_rows[0][0]).lower() != "ok":
            raise WorkspaceIndexFailure(
                "workspace_index_corrupt",
                f"quick_check failed: {quick_rows}",
            )
        foreign_rows = conn.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_rows:
            raise WorkspaceIndexFailure(
                "workspace_index_corrupt",
                f"foreign_key_check failed: {foreign_rows}",
            )

    def _begin_immediate(self, conn: sqlite3.Connection) -> None:
        try:
            conn.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as exc:
            if _is_sqlite_busy_message(exc):
                raise WorkspaceIndexFailure("workspace_index_busy", str(exc)) from exc
            raise WorkspaceIndexFailure("workspace_index_corrupt", str(exc)) from exc

    def _create_schema_if_missing(self, conn: sqlite3.Connection) -> None:
        tables = {
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        if tables:
            return
        for statement in SCHEMA_DDL:
            conn.execute(statement)

    def _verify_schema(self, conn: sqlite3.Connection) -> None:
        tables = {
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        if tables != EXPECTED_TABLES:
            raise WorkspaceIndexFailure(
                "workspace_index_corrupt",
                f"unexpected sqlite schema: {sorted(tables)}",
            )
        for table_name, expected_columns in EXPECTED_COLUMNS.items():
            rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
            columns = tuple(str(row["name"]) for row in rows)
            if columns != expected_columns:
                raise WorkspaceIndexFailure(
                    "workspace_index_corrupt",
                    f"unexpected columns for {table_name}: {columns}",
                )
        metadata = {
            row["key"]: row["value"]
            for row in conn.execute("SELECT key, value FROM meta").fetchall()
        }
        rebuild_reason = self._schema_rebuild_reason(conn, metadata=metadata)
        if rebuild_reason is not None:
            raise WorkspaceIndexFailure("workspace_index_stale", rebuild_reason)

    def _schema_rebuild_reason(
        self,
        conn: sqlite3.Connection,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        if metadata is None:
            metadata = {
                row["key"]: row["value"]
                for row in conn.execute("SELECT key, value FROM meta").fetchall()
            }
        watch_info = {
            str(row["name"]): str(row["type"]).upper()
            for row in conn.execute("PRAGMA table_info(watch_entries)").fetchall()
        }
        if watch_info.get("inode") != "TEXT" or watch_info.get("device") != "TEXT":
            return "legacy identity storage requires refresh rebuild"
        schema_version = metadata.get("schema_version")
        if schema_version is None:
            return None
        if str(schema_version) != str(SCHEMA_VERSION):
            return "schema version mismatch requires refresh rebuild"
        return None

    def _rebuild_schema_locked(self, conn: sqlite3.Connection) -> None:
        conn.execute("DROP INDEX IF EXISTS reservation_claim_lookup")
        for table in (
            "reservation_claims",
            "reservations",
            "symbols",
            "source_basenames",
            "doc_families",
            "files",
            "directories",
            "watch_entries",
            "meta",
        ):
            conn.execute(f"DROP TABLE IF EXISTS {table}")
        self._create_schema_if_missing(conn)

    def _clear_index_state(self, conn: sqlite3.Connection) -> None:
        for table in (
            "watch_entries",
            "directories",
            "files",
            "doc_families",
            "source_basenames",
            "symbols",
        ):
            conn.execute(f"DELETE FROM {table}")

    def _generation(self, conn: sqlite3.Connection) -> str:
        row = conn.execute("SELECT value FROM meta WHERE key = 'generation'").fetchone()
        if row is None or not str(row["value"]).strip():
            raise WorkspaceIndexFailure(
                "workspace_index_corrupt",
                "missing generation metadata",
            )
        return str(row["value"])

    def _top_levels(self, conn: sqlite3.Connection) -> set[str]:
        rows = conn.execute(
            """
            SELECT path
            FROM watch_entries
            WHERE entry_kind = 'dir' AND path <> ''
            """
        ).fetchall()
        top_levels = {str(row["path"]).split("/", 1)[0] for row in rows}
        return top_levels

    def _meta_value(self, conn: sqlite3.Connection, key: str) -> str | None:
        row = conn.execute(
            "SELECT value FROM meta WHERE key = ?",
            (key,),
        ).fetchone()
        return None if row is None else str(row["value"])

    def _set_meta_locked(self, conn: sqlite3.Connection, **entries: str) -> None:
        conn.executemany(
            "INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)",
            sorted(entries.items()),
        )

    def _require_healthy_locked(self, conn: sqlite3.Connection) -> None:
        status = self._meta_value(conn, "health_status") or "ok"
        if status == "ok":
            return
        reason = (
            self._meta_value(conn, "health_reason") or "workspace marked needs_refresh"
        )
        raise WorkspaceIndexFailure("workspace_index_stale", reason)

    def _assert_no_active_reservations_locked(self, conn: sqlite3.Connection) -> None:
        row = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM reservations
            WHERE status = 'reserved'
            """
        ).fetchone()
        claim_row = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM reservation_claims
            INNER JOIN reservations
                ON reservations.owner = reservation_claims.owner
               AND reservations.operation_id = reservation_claims.operation_id
            WHERE reservations.status = 'reserved'
            """
        ).fetchone()
        if row is None or claim_row is None:
            raise WorkspaceIndexFailure(
                "workspace_index_corrupt",
                "failed to inspect active reservations",
            )
        if int(row["count"]) or int(claim_row["count"]):
            raise WorkspaceIndexFailure(
                "workspace_index_stale",
                "refresh blocked by active reservations",
            )

    def _reservation_plan_json(self, operations: Sequence[dict[str, Any]]) -> str:
        return json.dumps(
            {
                "version": 1,
                "operations": [
                    {
                        "kind": str(op["kind"]),
                        "path": op["target"].as_posix(),
                        "source_path": (
                            None if op["source"] is None else op["source"].as_posix()
                        ),
                        "postimage_sha256": (
                            None
                            if op["postimage"] is None
                            else _content_signature(str(op["postimage"]))
                        ),
                    }
                    for op in operations
                ],
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    def _load_reservation_plan(self, raw: str) -> dict[str, Any]:
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise WorkspaceIndexFailure("workspace_index_corrupt", str(exc)) from exc
        if not isinstance(payload, dict):
            raise WorkspaceIndexFailure(
                "workspace_index_corrupt",
                "reservation payload must be an object",
            )
        operations = payload.get("operations")
        if payload.get("version") != 1 or not isinstance(operations, list):
            raise WorkspaceIndexFailure(
                "workspace_index_corrupt",
                "reservation payload shape is invalid",
            )
        normalized: list[dict[str, Any]] = []
        for item in operations:
            if not isinstance(item, dict):
                raise WorkspaceIndexFailure(
                    "workspace_index_corrupt",
                    "reservation operation metadata is invalid",
                )
            normalized.append(
                {
                    "kind": str(item["kind"]),
                    "path": str(item["path"]),
                    "source_path": (
                        None
                        if item.get("source_path") is None
                        else str(item["source_path"])
                    ),
                    "postimage_sha256": (
                        None
                        if item.get("postimage_sha256") is None
                        else str(item["postimage_sha256"])
                    ),
                }
            )
        return {"version": 1, "operations": normalized}

    def _assert_fresh_locked(
        self,
        conn: sqlite3.Connection,
        *,
        deadline_monotonic: float | None = None,
    ) -> None:
        started = time.perf_counter()
        rows = conn.execute(
            """
            SELECT path, entry_kind, mtime_ns, ctime_ns, size, inode, device, child_count, child_signature
            FROM watch_entries
            ORDER BY CASE WHEN path = '' THEN 0 ELSE 1 END, LENGTH(path), path
            """
        )
        saw_row = False
        for row in rows:
            saw_row = True
            if (
                deadline_monotonic is None
                and time.perf_counter() - started > ASSERT_FRESH_DEADLINE_SEC
            ):
                raise WorkspaceIndexFailure(
                    "workspace_index_deadline",
                    "freshness check exceeded soft deadline",
                )
            _require_before_deadline(
                deadline_monotonic,
                message="deadline exceeded during freshness check",
            )
            self._assert_watch_row_matches(str(row["path"]), row)
        if not saw_row:
            raise WorkspaceIndexFailure(
                "workspace_index_corrupt",
                "watch vector is empty",
            )

    def _assert_watch_row_matches(self, relative_path: str, row: sqlite3.Row) -> None:
        physical = (
            self.repo.repo_root
            if not relative_path
            else self.repo.repo_root / Path(relative_path)
        )
        if not physical.exists():
            raise WorkspaceIndexFailure(
                "workspace_index_stale", f"missing path: {relative_path}"
            )
        if _is_reparse_point(physical):
            raise WorkspaceIndexFailure(
                "workspace_index_uncertain",
                f"reparse point detected: {relative_path}",
            )
        resolved = physical.resolve(strict=True)
        if not _contains(self.repo.repo_root, resolved):
            raise WorkspaceIndexFailure(
                "workspace_index_uncertain",
                f"path escaped repo root: {relative_path}",
            )
        current_stat = physical.stat()
        if int(row["mtime_ns"]) != int(current_stat.st_mtime_ns):
            raise WorkspaceIndexFailure(
                "workspace_index_stale",
                f"mtime changed: {relative_path}",
            )
        if int(row["ctime_ns"]) != int(current_stat.st_ctime_ns):
            raise WorkspaceIndexFailure(
                "workspace_index_stale",
                f"ctime changed: {relative_path}",
            )
        entry_kind = str(row["entry_kind"])
        if entry_kind == "dir":
            if not physical.is_dir():
                raise WorkspaceIndexFailure(
                    "workspace_index_stale",
                    f"directory changed type: {relative_path}",
                )
            child_count, child_signature = _child_listing_signature(physical)
            if (
                int(row["child_count"]) != child_count
                or str(row["child_signature"]) != child_signature
            ):
                raise WorkspaceIndexFailure(
                    "workspace_index_stale",
                    f"directory listing changed: {relative_path}",
                )
            return
        if not physical.is_file():
            raise WorkspaceIndexFailure(
                "workspace_index_stale",
                f"file changed type: {relative_path}",
            )
        recorded_signature = row["child_signature"]
        if recorded_signature is None:
            device, inode = _file_identity(physical, current_stat)
            recorded_identity = (str(row["device"]), str(row["inode"]))
            if recorded_identity != (device, inode):
                retry_device, retry_inode = _file_identity(physical, current_stat)
                if recorded_identity == (retry_device, retry_inode):
                    device, inode = retry_device, retry_inode
                else:
                    raise WorkspaceIndexFailure(
                        "workspace_index_stale",
                        f"identity changed: {relative_path}",
                    )
        if int(row["size"]) != int(current_stat.st_size):
            raise WorkspaceIndexFailure(
                "workspace_index_stale",
                f"size changed: {relative_path}",
            )
        if recorded_signature is not None:
            current_signature = _bounded_content_signature(
                physical,
                MAX_RELEVANT_FILE_BYTES,
            )
            if str(recorded_signature) != current_signature:
                raise WorkspaceIndexFailure(
                    "workspace_index_stale",
                    f"content changed: {relative_path}",
                )

    def _normalize_operation(
        self,
        op: MutationOp,
        *,
        top_levels: set[str],
    ) -> dict[str, Any]:
        if op.kind not in {"add", "update", "move", "delete"}:
            raise WorkspaceIndexFailure(
                "workspace_index_uncertain",
                f"unsupported op {op.kind}",
            )
        if op.kind != "move" and op.source_path is not None:
            raise WorkspaceIndexFailure(
                "workspace_index_uncertain",
                "source_path only valid for move",
            )
        target = _sanitize_relative_path(op.path)
        source = (
            _sanitize_relative_path(op.source_path)
            if op.source_path is not None
            else None
        )
        target_path, target_exists = self._materialize_relative_path(
            target,
            allow_missing_leaf=op.kind in {"add", "move"},
            deadline_monotonic=self.deadline_monotonic,
        )
        source_path: Path | None = None
        if source is not None:
            source_path, source_exists = self._materialize_relative_path(
                source,
                allow_missing_leaf=False,
                deadline_monotonic=self.deadline_monotonic,
            )
            if not source_exists:
                raise WorkspaceIndexFailure(
                    "workspace_index_uncertain",
                    "move source missing",
                )
        if op.kind == "add" and target_exists:
            raise WorkspaceIndexFailure(
                "workspace_index_uncertain",
                f"{target.as_posix()} already exists",
            )
        if op.kind in {"add", "move"} and target.parts[0] not in top_levels:
            raise WorkspaceIndexFailure(
                "workspace_top_level_slop",
                f"top-level {target.parts[0]} is new",
            )
        if op.kind in {"update", "delete"} and not target_exists:
            raise WorkspaceIndexFailure(
                "workspace_index_uncertain",
                f"{target.as_posix()} missing for {op.kind}",
            )
        if (
            op.kind in {"update", "delete"}
            and target_exists
            and not target_path.is_file()
        ):
            raise WorkspaceIndexFailure(
                "workspace_index_uncertain",
                f"{target.as_posix()} is not a file",
            )
        if op.kind in {"update", "delete"} and target_exists:
            _ensure_single_link(
                target_path,
                target_path.stat(),
                label=target.as_posix(),
            )
        if op.kind == "move" and source is None:
            raise WorkspaceIndexFailure(
                "workspace_index_uncertain",
                "move source missing",
            )
        if op.kind == "move" and source_path is not None and not source_path.is_file():
            raise WorkspaceIndexFailure(
                "workspace_index_uncertain",
                f"{source.as_posix()} is not a file",
            )
        if op.kind == "move" and source_path is not None:
            _ensure_single_link(
                source_path,
                source_path.stat(),
                label=source.as_posix(),
            )
        if op.kind == "move" and target_exists:
            raise WorkspaceIndexFailure(
                "workspace_index_uncertain",
                "move destination already exists",
            )
        postimage = op.postimage
        if op.kind == "delete" and postimage is not None:
            raise WorkspaceIndexFailure(
                "workspace_index_uncertain",
                "delete cannot carry postimage",
            )
        if op.kind != "delete" and not isinstance(postimage, str):
            raise WorkspaceIndexFailure(
                "workspace_index_uncertain",
                "postimage required",
            )
        postimage_bytes = 0
        if isinstance(postimage, str):
            postimage_bytes = _utf8_size(postimage)
            if postimage_bytes > MAX_POSTIMAGE_BYTES:
                raise WorkspaceIndexFailure(
                    "workspace_op_limit",
                    f"postimage exceeds {MAX_POSTIMAGE_BYTES} bytes",
                )
        return {
            "kind": op.kind,
            "target": target,
            "target_path": target_path,
            "target_key": target.as_posix().lower(),
            "target_exists": target_exists,
            "source": source,
            "source_path": source_path,
            "source_key": source.as_posix().lower() if source is not None else None,
            "postimage": postimage,
            "postimage_bytes": postimage_bytes,
        }

    def _postimage_matches(self, op: dict[str, Any]) -> bool:
        target = _sanitize_relative_path(op["path"])
        target_path, target_exists = self._materialize_relative_path(
            target,
            allow_missing_leaf=False,
            deadline_monotonic=self.deadline_monotonic,
        )
        if op["kind"] == "delete":
            return not target_exists
        if not target_exists:
            return False
        if not target_path.is_file():
            return False
        try:
            _ensure_single_link(
                target_path,
                target_path.stat(),
                label=target.as_posix(),
            )
        except WorkspaceIndexFailure:
            return False
        if _content_signature(
            _read_bounded_stable_text(target_path, MAX_RELEVANT_FILE_BYTES)
        ) != str(op["postimage_sha256"]):
            return False
        if op["kind"] == "move":
            if op["source_path"] is None:
                return False
            source = _sanitize_relative_path(str(op["source_path"]))
            _source_path, source_exists = self._materialize_relative_path(
                source,
                allow_missing_leaf=False,
                deadline_monotonic=self.deadline_monotonic,
            )
            return not source_exists
        return True

    def _directory_watch_row(
        self,
        relative_dir: PurePosixPath,
        physical: Path,
    ) -> tuple[Any, ...]:
        top_level = "" if relative_dir == PurePosixPath(".") else relative_dir.parts[0]
        dir_stat = physical.stat()
        child_count, child_signature = _child_listing_signature(physical)
        device, inode = _file_identity(physical, dir_stat)
        dir_path = "" if relative_dir == PurePosixPath(".") else relative_dir.as_posix()
        return (
            dir_path,
            "dir",
            top_level,
            int(dir_stat.st_mtime_ns),
            int(dir_stat.st_ctime_ns),
            None,
            inode,
            device,
            child_count,
            child_signature,
        )

    def _file_index_rows(
        self,
        relative_file: PurePosixPath,
        physical: Path,
    ) -> dict[str, Any]:
        file_stat = physical.stat()
        file_path = relative_file.as_posix()
        device, inode = _file_identity(physical, file_stat)
        kind = "other"
        content_signature: str | None = None
        doc_families: list[tuple[str, str]] = []
        basenames: list[tuple[str, str]] = []
        symbols: list[tuple[str, str]] = []
        if _is_doc_path(relative_file):
            kind = "doc"
            doc_families.append((_normalize_doc_family(relative_file), file_path))
            content_signature = _content_signature(_strict_read_relevant_text(physical))
        elif _is_source_path(relative_file):
            kind = "source"
            basename = relative_file.name.lower()
            if basename not in RECURRING_BASENAMES:
                basenames.append((basename, file_path))
            text = _strict_read_relevant_text(physical)
            content_signature = _content_signature(text)
            symbols.extend((symbol, file_path) for symbol in _extract_symbols(text))
        return {
            "watch": (
                file_path,
                "file",
                relative_file.parts[0],
                int(file_stat.st_mtime_ns),
                int(file_stat.st_ctime_ns),
                int(file_stat.st_size),
                inode,
                device,
                None,
                content_signature,
            ),
            "file": (
                file_path,
                ""
                if relative_file.parent == PurePosixPath(".")
                else relative_file.parent.as_posix(),
                relative_file.name.lower(),
                relative_file.parts[0],
                kind,
            ),
            "doc_families": doc_families,
            "basenames": basenames,
            "symbols": symbols,
        }

    def _changed_paths(self, operations: Sequence[dict[str, Any]]) -> set[str]:
        changed: set[str] = set()
        for op in operations:
            changed.add(str(op["path"]).lower())
            if op["source_path"] is not None:
                changed.add(str(op["source_path"]).lower())
        return changed

    def _mark_repo_needs_refresh_locked(
        self,
        conn: sqlite3.Connection,
        *,
        reason: str,
    ) -> None:
        conn.execute(
            """
            UPDATE reservations
            SET status = 'needs_refresh'
            WHERE status = 'reserved'
            """
        )
        conn.execute("DELETE FROM reservation_claims")
        self._set_meta_locked(
            conn,
            health_status="needs_refresh",
            health_reason=reason,
            health_updated_at=_utc_now(),
        )

    def _assert_expected_directory_state_locked(
        self,
        conn: sqlite3.Connection,
        operations: Sequence[dict[str, Any]],
    ) -> None:
        expected_entries, touched_dirs = self._expected_directory_entries_locked(
            conn,
            operations,
        )
        for dir_path in sorted(
            touched_dirs, key=lambda item: (item != "", item.count("/"), item)
        ):
            physical = (
                self.repo.repo_root
                if not dir_path
                else self.repo.repo_root / Path(dir_path)
            )
            if not physical.exists() or not physical.is_dir():
                raise WorkspaceIndexFailure(
                    "workspace_index_stale",
                    f"unexpected directory delta: {dir_path or '.'}",
                )
            actual_entries = tuple(_directory_entries(physical))
            expected = tuple(
                sorted(
                    expected_entries.get(dir_path, set()),
                    key=lambda item: (item[0], item[1].lower(), item[1]),
                )
            )
            if actual_entries != expected:
                raise WorkspaceIndexFailure(
                    "workspace_index_stale",
                    f"unexpected directory delta: {dir_path or '.'}",
                )
        planned_paths = self._changed_paths(operations)
        rows = conn.execute(
            """
            SELECT path, entry_kind, mtime_ns, ctime_ns, size, inode, device, child_count, child_signature
            FROM watch_entries
            WHERE path <> ''
            """
        ).fetchall()
        for row in rows:
            relative_path = str(row["path"])
            if relative_path.lower() in planned_paths:
                continue
            if str(row["entry_kind"]) != "file":
                continue
            parent, _name = self._split_parent_name(relative_path)
            if parent not in touched_dirs:
                continue
            self._assert_watch_row_matches(relative_path, row)

    def _expected_directory_entries_locked(
        self,
        conn: sqlite3.Connection,
        operations: Sequence[dict[str, Any]],
    ) -> tuple[dict[str, set[tuple[str, str]]], set[str]]:
        touched_dirs: set[str] = {""}
        existing_dirs = {""}
        for row in conn.execute(
            "SELECT path FROM watch_entries WHERE entry_kind = 'dir'"
        ).fetchall():
            existing_dirs.add(str(row["path"]))
        for op in operations:
            target = _sanitize_relative_path(str(op["path"]))
            touched_dirs.update(self._ancestor_directory_paths(target))
            if op["source_path"] is not None:
                source = _sanitize_relative_path(str(op["source_path"]))
                touched_dirs.update(self._ancestor_directory_paths(source))
        entries_by_dir: dict[str, set[tuple[str, str]]] = {
            dir_path: set() for dir_path in touched_dirs
        }
        for row in conn.execute(
            "SELECT path, entry_kind FROM watch_entries WHERE path <> ''"
        ).fetchall():
            path = str(row["path"])
            parent, name = self._split_parent_name(path)
            if parent in entries_by_dir:
                entries_by_dir[parent].add((str(row["entry_kind"]), name))
        for op in operations:
            target = _sanitize_relative_path(str(op["path"]))
            target_parent, target_name = self._split_parent_name(target.as_posix())
            if op["kind"] == "move":
                source = _sanitize_relative_path(str(op["source_path"]))
                source_parent, source_name = self._split_parent_name(source.as_posix())
                entries_by_dir.setdefault(source_parent, set()).discard(
                    ("file", source_name)
                )
            if op["kind"] == "delete":
                entries_by_dir.setdefault(target_parent, set()).discard(
                    ("file", target_name)
                )
                continue
            if op["kind"] in {"add", "move"}:
                self._apply_expected_directory_creations(
                    entries_by_dir,
                    existing_dirs,
                    target.parent,
                )
                entries_by_dir.setdefault(target_parent, set()).add(
                    ("file", target_name)
                )
        return entries_by_dir, touched_dirs

    def _apply_expected_directory_creations(
        self,
        entries_by_dir: dict[str, set[tuple[str, str]]],
        existing_dirs: set[str],
        parent: PurePosixPath,
    ) -> None:
        current = ""
        for part in parent.parts:
            next_path = part if not current else f"{current}/{part}"
            if next_path not in existing_dirs:
                parent_path, name = self._split_parent_name(next_path)
                entries_by_dir.setdefault(parent_path, set()).add(("dir", name))
                existing_dirs.add(next_path)
            current = next_path

    def _split_parent_name(self, path: str) -> tuple[str, str]:
        if "/" not in path:
            return "", path
        parent, name = path.rsplit("/", 1)
        return parent, name

    def _apply_finalized_operations_locked(
        self,
        conn: sqlite3.Connection,
        *,
        operations: Sequence[dict[str, Any]],
    ) -> None:
        touched_files: set[str] = set()
        touched_dirs: set[str] = {""}
        for op in operations:
            target = _sanitize_relative_path(str(op["path"]))
            touched_files.add(target.as_posix())
            touched_dirs.update(self._ancestor_directory_paths(target))
            if op["source_path"] is not None:
                source = _sanitize_relative_path(str(op["source_path"]))
                touched_files.add(source.as_posix())
                touched_dirs.update(self._ancestor_directory_paths(source))
        conn.executemany(
            "DELETE FROM watch_entries WHERE path = ?",
            [(path,) for path in sorted({*touched_files, *touched_dirs})],
        )
        conn.executemany(
            "DELETE FROM directories WHERE path = ?",
            [(path,) for path in sorted(path for path in touched_dirs if path)],
        )
        conn.executemany(
            "DELETE FROM files WHERE path = ?",
            [(path,) for path in sorted(touched_files)],
        )
        conn.executemany(
            "DELETE FROM doc_families WHERE path = ?",
            [(path,) for path in sorted(touched_files)],
        )
        conn.executemany(
            "DELETE FROM source_basenames WHERE path = ?",
            [(path,) for path in sorted(touched_files)],
        )
        conn.executemany(
            "DELETE FROM symbols WHERE path = ?",
            [(path,) for path in sorted(touched_files)],
        )
        dir_rows: list[tuple[Any, ...]] = []
        directory_catalog_rows: list[tuple[str, str]] = []
        for dir_path in sorted(
            touched_dirs, key=lambda item: (item != "", item.count("/"), item)
        ):
            relative_dir = (
                PurePosixPath(".") if not dir_path else PurePosixPath(dir_path)
            )
            physical = (
                self.repo.repo_root
                if not dir_path
                else self.repo.repo_root / Path(dir_path)
            )
            if not physical.exists():
                continue
            if _is_reparse_point(physical):
                raise WorkspaceIndexFailure(
                    "workspace_index_uncertain",
                    f"reparse point detected: {dir_path}",
                )
            if not physical.is_dir():
                raise WorkspaceIndexFailure(
                    "workspace_index_uncertain",
                    f"expected directory missing: {dir_path}",
                )
            dir_rows.append(self._directory_watch_row(relative_dir, physical))
            if dir_path:
                directory_catalog_rows.append((dir_path, relative_dir.parts[0]))
        if dir_rows:
            conn.executemany(
                """
                INSERT INTO watch_entries(
                    path, entry_kind, top_level, mtime_ns, ctime_ns, size, inode, device, child_count, child_signature
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                dir_rows,
            )
        if directory_catalog_rows:
            conn.executemany(
                "INSERT INTO directories(path, top_level) VALUES(?, ?)",
                directory_catalog_rows,
            )
        file_watch_rows: list[tuple[Any, ...]] = []
        file_catalog_rows: list[tuple[str, str, str, str, str]] = []
        doc_rows: list[tuple[str, str]] = []
        basename_rows: list[tuple[str, str]] = []
        symbol_rows: list[tuple[str, str]] = []
        for file_path in sorted(touched_files):
            relative_file = _sanitize_relative_path(file_path)
            physical = self.repo.repo_root / Path(file_path)
            if not physical.exists():
                continue
            if _is_reparse_point(physical):
                raise WorkspaceIndexFailure(
                    "workspace_index_uncertain",
                    f"reparse point detected: {file_path}",
                )
            if not physical.is_file():
                raise WorkspaceIndexFailure(
                    "workspace_index_uncertain",
                    f"expected file missing: {file_path}",
                )
            file_entry = self._file_index_rows(relative_file, physical)
            file_watch_rows.append(file_entry["watch"])
            file_catalog_rows.append(file_entry["file"])
            doc_rows.extend(file_entry["doc_families"])
            basename_rows.extend(file_entry["basenames"])
            symbol_rows.extend(file_entry["symbols"])
        if file_watch_rows:
            conn.executemany(
                """
                INSERT INTO watch_entries(
                    path, entry_kind, top_level, mtime_ns, ctime_ns, size, inode, device, child_count, child_signature
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                file_watch_rows,
            )
            conn.executemany(
                "INSERT INTO files(path, dir_path, basename, top_level, kind) VALUES(?, ?, ?, ?, ?)",
                file_catalog_rows,
            )
        if doc_rows:
            conn.executemany(
                "INSERT INTO doc_families(family, path) VALUES(?, ?)",
                doc_rows,
            )
        if basename_rows:
            conn.executemany(
                "INSERT INTO source_basenames(basename, path) VALUES(?, ?)",
                basename_rows,
            )
        if symbol_rows:
            conn.executemany(
                "INSERT INTO symbols(symbol, path) VALUES(?, ?)",
                symbol_rows,
            )

    def _ancestor_directory_paths(self, target: PurePosixPath) -> set[str]:
        directory_paths = {""}
        current = PurePosixPath(".")
        for part in target.parent.parts:
            current = (
                PurePosixPath(part) if current == PurePosixPath(".") else current / part
            )
            directory_paths.add(current.as_posix())
        return directory_paths

    def _recompute_generation_locked(self, conn: sqlite3.Connection) -> str:
        return _hash_json(
            {
                "watch_rows": [
                    tuple(row)
                    for row in conn.execute(
                        """
                        SELECT path, entry_kind, top_level, mtime_ns, ctime_ns, size, inode, device, child_count, child_signature
                        FROM watch_entries
                        ORDER BY CASE WHEN path = '' THEN 0 ELSE 1 END, LENGTH(path), path
                        """
                    ).fetchall()
                ],
                "directories": [
                    tuple(row)
                    for row in conn.execute(
                        "SELECT path, top_level FROM directories ORDER BY path"
                    ).fetchall()
                ],
                "files": [
                    tuple(row)
                    for row in conn.execute(
                        "SELECT path, dir_path, basename, top_level, kind FROM files ORDER BY path"
                    ).fetchall()
                ],
                "doc_families": [
                    tuple(row)
                    for row in conn.execute(
                        "SELECT family, path FROM doc_families ORDER BY family, path"
                    ).fetchall()
                ],
                "basenames": [
                    tuple(row)
                    for row in conn.execute(
                        "SELECT basename, path FROM source_basenames ORDER BY basename, path"
                    ).fetchall()
                ],
                "symbols": [
                    tuple(row)
                    for row in conn.execute(
                        "SELECT symbol, path FROM symbols ORDER BY symbol, path"
                    ).fetchall()
                ],
            }
        )

    def _rebase_active_reservations_locked(
        self,
        conn: sqlite3.Connection,
        *,
        completed_owner: str,
        completed_operation_id: str,
        generation: str,
        changed_paths: set[str],
    ) -> None:
        rows = conn.execute(
            """
            SELECT owner, operation_id, plan_json
            FROM reservations
            WHERE status = 'reserved' AND NOT (owner = ? AND operation_id = ?)
            """,
            (completed_owner, completed_operation_id),
        ).fetchall()
        for row in rows:
            owner = str(row["owner"])
            operation_id = str(row["operation_id"])
            if not self._reservation_can_rebase_locked(
                conn,
                owner=owner,
                operation_id=operation_id,
                payload=self._load_reservation_plan(str(row["plan_json"])),
                changed_paths=changed_paths,
            ):
                conn.execute(
                    """
                    UPDATE reservations
                    SET status = 'needs_refresh'
                    WHERE owner = ? AND operation_id = ?
                    """,
                    (owner, operation_id),
                )
                conn.execute(
                    "DELETE FROM reservation_claims WHERE owner = ? AND operation_id = ?",
                    (owner, operation_id),
                )
                continue
            conn.execute(
                """
                UPDATE reservations
                SET generation = ?
                WHERE owner = ? AND operation_id = ?
                """,
                (generation, owner, operation_id),
            )

    def _reservation_can_rebase_locked(
        self,
        conn: sqlite3.Connection,
        *,
        owner: str,
        operation_id: str,
        payload: dict[str, Any],
        changed_paths: set[str],
    ) -> bool:
        plan_paths = self._changed_paths(payload["operations"])
        if plan_paths & changed_paths:
            return False
        top_levels = self._top_levels(conn)
        try:
            for op in payload["operations"]:
                self._validate_stored_operation(
                    conn,
                    op,
                    owner=owner,
                    operation_id=operation_id,
                    top_levels=top_levels,
                )
        except WorkspaceIndexFailure:
            return False
        return True

    def _validate_stored_operation(
        self,
        conn: sqlite3.Connection,
        op: dict[str, Any],
        *,
        owner: str,
        operation_id: str,
        top_levels: set[str],
    ) -> None:
        normalized = self._normalize_operation(
            MutationOp(
                kind=str(op["kind"]),
                path=str(op["path"]),
                postimage="" if op["kind"] != "delete" else None,
                source_path=(
                    None if op["source_path"] is None else str(op["source_path"])
                ),
            ),
            top_levels=top_levels,
        )
        allowed = {
            str(row["claim_path"])
            for row in conn.execute(
                """
                SELECT claim_path
                FROM reservation_claims
                WHERE owner = ? AND operation_id = ? AND claim_kind = 'file'
                """,
                (owner, operation_id),
            ).fetchall()
        }
        if not allowed:
            allowed = {normalized["target"].as_posix()}
            if normalized["source"] is not None:
                allowed.add(normalized["source"].as_posix())
        self._check_existing_conflicts_for_paths(
            conn,
            target=normalized["target"],
            allowed=allowed,
            owner=owner,
            operation_id=operation_id,
        )

    def _check_existing_conflicts_for_paths(
        self,
        conn: sqlite3.Connection,
        *,
        target: PurePosixPath,
        allowed: set[str],
        owner: str | None,
        operation_id: str | None,
    ) -> None:
        if _is_doc_path(target):
            family = _normalize_doc_family(target)
            rows = conn.execute(
                "SELECT path FROM doc_families WHERE family = ?",
                (family,),
            ).fetchall()
            if any(str(row["path"]) not in allowed for row in rows):
                raise WorkspaceIndexFailure("workspace_doc_family_conflict", family)
        if _is_source_path(target):
            basename = target.name.lower()
            if basename not in RECURRING_BASENAMES:
                rows = conn.execute(
                    "SELECT path FROM source_basenames WHERE basename = ?",
                    (basename,),
                ).fetchall()
                if any(str(row["path"]) not in allowed for row in rows):
                    raise WorkspaceIndexFailure(
                        "workspace_source_basename_conflict",
                        basename,
                    )
            claim_rows = conn.execute(
                """
                SELECT claim_key
                FROM reservation_claims
                WHERE owner = ? AND operation_id = ? AND claim_kind = 'symbol'
                """,
                (owner, operation_id),
            ).fetchall()
            for claim_row in claim_rows:
                symbol = str(claim_row["claim_key"])
                rows = conn.execute(
                    "SELECT path FROM symbols WHERE symbol = ?",
                    (symbol,),
                ).fetchall()
                if any(str(row["path"]) not in allowed for row in rows):
                    raise WorkspaceIndexFailure(
                        "workspace_primary_symbol_conflict",
                        symbol,
                    )

    def _materialize_relative_path(
        self,
        relative: PurePosixPath,
        *,
        allow_missing_leaf: bool,
        deadline_monotonic: float | None = None,
    ) -> tuple[Path, bool]:
        current = self.repo.repo_root
        parts = list(relative.parts)
        for index, part in enumerate(parts):
            _require_before_deadline(
                deadline_monotonic,
                message=f"deadline exceeded while resolving {relative.as_posix()}",
            )
            last = index == len(parts) - 1
            exact_child = self._resolve_exact_child(
                current,
                part,
                deadline_monotonic=deadline_monotonic,
            )
            if exact_child is None:
                if not allow_missing_leaf and last:
                    return current / Path(part), False
                if not last:
                    lexical = current / Path(*parts[index:])
                    if not _contains(self.repo.repo_root, lexical):
                        raise WorkspaceIndexFailure(
                            "workspace_index_uncertain",
                            f"path escaped repo root: {relative.as_posix()}",
                        )
                    return lexical, False
                return current / Path(part), False
            if _is_reparse_point(exact_child):
                raise WorkspaceIndexFailure(
                    "workspace_index_uncertain",
                    f"reparse point in path: {relative.as_posix()}",
                )
            resolved = exact_child.resolve(strict=True)
            if not _contains(self.repo.repo_root, resolved):
                raise WorkspaceIndexFailure(
                    "workspace_index_uncertain",
                    f"path escaped repo root: {relative.as_posix()}",
                )
            current = exact_child
        return current, True

    def _resolve_exact_child(
        self,
        parent: Path,
        part: str,
        *,
        deadline_monotonic: float | None = None,
    ) -> Path | None:
        exact_match: Path | None = None
        alias_found = False
        try:
            with os.scandir(parent) as entries:
                for entry in entries:
                    _require_before_deadline(
                        deadline_monotonic,
                        message=f"deadline exceeded while resolving {part}",
                    )
                    child = Path(entry.path)
                    if entry.name == part:
                        exact_match = child
                        break
                    if entry.name.casefold() == part.casefold():
                        alias_found = True
        except OSError as exc:
            raise WorkspaceIndexFailure("workspace_index_uncertain", str(exc)) from exc
        if exact_match is not None:
            return exact_match
        if alias_found:
            raise WorkspaceIndexFailure(
                "workspace_index_uncertain",
                f"case alias rejected: {part}",
            )
        return None

    def _summarize_plan(self, operations: Sequence[dict[str, Any]]) -> dict[str, Any]:
        touched_targets: set[str] = set()
        claims: dict[tuple[str, str], str] = {}
        new_dir_paths: set[str] = set()
        new_file_count = 0
        for op in operations:
            target: PurePosixPath = op["target"]
            target_key: str = op["target_key"]
            if target_key in touched_targets:
                raise WorkspaceIndexFailure(
                    "workspace_index_uncertain",
                    f"duplicate target {target.as_posix()}",
                )
            touched_targets.add(target_key)
            self._record_claim(claims, "file", target_key, target.as_posix())
            source: PurePosixPath | None = op["source"]
            if source is not None:
                self._record_claim(
                    claims,
                    "file",
                    op["source_key"],
                    source.as_posix(),
                )
            if op["kind"] in {"add", "move"} and not op["target_exists"]:
                new_file_count += 1
                missing_dirs = self._missing_directories(target)
                if len(missing_dirs) > MAX_OP_DEPTH:
                    raise WorkspaceIndexFailure(
                        "workspace_op_limit",
                        "depth slop exceeded",
                    )
                for directory in missing_dirs:
                    new_dir_paths.add(directory.as_posix().lower())
                    self._record_claim(
                        claims,
                        "dir",
                        directory.as_posix().lower(),
                        directory.as_posix(),
                    )
            if _is_doc_path(target) and op["kind"] != "delete":
                self._record_claim(
                    claims,
                    "doc_family",
                    _normalize_doc_family(target),
                    target.as_posix(),
                )
            if _is_source_path(target) and op["kind"] != "delete":
                basename = target.name.lower()
                if basename not in RECURRING_BASENAMES:
                    self._record_claim(
                        claims,
                        "basename",
                        basename,
                        target.as_posix(),
                    )
                for symbol in _extract_symbols(op["postimage"] or ""):
                    self._record_claim(
                        claims,
                        "symbol",
                        symbol,
                        target.as_posix(),
                    )
        claim_rows = [
            (claim_kind, claim_key, claim_path)
            for (claim_kind, claim_key), claim_path in sorted(claims.items())
        ]
        file_claim_count = sum(
            1
            for claim_kind, _claim_key, _claim_path in claim_rows
            if claim_kind == "file"
        )
        if file_claim_count > MAX_OP_FILES:
            raise WorkspaceIndexFailure("workspace_op_limit", "file slop exceeded")
        if len(new_dir_paths) > MAX_OP_DIRS:
            raise WorkspaceIndexFailure("workspace_op_limit", "dir slop exceeded")
        return {
            "file_claim_count": file_claim_count,
            "new_file_count": new_file_count,
            "new_dir_count": len(new_dir_paths),
            "claims": claim_rows,
        }

    def _record_claim(
        self,
        claims: dict[tuple[str, str], str],
        claim_kind: str,
        claim_key: str,
        claim_path: str,
    ) -> None:
        key = (claim_kind, claim_key)
        existing = claims.get(key)
        if existing is None:
            claims[key] = claim_path
            return
        if existing == claim_path:
            return
        code_map = {
            "file": "workspace_path_conflict",
            "dir": "workspace_path_conflict",
            "doc_family": "workspace_doc_family_conflict",
            "basename": "workspace_source_basename_conflict",
            "symbol": "workspace_primary_symbol_conflict",
        }
        raise WorkspaceIndexFailure(code_map[claim_kind], claim_key)

    def _missing_directories(self, target: PurePosixPath) -> list[PurePosixPath]:
        missing: list[PurePosixPath] = []
        relative_parts = list(target.parent.parts)
        current = self.repo.repo_root
        built_parts: list[str] = []
        for part in relative_parts:
            built_parts.append(part)
            next_path = current / Path(part)
            if next_path.exists():
                current = next_path
                continue
            missing.append(PurePosixPath(*built_parts))
            current = next_path
        return missing

    def _check_conflicts(
        self, conn: sqlite3.Connection, operations: Sequence[dict[str, Any]]
    ) -> None:
        for op in operations:
            target: PurePosixPath = op["target"]
            source_path = op["source"].as_posix() if op["source"] is not None else None
            if op["kind"] != "delete":
                self._check_existing_conflicts(
                    conn,
                    target,
                    op["postimage"] or "",
                    source_path,
                )
            self._check_reservation_conflicts(
                conn,
                target,
                op["postimage"] or "",
                source_path,
            )

    def _check_existing_conflicts(
        self,
        conn: sqlite3.Connection,
        target: PurePosixPath,
        postimage: str,
        source_path: str | None,
    ) -> None:
        source_exclusion = {source_path} if source_path else set()
        allowed = {target.as_posix(), *source_exclusion}
        if _is_doc_path(target):
            family = _normalize_doc_family(target)
            rows = conn.execute(
                "SELECT path FROM doc_families WHERE family = ?",
                (family,),
            ).fetchall()
            if any(str(row["path"]) not in allowed for row in rows):
                raise WorkspaceIndexFailure("workspace_doc_family_conflict", family)
        if _is_source_path(target):
            basename = target.name.lower()
            if basename not in RECURRING_BASENAMES:
                rows = conn.execute(
                    "SELECT path FROM source_basenames WHERE basename = ?",
                    (basename,),
                ).fetchall()
                if any(str(row["path"]) not in allowed for row in rows):
                    raise WorkspaceIndexFailure(
                        "workspace_source_basename_conflict",
                        basename,
                    )
            for symbol in _extract_symbols(postimage):
                rows = conn.execute(
                    "SELECT path FROM symbols WHERE symbol = ?",
                    (symbol,),
                ).fetchall()
                if any(str(row["path"]) not in allowed for row in rows):
                    raise WorkspaceIndexFailure(
                        "workspace_primary_symbol_conflict",
                        symbol,
                    )

    def _check_reservation_conflicts(
        self,
        conn: sqlite3.Connection,
        target: PurePosixPath,
        postimage: str,
        source_path: str | None,
    ) -> None:
        claim_checks: list[tuple[str, str]] = [
            ("file", target.as_posix().lower()),
        ]
        if source_path:
            claim_checks.append(("file", source_path.lower()))
        if _is_doc_path(target):
            claim_checks.append(("doc_family", _normalize_doc_family(target)))
        if _is_source_path(target):
            basename = target.name.lower()
            if basename not in RECURRING_BASENAMES:
                claim_checks.append(("basename", basename))
            for symbol in _extract_symbols(postimage):
                claim_checks.append(("symbol", symbol))
        for claim_kind, claim_key in claim_checks:
            rows = conn.execute(
                """
                SELECT claim_path
                FROM reservation_claims
                WHERE claim_kind = ? AND claim_key = ?
                """,
                (claim_kind, claim_key),
            ).fetchall()
            if not rows:
                continue
            mapping = {
                "doc_family": "workspace_doc_family_conflict",
                "basename": "workspace_source_basename_conflict",
                "symbol": "workspace_primary_symbol_conflict",
                "file": "workspace_path_conflict",
            }
            raise WorkspaceIndexFailure(mapping[claim_kind], claim_key)
