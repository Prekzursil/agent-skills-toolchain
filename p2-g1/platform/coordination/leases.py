"""File leases and conflict detection.

WHY PATH CONTAINMENT IS COMPARED PART-WISE AND NEVER WITH ``startswith``

A lease on ``dir/`` must conflict with a lease on ``dir/file.py``; a lease on ``dir`` must NOT
conflict with a lease on ``dir-sibling``. A string prefix test gets the second case wrong, and this
estate has paid for that exact bug twice - once in a backup guard (``StartsWith``) and once in an
``ensure_within`` sibling. So containment here is a comparison of PATH PART TUPLES:
``("dir",)`` is a prefix of ``("dir","file.py")`` but not of ``("dir-sibling",)``.
``test_leases.py`` carries the sibling case as a negative control, so a regression to a prefix test
turns the suite red instead of silently widening every lease.

WHY UNVERIFIED SESSIONS STILL HOLD THEIR LEASES

A lease is "in force" when it has not expired AND its holder's liveness is ``LIVE`` or
``UNVERIFIED``. Treating UNVERIFIED as free would be the cheap read; it is also the dangerous
direction of the error. The estate's measured lesson is to grade a heuristic by error DIRECTION,
not accuracy: 100% of one wrong classifier's errors pointed at data loss. Granting an exclusive
lease over a file whose real owner is still writing it is that same direction, so UNVERIFIED
blocks and says why.

MODES: ``SHARED`` readers coexist; ``EXCLUSIVE`` excludes everything overlapping, including other
readers. There is no upgrade path from SHARED to EXCLUSIVE in place - an upgrade is a release plus
an acquire, so the window where the holder believes it is exclusive and is not cannot exist.

LEASES ARE ADVISORY (leak L-05). They coordinate cooperating agents; they do not stop a
non-participating process - the owner's editor, a sibling agent that does not consult this store, a
``git checkout`` - from writing the file. That is stated here and in ABSTRACTION-LEAKS.md rather
than implied, because an advisory lock described as a lock is a false guarantee.

CASE FOLDING IS A FILESYSTEM PROPERTY, NOT A PATH PROPERTY (leak L-07). Keys are case-folded on
win32 and darwin, where ``a/B.py`` and ``A\b.py`` really are one file, and NOT on Linux, where they
are two. A store written on one platform and read on another would fold differently; single-platform
stores are the only measured configuration.
"""

from __future__ import annotations

import sys
import uuid
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence

from .errors import LeaseConflict, PathOutsideRoot
from .session import DEFAULT_HEARTBEAT_TTL, Liveness, classify, SessionRecord
from .store import Store

__all__ = [
    "DEFAULT_LEASE_TTL",
    "Conflict",
    "Lease",
    "LeaseMode",
    "LeaseOutcome",
    "LeaseResult",
    "acquire_lease",
    "detect_conflicts",
    "normalize_lease_path",
    "overlaps",
    "path_parts",
    "release_leases",
    "renew_lease",
    "require_lease",
]

#: Seconds. 900s = 15 min, comfortably longer than a single work unit's edit burst and far shorter
#: than the 30-min dispatch timeout, so an abandoned lease frees before the dispatch that held it.
DEFAULT_LEASE_TTL = 900.0

_CASE_INSENSITIVE_FS = sys.platform in {"win32", "darwin"}


class LeaseMode(str, Enum):
    SHARED = "SHARED"
    EXCLUSIVE = "EXCLUSIVE"


class LeaseOutcome(str, Enum):
    GRANTED = "GRANTED"
    #: This session already holds an overlapping lease in a mode that covers the request.
    ALREADY_HELD = "ALREADY-HELD"
    #: Another in-force lease overlaps. Nothing was written.
    CONFLICT = "CONFLICT"


def normalize_lease_path(root: str | Path, raw: str | Path) -> str:
    """Fold a path to the canonical lease key: root-relative, POSIX, case-folded where the
    filesystem is.

    Raises :class:`PathOutsideRoot` when the path escapes ``root``. Containment is checked on
    RESOLVED, part-wise paths - not on the string - so ``root/../root-sibling/x`` cannot slip
    through, and neither can ``root-sibling`` looking like a child of ``root``.
    """
    root_path = Path(root).resolve()
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = root_path / candidate
    resolved = _resolve_without_requiring_existence(candidate)
    root_parts = root_path.parts
    cand_parts = resolved.parts
    if len(cand_parts) < len(root_parts) or not _parts_equal(
        cand_parts[: len(root_parts)], root_parts
    ):
        raise PathOutsideRoot(
            f"{raw!r} resolves to {resolved} which is not under the declared root {root_path}"
        )
    rel = PurePosixPath(*cand_parts[len(root_parts) :])
    text = rel.as_posix()
    if text in {"", "."}:
        text = "."
    return text.casefold() if _CASE_INSENSITIVE_FS else text


