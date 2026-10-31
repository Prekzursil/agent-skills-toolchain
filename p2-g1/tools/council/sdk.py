#!/usr/bin/env python3
"""Typed council SDK + CLI inspect (IMP-0326)."""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

ARTIFACT_KEYS = (
    "meta",
    "decision",
    "votes",
    "budgets",
    "stopping",
    "transcript",
)


class DecisionStatus(str, Enum):
    ADOPT = "ADOPT"
    REJECT = "REJECT"
    PARK = "PARK"


@dataclass(frozen=True)
class CouncilSpec:
    question: str
    seats: tuple[str, ...]
    rounds: int = 2


@dataclass
class Decision:
    status: DecisionStatus
    rationale: str = "majority"


@dataclass
class Meta:
    run_id: str
    spec_question: str


@dataclass
class Votes:
    for_count: int
    against_count: int
    ballots: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Budgets:
    turns: int
    tokens: int = 0


@dataclass
class Stopping:
    rounds_completed: int
    reason: str = "quorum"


@dataclass
class CouncilResult:
    meta: Meta
    decision: Decision
    votes: Votes
    budgets: Budgets
    stopping: Stopping
    transcript: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Parity:
    sdk_keys: list[str]
    cli_keys: list[str]
    sdk_minus_cli: list[str]
    cli_minus_sdk: list[str]
    equal: bool


def assert_typed_result(result: Any) -> None:
    if type(result) is not CouncilResult:
        raise TypeError(f"expected CouncilResult, got {type(result)!r}")
    if type(result.decision) is not Decision:
        raise TypeError("decision is not Decision")
    if type(result.decision.status) is not DecisionStatus:
        raise TypeError("decision.status is not DecisionStatus")


def sdk_reachable_keys(result: CouncilResult) -> set[str]:
    return set(ARTIFACT_KEYS)


def _cli_view(result: CouncilResult, hide: list[str] | None = None) -> dict[str, Any]:
    payload = {
        "meta": {"run_id": result.meta.run_id, "spec_question": result.meta.spec_question},
        "decision": {"status": result.decision.status.value, "rationale": result.decision.rationale},
        "votes": {
            "for_count": result.votes.for_count,
            "against_count": result.votes.against_count,
            "ballots": list(result.votes.ballots),
        },
        "budgets": {"turns": result.budgets.turns, "tokens": result.budgets.tokens},
        "stopping": {
            "rounds_completed": result.stopping.rounds_completed,
            "reason": result.stopping.reason,
        },
        "transcript": list(result.transcript),
    }
    for key in hide or []:
        payload.pop(key, None)
    return payload


def surface_parity(result: CouncilResult, hide_from_cli: list[str] | None = None) -> Parity:
    sdk = set(ARTIFACT_KEYS)
    cli = set(_cli_view(result, hide_from_cli))
    return Parity(
        sdk_keys=sorted(sdk),
        cli_keys=sorted(cli),
        sdk_minus_cli=sorted(sdk - cli),
        cli_minus_sdk=sorted(cli - sdk),
        equal=sdk == cli,
    )


class CouncilSpecBuilder:
    def __init__(self) -> None:
        self._question = "untitled"
        self._seats: list[str] = []
        self._rounds = 2

    def question(self, text: str) -> "CouncilSpecBuilder":
        self._question = text
        return self

    def seats(self, seats: list[str] | tuple[str, ...]) -> "CouncilSpecBuilder":
        self._seats = list(seats)
        return self

    def rounds(self, n: int) -> "CouncilSpecBuilder":
        self._rounds = int(n)
        return self

    def build(self) -> CouncilSpec:
        return CouncilSpec(question=self._question, seats=tuple(self._seats), rounds=self._rounds)


def execute_spec(spec: CouncilSpec, run_id: str = "run") -> CouncilResult:
    return CouncilSDK().execute(spec, run_id)


def jsonable(obj: Any) -> Any:
    if hasattr(obj, "__dict__"):
        return {k: jsonable(v) for k, v in vars(obj).items() if not k.startswith("_")}
    if isinstance(obj, (list, tuple)):
        return [jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {k: jsonable(v) for k, v in obj.items()}
    if isinstance(obj, Enum):
        return obj.value
    return obj


class CouncilSDK:
    def build_fixture(self) -> CouncilSpec:
        return CouncilSpec(
            question="Should we adopt the typed SDK artifact contract?",
            seats=("advocate", "critic", "scribe"),
            rounds=2,
        )

    def execute(self, spec: CouncilSpec, run_id: str) -> CouncilResult:
        ballots = [{"seat": s, "vote": "yes"} for s in spec.seats]
        return CouncilResult(
            meta=Meta(run_id=run_id, spec_question=spec.question),
            decision=Decision(status=DecisionStatus.ADOPT, rationale="unanimous-fixture"),
            votes=Votes(for_count=len(spec.seats), against_count=0, ballots=ballots),
            budgets=Budgets(turns=len(spec.seats) * spec.rounds, tokens=len(spec.seats) * 800),
            stopping=Stopping(rounds_completed=spec.rounds, reason="quorum"),
            transcript=[{"round": i + 1, "note": "fixture"} for i in range(spec.rounds)],
        )

    def inspect(self, result: CouncilResult) -> dict[str, Any]:
        return _cli_view(result)

    def persist(self, result: CouncilResult, run_dir: Path) -> Path:
        run_dir = Path(run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        path = run_dir / "council-result.json"
        path.write_text(json.dumps(_cli_view(result), indent=2) + "\n", encoding="utf-8")
        return path


def _cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    inspect_p = sub.add_parser("inspect")
    inspect_p.add_argument("--run-dir", required=True)
    inspect_p.add_argument("--hide", action="append", default=[])
    args = parser.parse_args(argv)
    if args.cmd == "inspect":
        path = Path(args.run_dir) / "council-result.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        for key in args.hide or []:
            data.pop(key, None)
        print(json.dumps(data))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(_cli())
