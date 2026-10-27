"""Plant idle/dead sessions and reap on two-signal death."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .liveness import (
    HOLD,
    NOT_ALIVE,
    REAP,
    SIGNAL_BYTES,
    SIGNAL_PROCESS,
    observe_bytes,
    observe_process,
    proof_of_death,
)


def pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(int(pid), 0)
    except OSError:
        return False
    except SystemError:
        return False
    return True


def make_release_record(*, target_id: str, kind: str, signals: list[dict[str, Any]], session_id: str | None = None, **kwargs: Any) -> dict:
    return {
        "target_id": target_id,
        "kind": kind,
        "signal_count": len(signals),
        "signals": signals,
        "death_proven": proof_of_death(signals),
    }


@dataclass
class Event:
    kind: str
    target_id: str
    action: str
    report: Any

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "target_id": self.target_id,
            "action": self.action,
            "death_proven": self.report.death_proven,
        }


@dataclass
class Report:
    death_proven: bool


@dataclass
class ReapResult:
    events: list[Event] = field(default_factory=list)


def plant_both_states(root: Path, *, live_pid: int, dead_pid: int) -> dict[str, Path]:
    claims = root / "claims"
    leases = root / "leases"
    releases = root / "releases"
    artifacts = root / "artifacts"
    for d in (claims, leases, releases, artifacts):
        d.mkdir(parents=True, exist_ok=True)
    idle_art = artifacts / "idle.bin"
    dead_art = artifacts / "dead.bin"
    idle_art.write_bytes(b"idle-bytes")
    dead_art.write_bytes(b"dead-bytes")
    (claims / "WU-IDLE.json").write_text(
        json.dumps({"id": "WU-IDLE", "pid": live_pid, "artifact": str(idle_art)}),
        encoding="utf-8",
    )
    (claims / "WU-DEAD.json").write_text(
        json.dumps({"id": "WU-DEAD", "pid": dead_pid, "artifact": str(dead_art)}),
        encoding="utf-8",
    )
    (leases / "lease-idle-src.json").write_text(
        json.dumps({"id": "lease-idle-src", "claim": "WU-IDLE"}), encoding="utf-8"
    )
    (leases / "lease-dead-src.json").write_text(
        json.dumps({"id": "lease-dead-src", "claim": "WU-DEAD"}), encoding="utf-8"
    )
    return {"claims": claims, "leases": leases, "releases": releases, "artifacts": artifacts}


def reap_tree(claims: Path, leases: Path, releases_dir: Path) -> ReapResult:
    result = ReapResult()
    for claim_path in list(claims.glob("*.json")):
        doc = json.loads(claim_path.read_text(encoding="utf-8"))
        pid = int(doc["pid"])
        art = Path(doc["artifact"])
        size = art.stat().st_size if art.is_file() else 0
        proc = observe_process(pid, pid_exists_now=pid_exists(pid), cpu_delta_ns=0)
        growth = observe_bytes(size, size)
        signals = [proc, growth]
        death = proof_of_death(signals) if proc["verdict"] == NOT_ALIVE else False
        action = REAP if death else HOLD
        report = Report(death_proven=death)
        result.events.append(
            Event(kind="claim", target_id=doc["id"], action=action, report=report)
        )
        if action == REAP:
            rec = make_release_record(target_id=doc["id"], kind="claim", signals=signals)
            (releases_dir / f"claim-{doc['id']}.json").write_text(
                json.dumps(rec, indent=2), encoding="utf-8"
            )
            claim_path.unlink()
    for lease_path in list(leases.glob("*.json")):
        doc = json.loads(lease_path.read_text(encoding="utf-8"))
        claim_id = doc.get("claim")
        still = (claims / f"{claim_id}.json").is_file()
        if not still:
            pid = 0
            proc = observe_process(pid, pid_exists_now=False, cpu_delta_ns=0)
            growth = observe_bytes(0, 0)
            rec = make_release_record(
                target_id=doc["id"], kind="lease", signals=[proc, growth]
            )
            (releases_dir / f"lease-{doc['id']}.json").write_text(
                json.dumps(rec, indent=2), encoding="utf-8"
            )
            lease_path.unlink()
    return result
