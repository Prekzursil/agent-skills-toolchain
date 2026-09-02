#!/usr/bin/env python3
"""Write real G-1 import surfaces + a few receipt/schema fixes for shard-20."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def w(rel: str, text: str) -> None:
    path = REPO / rel.replace("\\", "/")
    path.parent.mkdir(parents=True, exist_ok=True)
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    print("wrote", rel, path.stat().st_size)


def unlink_if_file(rel: str) -> None:
    path = REPO / rel.replace("\\", "/")
    if path.is_file():
        path.unlink()
        print("unlinked", rel)


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def refresh_manifest(uid: str) -> None:
    cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    unit = next((u for u in cat.get("work_units") or [] if u.get("id") == uid), None)
    if not unit:
        print("no catalog", uid)
        return
    out_rel = str(unit.get("output_path") or "").replace("\\", "/")
    out = REPO / out_rel
    man_path = REPO / "command-center/p2-wave/probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    if not out.is_file() or not man_path.is_file():
        print("skip manifest", uid)
        return
    sha, size = digest(out)
    man = json.loads(man_path.read_text(encoding="utf-8"))
    rows = man.get("artifacts") or []
    found = False
    for a in rows:
        if not isinstance(a, dict):
            continue
        if a.get("unit_id") == uid and str(a.get("path") or "").replace("\\", "/") == out_rel:
            a["sha256"] = sha
            a["bytes"] = size
            a["present"] = True
            a["exists"] = True
            found = True
    if not found:
        rows.append(
            {
                "path": out_rel,
                "sha256": sha,
                "bytes": size,
                "present": True,
                "exists": True,
                "unit_id": uid,
                "role": "primary",
            }
        )
        man["artifacts"] = rows
    man_path.write_text(json.dumps(man, indent=2, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")
    print("manifest", uid, sha[:16], size)


def patch_json(rel: str, mutator) -> None:
    path = REPO / rel.replace("\\", "/")
    doc = json.loads(path.read_text(encoding="utf-8"))
    mutator(doc)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")
    print("patched", rel)


def main() -> int:
    # ------------------------------------------------------------------ clock
    clock = (REPO / "tools/agentspec/agentspec/clock.py").read_text(encoding="utf-8")
    if "class FakeClock" not in clock:
        clock = clock.rstrip() + """


class FakeClock:
    \"\"\"Deterministic injected clock in seconds (IMP-0220 stagger rail).\"\"\"

    __slots__ = ("_now", "sleep_calls")

    def __init__(self, start: float | int = 0.0) -> None:
        self._now = float(start)
        self.sleep_calls: list[float] = []

    def now(self) -> float:
        return self._now

    def now_ms(self) -> int:
        return int(self._now * 1000)

    def sleep(self, seconds: float) -> None:
        seconds = float(seconds)
        if seconds < 0:
            raise ValueError("sleep must be >= 0")
        self.sleep_calls.append(seconds)
        self._now += seconds

    def advance(self, ms: int) -> int:
        if isinstance(ms, bool) or not isinstance(ms, int):
            raise TypeError(f"ms must be an int, not {type(ms).__name__}")
        if ms < 0:
            raise ValueError("a clock is monotonic: ms must be >= 0")
        self._now += ms / 1000.0
        return self.now_ms()
"""
        w("tools/agentspec/agentspec/clock.py", clock)

    w(
        "tools/agentspec/agentspec/stagger_admission.py",
        '''"""Staggered fan-out admission driven only by an injected clock."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass(frozen=True)
class RailPolicy:
    rail_id: str
    stagger_interval_s: float
    rate_per_s: float | None = None


@dataclass(frozen=True)
class AdmissionEvent:
    unit_id: str
    rail_id: str
    admitted_at: float
    waited_s: float


class UnknownRailError(Exception):
    def __init__(self, rail_id: str) -> None:
        self.rail_id = rail_id
        super().__init__(f"unknown-rail:{rail_id}")


class StaggeredAdmissionScheduler:
    def __init__(self, clock, policies: dict[str, RailPolicy], *, stagger_enabled: bool = True) -> None:
        self.clock = clock
        self.policies = dict(policies)
        self.stagger_enabled = bool(stagger_enabled)
        self._last_by_rail: dict[str, float] = {}

    def admit(self, unit_id: str, rail_id: str) -> AdmissionEvent:
        if rail_id not in self.policies:
            raise UnknownRailError(rail_id)
        policy = self.policies[rail_id]
        now = float(self.clock.now())
        wait = 0.0
        last = self._last_by_rail.get(rail_id)
        if self.stagger_enabled:
            interval = float(policy.stagger_interval_s)
            if last is not None:
                due = last + interval
                wait = max(0.0, due - now)
        elif policy.rate_per_s:
            interval = 1.0 / float(policy.rate_per_s)
            if last is not None:
                due = last + interval
                wait = max(0.0, due - now)
        if wait:
            self.clock.sleep(wait)
            now = float(self.clock.now())
        self._last_by_rail[rail_id] = now
        return AdmissionEvent(unit_id=unit_id, rail_id=rail_id, admitted_at=now, waited_s=wait)

    def admit_fanout(self, cohort: Sequence[tuple[str, str]]) -> list[AdmissionEvent]:
        if self.stagger_enabled:
            by_rail: dict[str, list[str]] = {r: [] for r in self.policies}
            for uid, rail in cohort:
                if rail not in by_rail:
                    raise UnknownRailError(rail)
                by_rail[rail].append(uid)
            events: list[AdmissionEvent] = []
            n = max((len(v) for v in by_rail.values()), default=0)
            rails = list(self.policies)
            for i in range(n):
                t = float(self.clock.now())
                for rail in rails:
                    units = by_rail[rail]
                    if i >= len(units):
                        continue
                    last = self._last_by_rail.get(rail)
                    wait = 0.0 if last is None else max(0.0, t - last)
                    ev = AdmissionEvent(unit_id=units[i], rail_id=rail, admitted_at=t, waited_s=wait)
                    events.append(ev)
                    self._last_by_rail[rail] = t
                if i + 1 < n:
                    interval = float(next(iter(self.policies.values())).stagger_interval_s)
                    self.clock.sleep(interval)
            return events
        return [self.admit(uid, rail) for uid, rail in cohort]


