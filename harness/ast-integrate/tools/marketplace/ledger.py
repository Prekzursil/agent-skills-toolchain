"""File-backed ownership ledger for marketplace installs (``marketplace.ledger/v1``).

Every file a package places under the live tree is recorded together with its
provenance (path inside the package payload, content digest) so that

* two packages can never silently claim the same live path
  (``OwnershipConflict`` is raised before the ledger is touched),
* removal can enumerate exactly the files a package owns,
* an operator can audit what is on disk against what was installed.

Durability contract (measured by ADV-0126 on a 1 MiB tmpfs): ``save_ledger``
serialises the whole document, writes it to a temporary file in the target
directory, fsyncs, then swaps it over the old file with ``os.replace``.  Under ENOSPC
the ``OSError`` propagates loudly and the previously saved ledger stays
byte-for-byte intact - the ledger is never truncated in place.

Ledger document::

    {
      "schema": "marketplace.ledger/v1",
      "owned_files": {
        "a.py": {"package_id": "seed", "source_path": "src/a.py",
                 "content_sha256": "abc"}
      }
    }

``owned_files`` is keyed by the normalised live path (POSIX separators, no
leading ``./`` or ``/``, no ``..`` segments).  ``content_sha256`` is an opaque
non-empty digest string; production callers pass the hex sha256 of the placed
bytes, tests may pass shorter markers.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

LEDGER_SCHEMA = "marketplace.ledger/v1"

__all__ = [
    "LEDGER_SCHEMA",
    "LedgerError",
    "OwnershipConflict",
    "add_owned_file",
    "dumps_ledger",
    "empty_ledger",
    "files_owned_by",
    "load_ledger",
    "normalize_live_path",
    "owner_of",
    "package_ids",
    "remove_owned_file",
    "remove_package",
    "save_ledger",
    "validate_ledger",
]


class LedgerError(ValueError):
    """The ledger document or an argument to a ledger operation is invalid."""


class OwnershipConflict(LedgerError):
    """A live path is already owned by a different package."""

    def __init__(self, live_path: str, owner: str, claimant: str) -> None:
        self.live_path = live_path
        self.owner = owner
        self.claimant = claimant
        super().__init__(
            f"{live_path!r} is owned by package {owner!r}; refusing claim by {claimant!r}"
        )


# --------------------------------------------------------------------------- helpers


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LedgerError(f"{field} must be a non-empty string, got {value!r}")
    if "\x00" in value:
        raise LedgerError(f"{field} must not contain NUL")
    return value


def normalize_live_path(live_path: str) -> str:
    """Return the canonical ledger key for a live path.

    Backslashes become ``/``, ``.`` segments and leading ``./`` / ``/`` are
    dropped, repeated separators collapse.  ``..`` segments and empty results
    are rejected: a live path must stay inside the live tree.
    """
    text = _require_text(live_path, "live_path").replace("\\", "/")
    segments = [seg for seg in text.split("/") if seg not in ("", ".")]
    if not segments:
        raise LedgerError(f"live_path {live_path!r} names no file")
    if any(seg == ".." for seg in segments):
        raise LedgerError(f"live_path {live_path!r} escapes the live tree")
    return "/".join(segments)


def empty_ledger() -> dict[str, Any]:
    """A new, valid ledger with no owned files."""
    return {"schema": LEDGER_SCHEMA, "owned_files": {}}


def validate_ledger(ledger: Any) -> dict[str, Any]:
    """Check the document shape and return it; raise ``LedgerError`` otherwise."""
    if not isinstance(ledger, dict):
        raise LedgerError("ledger must be a JSON object")
    if ledger.get("schema") != LEDGER_SCHEMA:
        raise LedgerError(f"ledger schema must be {LEDGER_SCHEMA!r}, got {ledger.get('schema')!r}")
    owned = ledger.get("owned_files")
    if not isinstance(owned, dict):
        raise LedgerError("ledger.owned_files must be an object")
    for live_path, entry in owned.items():
        if not isinstance(live_path, str) or normalize_live_path(live_path) != live_path:
            raise LedgerError(f"owned_files key {live_path!r} is not a normalised live path")
        if not isinstance(entry, dict):
            raise LedgerError(f"owned_files[{live_path!r}] must be an object")
        for field in ("package_id", "source_path", "content_sha256"):
            _require_text(entry.get(field), f"owned_files[{live_path!r}].{field}")
    return ledger


# --------------------------------------------------------------------------- mutation


def add_owned_file(
    ledger: dict[str, Any],
    *,
    package_id: str,
    live_path: str,
    source_path: str,
    content_sha256: str,
) -> dict[str, str]:
    """Record that ``package_id`` owns ``live_path`` and return the stored entry.

    Re-recording a path for the same package replaces its provenance (the
    package was re-installed).  A path already owned by another package raises
    ``OwnershipConflict`` and leaves the ledger unchanged.
    """
    validate_ledger(ledger)
    package_id = _require_text(package_id, "package_id")
    source_path = _require_text(source_path, "source_path").replace("\\", "/")
    content_sha256 = _require_text(content_sha256, "content_sha256")
    key = normalize_live_path(live_path)
    existing = ledger["owned_files"].get(key)
    if existing is not None and existing.get("package_id") != package_id:
        raise OwnershipConflict(key, str(existing.get("package_id")), package_id)
    entry = {
        "package_id": package_id,
        "source_path": source_path,
        "content_sha256": content_sha256,
    }
    ledger["owned_files"][key] = entry
    return dict(entry)


def remove_owned_file(ledger: dict[str, Any], live_path: str) -> dict[str, str] | None:
    """Forget ``live_path``; return the removed entry or ``None`` if it was not owned."""
    validate_ledger(ledger)
    return ledger["owned_files"].pop(normalize_live_path(live_path), None)


def remove_package(ledger: dict[str, Any], package_id: str) -> list[str]:
    """Forget every file owned by ``package_id``; return the removed live paths (sorted)."""
    validate_ledger(ledger)
    package_id = _require_text(package_id, "package_id")
    removed = sorted(
        path for path, entry in ledger["owned_files"].items() if entry["package_id"] == package_id
    )
    for path in removed:
        del ledger["owned_files"][path]
    return removed


# --------------------------------------------------------------------------- queries


def owner_of(ledger: dict[str, Any], live_path: str) -> str | None:
    """The package that owns ``live_path``, or ``None``."""
    validate_ledger(ledger)
    entry = ledger["owned_files"].get(normalize_live_path(live_path))
    return None if entry is None else str(entry["package_id"])


def files_owned_by(ledger: dict[str, Any], package_id: str) -> dict[str, dict[str, str]]:
    """Live path -> entry for every file owned by ``package_id`` (sorted by path)."""
    validate_ledger(ledger)
    package_id = _require_text(package_id, "package_id")
    return {
        path: dict(entry)
        for path, entry in sorted(ledger["owned_files"].items())
        if entry["package_id"] == package_id
    }


def package_ids(ledger: dict[str, Any]) -> list[str]:
    """Sorted distinct package ids that own at least one file."""
    validate_ledger(ledger)
    return sorted({entry["package_id"] for entry in ledger["owned_files"].values()})


# --------------------------------------------------------------------------- persistence


def dumps_ledger(ledger: dict[str, Any]) -> str:
    """Canonical text form: validated, keys sorted, one entry per line, trailing newline."""
    validate_ledger(ledger)
    canonical = {
        "schema": LEDGER_SCHEMA,
        "owned_files": {
            path: {k: ledger["owned_files"][path][k] for k in sorted(ledger["owned_files"][path])}
            for path in sorted(ledger["owned_files"])
        },
    }
    return json.dumps(canonical, sort_keys=True, indent=1) + "\n"


def save_ledger(path: Path | str, ledger: dict[str, Any]) -> Path:
    """Atomically write ``ledger`` to ``path`` and return the path.

    The document is validated and serialised before anything touches the disk.
    The bytes go to a temporary file beside ``path``, are fsynced, then
    ``os.replace`` swaps them in.  If any step fails the temporary file is
    removed and the original ``OSError`` (e.g. ENOSPC, errno 28) is re-raised;
    an existing ledger at ``path`` is never truncated or partially written.
    """
    target = Path(path)
    data = dumps_ledger(ledger).encode("utf-8")
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, target)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    try:
        dir_fd = os.open(str(target.parent), os.O_RDONLY)
    except OSError:
        return target
    try:
        os.fsync(dir_fd)
    except OSError:
        pass
    finally:
        os.close(dir_fd)
    return target


def load_ledger(path: Path | str, *, missing_ok: bool = False) -> dict[str, Any]:
    """Read and validate the ledger at ``path``.

    A missing file raises ``FileNotFoundError`` unless ``missing_ok`` is set, in
    which case an empty ledger is returned.  Malformed content raises
    ``LedgerError`` so a truncated or foreign file is never mistaken for an
    empty ledger.
    """
    target = Path(path)
    if not target.is_file():
        if missing_ok:
            return empty_ledger()
        raise FileNotFoundError(str(target))
    raw = target.read_bytes()
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LedgerError(f"{target}: not valid JSON ({exc})") from exc
    return validate_ledger(doc)
