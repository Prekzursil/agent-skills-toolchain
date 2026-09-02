"""Write-once unit receipts with a version guard and an append-only event log.

Catalog names tools/lib/handled-ledger.mjs (absent on this worktree). This
module is the live SUT for TST-0159: a false-negative timeout retry must not
overwrite a terminal SUCCESS receipt; it must record DUPLICATE-COMPLETION.
A genuinely FAILED receipt may be replaced when the caller presents the
current version (CAS). last_write_wins=True is the known-broken mutant.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

TERMINAL_SUCCESS = frozenset({"SUCCESS", "COMPLETED", "PASS"})
GENUINE_FAILED = frozenset({"FAILED", "ERROR", "INCOMPLETE"})
DUPLICATE_COMPLETION = "DUPLICATE-COMPLETION"
RECEIPT_WRITTEN = "RECEIPT-WRITTEN"
VERSION_MISMATCH = "VERSION-MISMATCH"


def sha256_path(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def sha256_obj(obj: dict[str, Any]) -> str:
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _canonical(obj: dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=True) + "\n"


def _atomic_write(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    text = _canonical(obj)
    with tmp.open("w", encoding="utf-8") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def write_once_holds(
    *,
    hash_before: str | None,
    hash_after: str | None,
    events: list[dict[str, Any]],
    unit_id: str,
) -> bool:
    """Independent predicate: hashes unchanged AND a named suppressed write."""
    if not hash_before or hash_before != hash_after:
        return False
    for ev in events:
        if ev.get("kind") != DUPLICATE_COMPLETION:
            continue
        if ev.get("unit_id") != unit_id:
            continue
        suppressed = ev.get("suppressed_write")
        if isinstance(suppressed, dict) and suppressed:
            if ev.get("existing_hash") == hash_before:
                return True
    return False


class WriteOnceReceiptStore:
    """Durable receipts/ plus events.jsonl. Replay always reloads from disk."""

    def __init__(self, root: Path, *, last_write_wins: bool = False) -> None:
        self.root = Path(root)
        self.receipts_dir = self.root / "receipts"
        self.event_log = self.root / "events.jsonl"
        self.last_write_wins = bool(last_write_wins)
        self.receipts_dir.mkdir(parents=True, exist_ok=True)
        if not self.event_log.exists():
            self.event_log.write_text("", encoding="utf-8")
        self._seq = 0

    def receipt_path(self, unit_id: str) -> Path:
        safe = unit_id.replace("/", "_").replace("\\", "_")
        return self.receipts_dir / f"{safe}.json"

    def file_hash(self, unit_id: str) -> str | None:
        path = self.receipt_path(unit_id)
        if not path.is_file() or path.stat().st_size <= 0:
            return None
        return sha256_path(path)

    def load_receipt(self, unit_id: str) -> dict[str, Any] | None:
        path = self.receipt_path(unit_id)
        if not path.is_file() or path.stat().st_size <= 0:
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def load_events(self) -> list[dict[str, Any]]:
        text = self.event_log.read_text(encoding="utf-8")
        out: list[dict[str, Any]] = []
        for line in text.splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
        return out

    def _append_event(self, event: dict[str, Any]) -> dict[str, Any]:
        self._seq += 1
        stored = dict(event)
        stored["seq"] = self._seq
        line = json.dumps(stored, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        with self.event_log.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        return stored

    def _is_terminal_success(self, rec: dict[str, Any]) -> bool:
        return str(rec.get("state") or "").upper() in TERMINAL_SUCCESS

    def _is_genuine_failed(self, rec: dict[str, Any]) -> bool:
        return str(rec.get("state") or "").upper() in GENUINE_FAILED

    def write(
        self,
        unit_id: str,
        body: dict[str, Any],
        *,
        expected_version: int | None = None,
        reason: str = "write",
    ) -> dict[str, Any]:
        """Create or replace a receipt, or suppress a duplicate terminal write.

        expected_version is the CAS token: None means "I believe no receipt
        exists" (first write or a false-negative timeout retry). A retry of a
        genuinely FAILED receipt must present the on-disk version.
        """
        existing = self.load_receipt(unit_id)
        hash_before = self.file_hash(unit_id)
        attempted = {
            "state": body.get("state"),
            "result": body.get("result"),
            "attempt": body.get("attempt"),
            "reason": reason,
            "expected_version": expected_version,
            "body_hash": sha256_obj(body),
        }

        if self.last_write_wins:
            return self._publish(
                unit_id,
                body,
                existing=existing,
                hash_before=hash_before,
                attempted=attempted,
                reason=reason,
                force=True,
            )

        if existing is not None and self._is_terminal_success(existing):
            event = self._append_event(
                {
                    "kind": DUPLICATE_COMPLETION,
                    "unit_id": unit_id,
                    "existing_state": existing.get("state"),
                    "existing_version": existing.get("version"),
                    "existing_hash": hash_before,
                    "suppressed_write": attempted,
                    "note": (
                        "retry after false-negative timeout refused: terminal "
                        "receipt is write-once"
                    ),
                }
            )
            hash_after = self.file_hash(unit_id)
            return {
                "ok": True,
                "action": "suppressed",
                "status": DUPLICATE_COMPLETION,
                "unit_id": unit_id,
                "hash_before": hash_before,
                "hash_after": hash_after,
                "version": existing.get("version"),
                "event": event,
            }

        if existing is None:
            if expected_version not in (None, 0):
                event = self._append_event(
                    {
                        "kind": VERSION_MISMATCH,
                        "unit_id": unit_id,
                        "existing_version": None,
                        "expected_version": expected_version,
                        "suppressed_write": attempted,
                    }
                )
                return {
                    "ok": False,
                    "action": "refused",
                    "status": VERSION_MISMATCH,
                    "unit_id": unit_id,
                    "hash_before": hash_before,
                    "hash_after": hash_before,
                    "version": None,
                    "event": event,
                }
            return self._publish(
                unit_id,
                body,
                existing=None,
                hash_before=hash_before,
                attempted=attempted,
                reason=reason,
                force=False,
            )

        if self._is_genuine_failed(existing):
            current = int(existing.get("version") or 0)
            if expected_version != current:
                event = self._append_event(
                    {
                        "kind": VERSION_MISMATCH,
                        "unit_id": unit_id,
                        "existing_version": current,
                        "expected_version": expected_version,
                        "existing_hash": hash_before,
                        "suppressed_write": attempted,
                    }
                )
                hash_after = self.file_hash(unit_id)
                return {
                    "ok": False,
                    "action": "refused",
                    "status": VERSION_MISMATCH,
                    "unit_id": unit_id,
                    "hash_before": hash_before,
                    "hash_after": hash_after,
                    "version": current,
                    "event": event,
                }
            return self._publish(
                unit_id,
                body,
                existing=existing,
                hash_before=hash_before,
                attempted=attempted,
                reason=reason,
                force=False,
            )

        event = self._append_event(
            {
                "kind": "UNEXPECTED-STATE",
                "unit_id": unit_id,
                "existing_state": existing.get("state"),
                "suppressed_write": attempted,
            }
        )
        return {
            "ok": False,
            "action": "refused",
            "status": "UNEXPECTED-STATE",
            "unit_id": unit_id,
            "hash_before": hash_before,
            "hash_after": self.file_hash(unit_id),
            "version": existing.get("version"),
            "event": event,
        }

    def _publish(
        self,
        unit_id: str,
        body: dict[str, Any],
        *,
        existing: dict[str, Any] | None,
        hash_before: str | None,
        attempted: dict[str, Any],
        reason: str,
        force: bool,
    ) -> dict[str, Any]:
        version = 1 if existing is None else int(existing.get("version") or 0) + 1
        stored = {
            "unit_id": unit_id,
            "state": str(body.get("state") or ""),
            "result": body.get("result"),
            "attempt": body.get("attempt"),
            "version": version,
            "previous_state": None if existing is None else existing.get("state"),
            "previous_version": None if existing is None else existing.get("version"),
            "previous_hash": hash_before,
            "reason": reason,
            "last_write_wins": bool(self.last_write_wins and force),
        }
        path = self.receipt_path(unit_id)
        _atomic_write(path, stored)
        hash_after = sha256_path(path)
        event = self._append_event(
            {
                "kind": RECEIPT_WRITTEN,
                "unit_id": unit_id,
                "version": version,
                "state": stored["state"],
                "hash": hash_after,
                "replaced": existing is not None,
                "previous_state": stored["previous_state"],
                "previous_hash": hash_before,
                "attempted": attempted,
                "last_write_wins": bool(self.last_write_wins and force),
                "reason": reason,
            }
        )
        return {
            "ok": True,
            "action": "replaced" if existing is not None else "created",
            "status": RECEIPT_WRITTEN,
            "unit_id": unit_id,
            "hash_before": hash_before,
            "hash_after": hash_after,
            "version": version,
            "event": event,
        }
