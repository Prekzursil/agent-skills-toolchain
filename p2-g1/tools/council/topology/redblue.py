"""Red/blue topology with cross-team token scan (IMP-0284)."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any


def mint_token(team: str, salt: str) -> str:
    digest = hashlib.sha256(f"{team}:{salt}".encode("utf-8")).hexdigest()[:16]
    return f"CANARY-{team.upper()}-{digest}"


@dataclass
class Scorecard:
    scores: dict[str, int]
    winner: str

    def as_dict(self) -> dict[str, Any]:
        return {"scores": dict(self.scores), "winner": self.winner}


@dataclass
class Finding:
    seat_id: str
    team: str
    foreign_token: str
    text: str
    token: str = ""
    prompt_team: str = ""
    owner_team: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "seat_id": self.seat_id,
            "team": self.team,
            "foreign_token": self.foreign_token,
            "token": self.token or self.foreign_token,
            "prompt_team": self.prompt_team or self.team,
            "owner_team": self.owner_team,
            "text": self.text,
        }


@dataclass
class Prompt:
    seat_id: str
    team: str
    text: str


@dataclass
class ExchangeResult:
    prompts: list[Prompt]
    seats: list[str]
    turns_executed: int
    findings: list[Finding]
    scorecard: Scorecard

    def as_dict(self) -> dict[str, Any]:
        return {
            "findings": [f.as_dict() for f in self.findings],
            "turns_executed": self.turns_executed,
            "seats": list(self.seats),
            "scorecard": self.scorecard.as_dict(),
        }


class RecordingKernel:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self.turns_executed = 0

    def record(self, event: dict[str, Any]) -> None:
        self.turns_executed += 1
        self.events.append(event)


def default_fixture_assignment() -> dict[str, str]:
    return {"red-1": "red", "red-2": "red", "blue-1": "blue", "blue-2": "blue"}


def default_fixture_moves() -> list[dict[str, Any]]:
    return [
        {"team": "red", "points": 2},
        {"team": "blue", "points": 1},
        {"team": "red", "points": 1},
        {"team": "blue", "points": 1},
    ]


def score_exchange(moves: list[dict[str, Any]]) -> Scorecard:
    scores: dict[str, int] = {"red": 0, "blue": 0}
    for move in moves:
        team = str(move.get("team"))
        scores[team] = scores.get(team, 0) + int(move.get("points") or 0)
    winner = max(scores, key=lambda t: (scores[t], t == "red"))
    return Scorecard(scores=scores, winner=winner)


def token_owner(token: str) -> str:
    parts = str(token).split("-")
    if len(parts) >= 2:
        return parts[1].lower()
    return ""


def scan_cross_team_tokens(prompts: list[Prompt]) -> list[Finding]:
    import re

    pat = re.compile(r"CANARY-(RED|BLUE)-[a-f0-9]+")
    findings: list[Finding] = []
    for prompt in prompts:
        for match in pat.finditer(prompt.text):
            owner = match.group(1).lower()
            tok = match.group(0)
            if owner != prompt.team:
                findings.append(
                    Finding(
                        seat_id=prompt.seat_id,
                        team=prompt.team,
                        foreign_token=tok,
                        text=prompt.text,
                        token=tok,
                        prompt_team=prompt.team,
                        owner_team=owner,
                    )
                )
    return findings


def known_shared_fixture() -> tuple[Prompt, Prompt, str]:
    shared = mint_token("blue", "clean-fixture:blue")
    blue = Prompt(seat_id="blue-1", team="blue", text=f"blue huddle {shared}")
    red = Prompt(seat_id="red-1", team="red", text=f"red leaked {shared}")
    return blue, red, shared


def deliberate_leak_fixture() -> tuple[Prompt, Prompt, str]:
    leak = mint_token("blue", "deliberate-leak")
    clean = Prompt(seat_id="red-clean", team="red", text="red huddle no-leak")
    leaked = Prompt(seat_id="red-leak", team="red", text=f"red huddle {leak}")
    return clean, leaked, leak


def run_clean_fixture(kernel: RecordingKernel | None = None) -> ExchangeResult:
    kernel = kernel or RecordingKernel()
    assignment = default_fixture_assignment()
    tokens = {
        "red": mint_token("red", "clean-fixture:red"),
        "blue": mint_token("blue", "clean-fixture:blue"),
    }
    prompts: list[Prompt] = []
    seats = list(assignment)
    for seat_id, team in assignment.items():
        text = f"huddle {seat_id} token={tokens[team]} mission=clean"
        prompts.append(Prompt(seat_id=seat_id, team=team, text=text))
        kernel.record({"seat_id": seat_id, "team": team, "text": text})
    scorecard = score_exchange(default_fixture_moves())
    return ExchangeResult(
        prompts=prompts,
        seats=seats,
        turns_executed=len(seats),
        findings=scan_cross_team_tokens(prompts),
        scorecard=scorecard,
    )


__all__ = [
    "ExchangeResult",
    "Finding",
    "Prompt",
    "RecordingKernel",
    "Scorecard",
    "default_fixture_assignment",
    "default_fixture_moves",
    "mint_token",
    "run_clean_fixture",
    "scan_cross_team_tokens",
    "score_exchange",
]
