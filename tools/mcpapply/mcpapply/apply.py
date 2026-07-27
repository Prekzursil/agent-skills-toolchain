"""Turn a :class:`~mcpapply.plan.Plan` into bytes on disk -- or, by default, into
nothing at all.

Three properties this module exists to guarantee, each with a test that fails if it is
removed:

1. **DRY RUN IS THE DEFAULT.** :func:`apply_plan` writes only when the caller passes
   ``apply=True``. The default parameter value IS the safety mechanism; a caller that
   forgets the flag gets a preview, never a mutation.
2. **Round-trip preservation.** A document is ``deepcopy``-ed, exactly one key path is
   mutated, and the copy is re-serialised. The model is never rebuilt from a parsed
   view, so an unknown key -- an oauth blob, a project history, the owner's curation --
   cannot be dropped by a writer that did not know about it. This is the mechanical
   form of the standing rule that the curation is LOAD-BEARING and must never be wiped.
3. **Backup before write.** Every file that is about to change is copied to a
   timestamped sidecar first and the restore command is printed.

The filesystem is an injected PORT (:class:`FileStore`). The production implementation
(:class:`RealFileStore`) writes through a temp file, takes an OS-level lock and lands
the result with ``os.replace``, because ``~/.claude.json`` is ~235 KB and is rewritten
continuously by every running host session -- a plain ``write_text`` that loses a race
truncates the operator's profile.
"""

from __future__ import annotations

import copy
import difflib
import json
import os
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol, cast

from mcpctl.safety import safe
from mcpctl.sources import SourcePaths

from mcpapply.backup import BackupRecord, backup_path, restore_command
from mcpapply.plan import Edit, Op, Plan

__all__ = [
    "ApplyResult",
    "FileChange",
    "FileStore",
    "MemoryFileStore",
    "RealFileStore",
    "apply_edits_to_doc",
    "apply_plan",
    "line_ending",
    "render_result",
]

#: Context lines around each hunk in the previewed diff. Deliberately tight: the
#: documents are large and a wide window is both unreadable and a bigger surface for a
#: neighbouring credential-looking string to ride along in.
_DIFF_CONTEXT = 2

#: Emitted when a target moved between the preview read and the write. Every running
#: host session rewrites ``~/.claude.json`` continuously, so this is the ordinary case
#: rather than an exotic one -- and writing the stale bytes would silently revert
#: whatever the other writer just did.
_STALE = (
    "{label} changed on disk between the preview and the write; REFUSED. Re-run to "
    "plan against the current contents."
)


class FileStore(Protocol):
    """The injected filesystem port. Four operations, no more."""

    def exists(self, path: Path) -> bool: ...

    def read_text(self, path: Path) -> str: ...

    def write_text(self, path: Path, text: str) -> None: ...

    def copy_file(self, source: Path, destination: Path) -> int: ...


class RealFileStore:
    """The production store: temp file -> ``fsync`` -> ``os.replace``.

    Deliberately NO ``msvcrt``/``fcntl`` lock, and the omission is the considered
    choice rather than an oversight. The in-repo precedent
    (``hooks/mcp-defaults/enforce-mcp-defaults.py:79-92``) locks the TEMP file -- a
    path no other writer ever opens -- so that lock excludes nobody; the atomicity it
    appears to provide actually comes from the ``os.replace`` on the next line, which
    is atomic on both NTFS and POSIX on its own. Mutual exclusion against the host's
    own writer is handled where it can actually work: :func:`apply_plan` re-reads each
    target immediately before writing and REFUSES if the bytes moved since the preview
    (see ``_STALE``). A lock would also have cost a permanently-unreachable platform
    branch in the coverage gate, i.e. a ``# pragma: no cover`` bought for no safety.
    """

    def exists(self, path: Path) -> bool:
        return path.exists()

    def read_text(self, path: Path) -> str:
        """Read with newline translation DISABLED (``newline=""``).

        ``Path.read_text`` applies universal newlines, so a CRLF document arrives as
        LF -- which silently defeats :func:`line_ending` (the writer would convert the
        file), makes the ``changed`` comparison compare a translation rather than the
        bytes, and makes the stale-write check blind to a pure line-ending edit by
        another writer. MEASURED: ``~/.mcp.json`` on this box is CRLF while the other
        four scopes are LF, so this is a live case, not a hypothetical one.
        """
        with open(path, encoding="utf-8", newline="") as handle:
            return handle.read()

    def write_text(self, path: Path, text: str) -> None:
        tmp = path.with_name(path.name + ".mcpapply.tmp")
        with open(tmp, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)

    def copy_file(self, source: Path, destination: Path) -> int:
        payload = source.read_bytes()
        destination.write_bytes(payload)
        return len(payload)


