"""Committee topology: standing committees, caucuses, and report-up fidelity.

A council can split into standing committees (dealt from the sorted roster so
each mixes the clusters), and participants may self-organise into caucuses.
An *affinity* caucus forms around a seed from its nearest neighbours in
position space; a *random* caucus is a uniform draw of the same size. The
echo-chamber detector compares a caucus's position spread with the mean spread
of random draws of that size: an affinity caucus whose spread is below
``max_ratio`` of the random baseline is flagged, a random draw is not.

Every group deliberates through a kernel (``kernel.execute_turn``) so each
turn is recorded once; a group's report-up conclusion must cite only its own
members' turns, cover every member, and carry the position those turns
support. :func:`report_up_fidelity` checks exactly that, and the two mutators
exist so a probe can show the check fires on a foreign or dropped citation.
"""

from __future__ import annotations

import random
import statistics
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

DEFAULT_MAX_RATIO = 0.5
DEFAULT_BASELINE_DRAWS = 200
POSITION_TOLERANCE = 1e-9


class RosterError(ValueError):
    """Roster problems: duplicates, unknown ids, or a group larger than the roster."""


@dataclass(frozen=True)
class Participant:
    id: str
    position: float
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class Group:
    id: str
    kind: str
    member_ids: tuple[str, ...]


@dataclass(frozen=True)
class Turn:
    turn_id: str
    group_id: str
    participant_id: str
    prompt: str
    text: str
    position: float


@dataclass(frozen=True)
class Conclusion:
    group_id: str
    member_ids: tuple[str, ...]
    position: float
    cited_turn_ids: tuple[str, ...]
    text: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "group_id": self.group_id,
            "member_ids": list(self.member_ids),
            "position": self.position,
            "cited_turn_ids": list(self.cited_turn_ids),
            "text": self.text,
        }


@dataclass(frozen=True)
class Deliberation:
    group: Group
    turns: tuple[Turn, ...]
    conclusion: Conclusion

    @property
    def prompts(self) -> tuple[str, ...]:
        return tuple(t.prompt for t in self.turns)


@dataclass(frozen=True)
class EchoVerdict:
    echo_chamber: bool
    observed_spread: float
    random_baseline_spread: float
    ratio: float
    max_ratio: float
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "echo_chamber": self.echo_chamber,
            "observed_spread": self.observed_spread,
            "random_baseline_spread": self.random_baseline_spread,
            "ratio": self.ratio,
            "max_ratio": self.max_ratio,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class FidelityVerdict:
    ok: bool
    reason: str
    missing_turn_ids: tuple[str, ...]
    foreign_turn_ids: tuple[str, ...]
    uncovered_member_ids: tuple[str, ...]
    position_matches: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "reason": self.reason,
            "missing_turn_ids": list(self.missing_turn_ids),
            "foreign_turn_ids": list(self.foreign_turn_ids),
            "uncovered_member_ids": list(self.uncovered_member_ids),
            "position_matches": self.position_matches,
        }


@dataclass(frozen=True)
class SpreadReport:
    affinity_member_ids: tuple[str, ...]
    random_member_ids: tuple[str, ...]
    affinity_spread: float
    random_spread: float
    baseline_spread: float
    affinity_echo: EchoVerdict
    random_echo: EchoVerdict

    @property
    def affinity_reduced_vs_random(self) -> bool:
        return self.affinity_spread < self.random_spread

    def as_dict(self) -> dict[str, Any]:
        return {
            "affinity_member_ids": list(self.affinity_member_ids),
            "random_member_ids": list(self.random_member_ids),
            "affinity_spread": self.affinity_spread,
            "random_spread": self.random_spread,
            "baseline_spread": self.baseline_spread,
            "affinity_echo": self.affinity_echo.as_dict(),
            "random_echo": self.random_echo.as_dict(),
            "affinity_reduced_vs_random": self.affinity_reduced_vs_random,
        }


