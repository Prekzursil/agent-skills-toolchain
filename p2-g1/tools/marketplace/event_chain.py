"""Append-only hash-chained registry event log (IMP-0072)."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

GENESIS_HASH = "0" * 64
ACTIONS = {"publish", "yank", "deprecate", "revoke", "moderate"}


class AppendOnlyViolation(Exception):
    """Writer refused a non-append mutation."""


def _canonical(rec: dict[str, Any]) -> str:
    body = {k: rec[k] for k in rec if k != "record_hash"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def record_hash(rec: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(rec).encode("utf-8")).hexdigest()


def _read_rows(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows),
        encoding="utf-8",
        newline="\n",
    )


@dataclass
class VerifyResult:
    ok: bool
    record_count: int
    first_bad_seq: int | None = None
    named_record: dict[str, Any] | None = None
    expected_hash: str | None = None
    observed_hash: str | None = None
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "record_count": self.record_count,
            "first_bad_seq": self.first_bad_seq,
            "named_record": self.named_record,
            "expected_hash": self.expected_hash,
            "observed_hash": self.observed_hash,
            "notes": list(self.notes),
        }


def _make_record(
    *,
    seq: int,
    action: str,
    actor: str,
    package_id: str,
    version: str,
    ts: str,
    payload: dict[str, Any],
    prev_hash: str,
) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "seq": seq,
        "action": action,
        "actor": actor,
        "package_id": package_id,
        "version": version,
        "ts": ts,
        "payload": payload,
        "prev_hash": prev_hash,
    }
    rec["record_hash"] = record_hash(rec)
    return rec


def build_demo_log(path: Path) -> list[dict[str, Any]]:
    path = Path(path)
    demo = [
        ("publish", "publisher:alice", "demo-pkg", "1.0.0", "2026-08-24T12:00:00Z", {"digest": "a" * 64}),
        ("yank", "publisher:alice", "demo-pkg", "1.0.0", "2026-08-24T13:00:00Z", {"reason": "broken"}),
        ("deprecate", "publisher:alice", "demo-pkg", "1.0.0", "2026-08-24T14:00:00Z", {"message": "use 1.1"}),
        ("revoke", "moderator:bob", "demo-pkg", "1.0.0", "2026-08-24T15:00:00Z", {"reason": "advisory"}),
        ("moderate", "moderator:bob", "demo-pkg", "1.0.0", "2026-08-24T16:00:00Z", {"flag": "review"}),
    ]
    rows: list[dict[str, Any]] = []
    prev = GENESIS_HASH
    for i, (action, actor, pkg, ver, ts, payload) in enumerate(demo, 1):
        rec = _make_record(
            seq=i,
            action=action,
            actor=actor,
            package_id=pkg,
            version=ver,
            ts=ts,
            payload=payload,
            prev_hash=prev,
        )
        rows.append(rec)
        prev = rec["record_hash"]
    _write_rows(path, rows)
    return rows


class EventLog:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.is_file():
            self.path.write_text("", encoding="utf-8")

    def _rows(self) -> list[dict[str, Any]]:
        return _read_rows(self.path)

    def replace(self, seq: int, payload: dict[str, Any] | None = None, **_kw: Any) -> None:
        raise AppendOnlyViolation(f"replace seq={seq} refused")

    def overwrite(self, seq: int, **_kw: Any) -> None:
        raise AppendOnlyViolation(f"overwrite seq={seq} refused")

    def truncate(self, **_kw: Any) -> None:
        raise AppendOnlyViolation("truncate refused")

    def rewrite_prefix(self, **_kw: Any) -> None:
        raise AppendOnlyViolation("rewrite_prefix refused")

    def append(
        self,
        action: str,
        actor: str,
        package_id: str,
        version: str,
        ts: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        rows = self._rows()
        prev = rows[-1]["record_hash"] if rows else GENESIS_HASH
        rec = _make_record(
            seq=len(rows) + 1,
            action=action,
            actor=actor,
            package_id=package_id,
            version=version,
            ts=ts,
            payload=payload,
            prev_hash=prev,
        )
        with self.path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
        return rec


def _set_path(rec: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    cur: Any = rec
    for key in path[:-1]:
        cur = cur[key]
    cur[path[-1]] = value


def tamper_field(path: Path, seq: int, field_path: tuple[str, ...], value: Any) -> dict[str, Any]:
    path = Path(path)
    rows = _read_rows(path)
    hit = None
    for rec in rows:
        if int(rec.get("seq") or 0) == seq:
            _set_path(rec, field_path, value)
            # leave record_hash stale so verification names this seq
            hit = rec
            break
    if hit is None:
        raise KeyError(f"seq {seq} missing")
    _write_rows(path, rows)
    return hit


def rechain_after_edit(
    path: Path, seq: int, field_path: tuple[str, ...], value: Any
) -> list[dict[str, Any]]:
    path = Path(path)
    rows = _read_rows(path)
    for rec in rows:
        if int(rec.get("seq") or 0) == seq:
            _set_path(rec, field_path, value)
    prev = GENESIS_HASH
    for rec in rows:
        rec["prev_hash"] = prev
        rec["record_hash"] = record_hash(rec)
        prev = rec["record_hash"]
    _write_rows(path, rows)
    # Honest residual: a fully re-chained rewrite verifies clean.
    # Detection of silent retroactive edits needs an external anchor.
    return rows


def verify_log(path: Path) -> VerifyResult:
    rows = _read_rows(Path(path))
    prev = GENESIS_HASH
    for rec in rows:
        seq = int(rec.get("seq") or 0)
        want_prev = prev
        got_prev = str(rec.get("prev_hash") or "")
        expected = record_hash(rec)
        observed = str(rec.get("record_hash") or "")
        if got_prev != want_prev or observed != expected:
            return VerifyResult(
                ok=False,
                record_count=len(rows),
                first_bad_seq=seq,
                named_record=dict(rec),
                expected_hash=expected if got_prev == want_prev else want_prev,
                observed_hash=observed if got_prev == want_prev else got_prev,
            )
        prev = observed
    notes: list[str] = []
    for rec in rows:
        if rec.get("action") == "deprecate":
            msg = (rec.get("payload") or {}).get("message")
            if msg and msg != "use 1.1":
                notes.append("unanchored-chain-limit")
    return VerifyResult(ok=True, record_count=len(rows), notes=notes)
