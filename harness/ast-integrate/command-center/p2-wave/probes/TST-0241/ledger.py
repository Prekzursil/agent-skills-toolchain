"""Instrumented ledgers: append-only JSONL vs a full-file rewrite mutant.

Write-size is the detector. Append returns O(1) bytes (one record).
Rewrite returns O(n) bytes (the whole file), so cumulative bytes to
build n records are quadratic.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class EmptyInputError(ValueError):
    """Cardinality is zero; the harness must not emit a time."""


class AppendLedger:
    """Open-append one canonical JSON line. Mirrors CandidateRegistry._append
    and close.append_event (mode 'a', one record, no rewrite)."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self.path.unlink()
        self.path.touch()
        self.records = 0

    def write(self, record: dict[str, Any]) -> int:
        line = (
            json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
        )
        data = line.encode("utf-8")
        with self.path.open("ab") as handle:
            handle.write(data)
            handle.flush()
        self.records += 1
        return len(data)

    def write_all(self, records: list[dict[str, Any]]) -> list[int]:
        if not records:
            raise EmptyInputError("append ledger: n_inputs=0; FAIL rather than time")
        return [self.write(r) for r in records]

    write_all = write_all


class RewriteLedger:
    """Deliberate O(n) mutant: every write rewrites the entire file.

    bytes_this_write == current file size after the write, which grows
    linearly with record count; the sum over 1..n is quadratic.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self.path.unlink()
        self.path.write_bytes(b"")
        self.records = 0
        self._blob = b""

    def write(self, record: dict[str, Any], *, persist: bool = True) -> int:
        line = (
            json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
        ).encode("utf-8")
        self._blob = self._blob + line
        self.records += 1
        if persist:
            self.path.write_bytes(self._blob)
        return len(self._blob)

    def write_all(self, records: list[dict[str, Any]]) -> list[int]:
        if not records:
            raise EmptyInputError("rewrite ledger: n_inputs=0; FAIL rather than time")
        return [self.write(r) for r in records]
