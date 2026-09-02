"""Report-time artifact-manifest verification gate (SYN-0019).

The final synthesis writer must verify the artifact manifest ON DISK before it
writes the completion report. This module is that BLOCKING gate:

* ``verify_manifest``   -- existence + non-empty + minimum size + schema parse
                           + LF-normalised content hash, one table row per
                           contracted entry. A row that fails is kept in the
                           table (``failed_never_skipped``), never omitted.
* ``authorize_write``   -- a PERMITTED verification authorises a write only
                           inside its freshness window; a green stamp older
                           than the window is ``decayed-green`` and BLOCKS.
* ``write_completion_report`` -- the writer itself: refuses to write unless
                           ``authorize_write`` says PERMITTED.

Windows reserved device names (NUL, CON, COM1 ...) are stat-ed through the
``\\\\?\\`` extended-length prefix so the name is not swallowed by the device
namespace; on POSIX the path is used unchanged.

Blocking-condition vocabulary (closed, sorted in output):
``manifest-missing`` ``manifest-unparseable`` ``manifest-no-entries``
``missing-artifact`` ``unreadable-path`` ``not-a-file`` ``empty-artifact``
``minimum-size`` ``size-mismatch`` ``hash-mismatch`` ``schema-missing``
``parse-failure`` ``decayed-green`` ``verification-not-permitted``.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat as _stat
from datetime import datetime, timezone
from pathlib import Path, PurePath, PureWindowsPath
from typing import Any

DEFAULT_FRESHNESS_WINDOW_SECONDS = 300
DEFAULT_MIN_BYTES = 1
EXTENDED_PREFIX = "\\\\?\\"

PERMITTED = "PERMITTED"
BLOCKED = "BLOCKED"

EXIT_PERMITTED = 0
EXIT_BLOCKED = 1
EXIT_DECAYED = 2

_RESERVED_BASE = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
_RESERVED_NUMBERED = re.compile(r"^(COM|LPT)[1-9]$", re.IGNORECASE)


# --------------------------------------------------------------------------- #
# digests
# --------------------------------------------------------------------------- #
def lf_digest(raw: bytes) -> tuple[str, int]:
    """sha256 + length of ``raw`` with CRLF/CR normalised to LF."""
    norm = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm)


def digest_file(path: Path | str) -> tuple[str, int]:
    return lf_digest(Path(path).read_bytes())


# --------------------------------------------------------------------------- #
# Windows reserved names / extended-length paths
# --------------------------------------------------------------------------- #
def is_reserved_device_name(name: str) -> bool:
    """True for NUL, CON, PRN, AUX, COM1-9, LPT1-9 -- with or without an
    extension, any case, ignoring trailing dots/spaces (Win32 name rules)."""
    base = str(name).replace("/", "\\").rsplit("\\", 1)[-1].rstrip(" .")
    if not base:
        return False
    stem = base.split(".", 1)[0].rstrip(" ")
    upper = stem.upper()
    return upper in _RESERVED_BASE or bool(_RESERVED_NUMBERED.match(upper))


def extended_length_path(path: PurePath | str) -> str:
    """Return ``path`` as a Win32 extended-length string (``\\\\?\\C:\\...``).

    Already-prefixed paths are returned unchanged; UNC paths become
    ``\\\\?\\UNC\\server\\share\\...``. Relative paths are anchored on the
    current drive/directory first because the prefix disables normalisation.
    """
    text = str(path)
    if text.startswith(EXTENDED_PREFIX):
        return text
    win = PureWindowsPath(text)
    if not win.is_absolute() and not (len(win.drive) == 2 and win.drive[1] == ":"):
        # Anchor a relative path; on POSIX the result is only ever a label.
        text = str(PureWindowsPath(os.getcwd()) / win)
        win = PureWindowsPath(text)
    text = str(win)
    if text.startswith("\\\\"):
        return EXTENDED_PREFIX + "UNC\\" + text.lstrip("\\")
    return EXTENDED_PREFIX + text


def stat_target(path: Path | str, *, reserved: bool = False, windows: bool | None = None):
    """Path handed to ``os.stat``: extended-length string on Windows when the
    leaf is a reserved device name, otherwise the path unchanged."""
    if windows is None:
        windows = os.name == "nt"
    if windows and reserved:
        return extended_length_path(path)
    return path


# --------------------------------------------------------------------------- #
# time helpers
# --------------------------------------------------------------------------- #
def _as_utc(value: datetime | str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# manifest loading
# --------------------------------------------------------------------------- #
def _load_manifest(root: Path, manifest: Any) -> tuple[dict | None, str | None, list[str]]:
    """Return (document, manifest_path, conditions)."""
    if isinstance(manifest, dict):
        return manifest, None, []
    if isinstance(manifest, list):
        return {"artifacts": manifest}, None, []
    path = Path(manifest) if manifest is not None else root / "ARTIFACT-MANIFEST.json"
    if not path.is_absolute():
        path = root / path
    if not path.is_file():
        return None, str(path), ["manifest-missing"]
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, str(path), ["manifest-unparseable"]
    if not isinstance(doc, dict):
        return None, str(path), ["manifest-unparseable"]
    return doc, str(path), []


def _entries_of(doc: dict) -> list[dict]:
    for key in ("artifacts", "entries", "files"):
        rows = doc.get(key)
        if isinstance(rows, list):
            return [r for r in rows if isinstance(r, dict)]
    return []


def _expected_hash(entry: dict) -> str | None:
    for key in ("sha256", "hash", "digest"):
        val = entry.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip().lower().removeprefix("sha256:")
    return None


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- #
# per-entry verification
# --------------------------------------------------------------------------- #
def _stat_entry(target: Path, rel: str, windows: bool) -> tuple[os.stat_result | None, str | None]:
    """(stat, condition). ENOTDIR/EACCES are ``unreadable-path``; ENOENT is
    ``missing-artifact`` unless a parent component is a file (then unreadable)."""
    reserved = is_reserved_device_name(PurePath(rel).name)
    probe = stat_target(target, reserved=reserved, windows=windows)
    try:
        return os.stat(probe), None
    except FileNotFoundError:
        cur = target.parent
        for _ in range(64):
            if cur.exists():
                if not cur.is_dir():
                    return None, "unreadable-path"
                break
            if cur.parent == cur:
                break
            cur = cur.parent
        return None, "missing-artifact"
    except (NotADirectoryError, PermissionError):
        return None, "unreadable-path"
    except OSError:
        return None, "unreadable-path"


def _schema_check(target: Path, root: Path, entry: dict, raw: bytes) -> tuple[str, list[str]]:
    """Parse the artifact against its contracted schema (or as JSON when it is
    a .json file with no schema). Returns (parse_verdict, conditions)."""
    schema_rel = entry.get("schema")
    is_json = str(entry.get("path") or "").lower().endswith(".json")
    if not schema_rel and not is_json:
        return "NOT-CONTRACTED", []
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "FAIL", ["parse-failure"]
    if not schema_rel:
        return "PASS", []
    schema_path = Path(schema_rel)
    if not schema_path.is_absolute():
        schema_path = root / schema_path
    if not schema_path.is_file():
        return "FAIL", ["schema-missing"]
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return "FAIL", ["schema-missing"]
    try:
        import jsonschema  # local import: the gate must still run without it
    except ImportError:
        jsonschema = None  # type: ignore[assignment]
    if jsonschema is None:
        return ("PASS", []) if isinstance(doc, (dict, list)) else ("FAIL", ["parse-failure"])
    validator_cls = jsonschema.validators.validator_for(schema, default=jsonschema.Draft7Validator)
    errors = list(validator_cls(schema).iter_errors(doc))
    if errors:
        return "FAIL", ["parse-failure"]
    return "PASS", []


def verify_entry(root: Path, entry: dict, *, default_min_bytes: int = DEFAULT_MIN_BYTES,
                 windows: bool | None = None) -> dict:
    if windows is None:
        windows = os.name == "nt"
    rel = str(entry.get("path") or "").replace("\\", "/")
    row: dict[str, Any] = {
        "path": rel,
        "present": False,
        "bytes": None,
        "expected_bytes": _int_or_none(entry.get("bytes")),
        "hash": None,
        "expected_hash": _expected_hash(entry),
        "min_bytes": _int_or_none(entry.get("min_bytes")) or int(default_min_bytes),
        "schema": entry.get("schema"),
        "parse_verdict": "NOT-CHECKED",
        "blocking_conditions": [],
        "failed_never_skipped": False,
    }
    conditions: list[str] = []
    if not rel:
        conditions.append("missing-artifact")
        row["parse_verdict"] = "NOT-CHECKED"
    else:
        target = root / rel
        st, cond = _stat_entry(target, rel, windows)
        if st is None:
            conditions.append(cond or "missing-artifact")
            row["parse_verdict"] = "UNREADABLE" if cond == "unreadable-path" else "NOT-CHECKED"
        elif not _stat.S_ISREG(st.st_mode):
            row["present"] = True
            conditions.append("not-a-file")
            row["parse_verdict"] = "NOT-CHECKED"
        else:
            row["present"] = True
            try:
                raw = target.read_bytes()
            except OSError:
                conditions.append("unreadable-path")
                row["parse_verdict"] = "UNREADABLE"
                raw = None
            if raw is not None:
                digest, size = lf_digest(raw)
                row["bytes"] = size
                row["hash"] = digest
                if size == 0:
                    conditions.append("empty-artifact")
                if size < row["min_bytes"]:
                    conditions.append("minimum-size")
                if row["expected_bytes"] is not None and row["expected_bytes"] != size:
                    conditions.append("size-mismatch")
                if row["expected_hash"] is not None and row["expected_hash"] != digest:
                    conditions.append("hash-mismatch")
                verdict, more = _schema_check(target, root, entry, raw)
                row["parse_verdict"] = verdict
                conditions.extend(more)
    row["blocking_conditions"] = sorted(set(conditions))
    row["failed_never_skipped"] = bool(row["blocking_conditions"])
    row["verdict"] = BLOCKED if row["blocking_conditions"] else PERMITTED
    return row


# --------------------------------------------------------------------------- #
# whole-manifest verification
# --------------------------------------------------------------------------- #
def verify_manifest(root: Path | str, manifest: Any = None, *,
                    verified_at: datetime | str | None = None,
                    freshness_window_seconds: int | float = DEFAULT_FRESHNESS_WINDOW_SECONDS,
                    default_min_bytes: int = DEFAULT_MIN_BYTES,
                    windows: bool | None = None) -> dict:
    """Verify every contracted entry of ``manifest`` (path or loaded dict)
    against the files under ``root``. Never raises for a bad entry: a bad row
    is kept in ``entries`` with its blocking conditions."""
    root = Path(root)
    stamp = _as_utc(verified_at)
    doc, manifest_path, conditions = _load_manifest(root, manifest)
    entries: list[dict] = []
    if doc is not None:
        raw_entries = _entries_of(doc)
        if not raw_entries:
            conditions.append("manifest-no-entries")
        for entry in raw_entries:
            entries.append(verify_entry(root, entry, default_min_bytes=default_min_bytes,
                                        windows=windows))
    union = set(conditions)
    for row in entries:
        union.update(row["blocking_conditions"])
    blocking = sorted(union)
    verdict = BLOCKED if blocking else PERMITTED
    return {
        "verdict": verdict,
        "exit_code": EXIT_PERMITTED if verdict == PERMITTED else EXIT_BLOCKED,
        "verified_at": _iso(stamp),
        "freshness_window_seconds": freshness_window_seconds,
        "root": str(root),
        "manifest_path": manifest_path,
        "entry_count": len(entries),
        "failed_count": sum(1 for r in entries if r["blocking_conditions"]),
        "blocking_conditions": blocking,
        "entries": entries,
        "checks": ["exists", "non-empty", "minimum-size", "schema-parse", "content-hash"],
    }


# --------------------------------------------------------------------------- #
# freshness-windowed authorisation and the blocked writer
# --------------------------------------------------------------------------- #
def authorize_write(verification: dict, *, write_time: datetime | str | None = None,
                    freshness_window_seconds: int | float | None = None) -> dict:
    """Authorise a report write from a verification result.

    PERMITTED only when the verification itself is PERMITTED and the write
    happens within ``freshness_window_seconds`` of ``verified_at``. A green
    verification older than the window is ``decayed-green``: it proves what
    the disk looked like then, not now."""
    now = _as_utc(write_time)
    window = freshness_window_seconds
    if window is None:
        window = verification.get("freshness_window_seconds", DEFAULT_FRESHNESS_WINDOW_SECONDS)
    window = float(window)
    verified_at_raw = verification.get("verified_at")
    conditions: list[str] = []
    gap: float | None = None
    if verified_at_raw is None:
        conditions.append("decayed-green")
    else:
        verified_at = _as_utc(verified_at_raw)
        gap = (now - verified_at).total_seconds()
        if gap < 0 or gap > window:
            conditions.append("decayed-green")
    if verification.get("verdict") != PERMITTED:
        conditions.append("verification-not-permitted")
        conditions.extend(verification.get("blocking_conditions") or [])
    blocking = sorted(set(conditions))
    if not blocking:
        verdict, exit_code = PERMITTED, EXIT_PERMITTED
    elif "verification-not-permitted" in blocking:
        verdict, exit_code = BLOCKED, EXIT_BLOCKED
    else:
        verdict, exit_code = BLOCKED, EXIT_DECAYED
    return {
        "verdict": verdict,
        "exit_code": exit_code,
        "blocking_conditions": blocking,
        "write_time": _iso(now),
        "verified_at": _iso(_as_utc(verified_at_raw)) if verified_at_raw is not None else None,
        "wall_clock_gap_seconds": gap,
        "freshness_window_seconds": window,
        "verification_verdict": verification.get("verdict"),
        "verification_exit_code": verification.get("exit_code"),
    }


def write_completion_report(dest: Path | str, payload: dict, verification: dict, *,
                            write_time: datetime | str | None = None,
                            freshness_window_seconds: int | float | None = None) -> dict:
    """Write ``payload`` (plus the gate summary) to ``dest`` iff the gate
    authorises it. BLOCKED never touches ``dest``."""
    dest = Path(dest)
    auth = authorize_write(verification, write_time=write_time,
                           freshness_window_seconds=freshness_window_seconds)
    result = dict(auth)
    result.update({"path": str(dest), "wrote": False, "output_exists": dest.exists()})
    if auth["verdict"] != PERMITTED:
        return result
    report = dict(payload or {})
    report["manifest_gate"] = {
        "verdict": verification.get("verdict"),
        "verified_at": verification.get("verified_at"),
        "write_time": auth["write_time"],
        "wall_clock_gap_seconds": auth["wall_clock_gap_seconds"],
        "freshness_window_seconds": auth["freshness_window_seconds"],
        "entry_count": verification.get("entry_count"),
        "blocking_conditions": list(verification.get("blocking_conditions") or []),
        "checks": list(verification.get("checks") or []),
    }
    dest.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    dest.write_text(text, encoding="utf-8", newline="\n")
    result["wrote"] = True
    result["output_exists"] = dest.exists()
    result["bytes"] = len(text.encode("utf-8"))
    return result


__all__ = [
    "BLOCKED",
    "DEFAULT_FRESHNESS_WINDOW_SECONDS",
    "DEFAULT_MIN_BYTES",
    "EXTENDED_PREFIX",
    "PERMITTED",
    "authorize_write",
    "digest_file",
    "extended_length_path",
    "is_reserved_device_name",
    "lf_digest",
    "stat_target",
    "verify_entry",
    "verify_manifest",
    "write_completion_report",
]
