"""Timestamped sidecar backups + the printed restore command.

The rule, and why it is not negotiable: **every write is preceded by a backup, and the
restore command is PRINTED, not merely possible.** A backup an operator has to
reverse-engineer at 2am is not a backup. :func:`restore_command` emits a copyable
command for each file that was saved.

Naming: ``<target>.mcpapply-<UTC stamp>.bak``, sibling to the original. A sidecar
beside the file (rather than a central backup directory) survives the case that
actually happens -- the operator finds a broken ``~/.claude.json`` and looks next to
it -- and needs no directory creation, so a backup can never fail because a parent is
missing.

Everything here is pure apart from the injected :class:`~mcpapply.apply.FileStore`;
the clock is injected too, so a backup name is deterministic under test.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

__all__ = [
    "BACKUP_SUFFIX",
    "BackupRecord",
    "backup_path",
    "restore_command",
    "utc_stamp",
]

#: Marker in the sidecar name. Distinct from other tools' ``.bak`` so a sweep can tell
#: whose backup it is looking at.
BACKUP_SUFFIX = "mcpapply"


@dataclass(frozen=True)
class BackupRecord:
    """One saved file: where it came from, where the copy went, and how big it was."""

    source: str
    backup: str
    size_bytes: int

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "backup": self.backup,
            "size_bytes": self.size_bytes,
        }


def utc_stamp(now: datetime) -> str:
    """A filesystem-safe UTC stamp, e.g. ``20260727T031500Z``.

    ``now`` is injected rather than read from the clock so a caller -- and every test
    -- gets a deterministic name. A naive datetime is treated as UTC rather than
    rejected: refusing to back up because a clock lacked a tzinfo would be the wrong
    failure mode for a safety feature.
    """
    moment = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def backup_path(target: Path, now: datetime) -> Path:
    """The sidecar path for ``target`` at ``now``."""
    return target.with_name(f"{target.name}.{BACKUP_SUFFIX}-{utc_stamp(now)}.bak")


def restore_command(records: tuple[BackupRecord, ...]) -> str:
    """The exact command that puts every backed-up file back.

    Emitted for BOTH shells this box runs, because a half-remembered ``copy`` vs ``cp``
    is exactly the friction that stops someone restoring.
    """
    if not records:
        return "no backup was taken (nothing was written)"
    lines = [
        "# PowerShell",
        *(
            f'Copy-Item -LiteralPath "{r.backup}" -Destination "{r.source}" -Force'
            for r in records
        ),
    ]
    lines.append("# bash")
    lines.extend(f"cp -- '{r.backup}' '{r.source}'" for r in records)
    return "\n".join(lines)


def make_clock() -> Callable[[], datetime]:
    """The production clock, as an injectable callable (UTC, tz-aware)."""
    return lambda: datetime.now(timezone.utc)
