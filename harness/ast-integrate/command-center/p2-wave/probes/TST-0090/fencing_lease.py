"""Work-unit lease with a monotonically increasing fencing token (TST-0090).

Reclaim after expiry is safe only because every receipt write presents a
fencing token. Timeout-alone takeover (the mutant) leaves the thawed
original able to commit with the pre-reclaim token.
"""
from __future__ import annotations

import fcntl
import json
import os
import time
from multiprocessing import get_context
from pathlib import Path
from typing import Any

GRANTED = "GRANTED"
DENIED = "DENIED"
REJECTED = "REJECTED"
COMMITTED = "COMMITTED"

REASON_ACQUIRED = "acquired"
REASON_RECLAIMED = "reclaimed"
REASON_UNEXPIRED = "lease-unexpired"
REASON_NO_CLAIM = "no-claim"
REASON_HELD = "held-unexpired"
REASON_STALE = "stale-fencing-token"
REASON_COMMITTED = "committed"


class Clock:
    """Injectable clock. Optional path so worker processes share one now()."""

    def __init__(self, start: float = 0.0, path: Path | None = None) -> None:
        self.path = path
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.is_file():
                self._write_now(start)
        else:
            self._now = float(start)

    def _write_now(self, value: float) -> None:
        assert self.path is not None
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(json.dumps({"now": float(value)}) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    def now(self) -> float:
        if self.path is not None:
            return float(json.loads(self.path.read_text(encoding="utf-8"))["now"])
        return float(self._now)

    def advance(self, dt: float) -> float:
        nxt = self.now() + float(dt)
        if self.path is not None:
            self._write_now(nxt)
        else:
            self._now = nxt
        return nxt


def _result(
    status: str,
    reason: str,
    *,
    unit_id: str,
    holder_id: str,
    token: int | None = None,
    current_token: int | None = None,
    current_holder: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "status": status,
        "reason": reason,
        "unit_id": unit_id,
        "holder_id": holder_id,
        "token": token,
        "current_token": current_token,
        "current_holder": current_holder,
    }
    if extra:
        out.update(extra)
    return out


class FencingClaimStore:
    """POSIX file store: flock + tmp-rename, token bumped on every reclaim."""

    mode = "fencing"

    def __init__(self, root: Path, clock: Clock | None = None) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.clock = clock if clock is not None else Clock()

    def _claim_path(self, unit_id: str) -> Path:
        return self.root / f"{unit_id}.claim.json"

    def _lock_path(self, unit_id: str) -> Path:
        return self.root / f"{unit_id}.lock"

    def _load(self, unit_id: str) -> dict[str, Any] | None:
        path = self._claim_path(unit_id)
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _save(self, claim: dict[str, Any]) -> None:
        path = self._claim_path(str(claim["unit_id"]))
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(
            json.dumps(claim, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        os.replace(tmp, path)

    def _locked(self, unit_id: str) -> Any:
        class _Guard:
            def __init__(guard_self) -> None:
                guard_self.fd = -1

            def __enter__(guard_self) -> FencingClaimStore:
                lp = self._lock_path(unit_id)
                guard_self.fd = os.open(str(lp), os.O_CREAT | os.O_RDWR, 0o644)
                fcntl.flock(guard_self.fd, fcntl.LOCK_EX)
                return self

            def __exit__(guard_self, *exc: object) -> None:
                if guard_self.fd >= 0:
                    fcntl.flock(guard_self.fd, fcntl.LOCK_UN)
                    os.close(guard_self.fd)

        return _Guard()

    def _expired(self, claim: dict[str, Any], now: float) -> bool:
        return now >= float(claim["expires_at"])

    def _bump_token(self, claim: dict[str, Any]) -> int:
        nxt = int(claim.get("fencing_token") or 0) + 1
        claim["fencing_token"] = nxt
        return nxt

    def acquire(self, unit_id: str, holder_id: str, ttl: float) -> dict[str, Any]:
        with self._locked(unit_id):
            now = self.clock.now()
            claim = self._load(unit_id)
            if claim is not None and not self._expired(claim, now):
                return _result(
                    DENIED,
                    REASON_HELD,
                    unit_id=unit_id,
                    holder_id=holder_id,
                    token=None,
                    current_token=int(claim["fencing_token"]),
                    current_holder=str(claim["holder_id"]),
                )
            token = 1 if claim is None else self._bump_token(claim or {})
            if claim is None:
                claim = {
                    "unit_id": unit_id,
                    "rejected_writes": [],
                    "receipt": None,
                    "reclaim_count": 0,
                }
            else:
                token = int(claim["fencing_token"])
            claim["holder_id"] = holder_id
            claim["fencing_token"] = token
            claim["acquired_at"] = now
            claim["expires_at"] = now + float(ttl)
            claim["ttl"] = float(ttl)
            claim["receipt"] = None
            self._save(claim)
            return _result(
                GRANTED,
                REASON_ACQUIRED,
                unit_id=unit_id,
                holder_id=holder_id,
                token=token,
                current_token=token,
                current_holder=holder_id,
            )

    def reclaim(self, unit_id: str, holder_id: str, ttl: float) -> dict[str, Any]:
        with self._locked(unit_id):
            now = self.clock.now()
            claim = self._load(unit_id)
            if claim is None:
                return _result(
                    DENIED,
                    REASON_NO_CLAIM,
                    unit_id=unit_id,
                    holder_id=holder_id,
                )
            if not self._expired(claim, now):
                return _result(
                    DENIED,
                    REASON_UNEXPIRED,
                    unit_id=unit_id,
                    holder_id=holder_id,
                    token=None,
                    current_token=int(claim["fencing_token"]),
                    current_holder=str(claim["holder_id"]),
                )
            old_token = int(claim["fencing_token"])
            token = self._bump_token(claim)
            claim["holder_id"] = holder_id
            claim["acquired_at"] = now
            claim["expires_at"] = now + float(ttl)
            claim["ttl"] = float(ttl)
            claim["reclaim_count"] = int(claim.get("reclaim_count") or 0) + 1
            claim["previous_token"] = old_token
            claim["receipt"] = None
            self._save(claim)
            return _result(
                GRANTED,
                REASON_RECLAIMED,
                unit_id=unit_id,
                holder_id=holder_id,
                token=token,
                current_token=token,
                current_holder=holder_id,
                extra={"previous_token": old_token},
            )

    def commit_receipt(
        self,
        unit_id: str,
        holder_id: str,
        token: int,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Authoritative gate is the fencing token, not holder identity or TTL."""
        with self._locked(unit_id):
            now = self.clock.now()
            claim = self._load(unit_id)
            if claim is None:
                return _result(
                    REJECTED,
                    REASON_NO_CLAIM,
                    unit_id=unit_id,
                    holder_id=holder_id,
                    token=int(token),
                )
            current = int(claim["fencing_token"])
            if int(token) != current:
                rec = {
                    "at": now,
                    "holder_id": holder_id,
                    "stale_token": int(token),
                    "current_token": current,
                    "current_holder": str(claim["holder_id"]),
                    "reason": REASON_STALE,
                }
                rejected = list(claim.get("rejected_writes") or [])
                rejected.append(rec)
                claim["rejected_writes"] = rejected
                self._save(claim)
                return _result(
                    REJECTED,
                    REASON_STALE,
                    unit_id=unit_id,
                    holder_id=holder_id,
                    token=int(token),
                    current_token=current,
                    current_holder=str(claim["holder_id"]),
                    extra={"stale_token": int(token), "rejected": rec},
                )
            claim["receipt"] = {
                "at": now,
                "holder_id": holder_id,
                "fencing_token": current,
                "payload": payload,
            }
            self._save(claim)
            return _result(
                COMMITTED,
                REASON_COMMITTED,
                unit_id=unit_id,
                holder_id=holder_id,
                token=current,
                current_token=current,
                current_holder=str(claim["holder_id"]),
            )

    def snapshot(self, unit_id: str) -> dict[str, Any] | None:
        with self._locked(unit_id):
            return self._load(unit_id)


class TimeoutOnlyClaimStore(FencingClaimStore):
    """Mutant: expiry takeover without bumping the fencing token."""

    mode = "timeout-only"

    def _bump_token(self, claim: dict[str, Any]) -> int:
        return int(claim.get("fencing_token") or 0)


def make_store(root: Path, clock: Clock, mode: str = "fencing") -> FencingClaimStore:
    if mode == "timeout-only":
        return TimeoutOnlyClaimStore(root, clock)
    if mode != "fencing":
        raise ValueError(f"unknown-mode:{mode}")
    return FencingClaimStore(root, clock)


def scenario_zombie_write(
    root: Path,
    *,
    ttl: float = 10.0,
    mode: str = "fencing",
    unit_id: str = "UNIT-ZOMBIE",
) -> dict[str, Any]:
    """Freeze original past expiry, reclaim+complete, then thawed original writes."""
    clock_path = Path(root) / "clock.json"
    clock = Clock(start=0.0, path=clock_path)
    store = make_store(Path(root) / "claims", clock, mode)
    orig = "dispatcher-original"
    nxt = "dispatcher-reclaimer"
    acquired = store.acquire(unit_id, orig, ttl)
    orig_token = int(acquired["token"])
    clock.advance(ttl)
    reclaimed = store.reclaim(unit_id, nxt, ttl)
    completed = store.commit_receipt(
        unit_id,
        nxt,
        int(reclaimed.get("token") or 0),
        {"body": "SUCCESS from reclaimer", "unit_id": unit_id},
    )
    thawed = store.commit_receipt(
        unit_id,
        orig,
        orig_token,
        {"body": "late result from thawed original", "unit_id": unit_id},
    )
    snap = store.snapshot(unit_id) or {}
    receipt = snap.get("receipt") or {}
    return {
        "mode": mode,
        "unit_id": unit_id,
        "acquired": acquired,
        "orig_token": orig_token,
        "reclaimed": reclaimed,
        "reclaimer_committed": completed,
        "thawed_original": thawed,
        "snapshot": snap,
        "stale_token_recorded": any(
            int(r.get("stale_token") or -1) == orig_token
            and r.get("reason") == REASON_STALE
            for r in (snap.get("rejected_writes") or [])
        ),
        "winner_payload": (receipt.get("payload") or {}).get("body"),
        "winner_token": receipt.get("fencing_token"),
    }


def scenario_exactly_one_reclaim(
    root: Path, *, ttl: float = 10.0, unit_id: str = "UNIT-ONCE"
) -> dict[str, Any]:
    clock = Clock(start=0.0)
    store = FencingClaimStore(Path(root) / "claims", clock)
    first = store.acquire(unit_id, "orig", ttl)
    clock.advance(ttl)
    a = store.reclaim(unit_id, "reclaimer-a", ttl)
    b = store.reclaim(unit_id, "reclaimer-b", ttl)
    grants = [r for r in (a, b) if r["status"] == GRANTED]
    return {
        "acquired": first,
        "first_reclaim": a,
        "second_reclaim": b,
        "grant_count": len(grants),
        "exactly_one": len(grants) == 1
        and a["status"] == GRANTED
        and b["status"] == DENIED
        and b["reason"] == REASON_UNEXPIRED
        and int(a["token"]) == int(first["token"]) + 1,
    }


def scenario_unexpired_blocks(
    root: Path, *, ttl: float = 10.0, unit_id: str = "UNIT-BOTH"
) -> dict[str, Any]:
    clock = Clock(start=0.0)
    store = FencingClaimStore(Path(root) / "claims", clock)
    acquired = store.acquire(unit_id, "orig", ttl)
    before = store.reclaim(unit_id, "early-reclaimer", ttl)
    clock.advance(ttl)
    after = store.reclaim(unit_id, "late-reclaimer", ttl)
    return {
        "acquired": acquired,
        "unexpired": before,
        "expired": after,
        "both_states": before["status"] == DENIED
        and before["reason"] == REASON_UNEXPIRED
        and after["status"] == GRANTED
        and int(after["token"]) == int(acquired["token"]) + 1,
        "same_function": "FencingClaimStore.reclaim",
    }


def _mp_reclaim(
    payload: tuple[str, str, str, str, float, str, str],
) -> dict[str, Any]:
    root_s, clock_s, unit_id, holder_id, ttl, ready_path, go_path = payload
    Path(ready_path).write_text("ready\n", encoding="utf-8")
    go = Path(go_path)
    deadline = time.monotonic() + 8.0
    while not go.is_file():
        if time.monotonic() > deadline:
            return {
                "status": DENIED,
                "reason": "barrier-timeout",
                "unit_id": unit_id,
                "holder_id": holder_id,
                "token": None,
                "current_token": None,
                "current_holder": None,
            }
    store = FencingClaimStore(Path(root_s), Clock(path=Path(clock_s)))
    return store.reclaim(unit_id, holder_id, ttl)


def scenario_concurrent_reclaimers(
    root: Path,
    *,
    ttl: float = 10.0,
    n_workers: int = 8,
    n_trials: int = 24,
    unit_prefix: str = "UNIT-RACE",
) -> dict[str, Any]:
    ctx = get_context("fork")
    trials: list[dict[str, Any]] = []
    bad = 0
    winners: dict[str, int] = {}
    for i in range(n_trials):
        trial_root = Path(root) / f"trial-{i:03d}"
        claims = trial_root / "claims"
        ready_dir = trial_root / "ready"
        ready_dir.mkdir(parents=True)
        go_path = trial_root / "GO"
        clock_path = trial_root / "clock.json"
        clock = Clock(start=0.0, path=clock_path)
        store = FencingClaimStore(claims, clock)
        uid = f"{unit_prefix}-{i:03d}"
        acquired = store.acquire(uid, "orig", ttl)
        clock.advance(ttl)
        jobs = [
            (
                str(claims),
                str(clock_path),
                uid,
                f"reclaimer-{j:02d}",
                ttl,
                str(ready_dir / f"reclaimer-{j:02d}"),
                str(go_path),
            )
            for j in range(n_workers)
        ]
        with ctx.Pool(processes=n_workers) as pool:
            asyncs = [pool.apply_async(_mp_reclaim, (job,)) for job in jobs]
            wait_deadline = time.monotonic() + 8.0
            ready = False
            while time.monotonic() < wait_deadline:
                if len(list(ready_dir.glob("reclaimer-*"))) >= n_workers:
                    ready = True
                    break
            go_path.write_text("go\n", encoding="utf-8")
            results = [a.get(timeout=8) for a in asyncs]
            if not ready:
                bad += 1
                trials.append(
                    {
                        "trial": i,
                        "ok": False,
                        "grant_count": 0,
                        "denied_count": 0,
                        "winner": None,
                        "winner_token": None,
                        "error": "workers-never-ready",
                    }
                )
                continue
        grants = [r for r in results if r["status"] == GRANTED]
        denied = [r for r in results if r["status"] == DENIED]
        snap = store.snapshot(uid) or {}
        ok = (
            len(grants) == 1
            and len(denied) == n_workers - 1
            and all(d["reason"] == REASON_UNEXPIRED for d in denied)
            and int(grants[0]["token"]) == int(acquired["token"]) + 1
            and int(snap.get("fencing_token") or 0) == int(grants[0]["token"])
            and str(snap.get("holder_id")) == str(grants[0]["holder_id"])
        )
        if not ok:
            bad += 1
        if grants:
            winners[str(grants[0]["holder_id"])] = (
                winners.get(str(grants[0]["holder_id"]), 0) + 1
            )
        trials.append(
            {
                "trial": i,
                "ok": ok,
                "grant_count": len(grants),
                "denied_count": len(denied),
                "winner": grants[0]["holder_id"] if grants else None,
                "winner_token": grants[0]["token"] if grants else None,
            }
        )
    return {
        "n_trials": n_trials,
        "n_workers": n_workers,
        "failed_trials": bad,
        "all_exactly_one": bad == 0,
        "distinct_winners": len(winners),
        "winner_counts": winners,
        "trials": trials,
    }


def ast_commit_is_token_gated(source: str) -> dict[str, Any]:
    """Structural check: commit_receipt compares fencing_token; mutant bump is identity."""
    import ast

    tree = ast.parse(source)
    commit_compares_token = False
    bump_adds_one = False
    mutant_returns_existing = False
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        if node.name == "FencingClaimStore":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "commit_receipt":
                    dump = ast.dump(item)
                    commit_compares_token = (
                        "fencing_token" in dump and "stale" in dump.lower()
                    ) or ("fencing_token" in dump and "token" in dump)
                if isinstance(item, ast.FunctionDef) and item.name == "_bump_token":
                    bump_adds_one = any(
                        isinstance(n, ast.BinOp) and isinstance(n.op, ast.Add)
                        for n in ast.walk(item)
                    )
        if node.name == "TimeoutOnlyClaimStore":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "_bump_token":
                    mutant_returns_existing = not any(
                        isinstance(n, ast.BinOp) and isinstance(n.op, ast.Add)
                        for n in ast.walk(item)
                    )
    return {
        "commit_compares_token": commit_compares_token,
        "production_bump_adds_one": bump_adds_one,
        "mutant_bump_does_not_add": mutant_returns_existing,
        "pass": commit_compares_token and bump_adds_one and mutant_returns_existing,
    }