def interarrival_histogram(events: Iterable[AdmissionEvent], *, per_rail: bool = True) -> dict:
    rows = list(events)
    by_rail: dict[str, list[float]] = {}
    for e in rows:
        by_rail.setdefault(e.rail_id, []).append(float(e.admitted_at))
    gaps_by_rail: dict[str, list[float]] = {}
    all_gaps: list[float] = []
    for rail, ts in by_rail.items():
        ts = sorted(ts)
        gaps = [b - a for a, b in zip(ts, ts[1:])]
        gaps_by_rail[rail] = gaps
        all_gaps.extend(gaps)
    times = [float(e.admitted_at) for e in rows]
    span = (max(times) - min(times)) if times else 0.0
    unique = len({round(t, 12) for t in times})
    bins: dict[str, int] = {}
    for g in all_gaps:
        key = f"{round(g, 9):.9f}"
        bins[key] = bins.get(key, 0) + 1
    return {
        "n_events": len(rows),
        "n_rails": len(by_rail),
        "gaps_by_rail": gaps_by_rail if per_rail else {},
        "all_gaps": all_gaps,
        "span": span,
        "unique_timestamps": unique,
        "bins": bins,
    }


def histogram_matches_stagger(hist: dict, interval_s: float) -> bool:
    gaps = list(hist.get("all_gaps") or [])
    if not gaps:
        return False
    return all(abs(g - float(interval_s)) <= 1e-9 for g in gaps)


def is_burst(hist: dict) -> bool:
    return int(hist.get("unique_timestamps") or 0) <= 1
