"""Two-signal death gate for the orphan reaper.

A session is proven dead only when BOTH independent signals read NOT_ALIVE:

* ``process`` -- the pid is absent from the process table (its CPU delta over
  the window is reported alongside so a slow-but-live process is visible);
* ``bytes``   -- the session's artifact bytes did not change over the idle
  window (``IDLE_WINDOW_SECONDS``).

The gate is an AND over ``REQUIRED_SIGNALS`` with cardinality ``MIN_SIGNALS``.
One signal can never prove death (``SingleSignalDeathError``); a release record
that does not name every required signal with its values is refused
(``IncompleteReleaseRecord``); and ``mtime`` is not representable as a signal
at all (``MtimeSignalUnrepresentable``) -- a live-but-idle process has exactly
the mtime profile of a dead one, so mtime cannot discriminate and must never
enter the gate. TTL expiry is likewise not a death signal.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

HOLD = "HOLD"
REAP = "REAP"
ALIVE = "ALIVE"
NOT_ALIVE = "NOT_ALIVE"
SIGNAL_PROCESS = "process"
SIGNAL_BYTES = "bytes"
SIGNAL_MTIME = "mtime"
IDLE_WINDOW_SECONDS = 20 * 60
MIN_SIGNALS = 2
REQUIRED_SIGNALS = frozenset({SIGNAL_PROCESS, SIGNAL_BYTES})
VERDICTS = frozenset({ALIVE, NOT_ALIVE})
# Every named signal must carry these measured values in a release record.
REQUIRED_VALUES: dict[str, tuple[str, ...]] = {
    SIGNAL_PROCESS: ("pid_exists", "cpu_delta_ns"),
    SIGNAL_BYTES: ("bytes_t0", "bytes_t1", "delta"),
}


class IncompleteReleaseRecord(ValueError):
    """A release must name every required signal together with its values."""


class MtimeSignalUnrepresentable(ValueError):
    """mtime cannot be expressed as a liveness signal; it is refused outright."""


class SingleSignalDeathError(ValueError):
    """Death needs MIN_SIGNALS independent signals; a single one is refused."""


@dataclass
class SignalObservation:
    """One measured liveness signal: its name, verdict and raw values."""

    name: str
    verdict: str
    values: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Flatten to a JSON-ready record (values sit beside name/verdict)."""
        out: dict[str, Any] = {"name": self.name, "verdict": self.verdict}
        for key in sorted(self.values):
            if key not in out:
                out[key] = self.values[key]
        return out

    @classmethod
    def coerce(cls, obj: Any) -> "SignalObservation":
        """Accept an observation or its flattened/nested dict form."""
        if isinstance(obj, cls):
            return obj
        if isinstance(obj, Mapping):
            if "name" not in obj or "verdict" not in obj:
                raise IncompleteReleaseRecord(
                    f"signal record lacks name/verdict: {sorted(obj)}"
                )
            nested = obj.get("values")
            values = dict(nested) if isinstance(nested, Mapping) else {}
            for key, val in obj.items():
                if key not in {"name", "verdict", "values"}:
                    values[key] = val
            return cls(name=str(obj["name"]), verdict=str(obj["verdict"]), values=values)
        raise TypeError(f"not a signal observation: {type(obj).__name__}")


