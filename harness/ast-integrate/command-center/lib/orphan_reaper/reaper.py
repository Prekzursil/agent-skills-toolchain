"""Orphan claim/lease reaper gated on the two-signal proof of death.

Claims record the session that holds them (pid, artifact path, the byte and
CPU snapshot taken at claim time). ``reap_tree`` re-observes each claim now,
runs ``proof_of_death`` over the process and byte signals and releases only on
REAP. Leases inherit the death proof of the claim they cover. Every release
record names both signals with their measured values; a HOLD can never be
turned into a release (``make_release_record`` refuses it).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .liveness import (
    HOLD,
    IDLE_WINDOW_SECONDS,
    IncompleteReleaseRecord,
    LivenessReport,
    REAP,
    observe_bytes,
    observe_process,
    proof_of_death,
    validate_release_signals,
)


def pid_exists(pid: int) -> bool:
    """True iff ``pid`` is in the process table (permission denied counts)."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
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


def read_cpu_ns(pid: int) -> int | None:
    """utime+stime of ``pid`` in nanoseconds from /proc, or None if unreadable."""
    try:
        raw = Path(f"/proc/{int(pid)}/stat").read_text(encoding="utf-8")
    except (OSError, ValueError):
        return None
    try:
        fields = raw[raw.rindex(")") + 2 :].split()
        ticks = int(fields[11]) + int(fields[12])
        hz = os.sysconf("SC_CLK_TCK") or 100
    except (ValueError, IndexError, OSError):
        return None
    return int(ticks * 1_000_000_000 // hz)


def artifact_bytes(path: str | Path | None) -> int:
    """Total bytes of an artifact file or directory tree (0 when absent)."""
    if not path:
        return 0
    p = Path(path)
    if p.is_file():
        return p.stat().st_size
    if p.is_dir():
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
    return 0


def make_release_record(
    *,
    kind: str,
    target_id: str,
    session_id: str | None = None,
    path: str | Path | None = None,
    report: LivenessReport | None = None,
    signals: Any = None,
    window_seconds: int | None = None,
) -> dict[str, Any]:
    """Build the release record for a proven-dead claim or lease.

    Either a ``report`` from ``proof_of_death`` or the raw ``signals`` must be
    supplied; both required signals must be present with their values and the
    report must be REAP. A HOLD report raises ``IncompleteReleaseRecord``.
    """
    if kind not in {"claim", "lease"}:
        raise ValueError(f"unknown release kind {kind!r}")
    if report is None:
        if signals is None:
            raise IncompleteReleaseRecord(
                f"{kind} {target_id}: a release needs a death report or its signals"
            )
        report = proof_of_death(
            signals,
            session_id=session_id,
            window_seconds=window_seconds or IDLE_WINDOW_SECONDS,
        )
    obs = validate_release_signals(report.signals)
    if not report.death_proven or report.action != REAP:
        raise IncompleteReleaseRecord(
            f"{kind} {target_id}: liveness verdict {report.action} is not a "
            "proof of death; nothing may be released"
        )
    return {
        "kind": kind,
        "target_id": target_id,
        "session_id": session_id or report.session_id,
        "path": str(path) if path is not None else None,
        "action": REAP,
        "death_proven": True,
        "gate": report.gate,
        "window_seconds": report.window_seconds,
        "signal_count": len(obs),
        "signal_names": [s.name for s in obs],
        "signals": [s.to_dict() for s in obs],
    }


@dataclass
class Event:
    """One reaper decision for a claim or lease."""

    kind: str
    target_id: str
    action: str
    report: LivenessReport
    path: str = ""
    session_id: str | None = None
    release_path: str | None = None
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "target_id": self.target_id,
            "action": self.action,
            "death_proven": self.report.death_proven,
            "session_id": self.session_id,
            "path": self.path,
            "release_path": self.release_path,
            "reason": self.reason,
            "signals": [s.to_dict() for s in self.report.signals],
        }


@dataclass
class ReapResult:
    """All decisions of one ``reap_tree`` pass."""

    events: list[Event] = field(default_factory=list)
    releases: list[Path] = field(default_factory=list)

    @property
    def released_count(self) -> int:
        return sum(1 for e in self.events if e.action == REAP)

    @property
    def held_count(self) -> int:
        return sum(1 for e in self.events if e.action == HOLD)

    def to_dict(self) -> dict[str, Any]:
        return {
            "released_count": self.released_count,
            "held_count": self.held_count,
            "releases": [str(p) for p in self.releases],
            "events": [e.to_dict() for e in self.events],
        }


