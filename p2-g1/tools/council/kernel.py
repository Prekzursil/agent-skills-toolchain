"""Council runtime kernel: round scheduler and turn state machine (IMP-0264)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence


class KernelError(RuntimeError):
    pass


@dataclass
class ExecutionPlan:
    council_id: str
    roster: Sequence[str]
    n_rounds: int = 1
    timeout_ms: int = 0
    max_chars: int = 0
    obligations: Sequence[str] = ()


@dataclass
class TurnSpec:
    participant_id: str
    obligations: Sequence[str] = ()
    timeout_ms: int = 0
    max_chars: int = 0


@dataclass
class TurnResponse:
    text: str = ""
    fields: dict[str, Any] | None = None
    elapsed_ms: int = 0
    timed_out: bool = False


class ScriptedAdapter:
    def __init__(self, response: TurnResponse) -> None:
        self.response = response

    def run(self, spec: TurnSpec) -> TurnResponse:
        return self.response


@dataclass
class Event:
    kind: str
    participant_id: str
    status: str
    output: str = ""
    obligations_missing: tuple[str, ...] = ()
    seq: int = 0
    round_index: int = 0
    turn_index: int = 0
    obligations: tuple[str, ...] = ()
    obligations_met: tuple[str, ...] = ()
    elapsed_ms: int = 0

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "participant_id": self.participant_id,
            "status": self.status,
            "output": self.output,
            "obligations_missing": list(self.obligations_missing),
            "seq": self.seq,
            "round_index": self.round_index,
            "turn_index": self.turn_index,
            "obligations": list(self.obligations),
            "obligations_met": list(self.obligations_met),
            "elapsed_ms": self.elapsed_ms,
        }


@dataclass
class RunResult:
    turns_executed: int
    turns_recorded: int
    invariant_ok: bool
    turn_order: tuple[str, ...]
    statuses: tuple[str, ...]
    events: list[Event]


class Kernel:
    def __init__(self, council_id: str) -> None:
        self.council_id = council_id
        self.events: tuple[Event, ...] = ()
        self.turns_executed = 0
        self.turns_recorded = 0
        self._in_round = False

    def run(self, plan: ExecutionPlan, topology: Any, adapters: dict[str, Any]) -> RunResult:
        order = list(topology.order(plan)) if hasattr(topology, "order") else list(plan.roster) * int(plan.n_rounds)
        events: list[Event] = []
        statuses: list[str] = []
        turn_order: list[str] = []
        self._in_round = True
        try:
            for pid in order:
                spec = TurnSpec(
                    participant_id=pid,
                    obligations=tuple(plan.obligations),
                    timeout_ms=int(plan.timeout_ms or 0),
                    max_chars=int(plan.max_chars or 0),
                )
                rec = self.execute_turn(spec, adapters.get(pid), plan)
                events.append(rec)
                statuses.append(rec.status)
                turn_order.append(pid)
        finally:
            self._in_round = False
        self.events = tuple(events)
        result = RunResult(
            turns_executed=self.turns_executed,
            turns_recorded=self.turns_recorded,
            invariant_ok=self.turns_executed == self.turns_recorded == len(order),
            turn_order=tuple(turn_order),
            statuses=tuple(statuses),
            events=events,
        )
        return result

    def execute_turn(
        self,
        spec: TurnSpec,
        adapter: Any = None,
        plan: ExecutionPlan | None = None,
    ) -> Event:
        if not self._in_round:
            raise KernelError("execute-turn-outside-round")
        self.turns_executed += 1
        resp = TurnResponse()
        if adapter is not None:
            if hasattr(adapter, "run"):
                resp = adapter.run(spec)
            elif isinstance(adapter, TurnResponse):
                resp = adapter
        return self._record(spec, resp, plan)

    def _record(
        self,
        spec: TurnSpec,
        resp: TurnResponse,
        plan: ExecutionPlan | None,
    ) -> Event:
        status = "ok"
        output = str(resp.text or "")
        missing: list[str] = []
        if resp.timed_out:
            status = "timeout"
        max_chars = int(spec.max_chars or 0)
        if status == "ok" and max_chars and len(output) > max_chars:
            output = output[:max_chars]
            status = "length_exceeded"
        fields = resp.fields if isinstance(resp.fields, dict) else {}
        if status == "ok":
            for ob in spec.obligations:
                if ob not in fields or fields.get(ob) in (None, ""):
                    missing.append(str(ob))
            if missing:
                status = "obligation_breach"
        rec = Event(
            kind="TURN",
            participant_id=spec.participant_id,
            status=status,
            output=output,
            obligations_missing=tuple(missing),
        )
        self.turns_recorded += 1
        return rec


def kernel_loop_records_turns() -> dict[str, bool]:
    src = Path(__file__).read_text(encoding="utf-8")
    return {
        "run_calls_execute_turn": "self.execute_turn(" in src,
        "execute_turn_calls_record": "self._record(" in src,
        "execute_turn_only_returns_record": "return self._record" in src,
    }


def audit_source(src: str, label: str = "") -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    if "participant.output" in src or "outputs[" in src:
        hits.append({"id": "direct-write-output", "label": label})
    if "events.append" in src and "TURN" in src and "execute_turn" not in src:
        hits.append({"id": "direct-write-events", "label": label})
    return hits


def audit_topology_callgraph(paths: Iterable[Any]) -> dict[str, Any]:
    findings = []
    for path in paths:
        p = Path(path)
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        hits = audit_source(text, label=str(p))
        findings.extend(hits)
    return {"finding_count": len(findings), "findings": findings}


def topology_module_paths(repo: Path) -> list[Path]:
    root = Path(repo) / "tools" / "council" / "topology"
    if not root.is_dir():
        return []
    return sorted(p for p in root.glob("*.py") if p.name != "__init__.py")
