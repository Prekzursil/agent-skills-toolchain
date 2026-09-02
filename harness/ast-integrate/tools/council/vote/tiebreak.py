"""Declared tie-break rules. Implicit listing order is not a rule."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

class MissingSeedRecord(ValueError):
    """recorded-seed-coin-flip with no seed is not a listing-order coin flip."""


DECLARED_RULES = frozenset(
    {
        "chair-casting-vote",
        "seniority",
        "recorded-seed-coin-flip",
        "escalation",
        "no-decision",
    }
)


@dataclass(frozen=True)
class BallotOption:
    option_id: str
    votes: int


@dataclass(frozen=True)
class Member:
    member_id: str
    role: str
    seniority: int
    ballot: str


@dataclass(frozen=True)
class Policy:
    rule: str
    policy_id: str = ""
    seed: str | None = None


@dataclass(frozen=True)
class TieCase:
    question_id: str
    options: tuple[BallotOption, ...]
    members: tuple[Member, ...]


@dataclass(frozen=True)
class Decision:
    kind: str
    winner: str | None
    seed_used: str | None = None
    rule: str = ""

    def is_consumable_as_completed_decision(self) -> bool:
        return self.kind == "DECISION" and self.winner is not None


def permute_case(case: TieCase) -> TieCase:
    return TieCase(
        question_id=case.question_id,
        options=tuple(reversed(case.options)),
        members=tuple(reversed(case.members)),
    )


def _chair_ballot(case: TieCase) -> str | None:
    for member in case.members:
        if member.role == "chair":
            return member.ballot
    return None


def _seniority_ballot(case: TieCase) -> str | None:
    if not case.members:
        return None
    top = max(case.members, key=lambda m: (m.seniority, m.member_id))
    return top.ballot


def _coin(case: TieCase, seed: str | None) -> str:
    payload = f"{seed or ''}|{case.question_id}".encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    ids = sorted(opt.option_id for opt in case.options)
    if not ids:
        return ""
    return ids[int(digest[:8], 16) % len(ids)]


def resolve(case: TieCase, policy: Policy) -> Decision:
    rule = policy.rule
    if rule == "chair-casting-vote":
        return Decision(kind="DECISION", winner=_chair_ballot(case), rule=rule)
    if rule == "seniority":
        return Decision(kind="DECISION", winner=_seniority_ballot(case), rule=rule)
    if rule == "recorded-seed-coin-flip":
        if policy.seed is None or str(policy.seed) == "":
            raise MissingSeedRecord("recorded-seed-coin-flip requires a recorded seed")
        return Decision(
            kind="DECISION",
            winner=_coin(case, policy.seed),
            seed_used=policy.seed,
            rule=rule,
        )
    if rule == "escalation":
        return Decision(kind="ESCALATION", winner=None, rule=rule)
    if rule == "no-decision":
        return Decision(kind="NO-DECISION", winner=None, rule=rule)
    raise ValueError(f"unknown rule {rule}")


def reproduce(case: TieCase, policy: Policy, first: Decision) -> bool:
    return resolve(case, policy) == first


def implicit_order_mutant_winner(options: tuple[BallotOption, ...] | list[BallotOption]) -> str:
    """Listing-order mutant: first listed option wins. Discriminates seed-coin-flip."""
    rows = list(options)
    if not rows:
        return ""
    return rows[0].option_id


def policy_census(case: TieCase, policies: dict[str, Policy]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for name, policy in policies.items():
        decision = resolve(case, policy)
        out[name] = {
            "kind": decision.kind,
            "winner": decision.winner,
            "seed_used": decision.seed_used,
        }
    return out