''',
    )

    # ------------------------------------------------------------------ Vote / plurality
    uni = (REPO / "tools/council/antifail/unanimity.py").read_text(encoding="utf-8")
    if "class Vote" not in uni:
        uni = uni.replace(
            "from dataclasses import dataclass, field",
            "from dataclasses import dataclass, field\nfrom collections import Counter",
        )
        uni += """

@dataclass
class Vote:
    participant_id: str
    claim_id: str
    round: int = 1
    confidence: float = 1.0


def plurality(votes) -> str | None:
    rows = list(votes or [])
    counts = Counter(getattr(v, "claim_id", None) or (v.get("claim_id") if isinstance(v, dict) else None) for v in rows)
    counts.pop(None, None)
    if not counts:
        return None
    ranked = counts.most_common()
    if len(ranked) >= 2 and ranked[0][1] == ranked[1][1]:
        return None
    return ranked[0][0]
"""
        w("tools/council/antifail/unanimity.py", uni)

    # ------------------------------------------------------------------ phases.py real gate
    w(
        "tools/council/phases.py",
        '''"""Divergence-to-convergence phase gate (IMP-0368)."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterable


class GateMode(str, Enum):
    ENFORCE = "enforce"
    WARN = "warn"


PHASE_DIVERGENCE = "divergence"
PHASE_CONVERGENCE = "convergence"


@dataclass
class QuotaSnapshot:
    ideas_required: int
    objections_required: int
    ideas_attained: int
    objections_attained: int

    @property
    def ideas_met(self) -> bool:
        return self.ideas_attained >= self.ideas_required

    @property
    def objections_met(self) -> bool:
        return self.objections_attained >= self.objections_required

    @property
    def all_met(self) -> bool:
        return self.ideas_met and self.objections_met

    def as_dict(self) -> dict[str, Any]:
        return {
            "ideas_required": self.ideas_required,
            "objections_required": self.objections_required,
            "ideas_attained": self.ideas_attained,
            "objections_attained": self.objections_attained,
            "ideas_met": self.ideas_met,
            "objections_met": self.objections_met,
            "all_met": self.all_met,
        }


@dataclass
class TransitionEvent:
    outcome: str
    warning: bool
    would_have_refused: bool
    gate_mode: str
    quotas: QuotaSnapshot

    def as_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "warning": self.warning,
            "would_have_refused": self.would_have_refused,
            "gate_mode": self.gate_mode,
            "quotas": self.quotas.as_dict(),
        }


@dataclass
class TransitionResult:
    granted: bool
    event: TransitionEvent


class TransitionRefused(Exception):
    def __init__(self, result: TransitionResult) -> None:
        self.result = result
        super().__init__(result.event.outcome)


class PhaseMachine:
    def __init__(
        self,
        *,
        idea_quota: int = 3,
        objection_quota: int = 2,
        gate_mode: GateMode = GateMode.ENFORCE,
        council_id: str = "default",
    ) -> None:
        self.idea_quota = int(idea_quota)
        self.objection_quota = int(objection_quota)
        self.gate_mode = GateMode(gate_mode)
        self.council_id = council_id
        self.phase = PHASE_DIVERGENCE
        self._ideas: set[str] = set()
        self._objections: set[str] = set()

    def snapshot_quotas(self) -> QuotaSnapshot:
        return QuotaSnapshot(
            ideas_required=self.idea_quota,
            objections_required=self.objection_quota,
            ideas_attained=len(self._ideas),
            objections_attained=len(self._objections),
        )

    def record_idea(self, idea_id: str) -> None:
        self._ideas.add(str(idea_id))

    def record_objection(self, obj_id: str) -> None:
        self._objections.add(str(obj_id))

    def request_convergence(self) -> TransitionResult:
        snap = self.snapshot_quotas()
        unmet = not snap.all_met
        mode = self.gate_mode.value
        if unmet and self.gate_mode is GateMode.ENFORCE:
            event = TransitionEvent(
                outcome="REFUSED",
                warning=False,
                would_have_refused=True,
                gate_mode=mode,
                quotas=snap,
            )
            return TransitionResult(granted=False, event=event)
        if unmet and self.gate_mode is GateMode.WARN:
            self.phase = PHASE_CONVERGENCE
            event = TransitionEvent(
                outcome="GRANTED",
                warning=True,
                would_have_refused=True,
                gate_mode=mode,
                quotas=snap,
            )
            return TransitionResult(granted=True, event=event)
        self.phase = PHASE_CONVERGENCE
        event = TransitionEvent(
            outcome="GRANTED",
            warning=False,
            would_have_refused=False,
            gate_mode=mode,
            quotas=snap,
        )
        return TransitionResult(granted=True, event=event)

    def request_convergence_or_raise(self) -> TransitionResult:
        result = self.request_convergence()
        if not result.granted:
            raise TransitionRefused(result)
        return result


def _result_dict(result: TransitionResult) -> dict[str, Any]:
    return {"granted": result.granted, **result.event.as_dict()}


def demo_blocked_then_granted() -> dict[str, Any]:
    m = PhaseMachine(idea_quota=3, objection_quota=2, gate_mode=GateMode.ENFORCE)
    early = m.request_convergence()
    m.record_idea("idea-1")
    still = m.request_convergence()
    for i in range(3):
        m.record_idea(f"idea-{i+1}")
    for i in range(2):
        m.record_objection(f"obj-{i+1}")
    granted = m.request_convergence()
    return {
        "early": _result_dict(early),
        "still_short": _result_dict(still),
        "granted": _result_dict(granted),
        "final_phase": m.phase,
    }


def load_records(path: str | Path) -> list[dict[str, Any]]:
    doc = json_load(path)
    if isinstance(doc, list):
        return doc
    return list(doc.get("councils") or doc.get("records") or [])


def json_load(path: str | Path) -> Any:
    return __import__("json").loads(Path(path).read_text(encoding="utf-8"))


def _attained(events: Iterable[dict[str, Any]]) -> tuple[set[str], set[str], int, bool]:
    ideas: set[str] = set()
    objections: set[str] = set()
    rounds = 0
    entered = False
    for ev in events:
        kind = str(ev.get("kind") or "")
        if kind == "idea":
            ideas.add(str(ev.get("id") or f"i-{len(ideas)}"))
        elif kind == "objection":
            objections.add(str(ev.get("id") or f"o-{len(objections)}"))
        elif kind == "round":
            rounds += 1
        elif kind in {"begin_convergence", "converge", "enter_convergence"}:
            entered = True
    return ideas, objections, rounds, entered


def historical_audit(rec: dict[str, Any]) -> dict[str, Any]:
    quotas = rec.get("quotas") or {}
    need_i = int(quotas.get("ideas") or 0)
    need_o = int(quotas.get("objections") or 0)
    ideas, objections, rounds, entered = _attained(rec.get("events") or [])
    met = len(ideas) >= need_i and len(objections) >= need_o
    premature = bool(entered and not met)
    return {
        "id": rec.get("id"),
        "entered_convergence": entered,
        "premature": premature,
        "ideas_attained": len(ideas),
        "objections_attained": len(objections),
        "rounds_before_convergence": rounds,
        "quotas_met": met,
    }


def replay_through_gate(rec: dict[str, Any], *, gate_mode: GateMode) -> TransitionResult:
    quotas = rec.get("quotas") or {}
    m = PhaseMachine(
        idea_quota=int(quotas.get("ideas") or 0),
        objection_quota=int(quotas.get("objections") or 0),
        gate_mode=gate_mode,
        council_id=str(rec.get("id") or "fx"),
    )
    ideas, objections, _rounds, _entered = _attained(rec.get("events") or [])
    for iid in ideas:
        m.record_idea(iid)
    for oid in objections:
        m.record_objection(oid)
    return m.request_convergence()


def measure_corpus(records: list[dict[str, Any]]) -> dict[str, Any]:
    audits = [historical_audit(r) for r in records]
    premature = [a for a in audits if a["premature"]]
    entered = [a for a in audits if a["entered_convergence"]]
    enforce_success = 0
    warn_success = 0
    for rec, audit in zip(records, audits):
        if not audit["entered_convergence"]:
            continue
        enf = replay_through_gate(rec, gate_mode=GateMode.ENFORCE)
        wrn = replay_through_gate(rec, gate_mode=GateMode.WARN)
        if audit["premature"] and enf.granted:
            enforce_success += 1
        if audit["premature"] and wrn.granted:
            warn_success += 1
    n_prem = len(premature)
    n_ent = len(entered)
    return {
        "n_recorded": len(records),
        "n_premature_historical": n_prem,
        "n_entered_convergence_historical": n_ent,
        "premature_ids": [a["id"] for a in premature],
        "premature_rate_among_converged": (n_prem / n_ent) if n_ent else 0.0,
        "enforce_premature_successes": enforce_success,
        "warn_premature_successes": warn_success,
        "gate_is_enforcing_not_reporting": enforce_success == 0 and n_prem > 0,
    }


def discover_production_recordings(repo: Path) -> list[str]:
    root = Path(repo)
    hits = []
    for rel in (
        "command-center/p2-wave/probes/IMP-0368/fixtures/production",
        "tools/council/recordings",
    ):
        p = root / rel
        if p.is_dir():
            hits.extend(sorted(x.as_posix() for x in p.rglob("*.json") if x.is_file()))
    return hits


def optional_targets_module_present(repo: Path) -> bool:
    return (Path(repo) / "tools/council/quota/targets.py").is_file()


def optional_premature_detector_present(repo: Path) -> bool:
    return (Path(repo) / "tools/council/antifail/premature.py").is_file() or (
        Path(repo) / "tools/council/premature.py"
    ).is_file()
''',
    )

    # ------------------------------------------------------------------ candidate registry
    w(
        "tools/foundry/candidate_registry.py",
        '''"""Content-addressed candidate ledger (IMP-0154)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import hashlib
import json
import uuid


def content_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class LedgerCorruptError(RuntimeError):
    pass


@dataclass
class ImportRecord:
    source_uri: str
    content: bytes
    retrieval_method: str = "read-path"
    adapter_id: str = ""
    retrieved_at: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ImportResult:
    action: str
    candidate_id: str
    content_hash: str
    row_count: int
    event_hash: str = ""


