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

**A backup must never overwrite an earlier backup.** The stamp alone does not
guarantee that: two writes inside the same second collide, and a caller that froze one
``datetime`` for a whole process (the GUI did exactly this) collides on EVERY write
after the first. A clobbered sidecar is silent data loss of precisely the artefact the
operator was promised, so :func:`backup_path` takes a ``taken`` predicate and walks to
the first free ``-1``/``-2``/... name. The production clock is a CALLABLE
(:func:`make_clock`) so a long-lived process re-reads it per write instead of reusing
one frozen instant.

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
    "Clock",
    "backup_path",
    "fixed_clock",
    "make_clock",
    "restore_command",
    "utc_stamp",
]

#: Marker in the sidecar name. Distinct from other tools' ``.bak`` so a sweep can tell
#: whose backup it is looking at.
BACKUP_SUFFIX = "mcpapply"

#: How many ``-N`` disambiguating suffixes to try before falling back to a
#: microsecond-precision stamp. One second of writes never approaches this.
MAX_COLLISION_SUFFIXES = 100

#: A source of "now". A CALLABLE, not a value: a process that keeps one ``datetime``
#: for its lifetime derives one backup filename for its lifetime.
Clock = Callable[[], datetime]


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


def utc_stamp(now: datetime, *, precise: bool = False) -> str:
    """A filesystem-safe UTC stamp, e.g. ``20260727T031500Z``.

    ``now`` is injected rather than read from the clock so a caller -- and every test
    -- gets a deterministic name. A naive datetime is treated as UTC rather than
    rejected: refusing to back up because a clock lacked a tzinfo would be the wrong
    failure mode for a safety feature.

    ``precise`` adds microseconds; it is the last-resort tiebreak in
    :func:`backup_path` when every ``-N`` suffix is somehow taken.
    """
    moment = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
    pattern = "%Y%m%dT%H%M%S%fZ" if precise else "%Y%m%dT%H%M%SZ"
    return moment.astimezone(timezone.utc).strftime(pattern)


def backup_path(
    target: Path, now: datetime, *, taken: Callable[[Path], bool] | None = None
) -> Path:
    """The sidecar path for ``target`` at ``now``, never colliding with an existing one.

    ``taken`` reports whether a candidate name already exists (in production,
    ``FileStore.exists``). Without it the bare stamped name is returned, which is only
    safe when the caller knows no earlier backup can share the second -- so
    :func:`~mcpapply.apply.apply_plan` always passes it. Overwriting an earlier sidecar
    would destroy the one artefact its own restore command points at.
    """
    stamp = utc_stamp(now)
    base = target.with_name(f"{target.name}.{BACKUP_SUFFIX}-{stamp}.bak")
    if taken is None or not taken(base):
        return base
    for index in range(1, MAX_COLLISION_SUFFIXES):
        candidate = target.with_name(
            f"{target.name}.{BACKUP_SUFFIX}-{stamp}-{index}.bak"
        )
        if not taken(candidate):
            return candidate
    return target.with_name(
        f"{target.name}.{BACKUP_SUFFIX}-{utc_stamp(now, precise=True)}.bak"
    )


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


def make_clock() -> Clock:
    """The production clock, as an injectable callable (UTC, tz-aware).

    Callers hold the CALLABLE, never a ``datetime`` snapshot: a GUI that captured one
    instant at launch reused a single backup filename for its whole session and every
    apply after the first silently overwrote the previous sidecar.
    """
    return lambda: datetime.now(timezone.utc)


def fixed_clock(moment: datetime) -> Clock:
    """A clock frozen at ``moment`` -- for a one-shot run and for deterministic tests."""
    return lambda: moment
