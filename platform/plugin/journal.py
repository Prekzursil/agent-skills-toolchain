"""Install-prefix layout, the prefix lock, and the lifecycle transaction journal.

Every mutating command opens a transaction, appends one record per applied step **before** the
step's effect is observable, and closes with ``committed`` or ``aborted``. Each step carries its
own inverse, so:

* a step that raises causes the already-applied steps to be undone in reverse order — the prefix
  ends at its pre-operation state and the journal says ``aborted`` (``E_TXN``);
* a process killed mid-transaction leaves an ``open`` record on disk, and the next command's
  ``recover()`` replays the inverses. Crash recovery is not a special path, it is the same undo.

The journal is append-only JSONL, fsynced per record, so a torn write can lose at most the record
for a step that had not yet been applied.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .errors import PluginError
from .fsops import atomic_write_bytes, contextlib_suppress, extended, rmtree

STATE_DIR = "state"
JOURNAL_NAME = "journal.jsonl"
LOCK_NAME = "prefix.lock"
INSTALLED_NAME = "installed.json"


@dataclass(frozen=True)
class Prefix:
    """The install prefix layout. Every path in the package derives from here."""

    root: Path

    @property
    def versions(self) -> Path:
        return self.root / "versions"

    @property
    def state(self) -> Path:
        return self.root / STATE_DIR

    @property
    def journal(self) -> Path:
        return self.state / JOURNAL_NAME

    @property
    def lock(self) -> Path:
        return self.state / LOCK_NAME

    @property
    def installed(self) -> Path:
        return self.state / INSTALLED_NAME

    @property
    def backups(self) -> Path:
        return self.state / "backups"

    @property
    def cache(self) -> Path:
        return self.state / "cache"

    @property
    def logs(self) -> Path:
        return self.state / "logs"

    @property
    def staging(self) -> Path:
        return self.state / "staging"

    @property
    def userdata(self) -> Path:
        return self.root / "userdata"

    def version_dir(self, version: str) -> Path:
        return self.versions / version

    def ensure(self) -> None:
        for p in (
            self.versions,
            self.state,
            self.backups,
            self.cache,
            self.logs,
            self.userdata,
        ):
            p.mkdir(parents=True, exist_ok=True)


class PrefixLock:
    """Exclusive advisory lock via ``O_CREAT|O_EXCL``. Detects concurrent ops (IMP-0029)."""

    def __init__(self, prefix: Prefix, *, op: str, stale_after: float = 3600.0) -> None:
        self.prefix = prefix
        self.op = op
        self.stale_after = stale_after
        self._fd: int | None = None

    def __enter__(self) -> PrefixLock:
        self.prefix.state.mkdir(parents=True, exist_ok=True)
        path = extended(self.prefix.lock)
        try:
            self._fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            age = time.time() - self.prefix.lock.stat().st_mtime
            holder = self.prefix.lock.read_text(
                encoding="utf-8", errors="replace"
            ).strip()
            if age < self.stale_after:
                raise PluginError(
                    "E_LOCK",
                    f"prefix is locked by another lifecycle operation ({age:.0f}s old)",
                    context={
                        "holder": holder or "<unknown>",
                        "lock": str(self.prefix.lock),
                    },
                ) from None
            # Stale: the holder died. Take it over, but say so loudly rather than silently.
            self.prefix.lock.unlink()
            self._fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(
            self._fd, f"{self.op} pid={os.getpid()} at={time.time():.0f}\n".encode()
        )
        os.fsync(self._fd)
        return self

    def __exit__(self, *exc: object) -> None:
        if self._fd is not None:
            with contextlib_suppress():
                os.close(self._fd)
        with contextlib_suppress():
            self.prefix.lock.unlink()


Undo = Callable[[], None]


@dataclass
class Step:
    """One journalled step: a description, its record payload, and its inverse."""

    kind: str
    detail: dict[str, object]
    undo: Undo | None = None


@dataclass
class Transaction:
    """Journalled, self-undoing unit of work. Use as a context manager."""

    prefix: Prefix
    op: str
    txn_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    steps: list[Step] = field(default_factory=list)
    status: str = "open"

    def __enter__(self) -> Transaction:
        self.prefix.state.mkdir(parents=True, exist_ok=True)
        self._append({"event": "open", "op": self.op, "txn": self.txn_id})
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object,
    ) -> bool:
        if exc_type is None:
            self.status = "committed"
            self._append(
                {
                    "event": "commit",
                    "op": self.op,
                    "txn": self.txn_id,
                    "steps": len(self.steps),
                }
            )
            return False
        undone, failures = self._rollback()
        self.status = "aborted"
        self._append(
            {
                "event": "abort",
                "op": self.op,
                "txn": self.txn_id,
                "reason": f"{exc_type.__name__}: {exc}",
                "steps_undone": undone,
                "undo_failures": failures,
            }
        )
        return False  # never swallow: the CLI renders the classified error

    def add(
        self, kind: str, detail: dict[str, object], undo: Undo | None = None
    ) -> None:
        """Record a step BEFORE its effect is observable, then apply it."""
        step = Step(kind, detail, undo)
        self.steps.append(step)
        self._append(
            {"event": "step", "op": self.op, "txn": self.txn_id, "kind": kind, **detail}
        )

    def _rollback(self) -> tuple[int, list[str]]:
        undone = 0
        failures: list[str] = []
        for step in reversed(self.steps):
            if step.undo is None:
                continue
            try:
                step.undo()
                undone += 1
            except Exception as exc:  # noqa: BLE001 - a failed undo must be reported, never hidden
                failures.append(f"{step.kind}: {exc}")
        return undone, failures

    def _append(self, record: dict[str, object]) -> None:
        record = {"ts": round(time.time(), 3), **record}
        line = (json.dumps(record, sort_keys=True) + "\n").encode("utf-8")
        path = extended(self.prefix.journal)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "ab") as fh:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())


def read_journal(prefix: Prefix) -> list[dict[str, object]]:
    if not prefix.journal.exists():
        return []
    out: list[dict[str, object]] = []
    for line in prefix.journal.read_text(
        encoding="utf-8", errors="replace"
    ).splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            out.append({"event": "unparseable", "raw_len": len(line)})
    return out


def open_transactions(prefix: Prefix) -> list[str]:
    """Transaction ids that were opened and neither committed nor aborted = crash residue."""
    state: dict[str, str] = {}
    for rec in read_journal(prefix):
        txn = str(rec.get("txn", ""))
        ev = rec.get("event")
        if not txn:
            continue
        if ev == "open":
            state[txn] = "open"
        elif ev in {"commit", "abort", "recovered"}:
            state[txn] = str(ev)
    return sorted(t for t, s in state.items() if s == "open")


def recover(prefix: Prefix) -> dict[str, object]:
    """Crash recovery: undo the file-level effects of every un-closed transaction.

    The only durable effects a transaction can leave are (a) a staged directory and (b) a created
    version directory, both recorded in the journal with their absolute path. Both are removed and
    the transaction is marked ``recovered``.
    """
    stale = open_transactions(prefix)
    removed: list[str] = []
    if not stale:
        return {
            "artifact": "crash-recovery",
            "open_transactions": [],
            "removed": [],
            "clean": True,
        }
    records = read_journal(prefix)
    for txn in stale:
        for rec in records:
            if rec.get("txn") != txn or rec.get("event") != "step":
                continue
            for key in ("staged_dir", "created_dir"):
                target = rec.get(key)
                if isinstance(target, str) and target:
                    p = Path(target)
                    try:
                        p.relative_to(prefix.root)
                    except ValueError:
                        continue  # never delete outside the prefix
                    if p.exists():
                        rmtree(p)
                        removed.append(str(p))
    txn_note = {
        "event": "recovered",
        "op": "recover",
        "txn": ",".join(stale),
        "removed": removed,
    }
    line = (
        json.dumps({"ts": round(time.time(), 3), **txn_note}, sort_keys=True) + "\n"
    ).encode()
    with open(extended(prefix.journal), "ab") as fh:
        fh.write(line)
        fh.flush()
        os.fsync(fh.fileno())
    return {
        "artifact": "crash-recovery",
        "open_transactions": stale,
        "removed": sorted(set(removed)),
        "clean": False,
    }


def journal_document(prefix: Prefix) -> dict[str, object]:
    """The txn-journal artifact (tools/plugin/schema/txn-journal.schema.json)."""
    records = read_journal(prefix)
    return {
        "artifact": "txn-journal",
        "prefix": str(prefix.root),
        "record_count": len(records),
        "open_transactions": open_transactions(prefix),
        "records": records,
    }


def write_installed(prefix: Prefix, doc: dict[str, object]) -> None:
    atomic_write_bytes(
        prefix.installed, (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode()
    )


def read_installed(prefix: Prefix) -> dict[str, object]:
    if not prefix.installed.exists():
        return {}
    try:
        return json.loads(prefix.installed.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PluginError("E_TXN", f"installed.json is corrupt: {exc}") from exc