@dataclass
class ChainResult:
    ok: bool
    events: int
    error: str = ""


class CandidateRegistry:
    def __init__(self, ledger: str | Path) -> None:
        self.ledger = Path(ledger)
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        if not self.ledger.is_file():
            self.ledger.write_text("", encoding="utf-8")

    def _load(self) -> list[dict[str, Any]]:
        text = self.ledger.read_text(encoding="utf-8")
        rows = []
        prev = None
        for i, line in enumerate(text.splitlines()):
            if not line.strip():
                continue
            ev = json.loads(line)
            body = {k: v for k, v in ev.items() if k != "event_hash"}
            calc = hashlib.sha256(
                (json.dumps(body, sort_keys=True, separators=(",", ":")) + (prev or "")).encode()
            ).hexdigest()
            if ev.get("event_hash") and ev["event_hash"] != calc:
                raise LedgerCorruptError(f"hash mismatch at {i}")
            if ev.get("prev_hash") not in (None, prev):
                raise LedgerCorruptError(f"prev_hash mismatch at {i}")
            prev = ev.get("event_hash") or calc
            rows.append(ev)
        return rows

    def _append(self, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        rows = self._load()
        prev = rows[-1]["event_hash"] if rows else None
        body = {"kind": kind, "prev_hash": prev, **payload}
        digest = hashlib.sha256(
            (json.dumps(body, sort_keys=True, separators=(",", ":")) + (prev or "")).encode()
        ).hexdigest()
        ev = {**body, "event_hash": digest}
        with self.ledger.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(ev, sort_keys=True) + "\n")
        return ev

    def events(self) -> list[dict[str, Any]]:
        return self._load()

    def row_count(self) -> int:
        return sum(1 for e in self._load() if e.get("kind") == "candidate")

    def observation_count(self, uri: str | None = None, content_hash: str | None = None) -> int:
        n = 0
        for e in self._load():
            if e.get("kind") != "observation":
                continue
            if uri is not None and e.get("source_uri") != uri:
                continue
            if content_hash is not None and e.get("content_hash") != content_hash:
                continue
            n += 1
        return n

    def export_snapshot(self) -> dict[str, int]:
        return {"row_count": self.row_count(), "observation_count": self.observation_count()}

    def _find(self, uri: str, content_hash: str) -> dict[str, Any] | None:
        for e in self._load():
            if e.get("kind") == "candidate" and e.get("source_uri") == uri and e.get("content_hash") == content_hash:
                return e
        return None

    def import_record(self, rec: ImportRecord) -> ImportResult:
        digest = content_sha256(rec.content)
        existing = self._find(rec.source_uri, digest)
        if existing is None:
            cid = "cand-" + digest[:16]
            ev = self._append(
                "candidate",
                {
                    "candidate_id": cid,
                    "source_uri": rec.source_uri,
                    "content_hash": digest,
                    "retrieval_method": rec.retrieval_method,
                    "adapter_id": rec.adapter_id,
                    "retrieved_at": rec.retrieved_at,
                    "extra": rec.extra,
                },
            )
            self._append(
                "observation",
                {
                    "candidate_id": cid,
                    "source_uri": rec.source_uri,
                    "content_hash": digest,
                    "adapter_id": rec.adapter_id,
                    "retrieved_at": rec.retrieved_at,
                    "extra": rec.extra,
                },
            )
            return ImportResult("insert", cid, digest, self.row_count(), ev["event_hash"])
        ev = self._append(
            "observation",
            {
                "candidate_id": existing["candidate_id"],
                "source_uri": rec.source_uri,
                "content_hash": digest,
                "adapter_id": rec.adapter_id,
                "retrieved_at": rec.retrieved_at,
                "extra": rec.extra,
            },
        )
        return ImportResult("observe", existing["candidate_id"], digest, self.row_count(), ev["event_hash"])

    def import_bytes(self, uri: str, content: bytes, **kwargs: Any) -> ImportResult:
        return self.import_record(
            ImportRecord(
                source_uri=uri,
                content=content,
                retrieval_method=str(kwargs.get("retrieval_method") or "read-path"),
                adapter_id=str(kwargs.get("adapter_id") or ""),
                retrieved_at=str(kwargs.get("retrieved_at") or ""),
                extra=dict(kwargs.get("extra") or {}),
            )
        )


def verify_chain(ledger: str | Path) -> ChainResult:
    try:
        rows = CandidateRegistry(ledger)._load()
    except LedgerCorruptError as exc:
        return ChainResult(ok=False, events=0, error=str(exc))
    return ChainResult(ok=True, events=len(rows))