def _pid_in_table(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def observe_process(
    pid: int | None = None,
    *,
    pid_exists: bool | None = None,
    pid_exists_now: bool | None = None,
    cpu_delta_ns: int = 0,
) -> SignalObservation:
    """Process-table signal. ALIVE iff the pid exists; CPU delta is recorded.

    ``pid_exists`` (or the legacy ``pid_exists_now``) states the measured
    presence; when neither is given the process table is probed for ``pid``.
    A live process that burned zero CPU is still ALIVE: idleness is not death.
    """
    present = pid_exists if pid_exists is not None else pid_exists_now
    if present is None:
        if pid is None:
            raise TypeError("observe_process needs pid_exists= or a pid to probe")
        present = _pid_in_table(int(pid))
    delta = int(cpu_delta_ns)
    if delta < 0:
        raise ValueError(f"cpu_delta_ns must be >= 0, got {delta}")
    values: dict[str, Any] = {"pid_exists": bool(present), "cpu_delta_ns": delta}
    if pid is not None:
        values["pid"] = int(pid)
    return SignalObservation(
        name=SIGNAL_PROCESS,
        verdict=ALIVE if present else NOT_ALIVE,
        values=values,
    )


def observe_bytes(
    bytes_t0: int, bytes_t1: int, *, window_seconds: int = IDLE_WINDOW_SECONDS
) -> SignalObservation:
    """Artifact byte-change signal over the window. Any change is activity."""
    t0, t1 = int(bytes_t0), int(bytes_t1)
    if t0 < 0 or t1 < 0:
        raise ValueError("byte counts cannot be negative")
    delta = t1 - t0
    return SignalObservation(
        name=SIGNAL_BYTES,
        verdict=ALIVE if delta != 0 else NOT_ALIVE,
        values={
            "bytes_t0": t0,
            "bytes_t1": t1,
            "delta": delta,
            "window_seconds": int(window_seconds),
        },
    )


def _coerce_all(signals: Iterable[Any]) -> tuple[SignalObservation, ...]:
    if isinstance(signals, (SignalObservation, Mapping, str, bytes)):
        raise TypeError("signals must be a sequence of observations")
    return tuple(SignalObservation.coerce(s) for s in signals)


def forbid_mtime(signals: Iterable[Any]) -> None:
    """Refuse any observation that smuggles mtime into the gate."""
    for sig in _coerce_all(signals):
        keys = {str(k).lower() for k in sig.values}
        if sig.name.lower() == SIGNAL_MTIME or any(
            k == SIGNAL_MTIME or k.startswith("st_mtime") for k in keys
        ):
            raise MtimeSignalUnrepresentable(
                "mtime cannot enter the death gate: a live-but-idle process is "
                "indistinguishable from a dead one by mtime"
            )


def require_named_pair(signals: Iterable[Any]) -> tuple[SignalObservation, ...]:
    """Enforce cardinality (MIN_SIGNALS) and identity (REQUIRED_SIGNALS)."""
    obs = _coerce_all(signals)
    if len(obs) < MIN_SIGNALS:
        raise SingleSignalDeathError(
            f"death needs {MIN_SIGNALS} independent signals, got {len(obs)}"
        )
    names = [s.name for s in obs]
    if len(set(names)) != len(names):
        raise IncompleteReleaseRecord(f"duplicate signal names: {names}")
    if frozenset(names) != REQUIRED_SIGNALS:
        raise IncompleteReleaseRecord(
            f"need exactly {sorted(REQUIRED_SIGNALS)}, got {sorted(names)}"
        )
    for sig in obs:
        if sig.verdict not in VERDICTS:
            raise IncompleteReleaseRecord(
                f"signal {sig.name!r} has unknown verdict {sig.verdict!r}"
            )
    return obs


def death_and_gate(
    signals_or_process_alive: Any, bytes_grew: bool | None = None
) -> bool:
    """AND over the signals: dead only when every signal reads NOT_ALIVE.

    Also accepts the legacy ``(process_alive, bytes_grew)`` boolean form.
    Cardinality is NOT checked here; ``proof_of_death`` does that first, which
    is exactly why bypassing it lets a bytes-only observation "prove" death.
    """
    if bytes_grew is not None or isinstance(signals_or_process_alive, bool):
        return (not bool(signals_or_process_alive)) and (not bool(bytes_grew))
    obs = _coerce_all(signals_or_process_alive)
    if not obs:
        return False
    return all(s.verdict == NOT_ALIVE for s in obs)


def validate_release_signals(signals: Iterable[Any]) -> tuple[SignalObservation, ...]:
    """A release record must carry both required signals with their values."""
    obs = _coerce_all(signals)
    forbid_mtime(obs)
    if len(obs) < MIN_SIGNALS:
        raise IncompleteReleaseRecord(
            f"release must name {MIN_SIGNALS} signals, got {len(obs)}"
        )
    names = [s.name for s in obs]
    if frozenset(names) != REQUIRED_SIGNALS or len(set(names)) != len(names):
        raise IncompleteReleaseRecord(
            f"release must name exactly {sorted(REQUIRED_SIGNALS)}, got {names}"
        )
    for sig in obs:
        if sig.verdict not in VERDICTS:
            raise IncompleteReleaseRecord(
                f"release signal {sig.name!r} has unknown verdict {sig.verdict!r}"
            )
        missing = [k for k in REQUIRED_VALUES.get(sig.name, ()) if k not in sig.values]
        if missing:
            raise IncompleteReleaseRecord(
                f"release signal {sig.name!r} lacks values {missing}"
            )
    return obs


@dataclass
class LivenessReport:
    """Outcome of the death gate for one session."""

    signals: tuple[SignalObservation, ...]
    death_proven: bool
    action: str
    session_id: str | None = None
    window_seconds: int = IDLE_WINDOW_SECONDS
    gate: str = "AND"
    min_signals: int = MIN_SIGNALS

    def signal_names(self) -> list[str]:
        return [s.name for s in self.signals]

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "action": self.action,
            "death_proven": self.death_proven,
            "gate": self.gate,
            "min_signals": self.min_signals,
            "window_seconds": self.window_seconds,
            "signal_count": len(self.signals),
            "signal_names": self.signal_names(),
            "signals": [s.to_dict() for s in self.signals],
        }


def proof_of_death(
    signals: Iterable[Any],
    *,
    session_id: str | None = None,
    window_seconds: int = IDLE_WINDOW_SECONDS,
) -> LivenessReport:
    """Run the gate: refuse mtime, require the named pair, AND the verdicts."""
    obs = _coerce_all(signals)
    forbid_mtime(obs)
    obs = require_named_pair(obs)
    dead = death_and_gate(obs)
    return LivenessReport(
        signals=obs,
        death_proven=bool(dead),
        action=REAP if dead else HOLD,
        session_id=session_id,
        window_seconds=int(window_seconds),
    )