class RecordingKernel:
    """Executes turns and records every one of them, in order, once."""

    def __init__(self, roster: Iterable[Participant]) -> None:
        self.participants = _index(roster)
        self.turns: list[Turn] = []
        self._executed = 0

    def execute_turn(self, group_id: str, participant_id: str, prompt: str) -> Turn:
        participant = self.participants.get(participant_id)
        if participant is None:
            raise RosterError(f"{participant_id} is not on the roster")
        self._executed += 1
        turn = Turn(
            turn_id=f"t-{self._executed}",
            group_id=group_id,
            participant_id=participant_id,
            prompt=prompt,
            text=f"{participant_id} in {group_id}: position {participant.position:+.2f}",
            position=float(participant.position),
        )
        self.turns.append(turn)
        return turn

    def turn(self, turn_id: str) -> Turn | None:
        for t in self.turns:
            if t.turn_id == turn_id:
                return t
        return None

    @property
    def turns_executed(self) -> int:
        return self._executed

    @property
    def turns_recorded(self) -> int:
        return len(self.turns)


def _index(roster: Iterable[Participant]) -> dict[str, Participant]:
    out: dict[str, Participant] = {}
    for p in roster:
        if p.id in out:
            raise RosterError(f"duplicate participant id {p.id}")
        out[p.id] = p
    if not out:
        raise RosterError("roster is empty")
    return out


def spread(positions: Sequence[float]) -> float:
    """Sample standard deviation; 0.0 for fewer than two positions."""
    values = [float(v) for v in positions]
    if len(values) < 2:
        return 0.0
    return statistics.stdev(values)


def cluster_tags(group: Group, roster: Iterable[Participant]) -> set[str]:
    index = _index(roster)
    tags: set[str] = set()
    for mid in group.member_ids:
        if mid not in index:
            raise RosterError(f"{mid} is not on the roster")
        tags.update(index[mid].tags)
    return tags


def form_standing_committees(
    roster: Iterable[Participant], n_standing: int
) -> tuple[Group, ...]:
    """Deal the sorted roster round-robin into ``n_standing`` committees."""
    if n_standing < 1:
        raise ValueError("n_standing must be >= 1")
    ids = sorted(_index(roster))
    buckets: list[list[str]] = [[] for _ in range(n_standing)]
    for i, pid in enumerate(ids):
        buckets[i % n_standing].append(pid)
    return tuple(
        Group(id=f"standing-{i}", kind="standing", member_ids=tuple(b))
        for i, b in enumerate(buckets)
    )


def form_affinity_caucus(
    roster: Iterable[Participant],
    seed_id: str,
    size: int,
    *,
    group_id: str = "caucus-affinity",
) -> Group:
    """The ``size`` participants nearest the seed in position (seed included)."""
    index = _index(roster)
    if seed_id not in index:
        raise RosterError(f"affinity seed {seed_id} is not on the roster")
    if size < 1 or size > len(index):
        raise RosterError(f"caucus size {size} out of range for roster of {len(index)}")
    seed = index[seed_id]
    ordered = sorted(
        index.values(),
        key=lambda p: (p.id != seed_id, abs(p.position - seed.position), p.id),
    )
    members = tuple(sorted(p.id for p in ordered[:size]))
    return Group(id=group_id, kind="caucus", member_ids=members)


def form_random_caucus(
    roster: Iterable[Participant],
    size: int,
    rng: random.Random,
    *,
    group_id: str = "caucus-random",
) -> Group:
    ids = sorted(_index(roster))
    if size < 1 or size > len(ids):
        raise RosterError(f"caucus size {size} out of range for roster of {len(ids)}")
    return Group(
        id=group_id, kind="caucus", member_ids=tuple(sorted(rng.sample(ids, size)))
    )


def random_baseline_spread(
    roster: Iterable[Participant],
    size: int,
    rng: random.Random,
    *,
    n_draws: int = DEFAULT_BASELINE_DRAWS,
) -> float:
    """Mean sample spread over ``n_draws`` uniform caucuses of ``size``."""
    index = _index(roster)
    ids = sorted(index)
    if size < 2 or size > len(ids):
        raise RosterError(f"baseline needs 2 <= size <= {len(ids)}, got {size}")
    if n_draws < 1:
        raise ValueError("n_draws must be >= 1")
    total = 0.0
    for _ in range(n_draws):
        draw = rng.sample(ids, size)
        total += spread([index[pid].position for pid in draw])
    return total / n_draws


def echo_chamber_check(
    observed_spread: float,
    baseline_spread: float,
    *,
    max_ratio: float = DEFAULT_MAX_RATIO,
) -> EchoVerdict:
    """Flag a group whose spread is below ``max_ratio`` of the random baseline."""
    if baseline_spread <= 0:
        return EchoVerdict(
            echo_chamber=False,
            observed_spread=float(observed_spread),
            random_baseline_spread=float(baseline_spread),
            ratio=float("inf"),
            max_ratio=max_ratio,
            reason="degenerate_baseline",
        )
    ratio = float(observed_spread) / float(baseline_spread)
    flagged = ratio < max_ratio
    return EchoVerdict(
        echo_chamber=flagged,
        observed_spread=float(observed_spread),
        random_baseline_spread=float(baseline_spread),
        ratio=ratio,
        max_ratio=max_ratio,
        reason="spread_below_ratio" if flagged else "spread_at_or_above_ratio",
    )