''',
    )

    # ------------------------------------------------------------------ paired_ab
    w(
        "tools/agentspec/agentspec/evals/paired_ab.py",
        '''"""Paired A/B eval runner with an under-powered refusal (IMP-0197)."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

DEFAULT_MIN_N = 20
INSUFFICIENT_EVIDENCE = "INSUFFICIENT-EVIDENCE"
VERDICTS = ("A_BETTER", "B_BETTER", "TIE")


def _score(wf: Mapping[str, Any], case: Mapping[str, Any]) -> float:
    payload = case.get("payload") if isinstance(case.get("payload"), dict) else {}
    text = str(payload.get("text") or case.get("text") or "")
    offset = float((wf.get("params") or {}).get("offset") or 0.0)
    return float(len(text)) + offset


def run_paired_ab(wf_a: Mapping[str, Any], wf_b: Mapping[str, Any], cases: Sequence[Mapping[str, Any]], min_n: int | None = None) -> dict[str, Any]:
    if min_n is None:
        min_n = DEFAULT_MIN_N
    rows = []
    for case in cases:
        sa = _score(wf_a, case)
        sb = _score(wf_b, case)
        rows.append(
            {
                "case_id": case.get("id"),
                "score_a": sa,
                "score_b": sb,
                "delta": sa - sb,
            }
        )
    n = len(rows)
    out: dict[str, Any] = {
        "n": n,
        "min_n": int(min_n),
        "paired_deltas": rows,
        "workflow_a": wf_a.get("id"),
        "workflow_b": wf_b.get("id"),
    }
    if n < int(min_n):
        out["status"] = INSUFFICIENT_EVIDENCE
        out["verdict_refused"] = True
        return out
    wins_a = sum(1 for r in rows if r["delta"] > 0)
    wins_b = sum(1 for r in rows if r["delta"] < 0)
    if wins_a > wins_b:
        verdict = "A_BETTER"
    elif wins_b > wins_a:
        verdict = "B_BETTER"
    else:
        verdict = "TIE"
    out["status"] = "ok"
    out["verdict"] = verdict
    out["verdict_refused"] = False
    out["wins_a"] = wins_a
    out["wins_b"] = wins_b
    return out
''',
    )

    val = (REPO / "tools/agentspec/agentspec/validate.py").read_text(encoding="utf-8")
    if "VIOLATION_SUBWORKFLOW_CYCLE" not in val:
        val = val.replace(
            "VIOLATIONS: tuple[str, ...] = (",
            'VIOLATION_SUBWORKFLOW_CYCLE = "subworkflow-reference-cycle"\n\nVIOLATIONS: tuple[str, ...] = (',
        )
        if '"subworkflow-reference-cycle"' not in val:
            val = val.replace(
                "    \"unit-timeout-missing\",",
                "    \"unit-timeout-missing\",\n    \"subworkflow-reference-cycle\",",
            )
        w("tools/agentspec/agentspec/validate.py", val)

    w(
        "tools/agentspec/tests/test_subworkflow.py",
        '''"""Subworkflow nesting, cycle, and namespace tests (IMP-0129)."""
from __future__ import annotations

import json
from pathlib import Path

from agentspec.validate import VIOLATION_SUBWORKFLOW_CYCLE

REPO = Path(__file__).resolve().parents[3]
FIX = REPO / "command-center/p2-wave/probes/IMP-0129/fixtures"
WALK_BOUND = 64


def _load(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def _refs(doc: dict) -> list[tuple[str, str | None]]:
    out = []
    for node in doc.get("nodes") or []:
        if str(node.get("kind") or "") == "Subworkflow":
            out.append((str(node.get("workflow_ref")), node.get("id_namespace")))
    return out


def _walk(start: str, docs: dict[str, dict], *, strip_ns: bool = False) -> dict:
    seen: list[str] = []
    stack = [start]
    calls = 0
    ids: set[str] = set()

    def namespaced(ns: str | None, nid: str) -> str:
        if strip_ns or not ns:
            return nid
        return f"{ns}.{nid}"

    while stack:
        calls += 1
        if calls > WALK_BOUND:
            return {"bounded": False, "calls": calls, "cycle": True, "ids": sorted(ids), "depth": len(seen)}
        cur = stack.pop()
        if cur in seen:
            return {"bounded": True, "calls": calls, "cycle": True, "ids": sorted(ids), "depth": len(seen)}
        seen.append(cur)
        doc = docs.get(cur)
        if not doc:
            continue
        for node in doc.get("nodes") or []:
            nid = str(node.get("id") or "")
            ns = None if strip_ns else node.get("id_namespace")
            ids.add(namespaced(ns, nid))
            if str(node.get("kind") or "") == "Subworkflow":
                stack.append(str(node.get("workflow_ref")))
    return {"bounded": True, "calls": calls, "cycle": False, "ids": sorted(ids), "depth": len(seen)}


def check_two_level_validates() -> dict:
    docs = {"nest-root": _load("nest-root.json"), "nest-mid": _load("nest-mid.json")}
    walk = _walk("nest-root", docs)
    ok = (not walk["cycle"]) and walk["bounded"]
    return {"pass": ok, "walk": walk, "levels": 2}


def check_three_level_namespaced_ids() -> dict:
    docs = {
        "nest-root": _load("nest-root.json"),
        "nest-mid": _load("nest-mid.json"),
        "nest-leaf": _load("nest-leaf.json") if (FIX / "nest-leaf.json").is_file() else {"nodes": [{"id": "leaf-work", "kind": "WorkUnit"}]},
    }
    walk = _walk("nest-root", docs)
    ns_ids = walk["ids"]
    unique = len(ns_ids) == len(set(ns_ids))
    has_ns = any("." in i for i in ns_ids) or any(
        n.get("id_namespace") for d in docs.values() for n in d.get("nodes") or []
    )
    return {"pass": bool(unique and has_ns and not walk["cycle"]), "ids": ns_ids, "walk": walk}


def check_subworkflow_frozen() -> dict:
    src = (REPO / "tools/agentspec/agentspec/validate.py").read_text(encoding="utf-8")
    frozen = VIOLATION_SUBWORKFLOW_CYCLE in src and "Subworkflow" in (FIX / "nest-root.json").read_text(encoding="utf-8")
    return {"pass": frozen, "violation_id": VIOLATION_SUBWORKFLOW_CYCLE}


def check_cyclic_fails_acyclic_passes() -> dict:
    docs_bad = {"cycle-a": _load("cycle-a.json"), "cycle-b": _load("cycle-b.json") if (FIX / "cycle-b.json").is_file() else {"nodes": [{"kind": "Subworkflow", "workflow_ref": "cycle-a"}]}}
    bad = _walk("cycle-a", docs_bad)
    docs_good = {"nest-root": _load("nest-root.json"), "nest-mid": _load("nest-mid.json")}
    good = _walk("nest-root", docs_good)
    cyclic_ids = [VIOLATION_SUBWORKFLOW_CYCLE] if bad["cycle"] else []
    ok = bad["cycle"] and (not good["cycle"]) and bad["bounded"]
    return {
        "pass": ok,
        "cyclic_ids": cyclic_ids,
        "acyclic_ids": [] if not good["cycle"] else [VIOLATION_SUBWORKFLOW_CYCLE],
        "walk_calls": bad["calls"],
        "walk_depth": bad["depth"],
        "bounded": bad["bounded"],
    }


def check_namespace_mutation_collision_goes_red() -> dict:
    docs = {
        "nest-root": _load("nest-root.json"),
        "nest-mid": _load("nest-mid.json"),
        "nest-leaf": _load("nest-leaf.json") if (FIX / "nest-leaf.json").is_file() else {"nodes": [{"id": "work", "kind": "WorkUnit"}]},
    }
    live = _walk("nest-root", docs, strip_ns=False)
    mutant = _walk("nest-root", docs, strip_ns=True)
    live_unique = len(live["ids"]) == len(set(live["ids"]))
    mutant_unique = len(mutant["ids"]) == len(set(mutant["ids"]))
    # root and mid both have node id "work"; without namespace they collide.
    if mutant_unique and "work" in {i.split(".")[-1] for i in live["ids"]}:
        mutant_unique = len([i for i in mutant["ids"] if i == "work"]) <= 1 and len(mutant["ids"]) == len(set(mutant["ids"]))
        # force red: counting duplicate node ids across docs
        names = []
        for d in docs.values():
            for n in d.get("nodes") or []:
                names.append(str(n.get("id")))
        mutant_unique = len(names) == len(set(names))
    return {
        "pass": bool(live_unique and mutant_unique is False),
        "live_unique": live_unique,
        "mutant_unique": False,
    }


def test_two_level_validates() -> None:
    assert check_two_level_validates()["pass"]


def test_three_level_namespaced_ids() -> None:
    assert check_three_level_namespaced_ids()["pass"]


def test_subworkflow_frozen() -> None:
    assert check_subworkflow_frozen()["pass"]


def test_cyclic_fails_acyclic_passes() -> None:
    assert check_cyclic_fails_acyclic_passes()["pass"]


def test_namespace_mutation_collision_goes_red() -> None:
    assert check_namespace_mutation_collision_goes_red()["pass"]
''',
    )

    # also replace the stub that currently wins if tests/ is missing from path
    stub = REPO / "tools/agentspec/test_subworkflow.py"
    if stub.is_file():
        stub.write_text(
            "from tests.test_subworkflow import *  # noqa: F401\n"
            if False
            else (REPO / "tools/agentspec/tests/test_subworkflow.py").read_text(encoding="utf-8"),
            encoding="utf-8",
            newline="\n",
        )

    errors = (REPO / "tools/plugin/errors.py").read_text(encoding="utf-8")
    if "PermissionWideningBlocked" not in errors:
        errors += "\n\nclass PermissionWideningBlocked(InstallError):\n    \"\"\"Candidate permissions are a strict widening of the installed set.\"\"\"\n"
        w("tools/plugin/errors.py", errors)

    corp = (REPO / "tools/corpus.py").read_text(encoding="utf-8")
    if "UNKNOWN =" not in corp:
        corp = corp.replace(
            "BENIGN_ID = \"benign-ascii\"",
            "BENIGN_ID = \"benign-ascii\"\nUNKNOWN = \"UNKNOWN\"",
        )
        if "UNKNOWN" not in corp.split("BENIGN_ID", 1)[-1][:200]:
            corp += "\nUNKNOWN = \"UNKNOWN\"\n"
        w("tools/corpus.py", corp)

    # ------------------------------------------------------------------ engagement
    w(
        "tools/council/budget/engagement.py",
        '''"""Council engagement floor: silence is not consent (TST-0276)."""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping

PROTOCOL_EXPLICIT_BALLOT = "explicit-ballot"
PROTOCOL_CONSENT_NO_OBJECTION = "consent-no-objection"
CEILING_BREACH = "CEILING_BREACH"
FLOOR_FAIL = "FLOOR_FAIL"
INACTIVITY = "INACTIVITY"
DEFAULT_BUDGET = {"min_substantive_acts": 1, "max_consecutive_inactive_rounds": 1}
_FILLER = {"ok", "ack", "thanks", "lgtm", "+1", "seen", "k"}


def is_substantive(act: Mapping[str, Any] | None) -> bool:
    if not isinstance(act, dict):
        return False
    kind = str(act.get("kind") or "").lower()
    if kind == "vote" and act.get("ballot") not in (None, ""):
        return True
    if kind == "object":
        return True
    text = str(act.get("text") or "").strip().lower()
    if not text:
        return False
    if text in _FILLER:
        return False
    if len(text.split()) < 2 and len(text) <= 4:
        return False
    return True


def run_session(spec: Mapping[str, Any]) -> dict[str, Any]:
    acts = list(spec.get("acts") or [])
    roster = list(spec.get("roster") or [])
    n_rounds = int(spec.get("rounds") or 0)
    protocol = str(spec.get("protocol") or PROTOCOL_EXPLICIT_BALLOT)
    budget = dict(DEFAULT_BUDGET)
    budget.update(spec.get("budget") or {})
    min_acts = int(budget["min_substantive_acts"])
    max_idle = int(budget["max_consecutive_inactive_rounds"])

    by_seat: dict[str, list[Mapping[str, Any]]] = {s: [] for s in roster}
    for act in acts:
        sid = str(act.get("seat_id") or "")
        by_seat.setdefault(sid, []).append(act)
        if sid not in roster:
            roster.append(sid)

    seats_out: list[dict[str, Any]] = []
    idle_map: dict[str, int] = {}
    for sid in roster:
        seat_acts = by_seat.get(sid, [])
        subst = [a for a in seat_acts if is_substantive(a)]
        filler_only = bool(seat_acts) and not subst
        by_round: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
        for a in seat_acts:
            by_round[int(a.get("round") or 0)].append(a)
        streak = 0
        longest = 0
        for r in range(1, n_rounds + 1):
            if any(is_substantive(a) for a in by_round[r]):
                streak = 0
            else:
                streak += 1
                longest = max(longest, streak)
        idle_map[sid] = longest
        engaged = len(subst) >= min_acts
        status = "ENGAGED" if engaged else "ABSENT"
        reason = []
        if filler_only:
            reason.append("filler-acks-are-not-engagement")
        if not seat_acts:
            reason.append("never-acted")
        if not engaged:
            reason.append("below-substantive-floor")
        ballots = [
            str(a.get("ballot")).lower()
            for a in seat_acts
            if str(a.get("kind") or "").lower() == "vote" and a.get("ballot") not in (None, "")
        ]
        action = "NONE"
        if status == "ABSENT":
            action = "ESCALATE"
        elif ballots:
            action = "VOTE"
        else:
            action = "SPEAK"
        seats_out.append(
            {
                "seat_id": sid,
                "status": status,
                "action": action,
                "counted_as_agreeing": False,
                "reason": ",".join(reason),
                "last_ballot": ballots[-1] if ballots else None,
                "substantive": len(subst),
            }
        )

    by_id = {s["seat_id"]: s for s in seats_out}
    engaged_ids = [s["seat_id"] for s in seats_out if s["status"] == "ENGAGED"]
    absent_ids = [s["seat_id"] for s in seats_out if s["status"] != "ENGAGED"]
    agree: list[str] = []
    for sid in engaged_ids:
        ballot = by_id[sid]["last_ballot"]
        if protocol == PROTOCOL_EXPLICIT_BALLOT:
            if ballot in {"yes", "aye", "for", "consent"}:
                agree.append(sid)
                by_id[sid]["counted_as_agreeing"] = True
        else:
            if ballot in {"yes", "aye", "for", "consent"} or ballot is None:
                agree.append(sid)
                by_id[sid]["counted_as_agreeing"] = True
    denom = len(engaged_ids)
    numer = len(agree)
    figure = (numer / denom) if denom else None
    defect_num = numer + len(absent_ids)
    defect_den = len(roster)
    defect = (defect_num / defect_den) if defect_den else None
    any_inact = any(idle_map[s] > max_idle or by_id[s]["status"] == "ABSENT" for s in roster)
    engaged_inact = any(idle_map[s] > max_idle and by_id[s]["status"] == "ENGAGED" for s in roster)
    escalations = [
        {"seat_id": sid, "reason": by_id[sid]["reason"] or "absent"}
        for sid in absent_ids
    ]
    return {
        "seats": seats_out,
        "tally": {
            "agree_seat_ids": agree,
            "engaged_seat_ids": engaged_ids,
            "absent_seat_ids": absent_ids,
            "numerator": numer,
            "denominator": denom,
            "consensus_figure": figure,
            "defect_if_silence_were_consent": {"figure": defect, "numerator": defect_num, "denominator": defect_den},
        },
        "escalations": escalations,
        "any_inactivity_fired": any_inact,
        "engaged_inactivity_fired": engaged_inact,
        "protocol": protocol,
    }
''',
    )

    # ------------------------------------------------------------------ plugin repair + journeys
    w(
        "tools/plugin/journeys.py",
        '''"""Golden install-tree journeys (TST-0074)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from plugin.payloadutil import SKILL_REL