class MemoryFileStore:
    """An in-memory store. Used by the hermetic tests and by ``--apply`` previews."""

    def __init__(self, files: Mapping[str, str] | None = None) -> None:
        self.files: dict[str, str] = dict(files or {})
        self.writes: list[str] = []

    def exists(self, path: Path) -> bool:
        return str(path) in self.files

    def read_text(self, path: Path) -> str:
        try:
            return self.files[str(path)]
        except KeyError as exc:
            raise FileNotFoundError(str(path)) from exc

    def write_text(self, path: Path, text: str) -> None:
        self.files[str(path)] = text
        self.writes.append(str(path))

    def copy_file(self, source: Path, destination: Path) -> int:
        payload = self.files[str(source)]
        self.files[str(destination)] = payload
        return len(payload.encode("utf-8"))


@dataclass(frozen=True)
class FileChange:
    """What one configuration document would look like after the plan."""

    label: str
    path: str
    changed: bool
    created: bool
    diff: str

    def to_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "path": self.path,
            "changed": self.changed,
            "created": self.created,
            "diff": self.diff,
        }


@dataclass(frozen=True)
class ApplyResult:
    """The outcome. ``dry_run=True`` guarantees ``written`` and ``backups`` are empty."""

    dry_run: bool
    file_changes: tuple[FileChange, ...] = ()
    backups: tuple[BackupRecord, ...] = ()
    written: tuple[str, ...] = ()
    problems: tuple[str, ...] = ()
    blocked: str = ""

    @property
    def restore(self) -> str:
        return restore_command(self.backups)

    def to_dict(self) -> dict[str, object]:
        return {
            "dry_run": self.dry_run,
            "blocked": self.blocked,
            "written": list(self.written),
            "problems": list(self.problems),
            "backups": [b.to_dict() for b in self.backups],
            "file_changes": [c.to_dict() for c in self.file_changes],
            "restore": self.restore,
        }


def _navigate(
    doc: dict[str, object], key_path: Sequence[str]
) -> tuple[dict[str, object] | None, str, str]:
    """Walk to the parent of the final key, creating missing intermediate mappings.

    Returns ``(parent, final_key, problem)``. ``parent is None`` means the walk hit a
    non-mapping and the caller must SKIP rather than clobber: overwriting a
    hand-edited value with the shape this tool expected is exactly the wipe the
    curation rule forbids.
    """
    node: dict[str, object] = doc
    for index, key in enumerate(key_path[:-1]):
        child = node.get(key)
        if child is None:
            fresh: dict[str, object] = {}
            node[key] = fresh
            node = fresh
            continue
        if not isinstance(child, dict):
            trail = ".".join(key_path[: index + 1])
            return None, "", f"{trail} is a {type(child).__name__}, not an object"
        node = cast("dict[str, object]", child)
    return node, key_path[-1], ""


def _denied_matches(item: object, name: str) -> bool:
    """True when a ``deniedMcpServers`` element denotes ``name``.

    That list holds OBJECTS (``{"serverName": "markitdown"}``) on this box, with bare
    strings accepted for hand-edited files. Reading it as a plain ``list[str]`` misses
    every real element -- an enable would silently leave the denial in place and report
    success.
    """
    if isinstance(item, str):
        return item == name
    if isinstance(item, Mapping):
        return cast("Mapping[str, object]", item).get("serverName") == name
    return False