def _resolve_without_requiring_existence(p: Path) -> Path:
    """``Path.resolve`` semantics that do not depend on the file existing.

    ``strict=False`` is the default on 3.6+, but on Windows a non-existent path with ``..``
    segments still needs the lexical collapse, so normalise explicitly.
    """
    return Path(p).absolute().resolve()


def _fold(part: str) -> str:
    return part.casefold() if _CASE_INSENSITIVE_FS else part


def _parts_equal(a: Sequence[str], b: Sequence[str]) -> bool:
    return [_fold(x) for x in a] == [_fold(y) for y in b]


def path_parts(key: str) -> tuple[str, ...]:
    """Split a normalised lease key into comparable parts. ``"."`` means the whole root."""
    if key in {"", "."}:
        return ()
    return tuple(PurePosixPath(key).parts)


def overlaps(a: str, b: str) -> bool:
    """True when two normalised lease keys cover any common file.

    Part-wise prefix containment in either direction. NOT ``str.startswith``: that reports
    ``"dir"`` as containing ``"dir-sibling"``.
    """
    pa, pb = path_parts(a), path_parts(b)
    shorter, longer = (pa, pb) if len(pa) <= len(pb) else (pb, pa)
    return longer[: len(shorter)] == shorter


@dataclass(frozen=True)
class Lease:
    lease_id: str
    session_id: str
    paths: tuple[str, ...]
    mode: LeaseMode
    acquired_at: float
    expires_at: float
    root: str
    purpose: str = ""
    renew_seq: int = 0
    released_at: float | None = None

    @property
    def active(self) -> bool:
        return self.released_at is None

    def expired(self, now: float) -> bool:
        return now > self.expires_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "lease",
            "lease_id": self.lease_id,
            "session_id": self.session_id,
            "paths": list(self.paths),
            "mode": self.mode.value,
            "acquired_at": self.acquired_at,
            "expires_at": self.expires_at,
            "root": self.root,
            "purpose": self.purpose,
            "renew_seq": self.renew_seq,
            "released_at": self.released_at,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> Lease:
        return cls(
            lease_id=str(raw["lease_id"]),
            session_id=str(raw["session_id"]),
            paths=tuple(str(p) for p in raw.get("paths", ())),
            mode=LeaseMode(raw.get("mode", "EXCLUSIVE")),
            acquired_at=float(raw.get("acquired_at", 0.0)),
            expires_at=float(raw.get("expires_at", 0.0)),
            root=str(raw.get("root", "")),
            purpose=str(raw.get("purpose", "")),
            renew_seq=int(raw.get("renew_seq", 0)),
            released_at=(
                None if raw.get("released_at") is None else float(raw["released_at"])
            ),
        )


@dataclass(frozen=True)
class Conflict:
    """One overlapping pair, with both sides named so a report is actionable."""

    path_a: str
    path_b: str
    lease_a: str
    lease_b: str
    session_a: str
    session_b: str
    mode_a: LeaseMode
    mode_b: LeaseMode
    holder_liveness: Liveness
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path_a": self.path_a,
            "path_b": self.path_b,
            "lease_a": self.lease_a,
            "lease_b": self.lease_b,
            "session_a": self.session_a,
            "session_b": self.session_b,
            "mode_a": self.mode_a.value,
            "mode_b": self.mode_b.value,
            "holder_liveness": self.holder_liveness.value,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class LeaseResult:
    outcome: LeaseOutcome
    lease: Lease | None
    conflicts: tuple[Conflict, ...] = ()

    @property
    def granted(self) -> bool:
        return self.outcome in {LeaseOutcome.GRANTED, LeaseOutcome.ALREADY_HELD}

    @property
    def sentinel_line(self) -> str:
        if self.granted and self.lease is not None:
            return (
                f"SUCCESS:lease/{self.lease.lease_id} outcome={self.outcome.value} "
                f"paths={len(self.lease.paths)}"
            )
        blockers = sorted({c.session_b for c in self.conflicts})
        return f"FAILED:lease outcome={self.outcome.value} blocked_by={blockers}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "lease_result",
            "outcome": self.outcome.value,
            "lease": self.lease.to_dict() if self.lease else None,
            "conflicts": [c.to_dict() for c in self.conflicts],
            "sentinel_line": self.sentinel_line,
        }