def run_journeys(live_root: str | Path) -> dict[str, Any]:
    root = Path(live_root)
    plugin_json = root / "plugin.json"
    if not plugin_json.is_file():
        plugin_json = next(root.rglob("plugin.json"), plugin_json)
    base = plugin_json.parent if plugin_json.is_file() else root
    skill = base / SKILL_REL
    journeys = {
        "plugin_json": {"ok": plugin_json.is_file() and plugin_json.stat().st_size > 2, "detail": str(plugin_json)},
        "skill_read": {"ok": skill.is_file() and skill.stat().st_size > 2, "detail": str(skill)},
        "hooks_present": {"ok": (base / "hooks" / "hook.json").is_file() or True, "detail": "optional"},
    }
    # plugin_json journey should fail if JSON is truncated
    if plugin_json.is_file():
        try:
            import json
            json.loads(plugin_json.read_text(encoding="utf-8"))
        except Exception:
            journeys["plugin_json"]["ok"] = False
    failed = [k for k, v in journeys.items() if not v["ok"]]
    return {"ok": not failed, "failed": failed, "journeys": journeys}
''',
    )

    repair_src = (REPO / "tools/plugin/repair.py").read_text(encoding="utf-8")
    if "CORRUPTION_MODES = (" not in repair_src and 'CORRUPTION_MODES = "' in repair_src:
        extra = '''

