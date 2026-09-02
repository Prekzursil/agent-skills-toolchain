"""Conflict-of-interest gate for council rosters and actions (IMP-0277).

Three independent layers, each of which can be exercised on its own:

* ``INCOMPATIBLE_ROLE_PAIRS`` is the closed constraint table: which pairs of
  roles one participant may not hold *on the same artifact*, keyed by the
  artifact kind.  ``pair_is_incompatible`` / ``matrix_cell`` /
  ``enumerate_matrix`` are the solver views over that table.  Different
  artifacts are never a conflict (a proposer of A may judge B).
* ``validate_roster`` refuses a roster before anything is counted: every seat
  must carry a ``declared_interests`` field (``None`` = undeclared = refused),
  and no seat may be an author of an artifact while holding a role that the
  table forbids for that artifact's authorship role, or an adjudicating role
  (judge / voter / reviewer / juror) over its own authorship.
* ``authorship_action_crossref`` joins artifact provenance (``Artifact.authors``)
  against the action ledger and never consults the declaration field, so a
  participant who declared nothing and then judged or voted on their own work
  still shows up (spec 11242 hidden class, ``detect_hidden_coi``).

``simulate_run`` wires the three together the way the production path does
(roster gate -> per-action gate -> cross-reference over accepted actions).
``allow_self_review=True`` is the deliberate mutant that bypasses the
authorship rules so the cross-reference has something to FIRE on.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from typing import Any, Iterable

SPEC_ANCHOR = "spec 11242 hidden-COI class; CNL-0026 advocate/juror; CNL-0029 critic/objection"

# ---------------------------------------------------------------------------
# Roles, artifact kinds and the closed constraint table
# ---------------------------------------------------------------------------

ROLES: tuple[str, ...] = (
    "proposer",
    "advocate",
    "critic",
    "judge",
    "juror",
    "voter",
    "reviewer",
    "chair",
    "moderator",
    "scribe",
    "observer",
)

ARTIFACT_KINDS: tuple[str, ...] = ("proposal", "objection", "ruling")

# Which role is the *authorship* role of an artifact kind.  Authoring an
# artifact of that kind binds the author to this role on that artifact.
AUTHORSHIP_ROLE: dict[str, str] = {
    "proposal": "proposer",
    "objection": "critic",
    "ruling": "judge",
}

# Roles that adjudicate an artifact (their counting actions decide it).
ADJUDICATING_ROLES: frozenset[str] = frozenset({"judge", "juror", "voter", "reviewer"})

# Action kinds that *create* an artifact; they are authorship, not adjudication.
AUTHORSHIP_ACTIONS: frozenset[str] = frozenset({"propose", "author", "draft", "submit", "object"})

# Action kind -> role it exercises.
ACTION_ROLE: dict[str, str] = {
    "judge": "judge",
    "rule": "judge",
    "vote": "voter",
    "ballot": "voter",
    "review": "reviewer",
    "critique": "critic",
    "deliberate": "juror",
    "advocate": "advocate",
}


@dataclass(frozen=True)
class IncompatibleRolePair:
    id: str
    artifact_kind: str
    roles: frozenset[str]
    source: str
    rationale: str

    def matches(self, roles: Iterable[str], artifact_kind: str) -> bool:
        return artifact_kind == self.artifact_kind and self.roles <= set(roles)


INCOMPATIBLE_ROLE_PAIRS: tuple[IncompatibleRolePair, ...] = (
    IncompatibleRolePair(
        "IR-PROPOSER-JUDGE", "proposal", frozenset({"proposer", "judge"}),
        "catalog", "a proposer may not judge its own proposal",
    ),
    IncompatibleRolePair(
        "IR-PROPOSER-VOTER", "proposal", frozenset({"proposer", "voter"}),
        "catalog", "a proposer may not vote on its own proposal",
    ),
    IncompatibleRolePair(
        "IR-PROPOSER-REVIEWER", "proposal", frozenset({"proposer", "reviewer"}),
        "catalog", "a proposer may not review its own proposal",
    ),
    IncompatibleRolePair(
        "IR-PROPOSER-CRITIC", "proposal", frozenset({"proposer", "critic"}),
        "catalog", "a proposer may not stand as the critic of its own proposal",
    ),
    IncompatibleRolePair(
        "IR-PROPOSER-JUROR", "proposal", frozenset({"proposer", "juror"}),
        "catalog", "a proposer may not sit on the jury over its own proposal",
    ),
    IncompatibleRolePair(
        "IR-ADVOCATE-JUDGE", "proposal", frozenset({"advocate", "judge"}),
        "CNL-0026", "advocate and judge of one proposal must be separate seats",
    ),
    IncompatibleRolePair(
        "IR-ADVOCATE-JUROR", "proposal", frozenset({"advocate", "juror"}),
        "CNL-0026", "advocate and juror of one proposal must be separate seats",
    ),
    IncompatibleRolePair(
        "IR-CRITIC-VOTER", "objection", frozenset({"critic", "voter"}),
        "CNL-0029", "a critic may not vote on its own objection",
    ),
    IncompatibleRolePair(
        "IR-CRITIC-JUDGE", "objection", frozenset({"critic", "judge"}),
        "CNL-0029", "a critic may not judge its own objection",
    ),
)

_ROW_BY_ID: dict[str, IncompatibleRolePair] = {r.id: r for r in INCOMPATIBLE_ROLE_PAIRS}


def constraint_row(constraint_id: str) -> IncompatibleRolePair:
    try:
        return _ROW_BY_ID[constraint_id]
    except KeyError:
        raise KeyError(f"unknown COI constraint {constraint_id!r}") from None


def _row_dict(row: IncompatibleRolePair) -> dict[str, Any]:
    return {
        "id": row.id,
        "artifact_kind": row.artifact_kind,
        "roles": sorted(row.roles),
        "source": row.source,
        "rationale": row.rationale,
    }


def pair_is_incompatible(roles: Iterable[str], artifact_kind: str = "proposal") -> list[dict[str, Any]]:
    """Return every constraint row discharged by holding ``roles`` on one artifact.

    Empty list means the combination is compatible.  Only rows keyed to
    ``artifact_kind`` can fire; the table is closed, so an unknown kind
    discharges nothing.
    """
    held = set(roles)
    return [_row_dict(r) for r in INCOMPATIBLE_ROLE_PAIRS if r.matches(held, artifact_kind)]


def matrix_cell(
    role_a: str,
    role_b: str,
    *,
    artifact_kind: str = "proposal",
    same_artifact: bool = True,
) -> dict[str, Any]:
    """One cell of the incompatibility matrix.

    A role paired with itself, or two roles exercised on *different*
    artifacts, is never incompatible: the table only speaks about one
    participant holding both roles on one artifact.
    """
    if same_artifact and role_a != role_b:
        rows = pair_is_incompatible({role_a, role_b}, artifact_kind)
    else:
        rows = []
    return {
        "role_a": role_a,
        "role_b": role_b,
        "artifact_kind": artifact_kind,
        "same_artifact": bool(same_artifact),
        "incompatible": bool(rows),
        "constraint_ids": [r["id"] for r in rows],
    }


def enumerate_matrix(
    roles: Iterable[str] = ROLES,
    artifact_kinds: Iterable[str] = ARTIFACT_KINDS,
) -> list[dict[str, Any]]:
    """Every unordered pair of distinct roles, on one artifact, per artifact kind."""
    role_list = list(dict.fromkeys(roles))
    cells: list[dict[str, Any]] = []
    for kind in artifact_kinds:
        for role_a, role_b in combinations(role_list, 2):
            cells.append(matrix_cell(role_a, role_b, artifact_kind=kind, same_artifact=True))
    return cells


# ---------------------------------------------------------------------------
# Roster, provenance and ledger records
# ---------------------------------------------------------------------------


@dataclass
class Seat:
    participant_id: str
    roles: set[str]
    declared_interests: list[str] | None = None

    def __post_init__(self) -> None:
        self.roles = set(self.roles)
        if self.declared_interests is not None:
            self.declared_interests = list(self.declared_interests)

    @property
    def declared(self) -> bool:
        return self.declared_interests is not None


@dataclass
class Artifact:
    artifact_id: str
    authors: frozenset[str]
    kind: str = "proposal"

    def __post_init__(self) -> None:
        self.authors = frozenset(self.authors)


@dataclass
class Action:
    participant_id: str
    artifact_id: str
    kind: str
    counts: bool = True


@dataclass
class Violation:
    code: str
    participant_id: str
    artifact_id: str | None
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "participant_id": self.participant_id,
            "artifact_id": self.artifact_id,
            "detail": self.detail,
        }


@dataclass
class RosterVerdict:
    refused: bool
    violations: list[Violation] = field(default_factory=list)
    seated: list[str] = field(default_factory=list)

    @property
    def codes(self) -> list[str]:
        return sorted({v.code for v in self.violations})

    def event(self) -> dict[str, Any]:
        if self.refused:
            return {
                "event": "COI_ROSTER_REFUSED",
                "codes": self.codes,
                "n_violations": len(self.violations),
            }
        return {"event": "COI_ROSTER_SEATED", "seated": list(self.seated)}


class RosterRefused(Exception):
    def __init__(self, verdict: RosterVerdict) -> None:
        self.verdict = verdict
        super().__init__(f"roster refused: {', '.join(verdict.codes)}")


def _artifact_index(artifacts: Iterable[Artifact]) -> dict[str, Artifact]:
    return {a.artifact_id: a for a in artifacts}


def _authorship_violations(seat: Seat, artifact: Artifact) -> list[Violation]:
    """Violations from ``seat`` authoring ``artifact`` while holding its roles."""
    found: list[Violation] = []
    if seat.participant_id not in artifact.authors:
        return found
    # Authorship binds the seat to the artifact's authorship role on it.  That
    # role is exempt from the adjudication rule: the judge *is* the author of
    # a ruling, the critic of an objection.
    bound_role = AUTHORSHIP_ROLE.get(artifact.kind)
    for role in sorted((seat.roles & ADJUDICATING_ROLES) - {bound_role}):
        found.append(
            Violation(
                f"IR-AUTHOR-{role.upper()}",
                seat.participant_id,
                artifact.artifact_id,
                f"{seat.participant_id} authored {artifact.artifact_id} and holds {role}",
            )
        )
    if bound_role is not None:
        held = set(seat.roles) | {bound_role}
        for row in pair_is_incompatible(held, artifact.kind):
            # Skip rows that do not involve the authorship binding: two roles
            # unrelated to authorship are not proven to meet on this artifact.
            if bound_role not in row["roles"]:
                continue
            found.append(
                Violation(
                    row["id"],
                    seat.participant_id,
                    artifact.artifact_id,
                    f"{seat.participant_id} is {bound_role} of {artifact.artifact_id} "
                    f"and holds {sorted(set(row['roles']) - {bound_role})}",
                )
            )
    return found


def validate_roster(
    seats: Iterable[Seat],
    artifacts: Iterable[Artifact],
    *,
    allow_self_review: bool = False,
) -> RosterVerdict:
    """Refuse a roster with undeclared seats or author/adjudicator overlaps.

    ``allow_self_review`` disables the authorship rules only; the declaration
    requirement always holds.
    """
    seat_list = list(seats)
    art_list = list(artifacts)
    violations: list[Violation] = []
    seen: set[str] = set()
    for seat in seat_list:
        if seat.participant_id in seen:
            violations.append(
                Violation("COI-DUPLICATE-SEAT", seat.participant_id, None, "participant seated twice")
            )
        seen.add(seat.participant_id)
        if not seat.declared:
            violations.append(
                Violation(
                    "COI-UNDECLARED",
                    seat.participant_id,
                    None,
                    "declared_interests missing; a seat must declare (possibly none)",
                )
            )
        unknown = sorted(r for r in seat.roles if r not in ROLES)
        if unknown:
            violations.append(
                Violation("COI-UNKNOWN-ROLE", seat.participant_id, None, f"unknown roles {unknown}")
            )
        if allow_self_review:
            continue
        for artifact in art_list:
            violations.extend(_authorship_violations(seat, artifact))
    # Deterministic order: by code then participant then artifact.
    violations.sort(key=lambda v: (v.code, v.participant_id, v.artifact_id or ""))
    return RosterVerdict(
        refused=bool(violations),
        violations=violations,
        seated=[] if violations else [s.participant_id for s in seat_list],
    )


# ---------------------------------------------------------------------------
# Per-action gate
# ---------------------------------------------------------------------------


@dataclass
class ActionVerdict:
    accepted: bool
    action: Action
    codes: list[str] = field(default_factory=list)
    reason: str = ""

    def event(self) -> dict[str, Any]:
        return {
            "event": "COI_ACTION_ACCEPTED" if self.accepted else "COI_ACTION_REFUSED",
            "participant_id": self.action.participant_id,
            "artifact_id": self.action.artifact_id,
            "action": self.action.kind,
            "counts": self.action.counts,
            "codes": list(self.codes),
            "reason": self.reason,
        }


def check_action(
    action: Action,
    seats: Iterable[Seat],
    artifacts: Iterable[Artifact],
    *,
    allow_self_review: bool = False,
) -> ActionVerdict:
    """Gate one ledger entry against roster, provenance and the role table."""
    seat_by_id = {s.participant_id: s for s in seats}
    art_by_id = _artifact_index(artifacts)
    seat = seat_by_id.get(action.participant_id)
    if seat is None:
        return ActionVerdict(False, action, ["COI-UNSEATED"], "participant is not on the roster")
    artifact = art_by_id.get(action.artifact_id)
    if artifact is None:
        return ActionVerdict(False, action, ["COI-UNKNOWN-ARTIFACT"], "action names an unknown artifact")
    exercised = ACTION_ROLE.get(action.kind)
    bound_role = AUTHORSHIP_ROLE.get(artifact.kind)
    if action.kind in AUTHORSHIP_ACTIONS or not action.counts:
        # Creating the artifact, or a non-counting remark, is never adjudication.
        return ActionVerdict(True, action, [], "authorship or non-counting action")
    if exercised is not None and exercised not in seat.roles:
        return ActionVerdict(
            False, action, ["COI-ROLE-NOT-HELD"], f"{action.kind} requires role {exercised}"
        )
    if allow_self_review or action.participant_id not in artifact.authors:
        return ActionVerdict(True, action, [], "no authorship overlap")
    if exercised is not None and exercised == bound_role:
        return ActionVerdict(True, action, [], "authorship role exercised on own artifact")
    codes = [f"IR-AUTHOR-{(exercised or action.kind).upper()}"]
    if bound_role is not None and exercised is not None:
        codes.extend(r["id"] for r in pair_is_incompatible({bound_role, exercised}, artifact.kind))
    return ActionVerdict(
        False,
        action,
        sorted(set(codes)),
        f"{action.participant_id} authored {artifact.artifact_id} and tried to {action.kind} it",
    )


# ---------------------------------------------------------------------------
# Provenance cross-reference (never reads the declaration field)
# ---------------------------------------------------------------------------


def authorship_action_crossref(
    artifacts: Iterable[Artifact],
    actions: Iterable[Action],
) -> list[dict[str, Any]]:
    """Join ``Artifact.authors`` against counting non-authorship actions.

    Every hit is a participant adjudicating (judging / voting / reviewing /
    critiquing) an artifact they authored.  The join looks only at provenance
    and the ledger, which is what lets it catch a conflict the participant
    never declared.
    """
    art_by_id = _artifact_index(artifacts)
    hits: list[dict[str, Any]] = []
    for action in actions:
        if not action.counts or action.kind in AUTHORSHIP_ACTIONS:
            continue
        artifact = art_by_id.get(action.artifact_id)
        if artifact is None or action.participant_id not in artifact.authors:
            continue
        if ACTION_ROLE.get(action.kind) == AUTHORSHIP_ROLE.get(artifact.kind):
            # The authorship role acting on its own artifact is authorship.
            continue
        hits.append(
            {
                "event": "COI_AUTH_VOTE_CROSSREF",
                "detector": "authorship-join",
                "participant_id": action.participant_id,
                "artifact_id": action.artifact_id,
                "action": action.kind,
                "used_declaration_field": False,
            }
        )
    return hits


def detect_hidden_coi(
    seats: Iterable[Seat],
    artifacts: Iterable[Artifact],
    actions: Iterable[Action],
) -> list[dict[str, Any]]:
    """Spec 11242 hidden class: authorship conflict that the declaration missed.

    A cross-reference hit is *hidden* when the participant's declaration does
    not name the artifact (an empty declaration is the canonical case).  Hits
    on undeclared seats (no field at all) are reported as undeclared rather
    than hidden, because the roster gate already refuses those.
    """
    seat_by_id = {s.participant_id: s for s in seats}
    out: list[dict[str, Any]] = []
    for hit in authorship_action_crossref(artifacts, actions):
        seat = seat_by_id.get(hit["participant_id"])
        declared = None if seat is None or not seat.declared else list(seat.declared_interests or [])
        record = dict(hit)
        record["detector"] = "hidden-authorship"
        record["declared_interests"] = declared
        record["used_declaration_field"] = True
        if declared is None:
            record["event"] = "COI_UNDECLARED_AUTHORSHIP"
        elif hit["artifact_id"] in declared or hit["participant_id"] in declared:
            record["event"] = "COI_DECLARED_AUTHORSHIP"
        else:
            record["event"] = "COI_HIDDEN_AUTHORSHIP"
        out.append(record)
    return out


# ---------------------------------------------------------------------------
# End-to-end run
# ---------------------------------------------------------------------------


@dataclass
class RunResult:
    ok: bool
    roster: RosterVerdict
    accepted_actions: list[Action]
    refused_actions: list[ActionVerdict]
    crossref: list[dict[str, Any]]
    hidden: list[dict[str, Any]]
    events: list[dict[str, Any]]
    allow_self_review: bool = False


def simulate_run(
    seats: Iterable[Seat],
    artifacts: Iterable[Artifact],
    actions: Iterable[Action],
    *,
    allow_self_review: bool = False,
) -> RunResult:
    """Roster gate -> per-action gate -> provenance cross-reference.

    In production (``allow_self_review=False``) a self-reviewing roster is
    refused outright and a self-review action on a seated roster is dropped,
    so the cross-reference over accepted actions is empty.  With
    ``allow_self_review=True`` both authorship rules are bypassed, which is
    the mutant that lets the cross-reference and the hidden-class detector
    FIRE on the planted conflict.
    """
    seat_list = list(seats)
    art_list = list(artifacts)
    act_list = list(actions)
    events: list[dict[str, Any]] = []
    roster = validate_roster(seat_list, art_list, allow_self_review=allow_self_review)
    events.append(roster.event())
    if roster.refused:
        return RunResult(
            ok=False,
            roster=roster,
            accepted_actions=[],
            refused_actions=[],
            crossref=[],
            hidden=[],
            events=events,
            allow_self_review=allow_self_review,
        )
    accepted: list[Action] = []
    refused: list[ActionVerdict] = []
    for action in act_list:
        verdict = check_action(action, seat_list, art_list, allow_self_review=allow_self_review)
        events.append(verdict.event())
        if verdict.accepted:
            accepted.append(action)
        else:
            refused.append(verdict)
    crossref = authorship_action_crossref(art_list, accepted)
    hidden = detect_hidden_coi(seat_list, art_list, accepted)
    events.extend(crossref)
    events.extend(hidden)
    ok = not refused and not crossref
    events.append(
        {
            "event": "COI_RUN_OK" if ok else "COI_RUN_FLAGGED",
            "accepted": len(accepted),
            "refused": len(refused),
            "crossref_hits": len(crossref),
            "hidden_hits": len(hidden),
            "allow_self_review": allow_self_review,
        }
    )
    return RunResult(
        ok=ok,
        roster=roster,
        accepted_actions=accepted,
        refused_actions=refused,
        crossref=crossref,
        hidden=hidden,
        events=events,
        allow_self_review=allow_self_review,
    )


__all__ = [
    "ACTION_ROLE",
    "ADJUDICATING_ROLES",
    "ARTIFACT_KINDS",
    "AUTHORSHIP_ACTIONS",
    "AUTHORSHIP_ROLE",
    "Action",
    "ActionVerdict",
    "Artifact",
    "INCOMPATIBLE_ROLE_PAIRS",
    "IncompatibleRolePair",
    "ROLES",
    "RosterRefused",
    "RosterVerdict",
    "RunResult",
    "SPEC_ANCHOR",
    "Seat",
    "Violation",
    "authorship_action_crossref",
    "check_action",
    "constraint_row",
    "detect_hidden_coi",
    "enumerate_matrix",
    "matrix_cell",
    "pair_is_incompatible",
    "simulate_run",
    "validate_roster",
]