def _holder_liveness(
    store: Store,
    session_id: str,
    *,
    now: float,
    heartbeat_ttl: float,
    cache: dict[str, Liveness],
) -> Liveness:
    if session_id in cache:
        return cache[session_id]
    raw = store.read(store.path_for("sessions", session_id))
    if raw is None:
        # No session row at all. Fail CLOSED: an orphan lease with no owner record cannot be
        # proven free, so it is UNVERIFIED and keeps blocking until recovery adjudicates it.
        cache[session_id] = Liveness.UNVERIFIED
        return cache[session_id]
    liveness = classify(
        store, SessionRecord.from_dict(raw), now=now, heartbeat_ttl=heartbeat_ttl
    ).liveness
    cache[session_id] = liveness
    return liveness


def _in_force(liveness: Liveness) -> bool:
    """LIVE and UNVERIFIED hold their leases; DEAD and CLOSED do not."""
    return liveness in {Liveness.LIVE, Liveness.UNVERIFIED}


def _active_leases(store: Store) -> list[Lease]:
    return [Lease.from_dict(raw) for _n, raw in store.iter_records("leases")]


def acquire_lease(
    store: Store,
    *,
    session_id: str,
    paths: Iterable[str | Path],
    root: str | Path,
    mode: LeaseMode = LeaseMode.EXCLUSIVE,
    ttl: float = DEFAULT_LEASE_TTL,
    purpose: str = "",
    now: float | None = None,
    heartbeat_ttl: float = DEFAULT_HEARTBEAT_TTL,
) -> LeaseResult:
    """Try to lease ``paths``. Returns an outcome; writes nothing on CONFLICT."""
    store.initialise()
    at = store.clock() if now is None else now
    keys = tuple(sorted({normalize_lease_path(root, p) for p in paths}))
    if not keys:
        raise PathOutsideRoot("a lease must name at least one path")

    conflicts: list[Conflict] = []
    cache: dict[str, Liveness] = {}
    covers_request = False
    for existing in _active_leases(store):
        if not existing.active or existing.expired(at):
            continue
        liveness = _holder_liveness(
            store, existing.session_id, now=at, heartbeat_ttl=heartbeat_ttl, cache=cache
        )
        if not _in_force(liveness):
            continue
        for want in keys:
            for held in existing.paths:
                if not overlaps(want, held):
                    continue
                if existing.session_id == session_id:
                    if existing.mode is LeaseMode.EXCLUSIVE or mode is LeaseMode.SHARED:
                        covers_request = True
                    continue
                if existing.mode is LeaseMode.SHARED and mode is LeaseMode.SHARED:
                    continue
                conflicts.append(
                    Conflict(
                        path_a=want,
                        path_b=held,
                        lease_a="(requested)",
                        lease_b=existing.lease_id,
                        session_a=session_id,
                        session_b=existing.session_id,
                        mode_a=mode,
                        mode_b=existing.mode,
                        holder_liveness=liveness,
                        reason=(
                            f"{mode.value} request overlaps {existing.mode.value} lease "
                            f"{existing.lease_id} held by {existing.session_id} "
                            f"(liveness={liveness.value})"
                            + (
                                " - UNVERIFIED holders keep their leases: granting over a session "
                                "that may still be writing is the data-loss direction of the error"
                                if liveness is Liveness.UNVERIFIED
                                else ""
                            )
                        ),
                    )
                )
    if conflicts:
        store.journal(
            "lease.conflict",
            session_id=session_id,
            paths=list(keys),
            mode=mode.value,
            conflicts=[c.to_dict() for c in conflicts],
        )
        return LeaseResult(LeaseOutcome.CONFLICT, None, tuple(conflicts))

    if covers_request:
        store.journal("lease.already_held", session_id=session_id, paths=list(keys))
        held = next(
            lease
            for lease in _active_leases(store)
            if lease.session_id == session_id
            and lease.active
            and not lease.expired(at)
            and any(overlaps(w, h) for w in keys for h in lease.paths)
        )
        return LeaseResult(LeaseOutcome.ALREADY_HELD, held)

    lease = Lease(
        lease_id=f"lease-{uuid.uuid4().hex[:12]}",
        session_id=session_id,
        paths=keys,
        mode=mode,
        acquired_at=at,
        expires_at=at + ttl,
        root=str(Path(root).resolve()),
        purpose=purpose,
    )
    store.write_atomic(store.path_for("leases", lease.lease_id), lease.to_dict())
    store.journal(
        "lease.granted",
        lease_id=lease.lease_id,
        session_id=session_id,
        paths=list(keys),
        mode=mode.value,
    )
    return LeaseResult(LeaseOutcome.GRANTED, lease)