def build_prompt(question: str, group: Group, participant_id: str) -> str:
    """Prompt for one member. Names only the group's own members, so a foreign
    participant id in a prompt is a leak the session can detect."""
    others = [m for m in group.member_ids if m != participant_id]
    return (
        f"[{group.id}] Question: {question}\n"
        f"You are {participant_id}. Fellow members: {', '.join(others) or '(none)'}.\n"
        "State your position and the reason for it."
    )


def deliberate_group(
    group: Group,
    roster: Iterable[Participant],
    question: str,
    kernel: RecordingKernel,
) -> Deliberation:
    """One turn per member through the kernel, then a report-up conclusion that
    cites every turn and carries the mean position of the members."""
    index = _index(roster)
    turns: list[Turn] = []
    for mid in group.member_ids:
        if mid not in index:
            raise RosterError(f"{mid} is not on the roster")
        turns.append(
            kernel.execute_turn(group.id, mid, build_prompt(question, group, mid))
        )
    position = statistics.fmean([t.position for t in turns]) if turns else 0.0
    cited = tuple(t.turn_id for t in turns)
    conclusion = Conclusion(
        group_id=group.id,
        member_ids=tuple(group.member_ids),
        position=position,
        cited_turn_ids=cited,
        text=f"report-up {group.id} position={position:.6f} cites={','.join(cited)}",
    )
    return Deliberation(group=group, turns=tuple(turns), conclusion=conclusion)


def report_up_fidelity(
    conclusion: Conclusion, kernel: RecordingKernel
) -> FidelityVerdict:
    """Every citation must exist, belong to this group's members, cover every
    member, and support the reported position."""
    cited = [kernel.turn(tid) for tid in conclusion.cited_turn_ids]
    missing = tuple(
        tid
        for tid, t in zip(conclusion.cited_turn_ids, cited, strict=True)
        if t is None
    )
    present = [t for t in cited if t is not None]
    members = set(conclusion.member_ids)
    foreign = tuple(
        t.turn_id
        for t in present
        if t.group_id != conclusion.group_id or t.participant_id not in members
    )
    own = [t for t in present if t.turn_id not in foreign]
    covered = {t.participant_id for t in own}
    uncovered = tuple(m for m in conclusion.member_ids if m not in covered)
    if own and not foreign and not missing:
        supported = statistics.fmean([t.position for t in own])
        position_matches = abs(supported - conclusion.position) <= POSITION_TOLERANCE
    else:
        position_matches = False

    if missing:
        reason = "cites_unknown_turn"
    elif foreign:
        reason = "cites_foreign_turn"
    elif uncovered:
        reason = "member_not_cited"
    elif not position_matches:
        reason = "position_not_supported"
    else:
        reason = "traceable"
    return FidelityVerdict(
        ok=reason == "traceable",
        reason=reason,
        missing_turn_ids=missing,
        foreign_turn_ids=foreign,
        uncovered_member_ids=uncovered,
        position_matches=position_matches,
    )


def mutate_foreign_citation(conclusion: Conclusion, foreign_turn_id: str) -> Conclusion:
    """A conclusion that additionally cites a turn from outside the group."""
    return replace(
        conclusion, cited_turn_ids=(*conclusion.cited_turn_ids, str(foreign_turn_id))
    )


def mutate_drop_citation(conclusion: Conclusion) -> Conclusion:
    """A conclusion that silently drops one member's turn from its citations."""
    if not conclusion.cited_turn_ids:
        return conclusion
    return replace(conclusion, cited_turn_ids=conclusion.cited_turn_ids[:-1])


def prompts_isolated(deliberation: Deliberation, roster: Iterable[Participant]) -> bool:
    """True when no prompt in the deliberation names a non-member."""
    outsiders = [
        pid for pid in _index(roster) if pid not in deliberation.group.member_ids
    ]
    return not any(
        pid in prompt for prompt in deliberation.prompts for pid in outsiders
    )


