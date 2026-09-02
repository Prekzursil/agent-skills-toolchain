"""The durable coordination store: atomic records plus an append-only journal.

DESIGN CONSTRAINTS THAT ARE NOT NEGOTIABLE HERE

1. **A claim must be won by exactly one session.** ``create_exclusive`` uses
   ``os.open(..., O_CREAT | O_EXCL)``, which is atomic on both NTFS and POSIX. A read-then-write
   check-and-set would let two sessions both observe "no claim" and both write one.

2. **Every write is atomic.** ``write_atomic`` writes a sibling temp file and ``os.replace``s it,
   so a crash mid-write leaves either the old record or the new one, never a truncated one. A
   half-written claim read as "no claim" is the same double-dispatch bug as (1).

3. **Newlines are pinned to ``\\n`` explicitly.** Python's text mode on Windows translates ``\\n``
   to ``\\r\\n``, which would make the journal's bytes platform-dependent and every digest over it
   unreproducible. ``rules/common/windows-shell.md`` section 8b records the class: a local green
   measured against CRLF bytes verifies nothing about the LF bytes CI sees.

4. **A corrupt record raises.** ``StoreCorrupt`` is raised rather than returning ``None``,
   because "unreadable claim" and "no claim" must not collapse into the same branch.

5. **The clock is injected.** ``Clock`` is a parameter, never ``time.time()`` reached for inside a
   decision function, so every liveness/expiry test is deterministic.

WHAT THIS IS NOT: a database. Record counts here are bounded by the number of concurrent agent
sessions (tens), their claims (thousands) and their leases (thousands); a directory scan at that
scale is measured in milliseconds and buys crash-safety that a single index file would lose.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping

from .errors import StoreCorrupt

__all__ = [
    "Clock",
    "JOURNAL_NAME",
    "RECORD_KINDS",
    "Store",
    "canonical_json",
    "fingerprint_bytes",
    "safe_record_name",
]

#: A zero-argument callable returning POSIX seconds. Injected everywhere; never called implicitly.
Clock = Callable[[], float]

JOURNAL_NAME = "journal.jsonl"

#: Record namespaces. Each is a directory under the store root.
RECORD_KINDS: tuple[str, ...] = (
    "sessions",
    "claims",
    "fingerprints",
    "leases",
    "handoffs",
)


def canonical_json(obj: Any) -> str:
    """Deterministic JSON text: sorted keys, no incidental whitespace, UTF-8 preserved."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def fingerprint_bytes(obj: Any) -> bytes:
    """The bytes a work-unit fingerprint is computed over.

    Deliberately derived from the canonical JSON of an in-memory object, never from a file read
    off the working tree: git stores LF and Windows checks out CRLF, so a working-tree byte hash
    differs by platform. Two shipped gates on this estate had exactly that bug.
    """
    return canonical_json(obj).encode("utf-8")


@dataclass(frozen=True)
class Store:
    """A coordination store rooted at one directory."""

    root: Path
    clock: Clock = time.time

    # -------------------------------------------------------------------------------- layout

    def dir_for(self, kind: str) -> Path:
        if kind not in RECORD_KINDS:
            raise StoreCorrupt(
                f"unknown record kind {kind!r}; expected one of {RECORD_KINDS}"
            )
        return self.root / kind

    def path_for(self, kind: str, name: str) -> Path:
        safe = safe_record_name(name)
        return self.dir_for(kind) / f"{safe}.json"

    @property
    def journal_path(self) -> Path:
        return self.root / JOURNAL_NAME

    def initialise(self) -> Store:
        """Create the directory skeleton. Idempotent."""
        self.root.mkdir(parents=True, exist_ok=True)
        for kind in RECORD_KINDS:
            (self.root / kind).mkdir(parents=True, exist_ok=True)
        return self

    # --------------------------------------------------------------------------------- writes

    def write_atomic(self, path: Path, record: Mapping[str, Any]) -> None:
        """Replace ``path`` with ``record``. A crash leaves the old file, never a partial one."""
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(canonical_json(record))
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)

    def create_exclusive(self, path: Path, record: Mapping[str, Any]) -> bool:
        """Create ``path`` only if it does not exist. Returns False when someone else won.

        The atomic primitive behind work claims. ``O_EXCL`` is the whole mechanism; do not
        replace it with an ``exists()`` check.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        except FileExistsError:
            return False
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(canonical_json(record))
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        return True

    # ---------------------------------------------------------------------------------- reads

    def read(self, path: Path) -> dict[str, Any] | None:
        """Read one record. ``None`` means absent; a corrupt file RAISES."""
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        try:
            obj = json.loads(text)
        except json.JSONDecodeError as exc:
            raise StoreCorrupt(f"{path}: not valid JSON ({exc})") from exc
        if not isinstance(obj, dict):
            raise StoreCorrupt(
                f"{path}: record is {type(obj).__name__}, expected object"
            )
        return obj

    def iter_records(self, kind: str) -> Iterator[tuple[str, dict[str, Any]]]:
        """Yield ``(name, record)`` for every record of ``kind``, sorted for determinism."""
        directory = self.dir_for(kind)
        if not directory.is_dir():
            return
        for child in sorted(directory.glob("*.json")):
            record = self.read(child)
            if record is not None:
                yield child.stem, record

    def records(self, kind: str) -> list[dict[str, Any]]:
        return [rec for _, rec in self.iter_records(kind)]

    def delete(self, path: Path) -> bool:
        try:
            path.unlink()
        except FileNotFoundError:
            return False
        return True

    # -------------------------------------------------------------------------------- journal

    def journal(self, event: str, **fields: Any) -> dict[str, Any]:
        """Append one audit line. Append-only: nothing in this package rewrites the journal."""
        entry = {"at": self.clock(), "event": event, **fields}
        self.root.mkdir(parents=True, exist_ok=True)
        with open(self.journal_path, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(canonical_json(entry))
            fh.write("\n")
        return entry

    def journal_entries(self) -> list[dict[str, Any]]:
        if not self.journal_path.exists():
            return []
        out: list[dict[str, Any]] = []
        for lineno, line in enumerate(
            self.journal_path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not line.strip():
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise StoreCorrupt(
                    f"{self.journal_path}:{lineno}: not valid JSON ({exc})"
                ) from exc
        return out


_FORBIDDEN = set('<>:"/\\|?*')


def safe_record_name(name: str) -> str:
    """Fold an identifier into a filename that is legal on NTFS and POSIX alike.

    Reversibility is not required (the record carries its own id); collision-freedom is. Any
    forbidden or control character becomes ``_`` and a short digest of the ORIGINAL string is
    appended whenever folding changed anything, so ``a/b`` and ``a_b`` cannot collide.
    """
    if not name:
        raise StoreCorrupt("record name is empty")
    folded = "".join("_" if (c in _FORBIDDEN or ord(c) < 0x20) else c for c in name)
    folded = folded.rstrip(" .") or "_"
    if folded != name or len(folded) > 120:
        import hashlib

        digest = hashlib.sha256(name.encode("utf-8")).hexdigest()[:12]
        folded = f"{folded[:100]}~{digest}"
    return folded