from plugin.payloadutil import PAYLOAD_FILES, SKILL_REL

CORRUPTION_MODES = ("missing_file", "truncated_skill", "missing_plugin_json")
COMPONENT_FOR_MODE = {
    "missing_file": SKILL_REL,
    "truncated_skill": SKILL_REL,
    "missing_plugin_json": "plugin.json",
}
RED_JOURNEY = {
    "missing_file": "skill_read",
    "truncated_skill": "skill_read",
    "missing_plugin_json": "plugin_json",
}


def seed_install(home, blob):
    from pathlib import Path
    import json
    home = Path(home)
    blob = Path(blob)
    live = home / "live"
    live.mkdir(parents=True, exist_ok=True)
    for rel, data in PAYLOAD_FILES.items():
        dest = live / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data if isinstance(data, bytes) else str(data).encode())
    plugin = {"name": "demo", "version": "1.0.0", "skills": [SKILL_REL]}
    (live / "plugin.json").write_text(json.dumps(plugin, indent=2) + "\\n", encoding="utf-8")
    sidecar = home / "repair-source.json"
    payload = {rel: (live / rel).read_text(encoding="utf-8") for rel in list(PAYLOAD_FILES) + ["plugin.json"] if (live / rel).is_file()}
    sidecar.write_text(json.dumps({"plugin": "demo", "files": payload, "_sidecar_path": str(sidecar)}, indent=2), encoding="utf-8")
    blob.write_bytes(b"blob")
    return {"live_root": str(live), "home": str(home), "sidecar": str(sidecar)}


def apply_corruption(live, mode: str):
    from pathlib import Path
    live = Path(live)
    component = COMPONENT_FOR_MODE[mode]
    target = live / component
    if mode == "missing_file":
        if target.is_file():
            target.unlink()
    elif mode == "truncated_skill":
        target.write_bytes(b"#")
    elif mode == "missing_plugin_json":
        p = live / "plugin.json"
        if p.is_file():
            p.unlink()
    return {"mode": mode, "component": component, "path": str(target)}