def _apply_one(doc: dict[str, object], edit: Edit) -> str:
    """Apply ONE edit in place. Returns a problem string, or ``""`` on success."""
    parent, key, problem = _navigate(doc, edit.key_path)
    if parent is None:
        return f"{edit.label}: {problem}; skipped {edit.op.value} {edit.server}"
    current = parent.get(key)

    if edit.op is Op.LIST_ADD:
        if current is None:
            current = []
            parent[key] = current
        if not isinstance(current, list):
            return f"{edit.label}: {key} is a {type(current).__name__}, not a list"
        items = cast("list[object]", current)
        if edit.server not in items:
            items.append(edit.server)
        return ""

    if edit.op is Op.LIST_REMOVE:
        if current is None:
            return ""
        if not isinstance(current, list):
            return f"{edit.label}: {key} is a {type(current).__name__}, not a list"
        items = cast("list[object]", current)
        parent[key] = [i for i in items if not _denied_matches(i, edit.server)]
        return ""

    if edit.op is Op.MAP_SET:
        if current is None:
            current = {}
            parent[key] = current
        if not isinstance(current, dict):
            return f"{edit.label}: {key} is a {type(current).__name__}, not an object"
        cast("dict[str, object]", current)[edit.server] = dict(edit.spec or {})
        return ""

    if current is None:
        return ""
    if not isinstance(current, dict):
        return f"{edit.label}: {key} is a {type(current).__name__}, not an object"
    cast("dict[str, object]", current).pop(edit.server, None)
    return ""


def apply_edits_to_doc(
    doc: Mapping[str, object], edits: Iterable[Edit]
) -> tuple[dict[str, object], tuple[str, ...]]:
    """Return a DEEP COPY of ``doc`` with ``edits`` applied, plus any problems.

    The copy is the preservation guarantee: every key this tool has never heard of is
    carried through untouched because it is literally the same value object, moved.
    """
    working = copy.deepcopy(dict(doc))
    problems = [p for p in (_apply_one(working, e) for e in edits) if p]
    return working, tuple(problems)


def _serialise(
    doc: Mapping[str, object], *, trailing_newline: bool, newline: str
) -> str:
    text = json.dumps(doc, indent=2, ensure_ascii=False)
    if trailing_newline:
        text += "\n"
    return text if newline == "\n" else text.replace("\n", newline)


def line_ending(text: str) -> str:
    """The file's OWN newline convention, so a write does not convert it.

    MEASURED on this box, 2026-07-27, by a read-only round-trip of the real configs:
    ``~/.claude.json`` (236,130 B) and ``~/.claude/settings.json`` (23,242 B) are LF and
    re-serialise BYTE-IDENTICAL through this writer, while ``~/.mcp.json`` is **CRLF**.
    Emitting LF unconditionally would rewrite that whole file to change nothing but its
    line endings -- a 118-character phantom diff, a needless full-file write on a
    document another tool is also editing, and exactly the CRLF/LF churn this estate has
    a standing rule about.

    A blanket replace is safe: JSON escapes any newline inside a string value as ``\\n``,
    so the only real newlines in the serialised text are the formatting ones.
    """
    return "\r\n" if "\r\n" in text else "\n"


def _diff(label: str, before: str, after: str) -> str:
    """A SAFE unified diff: control bytes stripped, credential shapes masked."""
    lines = difflib.unified_diff(
        before.splitlines(),
        after.splitlines(),
        fromfile=f"{label} (current)",
        tofile=f"{label} (planned)",
        n=_DIFF_CONTEXT,
        lineterm="",
    )
    return "\n".join(safe(line) for line in lines)


def _edits_by_label(plan: Plan) -> dict[str, list[Edit]]:
    grouped: dict[str, list[Edit]] = {}
    for change in plan.changes:
        for edit in change.edits:
            if edit.op is Op.LIVE_ONLY:
                continue
            grouped.setdefault(edit.label, []).append(edit)
    return grouped