@dataclass
class CommitteeSession:
    question: str
    roster: tuple[Participant, ...]
    standing: tuple[Group, ...]
    caucuses: tuple[Group, ...]
    deliberations: list[Deliberation]
    spread: SpreadReport
    kernel: RecordingKernel
    fidelity: list[FidelityVerdict] = field(default_factory=list)
    isolation_ok: bool = True

    @property
    def all_faithful(self) -> bool:
        return bool(self.fidelity) and all(f.ok for f in self.fidelity)

    @property
    def turns_executed(self) -> int:
        return self.kernel.turns_executed

    @property
    def turns_recorded(self) -> int:
        return self.kernel.turns_recorded

    @property
    def report_up(self) -> list[Conclusion]:
        return [d.conclusion for d in self.deliberations]

    def as_dict(self) -> dict[str, Any]:
        return {
            "topology": "committee",
            "question": self.question,
            "standing": [
                {"id": g.id, "kind": g.kind, "member_ids": list(g.member_ids)}
                for g in self.standing
            ],
            "caucuses": [
                {"id": g.id, "kind": g.kind, "member_ids": list(g.member_ids)}
                for g in self.caucuses
            ],
            "report_up": [c.as_dict() for c in self.report_up],
            "fidelity": [f.as_dict() for f in self.fidelity],
            "spread": self.spread.as_dict(),
            "all_faithful": self.all_faithful,
            "isolation_ok": self.isolation_ok,
            "turns_executed": self.turns_executed,
            "turns_recorded": self.turns_recorded,
        }


def run_session(
    roster: Sequence[Participant],
    *,
    question: str,
    caucus_size: int,
    n_standing: int,
    affinity_seed_id: str,
    random_rng: random.Random,
    baseline_rng: random.Random,
    kernel: RecordingKernel | None = None,
    max_ratio: float = DEFAULT_MAX_RATIO,
    baseline_draws: int = DEFAULT_BASELINE_DRAWS,
) -> CommitteeSession:
    """Form standing committees and both caucuses, deliberate each through the
    kernel, then measure spread, echo-chamber status and report-up fidelity."""
    members = tuple(roster)
    index = _index(members)
    kernel = kernel if kernel is not None else RecordingKernel(members)

    standing = form_standing_committees(members, n_standing)
    affinity = form_affinity_caucus(members, affinity_seed_id, caucus_size)
    random_group = form_random_caucus(members, caucus_size, random_rng)
    caucuses = (affinity, random_group)

    deliberations = [
        deliberate_group(g, members, question, kernel) for g in (*standing, *caucuses)
    ]
    fidelity = [report_up_fidelity(d.conclusion, kernel) for d in deliberations]
    isolation_ok = all(prompts_isolated(d, members) for d in deliberations)

    baseline = random_baseline_spread(
        members, caucus_size, baseline_rng, n_draws=baseline_draws
    )
    affinity_spread = spread([index[m].position for m in affinity.member_ids])
    random_spread = spread([index[m].position for m in random_group.member_ids])
    report = SpreadReport(
        affinity_member_ids=affinity.member_ids,
        random_member_ids=random_group.member_ids,
        affinity_spread=affinity_spread,
        random_spread=random_spread,
        baseline_spread=baseline,
        affinity_echo=echo_chamber_check(
            affinity_spread, baseline, max_ratio=max_ratio
        ),
        random_echo=echo_chamber_check(random_spread, baseline, max_ratio=max_ratio),
    )
    return CommitteeSession(
        question=question,
        roster=members,
        standing=standing,
        caucuses=caucuses,
        deliberations=deliberations,
        spread=report,
        kernel=kernel,
        fidelity=fidelity,
        isolation_ok=isolation_ok,
    )


__all__ = [
    "DEFAULT_BASELINE_DRAWS",
    "DEFAULT_MAX_RATIO",
    "CommitteeSession",
    "Conclusion",
    "Deliberation",
    "EchoVerdict",
    "FidelityVerdict",
    "Group",
    "Participant",
    "RecordingKernel",
    "RosterError",
    "SpreadReport",
    "Turn",
    "build_prompt",
    "cluster_tags",
    "deliberate_group",
    "echo_chamber_check",
    "form_affinity_caucus",
    "form_random_caucus",
    "form_standing_committees",
    "mutate_drop_citation",
    "mutate_foreign_citation",
    "prompts_isolated",
    "random_baseline_spread",
    "report_up_fidelity",
    "run_session",
    "spread",
]