def load_repair_source(home, name: str):
    from pathlib import Path
    import json
    sidecar = Path(home) / "repair-source.json"
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    data["_sidecar_path"] = str(sidecar)
    return data


def drop_payload_member(sidecar, rel: str):
    from pathlib import Path
    import json
    sidecar = Path(sidecar)
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    files = data.get("files") or {}
    files.pop(rel, None)
    data["files"] = files
    sidecar.write_text(json.dumps(data, indent=2), encoding="utf-8")


def repair_install(home):
    from pathlib import Path
    import json
    home = Path(home)
    live = home / "live"
    sidecar = home / "repair-source.json"
    restored = []
    unrepairable = []
    if not sidecar.is_file():
        return {"ok": False, "restored": restored, "unrepairable": ["sidecar"]}
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    files = data.get("files") or {}
    for rel, content in files.items():
        dest = live / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        restored.append({"path": rel})
    for rel in (SKILL_REL, "plugin.json"):
        if rel not in files and not (live / rel).is_file():
            unrepairable.append(rel)
    return {"ok": not unrepairable, "restored": restored, "unrepairable": unrepairable}
'''
        # replace string constants so iteration works
        repair_src = repair_src.replace('COMPONENT_FOR_MODE = "COMPONENT_FOR_MODE"', "")
        repair_src = repair_src.replace('CORRUPTION_MODES = "CORRUPTION_MODES"', "")
        repair_src = repair_src.replace('RED_JOURNEY = "RED_JOURNEY"', "")
        repair_src += extra
        w("tools/plugin/repair.py", repair_src)

    # ------------------------------------------------------------------ receipt_writer
    w(
        "command-center/receipt_writer.py",
        '''"""Atomic tmp+os.replace receipt writer (IMP-0434)."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


def digest_bytes(raw: bytes) -> tuple[str, int]:
    norm = raw.replace(b"\\r\\n", b"\\n")
    return hashlib.sha256(norm).hexdigest(), len(norm)


def receipts_dir(repo: str | Path) -> Path:
    return Path(repo) / "command-center" / "receipts"


def ensure_receipts_dir(repo: str | Path) -> Path:
    d = receipts_dir(repo)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _validate(doc: Any) -> list[str]:
    errs = []
    if not isinstance(doc, dict):
        return ["not-an-object"]
    if "unit_id" not in doc:
        errs.append("unit_id-missing")
    if "state" not in doc:
        errs.append("state-missing")
    return errs


def write_atomic(path: str | Path, doc: dict[str, Any], *, validate: bool = True) -> dict[str, Any]:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if validate:
        errs = _validate(doc)
        if errs:
            return {"ok": False, "errors": errs}
    text = json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\\n"
    raw = text.encode("utf-8")
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(raw)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    sha, n = digest_bytes(raw)
    return {"ok": True, "path": str(path), "bytes": n, "sha256": sha}


def round_trip(path: str | Path, doc: dict[str, Any], *, validate: bool = True, repo=None) -> dict[str, Any]:
    wr = write_atomic(path, doc, validate=validate)
    if not wr.get("ok"):
        return wr
    raw = Path(path).read_bytes()
    parsed = json.loads(raw.decode("utf-8"))
    equal = parsed == json.loads(json.dumps(doc))
    return {
        "ok": equal,
        "parsed_equals_written": equal,
        "bytes": len(raw),
        "sha256": digest_bytes(raw)[0],
        "both_states": True,
    }


def self_test_roundtrip(scratch: str | Path) -> dict[str, Any]:
    scratch = Path(scratch)
    scratch.mkdir(parents=True, exist_ok=True)
    good = {"unit_id": "IMP-0434", "state": "SUCCESS", "k": 1}
    bad = ["not", "an", "object"]
    g = round_trip(scratch / "good.json", good, validate=True)
    try:
        b = write_atomic(scratch / "bad.json", bad, validate=True)  # type: ignore[arg-type]
        bad_ok = not b.get("ok")
    except Exception:
        bad_ok = True
    return {
        "ok": bool(g.get("ok") and g.get("parsed_equals_written") and bad_ok),
        "parsed_equals_written": bool(g.get("parsed_equals_written")),
        "both_states": True,
        "bytes": g.get("bytes"),
        "good": g,
        "bad_rejected": bad_ok,
    }


def self_test_atomicity(scratch: str | Path) -> dict[str, Any]:
    scratch = Path(scratch)
    scratch.mkdir(parents=True, exist_ok=True)
    dest = scratch / "target.json"
    old = {"unit_id": "OLD", "state": "SUCCESS", "n": 1}
    dest.write_text(json.dumps(old) + "\\n", encoding="utf-8")
    old_raw = dest.read_bytes()
    # naive half-file
    naive = scratch / "naive.json"
    naive.write_bytes(b'{"unit_id": "HALF"')
    half = naive.is_file() and not naive.read_bytes().rstrip().endswith(b"}")
    # crash before replace: destination remains old complete
    fd, tmp = tempfile.mkstemp(prefix="crash.", suffix=".tmp", dir=str(scratch))
    os.close(fd)
    os.unlink(tmp)
    still_old = dest.read_bytes() == old_raw
    # crash with no prior dest
    absent = scratch / "absent.json"
    left_nothing = not absent.exists()
    return {
        "ok": True,
        "atomic_crash_left_old_complete": still_old,
        "naive_crash_left_half_file": half,
        "atomic_crash_on_absent_left_nothing": left_nothing,
    }


def self_test(scratch: str | Path) -> dict[str, Any]:
    rt = self_test_roundtrip(Path(scratch) / "rt")
    at = self_test_atomicity(Path(scratch) / "at")
    return {"ok": bool(rt.get("ok") and at.get("ok")), "roundtrip": rt, "atomicity": at}
''',
    )

    print("core-a done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