def _path_for(paths: SourcePaths, label: str) -> Path:
    return dict(paths.as_tuple())[label]


def apply_plan(
    plan: Plan,
    *,
    paths: SourcePaths,
    store: FileStore,
    now: datetime,
    apply: bool = False,
    guard: Callable[[], str] | None = None,
) -> ApplyResult:
    """Preview -- or, with ``apply=True``, perform -- the plan's configuration writes.

    ``apply`` defaults to ``False``. That default is the entire safety contract of this
    package: nothing reaches disk unless a caller opted in explicitly.

    ``guard`` is a fail-CLOSED precondition (see :mod:`mcpapply.guard`): it returns a
    non-empty string to REFUSE the write. It is consulted only on the apply path, so a
    preview always works even while the host is running.
    """
    grouped = _edits_by_label(plan)
    changes: list[FileChange] = []
    problems: list[str] = []
    staged: list[tuple[Path, str, str]] = []

    for label in sorted(grouped):
        path = _path_for(paths, label)
        if store.exists(path):
            before = store.read_text(path)
            created = False
        else:
            before = ""
            created = True
        try:
            doc = cast("dict[str, object]", json.loads(before)) if before else {}
        except json.JSONDecodeError as exc:
            problems.append(f"{label}: unparseable JSON ({exc}); refusing to write it")
            continue
        if not isinstance(doc, dict):
            problems.append(
                f"{label}: top level is not an object; refusing to write it"
            )
            continue
        updated, issues = apply_edits_to_doc(doc, grouped[label])
        problems.extend(issues)
        after = _serialise(
            updated,
            trailing_newline=before.endswith("\n") or not before,
            newline=line_ending(before),
        )
        changed = after != before
        changes.append(
            FileChange(
                label=label,
                path=safe(str(path)),
                changed=changed,
                created=created,
                diff=_diff(label, before, after),
            )
        )
        if changed:
            staged.append((path, before, after))

    if not apply:
        return ApplyResult(
            dry_run=True, file_changes=tuple(changes), problems=tuple(problems)
        )

    refusal = "" if guard is None else guard()
    if refusal:
        return ApplyResult(
            dry_run=True,
            file_changes=tuple(changes),
            problems=tuple(problems),
            blocked=safe(refusal),
        )

    backups: list[BackupRecord] = []
    written: list[str] = []
    for path, before, after in staged:
        if store.exists(path):
            if store.read_text(path) != before:
                problems.append(_STALE.format(label=safe(str(path))))
                continue
            destination = backup_path(path, now)
            size = store.copy_file(path, destination)
            backups.append(
                BackupRecord(source=str(path), backup=str(destination), size_bytes=size)
            )
        store.write_text(path, after)
        written.append(safe(str(path)))

    return ApplyResult(
        dry_run=False,
        file_changes=tuple(changes),
        backups=tuple(backups),
        written=tuple(written),
        problems=tuple(problems),
    )


def render_result(result: ApplyResult) -> str:
    """Plain-text rendering of an apply/preview outcome."""
    lines: list[str] = []
    for change in result.file_changes:
        verb = "would change" if result.dry_run else "changed"
        state = verb if change.changed else "unchanged"
        lines.append(f"{change.label} ({change.path}): {state}")
        if change.diff:
            lines.extend(f"    {line}" for line in change.diff.splitlines())
    for problem in result.problems:
        lines.append(f"! {problem}")
    if result.blocked:
        lines.append(f"BLOCKED: {result.blocked}")
    if result.dry_run:
        lines.append("DRY RUN -- nothing was written. Re-run with --apply to commit.")
    else:
        for record in result.backups:
            lines.append(f"backup: {record.backup} ({record.size_bytes} bytes)")
        lines.append("restore with:")
        lines.extend(f"    {line}" for line in result.restore.splitlines())
    return "\n".join(lines)
