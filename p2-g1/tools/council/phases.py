"""Divergence-to-convergence phase gate (IMP-0368)."""
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
    ideas: set[str] = set()
    objections: set[str] = set()
    rounds = 0
    entered = False
    premature = False
    for ev in rec.get("events") or []:
        kind = str(ev.get("kind") or "")
        if kind == "idea":
            ideas.add(str(ev.get("id") or f"i-{len(ideas)}"))
        elif kind == "objection":
            objections.add(str(ev.get("id") or f"o-{len(objections)}"))
        elif kind == "round":
            rounds += 1
        elif kind in {"begin_convergence", "converge", "enter_convergence"} or (
            kind == "phase" and str(ev.get("phase") or "") == "convergence"
        ):
            entered = True
            if not (len(ideas) >= need_i and len(objections) >= need_o):
                premature = True
    met = len(ideas) >= need_i and len(objections) >= need_o
    return {
        "id": rec.get("id"),
        "entered_convergence": entered,
        "premature": premature,
        "ideas_attained": len(ideas),
        "objections_attained": len(objections),
        "rounds_before_convergence": rounds,
        "quotas_met": met,
    }


def replay_through_gate(rec: dict[str, Any], gate_mode: GateMode = GateMode.ENFORCE) -> TransitionResult:
    quotas = rec.get("quotas") or {}
    m = PhaseMachine(
        idea_quota=int(quotas.get("ideas") or 0),
        objection_quota=int(quotas.get("objections") or 0),
        gate_mode=gate_mode,
        council_id=str(rec.get("id") or "fx"),
    )
    last = None
    for ev in rec.get("events") or []:
        kind = str(ev.get("kind") or "")
        if kind == "idea":
            m.record_idea(str(ev.get("id") or f"i-{id(ev)}"))
        elif kind == "objection":
            m.record_objection(str(ev.get("id") or f"o-{id(ev)}"))
        elif kind in {"begin_convergence", "converge", "enter_convergence"} or (
            kind == "phase" and str(ev.get("phase") or "") == "convergence"
        ):
            last = m.request_convergence()
            if not last.granted and gate_mode is GateMode.ENFORCE:
                result = last
                return {
                    "granted": result.granted,
                    "entered_convergence": bool(result.granted),
                    **result.event.as_dict(),
                    "result": result,
                }
    result = last if last is not None else m.request_convergence()
    return {
        "granted": result.granted,
        "entered_convergence": bool(result.granted),
        **result.event.as_dict(),
        "result": result,
    }


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
        enf_g = enf.get("granted") if isinstance(enf, dict) else enf.granted
        wrn_g = wrn.get("granted") if isinstance(wrn, dict) else wrn.granted
        if audit["premature"] and enf_g:
            enforce_success += 1
        if audit["premature"] and wrn_g:
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
