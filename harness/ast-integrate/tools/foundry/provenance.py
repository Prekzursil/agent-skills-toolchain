"""Provenance records: capture + live re-fetch with hash verification (IMP-0155)."""
from __future__ import annotations

import hashlib
import io
import tarfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

FIELDS = ("source", "ref", "retrieval_time", "hash", "retrieval_method")


class HashMismatch(Exception):
    def __init__(self, expected: str, actual: str, ref: str = "") -> None:
        self.expected = expected
        self.actual = actual
        self.ref = ref
        super().__init__(f"hash mismatch ref={ref} expected={expected} actual={actual}")


@dataclass
class ProvenanceRecord:
    source: str
    ref: str
    retrieval_time: str
    hash: str
    retrieval_method: str

    def as_dict(self) -> dict[str, str]:
        return {
            "source": self.source,
            "ref": self.ref,
            "retrieval_time": self.retrieval_time,
            "hash": self.hash,
            "retrieval_method": self.retrieval_method,
        }


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _repo_path(source: str, repo_root: Path) -> Path:
    rel = source
    if rel.startswith("repo:"):
        rel = rel[5:]
    return (Path(repo_root) / rel).resolve()


def _read_bytes(source: str, ref: str, method: str, repo_root: Path) -> bytes:
    path = _repo_path(source, repo_root)
    if method == "posix-read":
        return (path / ref).read_bytes()
    if method == "tar-member":
        with tarfile.open(path, mode="r") as tf:
            member = tf.extractfile(ref)
            if member is None:
                raise FileNotFoundError(ref)
            return member.read()
    raise ValueError(f"unknown retrieval_method {method}")


def capture(
    *,
    source: str,
    ref: str,
    retrieval_method: str,
    now: datetime | None = None,
    repo_root: Path | None = None,
) -> dict[str, str]:
    root = Path(repo_root) if repo_root is not None else Path.cwd()
    data = _read_bytes(source, ref, retrieval_method, root)
    ts = now or datetime.now(timezone.utc)
    rec = ProvenanceRecord(
        source=source,
        ref=ref,
        retrieval_time=ts.isoformat(),
        hash=_sha(data),
        retrieval_method=retrieval_method,
    )
    return rec.as_dict()


def attach_provenance(obj: dict[str, Any], rec: dict[str, str] | ProvenanceRecord) -> dict[str, Any]:
    payload = rec.as_dict() if isinstance(rec, ProvenanceRecord) else dict(rec)
    out = dict(obj)
    out["provenance"] = payload
    return out


def provenance_only(obj: dict[str, Any]) -> dict[str, str]:
    if set(obj.keys()) >= set(FIELDS) and all(isinstance(obj.get(k), str) for k in FIELDS):
        if "provenance" not in obj:
            return {k: str(obj[k]) for k in FIELDS}
    prov = obj.get("provenance") or obj
    return {k: str(prov[k]) for k in FIELDS}


def record_fields_present(rec: dict[str, Any]) -> bool:
    return set(FIELDS) <= set(rec.keys()) and all(rec.get(k) not in (None, "") for k in FIELDS)


def mutate_ref(rec: dict[str, str], new_ref: str) -> dict[str, str]:
    out = dict(rec)
    out["ref"] = new_ref
    return out


def refetch(rec: dict[str, str], *, verify: bool = True, repo_root: Path | None = None) -> bytes:
    root = Path(repo_root) if repo_root is not None else Path.cwd()
    data = _read_bytes(rec["source"], rec["ref"], rec["retrieval_method"], root)
    actual = _sha(data)
    if verify and actual != rec["hash"]:
        raise HashMismatch(expected=rec["hash"], actual=actual, ref=rec["ref"])
    return data


def refetch_report(rec: dict[str, str], *, repo_root: Path | None = None) -> dict[str, Any]:
    root = Path(repo_root) if repo_root is not None else Path.cwd()
    try:
        data = _read_bytes(rec["source"], rec["ref"], rec["retrieval_method"], root)
        actual = _sha(data)
        ok = actual == rec.get("hash")
        return {
            "ok": ok,
            "actual_hash": actual,
            "expected_hash": rec.get("hash"),
            "bytes": len(data),
            "error": None if ok else "HashMismatch",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "actual_hash": None,
            "expected_hash": rec.get("hash"),
            "bytes": 0,
            "error": f"{type(exc).__name__}: {exc}",
        }
