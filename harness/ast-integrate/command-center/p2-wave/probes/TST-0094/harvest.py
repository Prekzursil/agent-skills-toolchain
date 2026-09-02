"""Remote-harvest classifier for FC-11319 (TST-0094).

Failure class: a harvest against a remote substrate that produced zero new
artifacts must not collapse into the same empty SUCCESS as a harvest whose
connection failed or whose filter matched nothing.

Measured analogue: a job filter keyed on session_id where the written record
carried null, hiding every result.

Typed outcomes (never a shared empty bag):

  NOTHING_TO_HARVEST  connected, filter matched a known session, delta == 0
  FILTER_MISMATCH     connected, filter did not match any known session
  CONNECTION_FAILURE  substrate unreachable; no filter application occurred
  HARVESTED           connected, filter matched, transferred > 0

A null/missing session_id is rejected at WRITE time so the analogue cannot
be recorded. Harvest filters with a null key are also rejected rather than
silently matching nothing.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any, Mapping

NOTHING_TO_HARVEST = "NOTHING_TO_HARVEST"
FILTER_MISMATCH = "FILTER_MISMATCH"
CONNECTION_FAILURE = "CONNECTION_FAILURE"
HARVESTED = "HARVESTED"

# Defect token used ONLY by the emptiness-collapsing mutant. Production
# harvest() never emits this.
EMPTY = "EMPTY"

TYPED_EMPTY_OR_BROKEN = frozenset(
    {NOTHING_TO_HARVEST, FILTER_MISMATCH, CONNECTION_FAILURE}
)
ALL_PRODUCTION_OUTCOMES = TYPED_EMPTY_OR_BROKEN | {HARVESTED}

FILTER_KEY = "session_id"


class NullFilterKeyError(ValueError):
    """Filter key is null/blank at write (or harvest) time."""


class RemoteHarvestError(RuntimeError):
    """Base for harvest-layer faults that are not typed outcomes."""


class ConnectionUnavailable(RuntimeError):
    """Raised only inside the substrate; harvest() maps it to a typed outcome."""


def _is_null_filter_key(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, bool):
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    if isinstance(value, (int, float)):
        return True
    return False


def reject_filter_key(value: Any, *, where: str) -> str:
    """Return a usable session_id or raise NullFilterKeyError.

    `where` is 'write' or 'harvest' so the analogue (null at write time)
    is distinguishable from a null harvest filter.
    """
    if _is_null_filter_key(value) or not isinstance(value, str):
        raise NullFilterKeyError(
            f"{FILTER_KEY} is null, blank, or non-string at {where} time; "
            "refusing rather than recording a hidden row"
        )
    return value


@dataclass
class ArtifactRecord:
    session_id: str
    artifact_id: str
    payload: str
    harvested: bool = False
    nbytes: int = 0

    def __post_init__(self) -> None:
        if not self.nbytes:
            self.nbytes = len(self.payload.encode("utf-8"))


@dataclass
class HarvestResult:
    outcome: str
    session_id: str | None
    connected: bool
    filter_matched: bool
    transferred: int
    transferred_bytes: int
    new_artifact_delta: int
    artifact_ids: list[str] = field(default_factory=list)
    reason: str = ""
    exit_code: int = 1

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def ok(self) -> bool:
        return (
            self.outcome == HARVESTED
            and self.transferred > 0
            and self.exit_code == 0
        )


def harvest_exit_code(result: HarvestResult) -> int:
    """Nonzero transfer is the only SUCCESS (IMP-0431 postcondition analogue)."""
    if result.outcome == HARVESTED and result.transferred > 0:
        return 0
    return 1


class RemoteSubstrate:
    """Deterministic stand-in for a remote job store.

    Sessions must be opened (or written) before they exist. A harvest of a
    session that was never opened is FILTER_MISMATCH, not NOTHING_TO_HARVEST.
    """

    def __init__(self, reachable: bool = True) -> None:
        self.reachable = reachable
        self._sessions: dict[str, list[ArtifactRecord]] = {}
        self._hidden: list[ArtifactRecord] = []

    def session_ids(self) -> tuple[str, ...]:
        return tuple(self._sessions.keys())

    def hidden_count(self) -> int:
        return len(self._hidden)

    def ensure_session(self, session_id: Any) -> str:
        sid = reject_filter_key(session_id, where="write")
        self._require_reachable()
        self._sessions.setdefault(sid, [])
        return sid

    def write(
        self,
        session_id: Any,
        artifact_id: str,
        payload: str = "",
        *,
        allow_null_key: bool = False,
    ) -> ArtifactRecord:
        """Persist one remote artifact.

        Production (`allow_null_key=False`) rejects a null session_id.
        The analogue mutant (`allow_null_key=True`) stores the row in a
        hidden bucket that session-keyed harvest never sees.
        """
        if allow_null_key and _is_null_filter_key(session_id):
            rec = ArtifactRecord(
                session_id="",
                artifact_id=str(artifact_id),
                payload=payload,
            )
            self._hidden.append(rec)
            return rec
        sid = reject_filter_key(session_id, where="write")
        self._require_reachable()
        if not artifact_id:
            raise RemoteHarvestError("artifact_id is required")
        rec = ArtifactRecord(
            session_id=sid, artifact_id=str(artifact_id), payload=payload
        )
        self._sessions.setdefault(sid, []).append(rec)
        return rec

    def _require_reachable(self) -> None:
        if not self.reachable:
            raise ConnectionUnavailable("remote substrate unreachable")

    def pending(self, session_id: str) -> list[ArtifactRecord]:
        return [r for r in self._sessions.get(session_id, []) if not r.harvested]


class RemoteHarvest:
    """Harvest runner. Classifies; never returns a shared empty SUCCESS."""

    def __init__(self, substrate: RemoteSubstrate | None = None) -> None:
        self.substrate = substrate if substrate is not None else RemoteSubstrate()

    def harvest(self, session_id: Any) -> HarvestResult:
        if not self.substrate.reachable:
            shown = None if _is_null_filter_key(session_id) else str(session_id)
            return HarvestResult(
                outcome=CONNECTION_FAILURE,
                session_id=shown,
                connected=False,
                filter_matched=False,
                transferred=0,
                transferred_bytes=0,
                new_artifact_delta=0,
                artifact_ids=[],
                reason="remote substrate unreachable; filter was not applied",
                exit_code=1,
            )
        sid = reject_filter_key(session_id, where="harvest")
        if sid not in self.substrate._sessions:
            return HarvestResult(
                outcome=FILTER_MISMATCH,
                session_id=sid,
                connected=True,
                filter_matched=False,
                transferred=0,
                transferred_bytes=0,
                new_artifact_delta=0,
                artifact_ids=[],
                reason=(
                    f"filter {FILTER_KEY}={sid!r} matched no known session "
                    f"(known={list(self.substrate.session_ids())})"
                ),
                exit_code=1,
            )
        pending = self.substrate.pending(sid)
        if not pending:
            return HarvestResult(
                outcome=NOTHING_TO_HARVEST,
                session_id=sid,
                connected=True,
                filter_matched=True,
                transferred=0,
                transferred_bytes=0,
                new_artifact_delta=0,
                artifact_ids=[],
                reason=(
                    "session exists and filter matched; remote produced "
                    "zero new artifacts"
                ),
                exit_code=1,
            )
        ids: list[str] = []
        total = 0
        for rec in pending:
            rec.harvested = True
            ids.append(rec.artifact_id)
            total += rec.nbytes
        return HarvestResult(
            outcome=HARVESTED,
            session_id=sid,
            connected=True,
            filter_matched=True,
            transferred=len(ids),
            transferred_bytes=total,
            new_artifact_delta=len(ids),
            artifact_ids=ids,
            reason=f"transferred {len(ids)} new artifact(s)",
            exit_code=0,
        )


def mutant_collapse_zero_transfer(result: HarvestResult) -> HarvestResult:
    """Known-broken mutant: every zero-transfer run is EMPTY.

    This is the FC-11319 defect. Production harvest() does not call this.
    """
    if result.transferred == 0:
        return replace(
            result,
            outcome=EMPTY,
            reason="silent empty (mutant collapsed typed zero-transfer)",
        )
    return result


def three_typed_runs() -> dict[str, Any]:
    """Evidence required by the catalog: three runs, three typed outcomes."""
    remote = RemoteSubstrate(reachable=True)
    harvester = RemoteHarvest(remote)

    remote.ensure_session("job-empty")
    genuine = harvester.harvest("job-empty")

    remote.ensure_session("job-A")
    remote.write("job-A", "art-1", "payload-a")
    mismatch = harvester.harvest("job-B")

    remote.reachable = False
    disconnected = harvester.harvest("job-empty")

    production_outcomes = [
        genuine.outcome,
        mismatch.outcome,
        disconnected.outcome,
    ]
    mutant_outcomes = [
        mutant_collapse_zero_transfer(genuine).outcome,
        mutant_collapse_zero_transfer(mismatch).outcome,
        mutant_collapse_zero_transfer(disconnected).outcome,
    ]
    return {
        "runs": [
            {
                "scenario": "genuinely-nothing-to-harvest",
                "outcome": genuine.outcome,
                "result": genuine.as_dict(),
            },
            {
                "scenario": "filter-mismatch",
                "outcome": mismatch.outcome,
                "result": mismatch.as_dict(),
            },
            {
                "scenario": "connection-failure",
                "outcome": disconnected.outcome,
                "result": disconnected.as_dict(),
            },
        ],
        "production_outcomes": production_outcomes,
        "mutant_outcomes": mutant_outcomes,
        "production_distinct": len(set(production_outcomes)) == 3,
        "mutant_collapsed": set(mutant_outcomes) == {EMPTY},
        "expected": {
            "genuinely-nothing-to-harvest": NOTHING_TO_HARVEST,
            "filter-mismatch": FILTER_MISMATCH,
            "connection-failure": CONNECTION_FAILURE,
        },
    }


def nonempty_harvest_control() -> dict[str, Any]:
    """Positive control: a real transfer is HARVESTED (exit 0), not EMPTY."""
    remote = RemoteSubstrate()
    h = RemoteHarvest(remote)
    remote.write("job-ok", "art-ok", "hello")
    first = h.harvest("job-ok")
    second = h.harvest("job-ok")
    return {
        "first": first.as_dict(),
        "second": second.as_dict(),
        "first_ok": first.ok,
        "second_is_nothing_new": second.outcome == NOTHING_TO_HARVEST,
    }


def null_key_write_demo() -> dict[str, Any]:
    """Write-time rejection plus the analogue mutant that hides rows."""
    production = RemoteSubstrate()
    raised: str | None = None
    try:
        production.write(None, "hidden-1", "secret")
    except NullFilterKeyError as exc:
        raised = type(exc).__name__
    production_hidden = production.hidden_count()
    production_sessions = list(production.session_ids())

    mutant = RemoteSubstrate()
    mutant.write(None, "hidden-1", "secret", allow_null_key=True)
    mutant.ensure_session("job-1")
    h = RemoteHarvest(mutant)
    after = h.harvest("job-1")
    return {
        "production_raised": raised,
        "production_hidden_count": production_hidden,
        "production_sessions": production_sessions,
        "production_write_rejected": (
            raised == "NullFilterKeyError"
            and production_hidden == 0
            and production_sessions == []
        ),
        "mutant_hidden_count": mutant.hidden_count(),
        "mutant_harvest_job1": after.as_dict(),
        "mutant_hides_row": (
            mutant.hidden_count() == 1
            and after.outcome == NOTHING_TO_HARVEST
            and after.transferred == 0
        ),
        "harvest_null_filter_rejected": _harvest_null_rejected(),
        "json_null_record_rejected": _json_null_record_rejected(),
    }


def _harvest_null_rejected() -> bool:
    h = RemoteHarvest()
    try:
        h.harvest(None)
    except NullFilterKeyError:
        return True
    return False


def _json_null_record_rejected() -> bool:
    """Records arriving as parsed JSON with session_id: null are rejected."""
    blob: Mapping[str, Any] = {
        "session_id": None,
        "artifact_id": "x",
        "payload": "y",
    }
    remote = RemoteSubstrate()
    try:
        remote.write(
            blob.get("session_id"), str(blob["artifact_id"]), str(blob["payload"])
        )
    except NullFilterKeyError:
        return True
    return False


def analogue_fixed() -> bool:
    demo = null_key_write_demo()
    return bool(demo["production_write_rejected"] and demo["mutant_hides_row"])
