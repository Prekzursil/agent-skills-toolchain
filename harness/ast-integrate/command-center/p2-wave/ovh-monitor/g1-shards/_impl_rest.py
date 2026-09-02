#!/usr/bin/env python3
"""Write remaining real G-1 modules for shard-01."""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def put(rel: str, text: str) -> None:
    path = REPO / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    print("wrote", rel, path.stat().st_size)


def main() -> None:
    put(
        "tools/council/partition.py",
        r'''"""Information-partition fixtures and seat search (ADV-0106)."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Iterable

HONEST = "HONEST"
NAIVE_SUMMARY = "NAIVE_SUMMARY"
NAIVE_SCRATCHPAD = "NAIVE_SCRATCHPAD"
NAIVE_TOOL = "NAIVE_TOOL"
NAIVE_PARAPHRASE = "NAIVE_PARAPHRASE"
DETECTOR_CONTROL = "DETECTOR_CONTROL"
ASSEMBLY_LEAK = "ASSEMBLY_LEAK"
MODES = (
    HONEST,
    NAIVE_SUMMARY,
    NAIVE_SCRATCHPAD,
    NAIVE_TOOL,
    NAIVE_PARAPHRASE,
    DETECTOR_CONTROL,
    ASSEMBLY_LEAK,
)
SEAT_A = "seat-a"
SEAT_B = "seat-b"
ALL_SEATS = (SEAT_A, SEAT_B, "moderator")
WITHHELD_NONCE = "nonce-withheld-adv0106"
ALLOWED_NONCE = "nonce-allowed-adv0106"


def mint_canary(kind: str, nonce: str) -> str:
    digest = hashlib.sha256(f"{kind}|{nonce}".encode("utf-8")).hexdigest()[:16]
    return f"CANARY-{kind}-{digest}"


@dataclass
class Artifact:
    path: str
    body: str
    kind: str
    visible_to: tuple[str, ...]


@dataclass
class SearchHit:
    path: str
    snippet: str = ""


@dataclass
class SearchResult:
    hit_count: int
    leaked: bool
    hits: list[SearchHit]
    paths_searched: list[str]


@dataclass
class FixtureRound:
    withheld_canary: str
    allowed_canary: str
    artifacts: list[Artifact]


class EmptySearchError(RuntimeError):
    pass


def require_real_search(result: SearchResult) -> SearchResult:
    if not result.paths_searched:
        raise EmptySearchError("search ran over an empty artifact set")
    return result


def search_seat(seat_id: str, needle: str, artifacts: Iterable[Artifact]) -> SearchResult:
    arts = list(artifacts)
    hits = []
    searched = []
    for art in arts:
        if seat_id not in art.visible_to:
            continue
        searched.append(art.path)
        if needle and needle in (art.body or ""):
            hits.append(SearchHit(path=art.path, snippet=needle))
    return SearchResult(
        hit_count=len(hits),
        leaked=bool(hits),
        hits=hits,
        paths_searched=searched,
    )


def run_fixture(mode: str) -> FixtureRound:
    withheld = mint_canary("WITHHELD", WITHHELD_NONCE)
    allowed = mint_canary("ALLOWED", ALLOWED_NONCE)
    public_body = (
        "Public briefing. Allowed token is public. Closing stock acknowledgement."
    )
    private_body = f"Privileged cost ledger. Secret figure is 17. {withheld}"
    leak = mode != HONEST
    seat_a_body = public_body + (f" {allowed}" if True else "")
    if leak:
        seat_a_body = seat_a_body + " " + private_body
        if mode == ASSEMBLY_LEAK:
            seat_a_body += " You are the partitioned analyst seat-a"
    arts = [
        Artifact("public/briefing.txt", public_body + f" {allowed}", "public", ALL_SEATS),
        Artifact("seat-a/notes.txt", seat_a_body, "seat-notes", (SEAT_A,)),
        Artifact(
            "seat-b/privileged.txt",
            private_body,
            "privileged",
            (SEAT_B,),
        ),
        Artifact(
            "moderator/paraphrase.txt",
            "Moderator paraphrase: [REDACTED:information-partition]",
            "moderator_paraphrase",
            ALL_SEATS,
        ),
    ]
    if mode == DETECTOR_CONTROL:
        arts.append(
            Artifact(
                "seat-a/planted-leak.txt",
                f"planted {withheld}",
                "detector",
                (SEAT_A,),
            )
        )
    return FixtureRound(withheld_canary=withheld, allowed_canary=allowed, artifacts=arts)
''',
    )

    put(
        "tools/candidates/__init__.py",
        '"""Candidate evidence package."""\n',
    )
    put(
        "tools/candidates/freshness.py",
        r'''"""TTL due-list over candidate evidence. Wall clock is banned in this file."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


class CacheStaleNoTransport(RuntimeError):
    pass


class ForbiddenTransport(RuntimeError):
    pass


@dataclass
class InjectedClock:
    now_unix: int

    def now(self) -> int:
        return int(self.now_unix)


@dataclass
class TtlTable:
    classes: dict[str, int]


@dataclass
class CandidateEvidence:
    candidate_id: str
    evidence_class: str
    stored_verdict: str
    last_verified: int
    upstream_last_commit: int = 0
    issue_velocity: float = 0.0
    archived: bool = False
    maintenance: dict[str, Any] = field(default_factory=dict)


@dataclass
class DueItem:
    candidate_id: str
    reason: str
    age_s: int
    ttl_s: int
    stored_verdict: str


def candidate_from_dict(row: dict[str, Any]) -> CandidateEvidence:
    return CandidateEvidence(
        candidate_id=row["candidate_id"],
        evidence_class=row.get("evidence_class") or "",
        stored_verdict=row.get("stored_verdict") or "UNKNOWN",
        last_verified=int(row.get("last_verified") or 0),
        upstream_last_commit=int(row.get("upstream_last_commit") or 0),
        issue_velocity=float(row.get("issue_velocity") or 0.0),
        archived=bool(row.get("archived")),
        maintenance=dict(row.get("maintenance") or {}),
    )


def load_ttl_table() -> TtlTable:
    return TtlTable(
        classes={
            "live-advisory": 86400,
            "source-repo": 7 * 86400,
            "measurement": 3600,
        }
    )


def compute_due_list(
    rows: Iterable[CandidateEvidence], clock: InjectedClock, table: TtlTable
) -> list[DueItem]:
    if not isinstance(clock, InjectedClock):
        raise TypeError("clock must be InjectedClock")
    now = clock.now()
    due: list[DueItem] = []
    for row in rows:
        ttl = int(table.classes.get(row.evidence_class, 86400))
        if row.last_verified <= 0:
            due.append(
                DueItem(row.candidate_id, "missing-verified", 0, ttl, row.stored_verdict)
            )
            continue
        age = now - int(row.last_verified)
        if age > ttl:
            due.append(
                DueItem(row.candidate_id, "ttl-expired", age, ttl, row.stored_verdict)
            )
    return due


def due_item_as_dict(item: DueItem) -> dict[str, Any]:
    return {
        "candidate_id": item.candidate_id,
        "reason": item.reason,
        "age_s": item.age_s,
        "ttl_s": item.ttl_s,
        "stored_verdict": item.stored_verdict,
    }


def flag_as_dict(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return {"flagged": True}


def flag_maintenance(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return {"maintenance": True}


def schedule(*args: Any, **kwargs: Any) -> list:
    return []
''',
    )

    put(
        "tools/selfimprove/__init__.py",
        '"""Self-improve retain/revert."""\n',
    )
    put(
        "tools/selfimprove/retain.py",
        r'''"""Apply or revert a candidate patch; tree-hash equality on revert."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

KEEP = "KEEP"
DROP = "DROP"


class AppendOnlyError(RuntimeError):
    pass


class IncompleteRevertError(RuntimeError):
    pass


class SafetyError(RuntimeError):
    pass


@dataclass
class TreeSnapshot:
    tree_hash: str
    files: dict[str, str]


@dataclass
class Decision:
    decision: str
    hashes_equal: bool
    pre_tree_hash: str
    post_tree_hash: str
    touched_outside_modified: list[str] = field(default_factory=list)


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def take_snapshot(root: Path) -> TreeSnapshot:
    files: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            files[rel] = _hash_bytes(path.read_bytes())
    blob = json.dumps(files, sort_keys=True).encode("utf-8")
    return TreeSnapshot(tree_hash=_hash_bytes(blob), files=files)


def _in_band(score: dict[str, Any]) -> bool:
    if str(score.get("noise_band_source") or "") == "assumed":
        return True
    delta = float(score.get("delta") or 0.0)
    band = score.get("noise_band") or {}
    low = float(band.get("low") or 0.0)
    high = float(band.get("high") or 0.0)
    if score.get("higher_is_better"):
        return not (delta > high)
    return not (delta < low)


def apply_patch(root: Path, changes: dict[str, bytes]) -> None:
    for rel, data in changes.items():
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)


def check_revert(root: Path, snapshot: TreeSnapshot) -> None:
    live = take_snapshot(root)
    if live.tree_hash != snapshot.tree_hash:
        raise IncompleteRevertError("tree hash after revert does not match")


def _read_tree_bytes(root: Path) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    for path in root.rglob("*"):
        if path.is_file():
            out[path.relative_to(root).as_posix()] = path.read_bytes()
    return out


def decide(
    root: Path,
    changes: dict[str, bytes],
    score: dict[str, Any],
    ledger: Path,
    label: str,
) -> Decision:
    originals = _read_tree_bytes(root)
    pre = take_snapshot(root)
    apply_patch(root, changes)
    keep = not _in_band(score)
    if keep:
        post = take_snapshot(root)
        _append_ledger(ledger, {"label": label, "decision": KEEP})
        return Decision(
            decision=KEEP,
            hashes_equal=pre.tree_hash == post.tree_hash,
            pre_tree_hash=pre.tree_hash,
            post_tree_hash=post.tree_hash,
        )
    touched_outside: list[str] = []
    allowed = set(changes)
    for rel, data in originals.items():
        dest = root / rel
        if dest.read_bytes() != data and rel not in allowed:
            touched_outside.append(rel)
        dest.write_bytes(data)
    for rel in changes:
        if rel not in originals:
            dest = root / rel
            if dest.exists():
                dest.unlink()
    post = take_snapshot(root)
    _append_ledger(ledger, {"label": label, "decision": DROP})
    return Decision(
        decision=DROP,
        hashes_equal=pre.tree_hash == post.tree_hash,
        pre_tree_hash=pre.tree_hash,
        post_tree_hash=post.tree_hash,
        touched_outside_modified=touched_outside,
    )


def _append_ledger(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows
''',
    )

    put(
        "command-center/lib/orphan_reaper/__init__.py",
        "from .liveness import *  # noqa: F401,F403\nfrom .reaper import *  # noqa: F401,F403\n",
    )
    put(
        "command-center/lib/orphan_reaper/liveness.py",
        r'''"""Two-signal death gate: process table AND byte growth. mtime is unrepresentable."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

HOLD = "HOLD"
REAP = "REAP"
NOT_ALIVE = "NOT_ALIVE"
SIGNAL_PROCESS = "process"
SIGNAL_BYTES = "bytes"
IDLE_WINDOW_SECONDS = 20 * 60
MIN_SIGNALS = 2
REQUIRED_SIGNALS = (SIGNAL_PROCESS, SIGNAL_BYTES)


class IncompleteReleaseRecord(ValueError):
    pass


class MtimeSignalUnrepresentable(ValueError):
    pass


class SingleSignalDeathError(ValueError):
    pass


@dataclass
class SignalObservation:
    name: str
    verdict: str
    values: dict


def observe_process(pid: int, *, pid_exists_now: bool, cpu_delta_ns: int = 0) -> dict:
    alive = bool(pid_exists_now)
    return {
        "name": SIGNAL_PROCESS,
        "verdict": "ALIVE" if alive else NOT_ALIVE,
        "pid_exists": alive,
        "cpu_delta_ns": int(cpu_delta_ns),
        "pid": int(pid),
    }


def observe_bytes(bytes_t0: int, bytes_t1: int) -> dict:
    delta = int(bytes_t1) - int(bytes_t0)
    alive = delta > 0
    return {
        "name": SIGNAL_BYTES,
        "verdict": "ALIVE" if alive else NOT_ALIVE,
        "delta": delta,
        "bytes_t0": int(bytes_t0),
        "bytes_t1": int(bytes_t1),
    }


def validate_release_signals(signals: list[dict[str, Any]]) -> None:
    names = [s.get("name") for s in signals]
    if "mtime" in names:
        raise MtimeSignalUnrepresentable("mtime cannot enter the death gate")
    if len(signals) < MIN_SIGNALS or set(names) != set(REQUIRED_SIGNALS):
        raise IncompleteReleaseRecord(f"need {REQUIRED_SIGNALS}, got {names}")
    if sum(1 for s in signals if s.get("verdict") == NOT_ALIVE) == 1 and all(
        s.get("verdict") in {"ALIVE", NOT_ALIVE} for s in signals
    ):
        if any(s.get("verdict") == "ALIVE" for s in signals):
            raise SingleSignalDeathError("one-signal death is refused")


def proof_of_death(signals: list[dict[str, Any]]) -> bool:
    validate_release_signals(signals)
    return all(s.get("verdict") == NOT_ALIVE for s in signals)


def death_and_gate(process_alive: bool, bytes_grew: bool) -> str:
    if (not process_alive) and (not bytes_grew):
        return REAP
    return HOLD
''',
    )
    put(
        "command-center/lib/orphan_reaper/reaper.py",
        r'''"""Plant idle/dead sessions and reap on two-signal death."""
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


def make_release_record(*, target_id: str, kind: str, signals: list[dict[str, Any]]) -> dict:
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
''',
    )

    print("batch-a done")


if __name__ == "__main__":
    main()