def require_lease(store: Store, **kwargs: Any) -> Lease:
    """``acquire_lease`` that raises on conflict, for call sites that cannot continue without it."""
    result = acquire_lease(store, **kwargs)
    if not result.granted or result.lease is None:
        raise LeaseConflict(result.sentinel_line)
    return result.lease


def renew_lease(
    store: Store,
    lease_id: str,
    *,
    ttl: float = DEFAULT_LEASE_TTL,
    now: float | None = None,
) -> Lease:
    at = store.clock() if now is None else now
    path = store.path_for("leases", lease_id)
    raw = store.read(path)
    if raw is None:
        raise LeaseConflict(f"cannot renew unknown lease {lease_id!r}")
    lease = Lease.from_dict(raw)
    updated = replace(lease, expires_at=at + ttl, renew_seq=lease.renew_seq + 1)
    store.write_atomic(path, updated.to_dict())
    return updated


def release_leases(
    store: Store,
    *,
    session_id: str | None = None,
    lease_ids: Iterable[str] = (),
    now: float | None = None,
) -> tuple[str, ...]:
    """Release leases by session or by id. Returns the ids released.

    Release MARKS the record (``released_at``) instead of deleting it, so the journal and the
    record agree on history and a post-hoc audit can see that a lease existed.
    """
    at = store.clock() if now is None else now
    targets = set(lease_ids)
    released: list[str] = []
    for _name, raw in store.iter_records("leases"):
        lease = Lease.from_dict(raw)
        if not lease.active:
            continue
        if session_id is not None and lease.session_id != session_id:
            continue
        if targets and lease.lease_id not in targets:
            continue
        store.write_atomic(
            store.path_for("leases", lease.lease_id),
            replace(lease, released_at=at).to_dict(),
        )
        released.append(lease.lease_id)
    if released:
        store.journal("lease.released", session_id=session_id, lease_ids=released)
    return tuple(sorted(released))


def detect_conflicts(
    store: Store,
    *,
    now: float | None = None,
    heartbeat_ttl: float = DEFAULT_HEARTBEAT_TTL,
) -> tuple[Conflict, ...]:
    """Audit the store for overlapping in-force leases that should never coexist.

    ``acquire_lease`` prevents these prospectively; this finds them retrospectively, which is the
    only way to catch a store corrupted by a crash mid-recovery, a hand-edited record, or a bug in
    a future call site. A prospective guard that is never audited is a guard nobody has measured.
    """
    at = store.clock() if now is None else now
    cache: dict[str, Liveness] = {}
    live: list[tuple[Lease, Liveness]] = []
    for lease in _active_leases(store):
        if not lease.active or lease.expired(at):
            continue
        liveness = _holder_liveness(
            store, lease.session_id, now=at, heartbeat_ttl=heartbeat_ttl, cache=cache
        )
        if _in_force(liveness):
            live.append((lease, liveness))

    out: list[Conflict] = []
    for i, (a, liveness_a) in enumerate(live):
        for b, liveness_b in live[i + 1 :]:
            if a.session_id == b.session_id:
                continue
            if a.mode is LeaseMode.SHARED and b.mode is LeaseMode.SHARED:
                continue
            for pa in a.paths:
                for pb in b.paths:
                    if not overlaps(pa, pb):
                        continue
                    out.append(
                        Conflict(
                            path_a=pa,
                            path_b=pb,
                            lease_a=a.lease_id,
                            lease_b=b.lease_id,
                            session_a=a.session_id,
                            session_b=b.session_id,
                            mode_a=a.mode,
                            mode_b=b.mode,
                            holder_liveness=liveness_b,
                            reason=(
                                f"two in-force leases overlap on {pa!r} / {pb!r}: "
                                f"{a.session_id} ({a.mode.value}, {liveness_a.value}) and "
                                f"{b.session_id} ({b.mode.value}, {liveness_b.value})"
                            ),
                        )
                    )
    return tuple(out)
