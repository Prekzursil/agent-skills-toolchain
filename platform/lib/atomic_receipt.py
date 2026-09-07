"""Atomic receipt writer — IMP-0434.

Every work unit emits its artifact via tmp-file + ``os.replace``. A writer killed
mid-write must leave either the previous complete file or nothing — never a
half-written target. Read-back must equal the object that was written.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping

__all__ = ["ATOMIC_WRITER_ID", "write_json_atomic", "read_json"]

ATOMIC_WRITER_ID = "platform/lib/atomic_receipt.py@v1"


def write_json_atomic(path: str | Path, doc: Mapping[str, Any]) -> Path:
    """Serialize ``doc`` as UTF-8 JSON and publish it atomically at ``path``.

    Steps (POSIX rename is atomic on the same filesystem):
      1. ensure parent directory exists
      2. write exclusive bytes to a sibling ``.tmp`` file
      3. ``fsync`` the temp file
      4. ``os.replace(tmp, path)`` — the only moment the target name appears/changes
    """
    target = Path(path)
    if not target.is_absolute():
        # Callers pass repo-relative paths; resolve against CWD (repo root in builds).
        target = Path.cwd() / target
    target.parent.mkdir(parents=True, exist_ok=True)

    payload = (json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=False) + "\n").encode(
        "utf-8"
    )

    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=str(target.parent),
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, target)
    except Exception:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise
    return target


def read_json(path: str | Path) -> Any:
    """Read and parse a JSON file written by :func:`write_json_atomic`."""
    p = Path(path)
    if not p.is_absolute():
        p = Path.cwd() / p
    return json.loads(p.read_text(encoding="utf-8"))