def _write_json(path: Path, doc: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def plant_claim(
    claims: Path,
    *,
    claim_id: str,
    session_id: str,
    pid: int,
    artifact: Path,
    window_seconds: int = IDLE_WINDOW_SECONDS,
) -> Path:
    """Write a claim carrying the t0 snapshot the reaper compares against."""
    cpu0 = read_cpu_ns(pid)
    doc = {
        "id": claim_id,
        "session_id": session_id,
        "pid": int(pid),
        "artifact": str(artifact),
        "bytes_t0": artifact_bytes(artifact),
        "cpu_ns_t0": cpu0 if cpu0 is not None else 0,
        "window_seconds": int(window_seconds),
    }
    path = claims / f"{claim_id}.json"
    _write_json(path, doc)
    return path


def plant_both_states(root: Path, *, live_pid: int, dead_pid: int) -> dict[str, Path]:
    """Plant one live-but-idle claim/lease pair and one dead pair under root."""
    claims = root / "claims"
    leases = root / "leases"
    releases = root / "releases"
    artifacts = root / "artifacts"
    for d in (claims, leases, releases, artifacts):
        d.mkdir(parents=True, exist_ok=True)
    idle_art = artifacts / "idle.bin"
    dead_art = artifacts / "dead.bin"
    idle_art.write_bytes(b"idle-bytes-unchanged-over-window\n")
    dead_art.write_bytes(b"dead-bytes-unchanged-over-window\n")
    plant_claim(
        claims, claim_id="WU-IDLE", session_id="sess-idle", pid=int(live_pid), artifact=idle_art
    )
    plant_claim(
        claims, claim_id="WU-DEAD", session_id="sess-dead", pid=int(dead_pid), artifact=dead_art
    )
    _write_json(
        leases / "lease-idle-src.json",
        {"id": "lease-idle-src", "claim": "WU-IDLE", "session_id": "sess-idle"},
    )
    _write_json(
        leases / "lease-dead-src.json",
        {"id": "lease-dead-src", "claim": "WU-DEAD", "session_id": "sess-dead"},
    )
    return {"claims": claims, "leases": leases, "releases": releases, "artifacts": artifacts}


def observe_claim(doc: dict[str, Any], *, window_seconds: int) -> LivenessReport:
    """Re-observe a claim now and run the death gate against its t0 snapshot."""
    pid = int(doc.get("pid") or 0)
    cpu1 = read_cpu_ns(pid)
    cpu0 = int(doc.get("cpu_ns_t0") or 0)
    cpu_delta = max(0, (cpu1 if cpu1 is not None else cpu0) - cpu0)
    proc = observe_process(pid, pid_exists=pid_exists(pid), cpu_delta_ns=cpu_delta)
    bytes_t1 = artifact_bytes(doc.get("artifact"))
    bytes_t0 = int(doc["bytes_t0"]) if "bytes_t0" in doc else bytes_t1
    growth = observe_bytes(bytes_t0, bytes_t1, window_seconds=window_seconds)
    return proof_of_death(
        (proc, growth),
        session_id=doc.get("session_id"),
        window_seconds=int(doc.get("window_seconds") or window_seconds),
    )


def reap_tree(
    claims: Path,
    leases: Path,
    releases_dir: Path,
    *,
    window_seconds: int = IDLE_WINDOW_SECONDS,
) -> ReapResult:
    """Reap dead claims and the leases covering them; hold everything else."""
    result = ReapResult()
    releases_dir.mkdir(parents=True, exist_ok=True)
    proven: dict[str, LivenessReport] = {}

    for claim_path in sorted(claims.glob("*.json")):
        doc = json.loads(claim_path.read_text(encoding="utf-8"))
        claim_id = str(doc.get("id") or claim_path.stem)
        report = observe_claim(doc, window_seconds=window_seconds)
        event = Event(
            kind="claim",
            target_id=claim_id,
            action=report.action,
            report=report,
            path=str(claim_path),
            session_id=doc.get("session_id"),
        )
        if report.action == REAP:
            rec = make_release_record(
                kind="claim",
                target_id=claim_id,
                session_id=doc.get("session_id"),
                path=claim_path,
                report=report,
            )
            out = releases_dir / f"claim-{claim_id}.json"
            _write_json(out, rec)
            claim_path.unlink()
            event.release_path = str(out)
            result.releases.append(out)
            proven[claim_id] = report
        result.events.append(event)

    for lease_path in sorted(leases.glob("*.json")):
        doc = json.loads(lease_path.read_text(encoding="utf-8"))
        lease_id = str(doc.get("id") or lease_path.stem)
        claim_id = str(doc.get("claim") or "")
        report = proven.get(claim_id)
        reason = ""
        if report is None and doc.get("pid") is not None:
            report = observe_claim(doc, window_seconds=window_seconds)
        if report is None:
            reason = (
                "covering claim held" if (claims / f"{claim_id}.json").is_file()
                else "no liveness evidence for this lease"
            )
            report = LivenessReport(
                signals=(), death_proven=False, action=HOLD,
                session_id=doc.get("session_id"), window_seconds=window_seconds,
            )
        event = Event(
            kind="lease",
            target_id=lease_id,
            action=report.action,
            report=report,
            path=str(lease_path),
            session_id=doc.get("session_id"),
            reason=reason,
        )
        if report.action == REAP:
            rec = make_release_record(
                kind="lease",
                target_id=lease_id,
                session_id=doc.get("session_id"),
                path=lease_path,
                report=report,
            )
            out = releases_dir / f"lease-{lease_id}.json"
            _write_json(out, rec)
            lease_path.unlink()
            event.release_path = str(out)
            result.releases.append(out)
        result.events.append(event)
    return result
