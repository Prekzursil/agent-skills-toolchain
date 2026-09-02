"""Append-only resumable work-unit ledger with exclusive CLAIM.

Delivery guarantee (honest): at-least-once plus idempotent units (or
skip-if-complete for units classified NON-IDEMPOTENT). Exactly-once is
not claimed: a crash after side effects and before COMPLETE still
re-dispatches.

Exclusive execution is a named mechanism, not a property:
  CLAIM record fields claim_id, fencing_token, lease_until_ns, dedupe_key
  plus fcntl.LOCK_EX around compare-and-append.
Winner of two concurrent claims for the same dedupe_key is the CLAIM
with the lowest seq whose lease has not expired and which has not been
followed by a matching COMPLETE/FAIL/TIMEOUT/SEVERED.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

GENESIS = "0" * 64
CLAIM_TYPES = frozenset({"CLAIM"})
TERMINAL_SUCCESS = frozenset({"SUCCEEDED"})
TERMINAL = frozenset({"SUCCEEDED", "FAILED", "BLOCKED"})
RETRYABLE = frozenset({"TIMEOUT", "SEVERED"})
SUBSTRATES = ("local", "worktree", "cloud")
REDUCER_NAME = "command-center/p2-wave/probes/TST-0003/reducer.py:evaluate"

LIFECYCLE = (
    ("QUEUED", "CLAIM", "CLAIMED"),
    ("CLAIMED", "START", "RUNNING"),
    ("CLAIMED", "lease-expiry", "QUEUED"),
    ("RUNNING", "REDUCE-PASS", "SUCCEEDED"),
    ("RUNNING", "REDUCE-FAIL", "FAILED"),
    ("RUNNING", "TIMEOUT", "TIMEOUT"),
    ("RUNNING", "SEVERED", "SEVERED"),
    ("TIMEOUT", "lease-expiry-or-requeue", "QUEUED"),
    ("SEVERED", "lease-expiry-or-requeue", "QUEUED"),
    ("QUEUED", "deps-unmet", "BARRIER_WAIT"),
    ("BARRIER_WAIT", "BARRIER_RELEASE", "QUEUED"),
    ("SUCCEEDED", "re-claim", "SUCCEEDED"),  # skip-if-complete
)


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def digest(obj: Any) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


def _payload_for_hash(rec: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in rec.items() if k != "sha256"}


class Ledger:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")

    @contextmanager
    def _locked(self) -> Iterator[Any]:
        fh = open(self.path, "a+", encoding="utf-8")
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            yield fh
            fh.flush()
            os.fsync(fh.fileno())
        finally:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
            fh.close()

    def read_all(self) -> list[dict[str, Any]]:
        with self._locked() as fh:
            return self._read_unlocked(fh)

    def _read_unlocked(self, fh) -> list[dict[str, Any]]:
        fh.seek(0)
        rows: list[dict[str, Any]] = []
        for line in fh.read().splitlines():
            if not line.strip():
                continue
            rows.append(json.loads(line))
        return rows

    def verify_chain(self, rows: list[dict[str, Any]] | None = None) -> tuple[bool, str]:
        rows = rows if rows is not None else self.read_all()
        prev = GENESIS
        for i, rec in enumerate(rows, 1):
            if rec.get("seq") != i:
                return False, f"seq-gap expected {i} got {rec.get('seq')}"
            if rec.get("prev_sha256") != prev:
                return False, f"prev-break at seq={i}"
            got = rec.get("sha256")
            want = digest(_payload_for_hash(rec))
            if got != want:
                return False, f"in-place-edit-detected seq={i}"
            prev = got
        return True, "ok"

    def _seal(self, rows: list[dict[str, Any]], rec: dict[str, Any]) -> dict[str, Any]:
        prev = rows[-1]["sha256"] if rows else GENESIS
        sealed = dict(rec)
        sealed["seq"] = len(rows) + 1
        sealed["prev_sha256"] = prev
        sealed["ts_ns"] = int(sealed.get("ts_ns") or time.time_ns())
        sealed["sha256"] = digest(_payload_for_hash(sealed))
        return sealed

    def _append_unlocked(self, fh, rows: list[dict[str, Any]], rec: dict[str, Any]) -> dict[str, Any]:
        sealed = self._seal(rows, rec)
        fh.seek(0, 2)
        fh.write(json.dumps(sealed, sort_keys=True, separators=(",", ":")) + "\n")
        rows.append(sealed)
        return sealed

    def enqueue(
        self,
        unit_id: str,
        *,
        unit_type: str,
        substrate: str,
        idempotence_key: str,
        deps: list[str] | None = None,
    ) -> dict[str, Any]:
        if substrate not in SUBSTRATES:
            raise ValueError(f"unknown-substrate:{substrate}")
        with self._locked() as fh:
            rows = self._read_unlocked(fh)
            for rec in rows:
                if rec.get("type") == "ENQUEUE" and rec.get("unit_id") == unit_id:
                    dup = {
                        "type": "ENQUEUE_DUP",
                        "unit_id": unit_id,
                        "dedupe_key": unit_id,
                        "reason": "idempotent-reenqueue",
                        "result": "SKIP",
                    }
                    return self._append_unlocked(fh, rows, dup)
            rec = {
                "type": "ENQUEUE",
                "unit_id": unit_id,
                "unit_type": unit_type,
                "substrate": substrate,
                "idempotence_key": idempotence_key,
                "dedupe_key": unit_id,
                "deps": list(deps or []),
            }
            return self._append_unlocked(fh, rows, rec)

    def active_claim(
        self, rows: list[dict[str, Any]], unit_id: str, now_ns: int | None = None
    ) -> dict[str, Any] | None:
        now = int(now_ns if now_ns is not None else time.time_ns())
        claims = [
            r
            for r in rows
            if r.get("type") == "CLAIM" and r.get("unit_id") == unit_id
        ]
        claims.sort(key=lambda r: int(r["seq"]))
        for claim in claims:
            if int(claim.get("lease_until_ns") or 0) <= now:
                continue
            token = int(claim["fencing_token"])
            superseded = False
            for later in rows:
                if int(later["seq"]) <= int(claim["seq"]):
                    continue
                if later.get("unit_id") != unit_id:
                    continue
                if later.get("type") in {"COMPLETE", "FAIL", "TIMEOUT", "SEVERED"}:
                    if int(later.get("fencing_token") or -1) == token:
                        superseded = True
                        break
                if later.get("type") == "CLAIM" and int(later.get("fencing_token") or 0) > token:
                    # A newer CLAIM only supersedes if this lease already expired
                    # (we skipped expired above). Live older claim still wins.
                    continue
            if not superseded:
                return claim
        return None

    def replay(self, rows: list[dict[str, Any]], unit_id: str) -> str:
        state = "ABSENT"
        now = time.time_ns()
        for rec in rows:
            if rec.get("unit_id") != unit_id:
                continue
            t = rec.get("type")
            if t == "ENQUEUE":
                state = "QUEUED"
            elif t == "BARRIER_WAIT":
                state = "BARRIER_WAIT"
            elif t == "BARRIER_RELEASE" and state == "BARRIER_WAIT":
                state = "QUEUED"
            elif t == "CLAIM":
                if int(rec.get("lease_until_ns") or 0) > now:
                    state = "CLAIMED"
            elif t == "START":
                state = "RUNNING"
            elif t == "COMPLETE":
                verdict = str(rec.get("reducer_verdict") or "")
                state = "SUCCEEDED" if verdict == "PASS" else "FAILED"
            elif t == "FAIL":
                state = "FAILED"
            elif t == "TIMEOUT":
                state = "TIMEOUT"
            elif t == "SEVERED":
                state = "SEVERED"
        active = self.active_claim(rows, unit_id, now)
        if state in {"TIMEOUT", "SEVERED"} and active is None:
            return "QUEUED"
        if state == "CLAIMED" and active is None:
            return "QUEUED"
        return state

    def claim(
        self,
        unit_id: str,
        dispatcher_id: str,
        substrate: str,
        *,
        lease_ns: int = 30_000_000_000,
    ) -> dict[str, Any]:
        if substrate not in SUBSTRATES:
            raise ValueError(f"unknown-substrate:{substrate}")
        with self._locked() as fh:
            rows = self._read_unlocked(fh)
            state = self.replay(rows, unit_id)
            if state == "SUCCEEDED":
                rec = {
                    "type": "CLAIM_DENIED",
                    "unit_id": unit_id,
                    "dispatcher_id": dispatcher_id,
                    "substrate": substrate,
                    "dedupe_key": unit_id,
                    "result": "SKIP",
                    "reason": "skip-if-complete",
                }
                sealed = self._append_unlocked(fh, rows, rec)
                return {"result": "SKIP", "record": sealed, "state": state}
            if state in {"FAILED", "BLOCKED"}:
                rec = {
                    "type": "CLAIM_DENIED",
                    "unit_id": unit_id,
                    "dispatcher_id": dispatcher_id,
                    "substrate": substrate,
                    "dedupe_key": unit_id,
                    "result": "LOST",
                    "reason": f"terminal:{state}",
                }
                sealed = self._append_unlocked(fh, rows, rec)
                return {"result": "LOST", "record": sealed, "state": state}
            now = time.time_ns()
            active = self.active_claim(rows, unit_id, now)
            if active is not None:
                rec = {
                    "type": "CLAIM_DENIED",
                    "unit_id": unit_id,
                    "dispatcher_id": dispatcher_id,
                    "substrate": substrate,
                    "dedupe_key": unit_id,
                    "winner_seq": active["seq"],
                    "fencing_token": active["fencing_token"],
                    "result": "LOST",
                    "reason": "active-claim-unexpired",
                }
                sealed = self._append_unlocked(fh, rows, rec)
                return {
                    "result": "LOST",
                    "record": sealed,
                    "winner": active,
                    "state": state,
                }
            max_tok = 0
            for r in rows:
                if r.get("unit_id") == unit_id and r.get("type") == "CLAIM":
                    max_tok = max(max_tok, int(r.get("fencing_token") or 0))
            rec = {
                "type": "CLAIM",
                "unit_id": unit_id,
                "dispatcher_id": dispatcher_id,
                "substrate": substrate,
                "dedupe_key": unit_id,
                "claim_id": uuid.uuid4().hex,
                "fencing_token": max_tok + 1,
                "lease_until_ns": now + int(lease_ns),
                "result": "WON",
                "reducer": REDUCER_NAME,
            }
            sealed = self._append_unlocked(fh, rows, rec)
            return {"result": "WON", "record": sealed, "state": "CLAIMED"}

    def start(self, unit_id: str, claim: dict[str, Any]) -> dict[str, Any]:
        with self._locked() as fh:
            rows = self._read_unlocked(fh)
            rec = {
                "type": "START",
                "unit_id": unit_id,
                "claim_id": claim["claim_id"],
                "fencing_token": claim["fencing_token"],
                "dispatcher_id": claim.get("dispatcher_id"),
                "substrate": claim.get("substrate"),
                "dedupe_key": unit_id,
            }
            return self._append_unlocked(fh, rows, rec)

    def complete(
        self,
        unit_id: str,
        claim: dict[str, Any],
        *,
        reducer_verdict: str,
        failing_condition_id: int | None,
        artifact_sha256: str,
    ) -> dict[str, Any]:
        with self._locked() as fh:
            rows = self._read_unlocked(fh)
            active = self.active_claim(rows, unit_id)
            if active is None or active.get("claim_id") != claim.get("claim_id"):
                rec = {
                    "type": "CLAIM_DENIED",
                    "unit_id": unit_id,
                    "claim_id": claim.get("claim_id"),
                    "fencing_token": claim.get("fencing_token"),
                    "result": "LOST",
                    "reason": "stale-fencing-token",
                }
                return self._append_unlocked(fh, rows, rec)
            rec = {
                "type": "COMPLETE",
                "unit_id": unit_id,
                "claim_id": claim["claim_id"],
                "fencing_token": claim["fencing_token"],
                "dedupe_key": unit_id,
                "reducer": REDUCER_NAME,
                "reducer_verdict": reducer_verdict,
                "failing_condition_id": failing_condition_id,
                "artifact_sha256": artifact_sha256,
            }
            return self._append_unlocked(fh, rows, rec)

    def barrier_wait(self, unit_id: str, barrier_id: str) -> dict[str, Any]:
        with self._locked() as fh:
            rows = self._read_unlocked(fh)
            return self._append_unlocked(
                fh,
                rows,
                {
                    "type": "BARRIER_WAIT",
                    "unit_id": unit_id,
                    "barrier_id": barrier_id,
                    "dedupe_key": unit_id,
                },
            )

    def barrier_release(self, barrier_id: str, unit_id: str) -> dict[str, Any]:
        with self._locked() as fh:
            rows = self._read_unlocked(fh)
            return self._append_unlocked(
                fh,
                rows,
                {
                    "type": "BARRIER_RELEASE",
                    "unit_id": unit_id,
                    "barrier_id": barrier_id,
                    "dedupe_key": unit_id,
                },
            )

    def fanout(self, unit_id: str, fanout_id: str, child_unit_ids: list[str]) -> dict[str, Any]:
        with self._locked() as fh:
            rows = self._read_unlocked(fh)
            return self._append_unlocked(
                fh,
                rows,
                {
                    "type": "FANOUT",
                    "unit_id": unit_id,
                    "fanout_id": fanout_id,
                    "child_unit_ids": list(child_unit_ids),
                    "dedupe_key": unit_id,
                },
            )
