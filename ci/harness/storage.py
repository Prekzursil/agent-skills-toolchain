from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    try:
        temp.write_text(text, encoding="utf-8")
        os.replace(temp, path)
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass


def atomic_write_json(path: Path, value: Any) -> None:
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


# Read outcomes. ``read_json`` collapses three DISTINCT states into the caller's
# default: the file is ABSENT, the file exists but is CORRUPT, and the file exists
# but cannot be read. For persisted control state that conflation is a real defect
# — a caller cannot tell "no baseline yet" (benign; failing open is correct) from
# "the baseline is DAMAGED" (a finding that must never be reported as healthy).
# ``read_json_status`` returns the same value PLUS why, so a caller can fail loudly
# on damage while still failing open on a genuinely-absent file.
READ_OK = "ok"
READ_MISSING = "missing"
READ_MALFORMED = "malformed"
READ_UNREADABLE = "unreadable"
# Damage = the path resolves to something that exists (or is otherwise not a plain
# "not yet written") but did not yield a document. Callers guard on this set.
READ_DAMAGED = frozenset({READ_MALFORMED, READ_UNREADABLE})


def read_json_status(path: Path, default: Any) -> tuple[Any, str]:
    """Return ``(value, status)`` where status is one of the ``READ_*`` constants.

    ``FileNotFoundError`` is checked before the general ``OSError`` (it is a
    subclass) so an absent file stays distinguishable from an unreadable one
    (a directory, a permission denial, a path under a non-directory).
    """
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return default, READ_MISSING
    except (OSError, TypeError):
        return default, READ_UNREADABLE
    try:
        return json.loads(text), READ_OK
    except (ValueError, TypeError):
        return default, READ_MALFORMED


def read_json(path: Path, default: Any) -> Any:
    """Value-only view of :func:`read_json_status` (unchanged fail-open contract)."""
    return read_json_status(path, default)[0]

