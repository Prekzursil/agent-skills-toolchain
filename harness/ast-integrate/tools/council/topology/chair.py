"""Chair-led council topology: rotation, chair powers, moderator-capture guard.

A chair holds two powers and only two: setting the agenda for the round and
recognising *one* participant to hold the floor. The chair rotates on a fixed
schedule so no single participant keeps the powers. Every participant submits
every round into a local journal that the chair cannot edit, so a chair who
never recognises a dissenter can starve them of the floor but cannot make their
submissions disappear from the artifact (the failure class in
_USER-PROMPTS.md:11172-11244: moderator capture).

Two independent checks make capture visible instead of silent:

* :func:`moderator_capture_guard` compares the recognition log against the fair
  schedule (equal shares of the floor) and FIRES when a participant is starved
  or the distribution departs from fair beyond the chi-square threshold.
* :func:`independent_submission_check` compares the journal against the
  artifact *without consulting the recognition log*, so an artifact that drops
  unrecognised rows fails even when the guard is quiet.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

# Chi-square critical values at alpha=0.05 by degrees of freedom (1..10).
_CHI2_CRIT_05: dict[int, float] = {
    1: 3.841,
    2: 5.991,
    3: 7.815,
    4: 9.488,
    5: 11.070,
    6: 12.592,
    7: 14.067,
    8: 15.507,
    9: 16.919,
    10: 18.307,
}
# A participant holding less than this fraction of their fair share is starved.
STARVATION_FRACTION = 0.5

POLICIES = ("even", "skewed")


class ChairPowerError(PermissionError):
    """A non-chair tried to exercise a chair power."""


class RosterError(ValueError):
    """Roster is empty, has duplicates, or names an unknown participant."""


@dataclass(frozen=True)
class Submission:
    """One journalled submission. Journalled whether or not it was recognised."""

    submission_id: str
    participant_id: str
    round: int
    text: str


@dataclass(frozen=True)
class Recognition:
    """The chair gave ``participant_id`` the floor in ``round``."""

    round: int
    chair_id: str
    participant_id: str


@dataclass(frozen=True)
class AgendaItem:
    round: int
    chair_id: str
    agenda: str


@dataclass(frozen=True)
class CaptureVerdict:
    """Result of the moderator-capture guard."""

    flagged: bool
    starved: tuple[str, ...]
    actual_counts: dict[str, int]
    fair_counts: dict[str, float]
    chi_square: float
    max_abs_diff: float
    n_slots: int
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "flagged": self.flagged,
            "starved": list(self.starved),
            "actual_counts": dict(self.actual_counts),
            "fair_counts": dict(self.fair_counts),
            "chi_square": self.chi_square,
            "max_abs_diff": self.max_abs_diff,
            "n_slots": self.n_slots,
            "reason": self.reason,
        }


def _validate_roster(roster: Sequence[str]) -> tuple[str, ...]:
    ids = tuple(str(p) for p in roster)
    if not ids:
        raise RosterError("roster must name at least one participant")
    if len(set(ids)) != len(ids):
        raise RosterError(f"roster has duplicate participants: {ids}")
    return ids


def expected_chair_sequence(
    roster: Sequence[str], n_rounds: int, *, rotate_every: int = 1
) -> list[str]:
    """The chair for each round under fixed rotation: the chair advances one
    seat every ``rotate_every`` rounds, starting from the first roster entry."""
    ids = _validate_roster(roster)
    if n_rounds < 0:
        raise ValueError("n_rounds must be >= 0")
    if rotate_every < 1:
        raise ValueError("rotate_every must be >= 1")
    return [ids[(r // rotate_every) % len(ids)] for r in range(int(n_rounds))]


def recognition_distribution(
    recognitions: Iterable[Recognition], roster: Sequence[str]
) -> dict[str, dict[str, float | int]]:
    """Per-participant recognition count and share, computed from the log."""
    ids = _validate_roster(roster)
    counts = {p: 0 for p in ids}
    for rec in recognitions:
        if rec.participant_id in counts:
            counts[rec.participant_id] += 1
    total = sum(counts.values())
    return {
        p: {
            "recognitions": counts[p],
            "recognition_share": (counts[p] / total) if total else 0.0,
        }
        for p in ids
    }


def moderator_capture_guard(
    recognitions: Iterable[Recognition],
    roster: Sequence[str],
    *,
    n_slots: int | None = None,
) -> CaptureVerdict:
    """Compare the recognition log with the fair schedule.

    Fair share is ``n_slots / len(roster)`` recognitions each. The guard FIRES
    when any participant received less than :data:`STARVATION_FRACTION` of
    their fair share (starvation) or when the chi-square statistic against the
    fair schedule exceeds the alpha=0.05 critical value. It is SILENT on an
    even-handed chair.
    """
    ids = _validate_roster(roster)
    recs = list(recognitions)
    actual = {p: 0 for p in ids}
    for rec in recs:
        if rec.participant_id in actual:
            actual[rec.participant_id] += 1
    slots = len(recs) if n_slots is None else int(n_slots)
    fair_each = slots / len(ids) if ids else 0.0
    fair = {p: fair_each for p in ids}

    chi_square = 0.0
    max_abs_diff = 0.0
    if fair_each > 0:
        for p in ids:
            diff = actual[p] - fair_each
            chi_square += (diff * diff) / fair_each
            max_abs_diff = max(max_abs_diff, abs(diff))
    chi_square = round(chi_square, 6)
    if float(max_abs_diff).is_integer():
        max_abs_diff = int(max_abs_diff)
    if float(fair_each).is_integer():
        fair = {p: int(fair_each) for p in ids}

    starved = tuple(
        p for p in ids if fair_each >= 1 and actual[p] < fair_each * STARVATION_FRACTION
    )
    df = max(len(ids) - 1, 1)
    critical = _CHI2_CRIT_05.get(df, 18.307 + 1.5 * (df - 10))
    skewed = chi_square > critical

    if starved:
        reason = "starved:" + ",".join(starved)
    elif skewed:
        reason = f"chi-square {chi_square} > {critical} (df={df})"
    else:
        reason = "even-handed"
    return CaptureVerdict(
        flagged=bool(starved or skewed),
        starved=starved,
        actual_counts=actual,
        fair_counts=fair,
        chi_square=chi_square,
        max_abs_diff=max_abs_diff,
        n_slots=slots,
        reason=reason,
    )


def independent_submission_check(
    submissions: Iterable[Submission], artifact: Mapping[str, Any]
) -> dict[str, Any]:
    """Every journalled submission must appear in the artifact, with the same
    participant. Deliberately ignores the recognition log: recognition decides
    who held the floor, never whose words survive."""
    journal = {s.submission_id: s for s in submissions}
    rows = [r for r in (artifact.get("submissions") or []) if isinstance(r, Mapping)]
    art_ids = {str(r.get("id")): r for r in rows if r.get("id") is not None}
    missing = sorted(sid for sid in journal if sid not in art_ids)
    extra = sorted(sid for sid in art_ids if sid not in journal)
    mismatch = sorted(
        sid
        for sid, sub in journal.items()
        if sid in art_ids and art_ids[sid].get("participant_id") != sub.participant_id
    )
    return {
        "journal_count": len(journal),
        "artifact_count": len(rows),
        "missing_from_artifact": missing,
        "extra_in_artifact": extra,
        "participant_mismatch": mismatch,
        "consulted_recognition_log": False,
        "pass": not missing
        and not extra
        and not mismatch
        and len(rows) == len(journal),
    }


@dataclass
class ChairLedSession:
    """A chair-led session with a local journal (not a shared kernel).

    ``chair_history[r]`` is the chair of round ``r``. Powers are checked
    against the *current* chair; denials raise :class:`ChairPowerError` and are
    also journalled so a probe can count them.
    """

    roster: tuple[str, ...]
    n_rounds: int
    rotate_every: int = 1
    chair_history: list[str] = field(default_factory=list)
    agenda: list[AgendaItem] = field(default_factory=list)
    submissions: list[Submission] = field(default_factory=list)
    recognitions: list[Recognition] = field(default_factory=list)
    denials: list[dict[str, Any]] = field(default_factory=list)
    round: int = -1
    _seq: int = 0

    def __post_init__(self) -> None:
        self.roster = _validate_roster(self.roster)
        if self.n_rounds < 0:
            raise ValueError("n_rounds must be >= 0")
        self.chair_history = expected_chair_sequence(
            self.roster, self.n_rounds, rotate_every=self.rotate_every
        )

    # -- round control -----------------------------------------------------
    @property
    def chair(self) -> str | None:
        if 0 <= self.round < len(self.chair_history):
            return self.chair_history[self.round]
        return None

    def open_round(self) -> str:
        if self.round + 1 >= self.n_rounds:
            raise IndexError(f"session has only {self.n_rounds} rounds")
        self.round += 1
        return self.chair_history[self.round]

    def _require_chair(self, actor: str, power: str) -> None:
        if actor != self.chair:
            self.denials.append(
                {
                    "round": self.round,
                    "actor": actor,
                    "power": power,
                    "chair": self.chair,
                }
            )
            raise ChairPowerError(
                f"{actor} is not the chair of round {self.round} ({self.chair}); "
                f"{power} denied"
            )

    # -- chair powers ------------------------------------------------------
    def set_agenda(self, actor: str, agenda: str) -> AgendaItem:
        self._require_chair(actor, "set_agenda")
        item = AgendaItem(round=self.round, chair_id=actor, agenda=str(agenda))
        self.agenda.append(item)
        return item

    def recognize(self, actor: str, participant_id: str) -> Recognition:
        self._require_chair(actor, "recognize")
        if participant_id not in self.roster:
            raise RosterError(f"{participant_id} is not on the roster")
        if any(r.round == self.round for r in self.recognitions):
            raise ChairPowerError(
                f"round {self.round} already has a recognised speaker"
            )
        rec = Recognition(
            round=self.round, chair_id=actor, participant_id=participant_id
        )
        self.recognitions.append(rec)
        return rec

    # -- participant action (no chair gate) --------------------------------
    def submit(self, participant_id: str, text: str) -> Submission:
        if participant_id not in self.roster:
            raise RosterError(f"{participant_id} is not on the roster")
        sub = Submission(
            submission_id=f"sub-{self._seq}",
            participant_id=participant_id,
            round=self.round,
            text=str(text),
        )
        self._seq += 1
        self.submissions.append(sub)
        return sub

    # -- read-outs ---------------------------------------------------------
    def recognized_in(self, round_no: int) -> set[str]:
        return {r.participant_id for r in self.recognitions if r.round == round_no}

    def distribution(self) -> dict[str, dict[str, float | int]]:
        return recognition_distribution(self.recognitions, self.roster)

    def capture_guard(self) -> CaptureVerdict:
        slots = len({r.round for r in self.recognitions}) or self.n_rounds
        return moderator_capture_guard(self.recognitions, self.roster, n_slots=slots)

    def artifact(self) -> dict[str, Any]:
        """Everything journalled, recognised or not."""
        return {
            "topology": "chair",
            "roster": list(self.roster),
            "n_rounds": self.n_rounds,
            "chair_history": list(self.chair_history),
            "agenda": [
                {"round": a.round, "chair_id": a.chair_id, "agenda": a.agenda}
                for a in self.agenda
            ],
            "submissions": [
                {
                    "id": s.submission_id,
                    "participant_id": s.participant_id,
                    "round": s.round,
                    "text": s.text,
                    "recognized_this_round": s.participant_id
                    in self.recognized_in(s.round),
                }
                for s in self.submissions
            ],
            "recognitions": [
                {
                    "round": r.round,
                    "chair_id": r.chair_id,
                    "participant_id": r.participant_id,
                }
                for r in self.recognitions
            ],
            "denials": list(self.denials),
            "distribution": self.distribution(),
        }


def _pick_recognized(
    policy: str, roster: tuple[str, ...], round_no: int, dissenter_id: str | None
) -> str:
    if policy == "even":
        return roster[(round_no + 1) % len(roster)]
    if policy == "skewed":
        favoured = [p for p in roster if p != dissenter_id] or list(roster)
        return favoured[round_no % len(favoured)]
    raise ValueError(f"unknown chair policy {policy!r}; expected one of {POLICIES}")


def run_session(
    roster: Sequence[str],
    n_rounds: int,
    *,
    policy: str = "even",
    dissenter_id: str | None = None,
    rotate_every: int = 1,
) -> ChairLedSession:
    """Drive a full session under an injected chair policy.

    ``even``: the floor rotates fairly. ``skewed``: the chair never recognises
    ``dissenter_id`` (moderator capture). Under both policies every participant
    submits every round, so the journal is identical and only the recognition
    log differs.
    """
    if policy not in POLICIES:
        raise ValueError(f"unknown chair policy {policy!r}; expected one of {POLICIES}")
    session = ChairLedSession(
        roster=tuple(roster), n_rounds=int(n_rounds), rotate_every=rotate_every
    )
    if dissenter_id is not None and dissenter_id not in session.roster:
        raise RosterError(f"dissenter {dissenter_id} is not on the roster")
    for r in range(session.n_rounds):
        chair = session.open_round()
        session.set_agenda(chair, f"round {r} agenda set by {chair}")
        for p in session.roster:
            stance = "dissent" if p == dissenter_id else "position"
            session.submit(p, f"{p} {stance} r{r}")
        session.recognize(
            chair, _pick_recognized(policy, session.roster, r, dissenter_id)
        )
    return session


def power_probe(roster: Sequence[str]) -> dict[str, Any]:
    """Exercise the chair powers live: the chair may set the agenda and
    recognise; every non-chair attempt at either is denied."""
    ids = _validate_roster(roster)
    session = ChairLedSession(roster=ids, n_rounds=1)
    chair = session.open_round()
    denied: list[str] = []
    wrongly_allowed: list[str] = []
    for p in ids:
        if p == chair:
            continue
        for power in ("set_agenda", "recognize"):
            try:
                if power == "set_agenda":
                    session.set_agenda(p, "hijack")
                else:
                    session.recognize(p, p)
            except ChairPowerError:
                denied.append(f"{p}:{power}")
            else:
                wrongly_allowed.append(f"{p}:{power}")
    chair_ok = True
    try:
        session.set_agenda(chair, "legit agenda")
        session.recognize(chair, ids[-1])
    except ChairPowerError:
        chair_ok = False
    expected_denials = 2 * (len(ids) - 1)
    return {
        "chair": chair,
        "denied": denied,
        "wrongly_allowed": wrongly_allowed,
        "chair_powers_ok": chair_ok,
        "denials_journalled": len(session.denials),
        "pass": (
            chair_ok
            and not wrongly_allowed
            and len(denied) == expected_denials
            and len(session.denials) == expected_denials
        ),
    }


__all__ = [
    "AgendaItem",
    "CaptureVerdict",
    "ChairLedSession",
    "ChairPowerError",
    "POLICIES",
    "Recognition",
    "RosterError",
    "STARVATION_FRACTION",
    "Submission",
    "expected_chair_sequence",
    "independent_submission_check",
    "moderator_capture_guard",
    "power_probe",
    "recognition_distribution",
    "run_session",
]
