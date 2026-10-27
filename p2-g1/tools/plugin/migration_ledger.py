"""Append-only hashed JSONL migration ledger (IMP-0049)."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from hash_census import census_diff, hash_census


class AppendOnlyError(RuntimeError):
    pass


class LedgerIntegrityError(RuntimeError):
    pass


def compute_record_hash(rec: dict[str, Any]) -> str:
    body = {k: rec.get(k) for k in sorted(rec) if k != "record_hash"}
    blob = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _as_bytes(data: Any) -> bytes:
    if data is None:
        return b""
    if isinstance(data, bytes):
        return data
    if isinstance(data, list):
        return bytes(int(x) & 0xFF for x in data)
    if isinstance(data, str):
        return data.encode("utf-8")
    return bytes(data)


def apply_preimage(root: Path, inverse: dict[str, Any] | None) -> None:
    root = Path(root)
    inverse = inverse or {}
    kind = inverse.get("kind")
    entries = inverse.get("entries") or []
    if kind == "delete-files":
        for rel in inverse.get("paths") or []:
            path = root / str(rel)
            if path.is_file():
                path.unlink()
        return
    if kind == "rename-dir":
        src = root / str(inverse.get("to") or "")
        dest = root / str(inverse.get("from") or "")
        dest.mkdir(parents=True, exist_ok=True)
        if src.exists():
            for p in list(src.rglob("*")):
                if p.is_file():
                    rel = p.relative_to(src).as_posix()
                    target = dest / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(p.read_bytes())
                    p.unlink()
            try:
                import shutil as _shutil

                _shutil.rmtree(src, ignore_errors=True)
            except OSError:
                pass
        for entry in entries:
            path = root / str(entry.get("path") or "")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(_as_bytes(entry.get("bytes")))
        return
    for entry in entries:
        rel = str(entry.get("path") or "")
        if not rel:
            continue
        path = root / rel
        data = entry.get("bytes")
        if data is None:
            if path.is_file():
                path.unlink()
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_as_bytes(data))


class MigrationLedger:
    def __init__(self, path: Path, machine: str = "host"):
        self.path = Path(path)
        self.machine = machine
        self.records: list[dict[str, Any]] = []
        if self.path.is_file():
            self.records = self._load_rows(self.path)

    @classmethod
    def load(cls, path: Path, machine: str = "host") -> "MigrationLedger":
        obj = cls(path, machine=machine)
        obj.records = cls._load_rows(Path(path), verify=True)
        return obj

    @staticmethod
    def _load_rows(path: Path, verify: bool = False) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        prev = ""
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if verify:
                if rec.get("prev_hash") != prev:
                    raise LedgerIntegrityError("prev_hash chain break")
                expect = compute_record_hash(rec)
                if rec.get("record_hash") != expect:
                    raise LedgerIntegrityError("record_hash mismatch")
                prev = rec.get("record_hash") or ""
            rows.append(rec)
        return rows

    def _append(self, rec: dict[str, Any]) -> dict[str, Any]:
        rec = _sanitize(rec)
        prev = self.records[-1]["record_hash"] if self.records else ""
        rec["prev_hash"] = prev
        rec["record_hash"] = compute_record_hash(rec)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
        self.records.append(rec)
        return rec

    def replace_record(self, seq: int, rec: dict[str, Any]) -> None:
        raise AppendOnlyError("in-place replace is forbidden")

    def rewrite_all(self, rows: list) -> None:
        raise AppendOnlyError("rewrite_all is forbidden")

    def truncate(self) -> None:
        raise AppendOnlyError("truncate is forbidden")

    def inverses_for_run(self, run_id: str) -> list[dict[str, Any]]:
        rows = [r for r in self.records if r.get("run_id") == run_id and r.get("inverse")]
        by_step: dict[str, dict[str, Any]] = {}
        for r in rows:
            sid = str(r.get("step_id") or "")
            if r.get("status") == "applied" or sid not in by_step:
                by_step[sid] = r
        return list(by_step.values())


def _json_default(obj: Any) -> Any:
    if isinstance(obj, bytes):
        return list(obj)
    raise TypeError(type(obj).__name__)


def _sanitize(obj: Any) -> Any:
    if isinstance(obj, bytes):
        return list(obj)
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    return obj


def run_recorded_steps(
    root: Path,
    ledger: MigrationLedger,
    steps: Iterable[tuple[str, Callable[[Path], dict[str, Any]]]],
    *,
    from_version: str,
    to_version: str,
    complete: bool = True,
) -> dict[str, Any]:
    root = Path(root)
    pre = hash_census(root)
    run_id = uuid.uuid4().hex
    step_ids: list[str] = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    seq = len(ledger.records) + 1
    items = list(steps)
    for i, (step_id, fn) in enumerate(items):
        started = {
            "seq": seq,
            "record_id": uuid.uuid4().hex,
            "recorded_at": now,
            "machine_id": ledger.machine,
            "run_id": run_id,
            "from_version": from_version,
            "to_version": to_version,
            "step_id": step_id,
            "status": "started",
            "touched_paths": [],
            "inverse": None,
        }
        inverse = fn(root)
        started["inverse"] = inverse
        started["touched_paths"] = list(inverse.get("touched") or [])
        ledger._append(started)
        seq += 1
        if not complete and i == len(items) - 1:
            step_ids.append(step_id)
            break
        applied = dict(started)
        applied["seq"] = seq
        applied["record_id"] = uuid.uuid4().hex
        applied["status"] = "applied"
        applied["inverse"] = inverse
        ledger._append(applied)
        seq += 1
        step_ids.append(step_id)
    post = hash_census(root)
    return {
        "run_id": run_id,
        "step_ids": step_ids,
        "pre_census": pre,
        "post_census": post,
    }


def replay_and_compare(
    root: Path, ledger: MigrationLedger, run_id: str, pre_census: dict[str, str]
) -> dict[str, Any]:
    inverses = [r for r in ledger.records if r.get("run_id") == run_id and r.get("status") in {"applied", "started"} and r.get("inverse")]
    # apply latest inverse per step in reverse applied order
    seen: set[str] = set()
    ordered = []
    for rec in reversed(inverses):
        sid = rec.get("step_id")
        if sid in seen:
            continue
        seen.add(sid)
        ordered.append(rec)
    for rec in ordered:
        apply_preimage(root, rec.get("inverse"))
    live = hash_census(root)
    diff = census_diff(pre_census, live)
    return {"equal": diff["equal"], "diff": diff, "live": live}
