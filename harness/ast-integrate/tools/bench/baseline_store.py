"""Content-addressed, write-once benchmark baseline store (TST-0229).

A baseline is a named *case* that points at an immutable blob addressed by the
sha256 of its bytes.  Layout under ``root``::

    blobs/<sha256>   write-once payload bytes (never rewritten, never deleted)
    pointers.json    {"<case_id>": "<sha256>"}  sorted; one atomic replace per change
    audit.jsonl      one JSON object per explicit re-baseline (who / when / why)

Rules enforced in code, not by convention:

* ``write(case, payload)`` for a case that already points at different bytes
  raises ``SilentOverwriteRefused`` before touching the disk, so the store
  digest, the pointer and the served bytes are unchanged.
* Changing a baseline requires ``Rebaseline(who, when, why)`` with every field
  non-blank and ``when`` a real ISO-8601 timestamp (``IncompleteRebaseline``
  otherwise).  The pointer is retargeted, an audit record naming old and new
  digests is appended, and the old blob is retained.
* ``get`` re-hashes the blob and raises ``BlobIntegrityError`` when the bytes
  no longer match their address, so an in-place rewrite can never be served
  as the original digest.
* ``compare`` is the read-only path a benchmark run uses: it never writes.
* Every file mutation is temp-file + fsync + ``os.replace``; under ENOSPC the
  ``OSError`` propagates loudly and existing pointers stay intact (ADV-0126).
* ``store_digest`` is a deterministic hash of the pointer map and the audit
  log; it moves only when a pointer or the audit history changes.

``NaiveMutableStore`` is the deliberately broken control TST-0229 uses to prove
the detector is alive: it overwrites in place and never refuses.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

POINTERS_SCHEMA_NOTE = "flat map case_id -> sha256 hex"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_CASE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@+-]{0,199}$")

__all__ = [
    "BaselineStore",
    "BaselineStoreError",
    "BlobIntegrityError",
    "IncompleteRebaseline",
    "NaiveMutableStore",
    "Rebaseline",
    "SilentOverwriteRefused",
    "UnknownCase",
    "sha256_bytes",
]


# --------------------------------------------------------------------------- errors


class BaselineStoreError(Exception):
    """Base class for baseline store failures."""


class SilentOverwriteRefused(BaselineStoreError):
    """A case already has a baseline and no ``Rebaseline`` record was supplied."""

    def __init__(self, case_id: str, current_digest: str, attempted_digest: str) -> None:
        self.case_id = case_id
        self.current_digest = current_digest
        self.attempted_digest = attempted_digest
        super().__init__(
            f"{case_id!r} already points at {current_digest[:12]}...; refusing silent "
            f"overwrite with {attempted_digest[:12]}... (supply Rebaseline(who, when, why))"
        )


class IncompleteRebaseline(BaselineStoreError, ValueError):
    """A ``Rebaseline`` record is missing who, when or why."""


class BlobIntegrityError(BaselineStoreError):
    """A blob's bytes no longer hash to the address it is stored under."""


class UnknownCase(BaselineStoreError, KeyError):
    """No baseline has been recorded for the case."""


# --------------------------------------------------------------------------- helpers


def sha256_bytes(data: bytes) -> str:
    """Hex sha256 of exactly ``data`` (no normalisation: addresses must be exact)."""
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise TypeError(f"payload must be bytes, got {type(data).__name__}")
    return hashlib.sha256(bytes(data)).hexdigest()


def _check_case_id(case_id: str) -> str:
    if not isinstance(case_id, str) or not _CASE_RE.match(case_id):
        raise ValueError(
            f"case_id must match {_CASE_RE.pattern} (path-safe, <=200 chars): {case_id!r}"
        )
    return case_id


