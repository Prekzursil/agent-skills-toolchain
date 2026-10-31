"""Content-addressed candidate ledger (IMP-0154)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import hashlib
import json
import uuid


def content_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class LedgerCorruptError(RuntimeError):
    pass


@dataclass
class ImportRecord:
    source_uri: str
    content: bytes
    retrieval_method: str = "read-path"
    adapter_id: str = ""
    retrieved_at: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ImportResult:
    action: str
    candidate_id: str
    content_hash: str
    row_count: int
    event_hash: str = ""
    observation_count_for_key: int = 0


@dataclass
class ChainResult:
    ok: bool
    events: int
    error: str = ""


class CandidateRegistry:
    def __init__(self, ledger: str | Path) -> None:
        self.ledger = Path(ledger)
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        if not self.ledger.is_file():
            self.ledger.write_text("", encoding="utf-8")
        elif self.ledger.read_text(encoding="utf-8").strip():
            self._load()

    def _load(self) -> list[dict[str, Any]]:
        text = self.ledger.read_text(encoding="utf-8")
        rows = []
        prev = None
        for i, line in enumerate(text.splitlines()):
            if not line.strip():
                continue
            ev = json.loads(line)
            body = {k: v for k, v in ev.items() if k != "event_hash"}
            calc = hashlib.sha256(
                (json.dumps(body, sort_keys=True, separators=(",", ":")) + (prev or "")).encode()
            ).hexdigest()
            if ev.get("event_hash") and ev["event_hash"] != calc:
                raise LedgerCorruptError(f"hash mismatch at {i}")
            if ev.get("prev_hash") not in (None, prev):
                raise LedgerCorruptError(f"prev_hash mismatch at {i}")
            prev = ev.get("event_hash") or calc
            rows.append(ev)
        return rows

    def _append(self, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        rows = self._load()
        prev = rows[-1]["event_hash"] if rows else None
        body = {"kind": kind, "prev_hash": prev, **payload}
        digest = hashlib.sha256(
            (json.dumps(body, sort_keys=True, separators=(",", ":")) + (prev or "")).encode()
        ).hexdigest()
        ev = {**body, "event_hash": digest}
        with self.ledger.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(ev, sort_keys=True) + "\n")
        return ev

    def events(self) -> list[dict[str, Any]]:
        return self._load()

    def candidates(self) -> list[dict[str, Any]]:
        return [e for e in self._load() if e.get("kind") == "candidate"]

    def row_count(self) -> int:
        return sum(1 for e in self._load() if e.get("kind") == "candidate")

    def observation_count(self, uri: str | None = None, content_hash: str | None = None) -> int:
        n = 0
        for e in self._load():
            if e.get("kind") != "observation":
                continue
            if uri is not None and e.get("source_uri") != uri:
                continue
            if content_hash is not None and e.get("content_hash") != content_hash:
                continue
            n += 1
        return n

    def export_snapshot(self) -> dict[str, int]:
        return {"row_count": self.row_count(), "observation_count": self.observation_count()}

    def _find(self, uri: str, content_hash: str) -> dict[str, Any] | None:
        for e in self._load():
            if e.get("kind") == "candidate" and e.get("source_uri") == uri and e.get("content_hash") == content_hash:
                return e
        return None

    def import_record(self, rec: ImportRecord) -> ImportResult:
        digest = content_sha256(rec.content)
        existing = self._find(rec.source_uri, digest)
        if existing is None:
            cid = "cand-" + digest[:16]
            ev = self._append(
                "candidate",
                {
                    "candidate_id": cid,
                    "source_uri": rec.source_uri,
                    "content_hash": digest,
                    "retrieval_method": rec.retrieval_method,
                    "adapter_id": rec.adapter_id,
                    "retrieved_at": rec.retrieved_at,
                    "extra": rec.extra,
                },
            )
            self._append(
                "observation",
                {
                    "candidate_id": cid,
                    "source_uri": rec.source_uri,
                    "content_hash": digest,
                    "adapter_id": rec.adapter_id,
                    "retrieved_at": rec.retrieved_at,
                    "extra": rec.extra,
                },
            )
            return ImportResult(
                "insert",
                cid,
                digest,
                self.row_count(),
                ev["event_hash"],
                self.observation_count(rec.source_uri, digest),
            )
        ev = self._append(
            "observation",
            {
                "candidate_id": existing["candidate_id"],
                "source_uri": rec.source_uri,
                "content_hash": digest,
                "adapter_id": rec.adapter_id,
                "retrieved_at": rec.retrieved_at,
                "extra": rec.extra,
            },
        )
        return ImportResult(
            "observe",
            existing["candidate_id"],
            digest,
            self.row_count(),
            ev["event_hash"],
            self.observation_count(rec.source_uri, digest),
        )

    def import_bytes(self, uri: str, content: bytes, **kwargs: Any) -> ImportResult:
        return self.import_record(
            ImportRecord(
                source_uri=uri,
                content=content,
                retrieval_method=str(kwargs.get("retrieval_method") or "read-path"),
                adapter_id=str(kwargs.get("adapter_id") or ""),
                retrieved_at=str(kwargs.get("retrieved_at") or ""),
                extra=dict(kwargs.get("extra") or {}),
            )
        )


def verify_chain(ledger: str | Path) -> ChainResult:
    try:
        rows = CandidateRegistry(ledger)._load()
    except LedgerCorruptError as exc:
        return ChainResult(ok=False, events=0, error=str(exc))
    return ChainResult(ok=True, events=len(rows))