def _atomic_write(path: Path, data: bytes) -> None:
    """Write ``data`` to ``path`` via temp file + fsync + ``os.replace``, or raise untouched."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def _parse_when(when: str) -> None:
    value = when.strip()
    if value.endswith(("Z", "z")):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed.replace(tzinfo=timezone.utc)


# --------------------------------------------------------------------------- re-baseline


@dataclass(frozen=True)
class Rebaseline:
    """Who changed a baseline, when (ISO-8601), and why - all mandatory."""

    who: str
    when: str
    why: str

    def validate(self) -> None:
        """Raise ``IncompleteRebaseline`` unless every field carries real content."""
        missing = [
            name
            for name in ("who", "when", "why")
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip()
        ]
        if missing:
            raise IncompleteRebaseline(
                f"re-baseline record is incomplete: blank {', '.join(missing)}"
            )
        try:
            _parse_when(self.when)
        except ValueError as exc:
            raise IncompleteRebaseline(
                f"re-baseline 'when' must be an ISO-8601 timestamp: {self.when!r}"
            ) from exc

    def as_record(self, case_id: str, old_digest: str | None, new_digest: str) -> dict[str, Any]:
        """The audit-log row for applying this re-baseline to ``case_id``."""
        return {
            "kind": "rebaseline",
            "case_id": case_id,
            "who": self.who.strip(),
            "when": self.when.strip(),
            "why": self.why.strip(),
            "old_digest": old_digest,
            "new_digest": new_digest,
        }


# --------------------------------------------------------------------------- production store


class BaselineStore:
    """Write-once, content-addressed baselines with an explicit re-baseline audit log."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.blobs = self.root / "blobs"
        self.pointers_path = self.root / "pointers.json"
        self.audit_path = self.root / "audit.jsonl"

    def __repr__(self) -> str:
        return f"BaselineStore({str(self.root)!r})"

    # -- pointers -------------------------------------------------------------

    def _load_pointers(self) -> dict[str, str]:
        if not self.pointers_path.is_file():
            return {}
        raw = self.pointers_path.read_bytes()
        try:
            doc = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BaselineStoreError(f"{self.pointers_path}: corrupt pointer map ({exc})") from exc
        if not isinstance(doc, dict):
            raise BaselineStoreError(f"{self.pointers_path}: pointer map must be an object")
        for case_id, digest in doc.items():
            if not isinstance(digest, str) or not _HEX64.match(digest):
                raise BaselineStoreError(
                    f"{self.pointers_path}: pointer for {case_id!r} is not a sha256 hex digest"
                )
            _check_case_id(case_id)
        return dict(doc)

    def _save_pointers(self, pointers: dict[str, str]) -> None:
        ordered = {case_id: pointers[case_id] for case_id in sorted(pointers)}
        _atomic_write(self.pointers_path, (json.dumps(ordered, indent=1) + "\n").encode("utf-8"))

    def pointers(self) -> dict[str, str]:
        """Copy of the case -> digest map."""
        return self._load_pointers()

    def cases(self) -> list[str]:
        """Sorted case ids with a recorded baseline."""
        return sorted(self._load_pointers())

    def has(self, case_id: str) -> bool:
        """Whether ``case_id`` has a baseline."""
        return _check_case_id(case_id) in self._load_pointers()

    def digest_of(self, case_id: str) -> str:
        """The sha256 address ``case_id`` currently points at."""
        pointers = self._load_pointers()
        try:
            return pointers[_check_case_id(case_id)]
        except KeyError:
            raise UnknownCase(case_id) from None

    # -- blobs ----------------------------------------------------------------

    def _read_blob(self, digest: str) -> bytes:
        path = self.blobs / digest
        if not path.is_file():
            raise BlobIntegrityError(f"blob {digest} is missing from {self.blobs}")
        data = path.read_bytes()
        actual = sha256_bytes(data)
        if actual != digest:
            raise BlobIntegrityError(
                f"blob {digest[:12]}... has been rewritten in place (bytes hash to {actual[:12]}...)"
            )
        return data

    def _write_blob(self, digest: str, payload: bytes) -> None:
        path = self.blobs / digest
        if path.is_file():
            self._read_blob(digest)  # existing address must still hold its bytes
            return
        _atomic_write(path, payload)

    # -- audit ----------------------------------------------------------------

    def audit_records(self) -> list[dict[str, Any]]:
        """Every re-baseline record, oldest first; a torn or foreign line is an error."""
        if not self.audit_path.is_file():
            return []
        records: list[dict[str, Any]] = []
        for lineno, line in enumerate(self.audit_path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise BaselineStoreError(f"{self.audit_path}:{lineno}: corrupt audit line ({exc})") from exc
            if not isinstance(record, dict) or record.get("kind") != "rebaseline":
                raise BaselineStoreError(f"{self.audit_path}:{lineno}: not a re-baseline record")
            records.append(record)
        return records

    def _append_audit(self, record: dict[str, Any]) -> None:
        existing = self.audit_path.read_bytes() if self.audit_path.is_file() else b""
        if existing and not existing.endswith(b"\n"):
            existing += b"\n"
        line = json.dumps(record, sort_keys=True) + "\n"
        _atomic_write(self.audit_path, existing + line.encode("utf-8"))

    # -- public API -------------------------------------------------------------

    def write(self, case_id: str, payload: bytes, rebaseline: Rebaseline | None = None) -> str:
        """Record ``payload`` as the baseline for ``case_id``; return its sha256 address.

        First write for a case: stores the blob and adds the pointer.  Writing
        the identical bytes again is a no-op that returns the same digest.
        Different bytes for an existing case raise ``SilentOverwriteRefused``
        unless a complete ``Rebaseline`` is given, in which case the blob is
        stored, the audit record is appended and the pointer is retargeted
        (old blob retained).  Nothing is written before validation passes.
        """
        _check_case_id(case_id)
        digest = sha256_bytes(payload)
        pointers = self._load_pointers()
        current = pointers.get(case_id)
        if rebaseline is not None and not isinstance(rebaseline, Rebaseline):
            raise TypeError("rebaseline must be a Rebaseline record")
        if current is not None and current != digest and rebaseline is None:
            raise SilentOverwriteRefused(case_id, current, digest)
        if rebaseline is not None:
            rebaseline.validate()
        self.blobs.mkdir(parents=True, exist_ok=True)
        self._write_blob(digest, bytes(payload))
        if rebaseline is not None:
            self._append_audit(rebaseline.as_record(case_id, current, digest))
        if current != digest:
            pointers[case_id] = digest
            self._save_pointers(pointers)
        return digest

    def get(self, case_id: str) -> bytes:
        """The baseline bytes for ``case_id``, verified against their address."""
        return self._read_blob(self.digest_of(case_id))

    def compare(self, case_id: str, payload: bytes) -> dict[str, Any]:
        """Read-only comparison of ``payload`` against the stored baseline.

        Never writes.  Returns ``match``, both digests and whether a baseline
        exists at all, so a benchmark run can report without mutating the store.
        """
        _check_case_id(case_id)
        observed = sha256_bytes(payload)
        pointers = self._load_pointers()
        expected = pointers.get(case_id)
        if expected is not None:
            self._read_blob(expected)  # integrity check on the reference blob
        return {
            "case_id": case_id,
            "baseline_present": expected is not None,
            "expected_digest": expected,
            "observed_digest": observed,
            "match": expected is not None and expected == observed,
        }

    def store_digest(self) -> str:
        """Deterministic sha256 over the pointer map plus the audit history."""
        state = {"pointers": self._load_pointers(), "audit": self.audit_records()}
        return sha256_bytes(json.dumps(state, sort_keys=True, separators=(",", ":")).encode("utf-8"))


# --------------------------------------------------------------------------- mutant control


class NaiveMutableStore:
    """Control mutant: a plain ``cases/<case_id>`` file per case, overwritten in place.

    Exists so TST-0229 can show its detector discriminates: this store accepts
    the very overwrite ``BaselineStore`` refuses, and its digest moves.
    """

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.cases_dir = self.root / "cases"

    def __repr__(self) -> str:
        return f"NaiveMutableStore({str(self.root)!r})"

    def _path(self, case_id: str) -> Path:
        return self.cases_dir / _check_case_id(case_id)

    def write(self, case_id: str, payload: bytes) -> str:
        """Overwrite the case file in place; return the sha256 of what was written."""
        digest = sha256_bytes(payload)
        self.cases_dir.mkdir(parents=True, exist_ok=True)
        self._path(case_id).write_bytes(bytes(payload))
        return digest

    def get(self, case_id: str) -> bytes:
        """Whatever bytes the case file currently holds."""
        path = self._path(case_id)
        if not path.is_file():
            raise UnknownCase(case_id)
        return path.read_bytes()

    def digest_of(self, case_id: str) -> str:
        """sha256 of the current case bytes."""
        return sha256_bytes(self.get(case_id))

    def cases(self) -> list[str]:
        """Sorted case ids present on disk."""
        if not self.cases_dir.is_dir():
            return []
        return sorted(p.name for p in self.cases_dir.iterdir() if p.is_file())

    def store_digest(self) -> str:
        """sha256 over (case_id, sha256(bytes)) pairs - changes whenever any case changes."""
        state = {case_id: self.digest_of(case_id) for case_id in self.cases()}
        return sha256_bytes(json.dumps(state, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def run_comparison(store: BaselineStore, case_id: str, produce: Callable[[], bytes]) -> dict[str, Any]:
    """Benchmark-run helper: produce bytes, compare, prove the store did not move.

    This is the read-only shape ``tools.bench.runner.run_benchmark`` is expected
    to expose for TST-0229: ``comparison`` (from ``compare``), ``wrote_store``
    (always ``False`` here) and ``store_unchanged`` (digest before == after).
    """
    before = store.store_digest()
    payload = produce()
    comparison = store.compare(case_id, payload)
    after = store.store_digest()
    return {
        "case_id": case_id,
        "comparison": comparison,
        "wrote_store": False,
        "store_unchanged": before == after,
        "store_digest": after,
    }
