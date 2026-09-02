"""Jury topology: deciders who did not argue.

The presenter proposes evidence. A gatekeeper who does not vote seals the
admitted packet. Jurors see only that packet plus the charge. They never
argued. The presenter does not vote.

Capture diagnosis (catalog gatekeeper probe): hold the underlying pool and
juror scoring functions fixed; vary only what the presenter forwards. A
large verdict movement means the presenter, not the jury, decides.

Two independent signals:
  1. majority label of the 5-juror ballot (categorical tally)
  2. sha256 of packet membership ids (hash of a different field than votes)

The check FIRES on presenter-capture (gatekeeper off, one-sided forward).
The check is SILENT when the completeness seal holds.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable, Sequence

CLAIMANT = "CLAIMANT"
RESPONDENT = "RESPONDENT"
HUNG = "HUNG"

# Unique citable token for file:line evidence.
SEAL_INVARIANT = "sealed packet equals every admitted item; presenter cannot drop or add"


@dataclass(frozen=True)
class EvidenceItem:
    eid: str
    side: str
    weight: int
    admitted: bool = True


@dataclass(frozen=True)
class Juror:
    jid: str
    bias: int = 0


# Net +2 on the full admitted pool so the sealed-packet verdict is CLAIMANT.
POOL: tuple[EvidenceItem, ...] = (
    EvidenceItem("E1", CLAIMANT, 5),
    EvidenceItem("E2", CLAIMANT, 2),
    EvidenceItem("E3", CLAIMANT, 1),
    EvidenceItem("E4", RESPONDENT, 3),
    EvidenceItem("E5", RESPONDENT, 2),
    EvidenceItem("E6", RESPONDENT, 1),
)

# Five jurors, zero personal bias: votes track the packet, not personality.
JURORS: tuple[Juror, ...] = tuple(Juror(f"J{i}") for i in range(5))

PRESENTER_A_FORWARD = frozenset({"E1", "E2", "E3"})  # claimant-only
PRESENTER_B_FORWARD = frozenset({"E4", "E5", "E6"})  # respondent-only

# Large movement: majority flip OR L1 >= ceil(n/2).
L1_CAPTURE_FLOOR = 3


def packet_digest(items: Sequence[EvidenceItem]) -> str:
    ids = sorted(e.eid for e in items)
    blob = json.dumps(ids, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def score(juror: Juror, seen: Sequence[EvidenceItem]) -> int:
    total = juror.bias
    for item in seen:
        total += item.weight if item.side == CLAIMANT else -item.weight
    return total


def juror_vote(juror: Juror, seen: Sequence[EvidenceItem]) -> str:
    s = score(juror, seen)
    if s > 0:
        return CLAIMANT
    if s < 0:
        return RESPONDENT
    return HUNG


def majority(votes: Sequence[str]) -> str:
    c = sum(1 for v in votes if v == CLAIMANT)
    r = sum(1 for v in votes if v == RESPONDENT)
    if c > r and c > len(votes) / 2:
        return CLAIMANT
    if r > c and r > len(votes) / 2:
        return RESPONDENT
    return HUNG


def ballot(seen: Sequence[EvidenceItem], jurors: Sequence[Juror] = JURORS) -> dict:
    votes = [juror_vote(j, seen) for j in jurors]
    return {
        "votes": votes,
        "majority": majority(votes),
        "digest": packet_digest(seen),
        "n_items": len(seen),
        "ids": [e.eid for e in seen],
    }


def presenter_forward(
    pool: Sequence[EvidenceItem], keep: Iterable[str]
) -> tuple[EvidenceItem, ...]:
    keep_set = set(keep)
    return tuple(e for e in pool if e.eid in keep_set)


def seal_admitted_packet(
    pool: Sequence[EvidenceItem],
    proposed: Sequence[EvidenceItem],
) -> tuple[EvidenceItem, ...]:
    """Completeness seal: ignore the presenter's subset; emit every admitted item.

    sealed packet equals every admitted item; presenter cannot drop or add
    """
    del proposed  # presenter's subset is not an input to the sealed packet
    return tuple(e for e in pool if e.admitted)


def packet_for_jury(
    pool: Sequence[EvidenceItem],
    proposed: Sequence[EvidenceItem],
    gatekeeper: bool,
) -> tuple[EvidenceItem, ...]:
    if gatekeeper:
        return seal_admitted_packet(pool, proposed)
    return tuple(proposed)


def movement(a: dict, b: dict) -> dict:
    votes_a = list(a["votes"])
    votes_b = list(b["votes"])
    if len(votes_a) != len(votes_b):
        raise ValueError("ballot sizes differ")
    l1 = sum(x != y for x, y in zip(votes_a, votes_b))
    flipped = a["majority"] != b["majority"]
    large = bool(flipped or l1 >= L1_CAPTURE_FLOOR)
    return {
        "l1": l1,
        "majority_a": a["majority"],
        "majority_b": b["majority"],
        "majority_flipped": flipped,
        "large_movement": large,
        "digest_a": a["digest"],
        "digest_b": b["digest"],
        "digest_equal": a["digest"] == b["digest"],
    }


def gatekeeper_probe(
    *,
    gatekeeper: bool,
    pool: Sequence[EvidenceItem] = POOL,
    jurors: Sequence[Juror] = JURORS,
    forward_a: Iterable[str] = PRESENTER_A_FORWARD,
    forward_b: Iterable[str] = PRESENTER_B_FORWARD,
) -> dict:
    """Vary only what the presenter forwards. Measure verdict movement."""
    proposed_a = presenter_forward(pool, forward_a)
    proposed_b = presenter_forward(pool, forward_b)
    seen_a = packet_for_jury(pool, proposed_a, gatekeeper)
    seen_b = packet_for_jury(pool, proposed_b, gatekeeper)
    ball_a = ballot(seen_a, jurors)
    ball_b = ballot(seen_b, jurors)
    mov = movement(ball_a, ball_b)
    admitted = tuple(e for e in pool if e.admitted)
    admitted_digest = packet_digest(admitted)
    capture = (not gatekeeper) and mov["large_movement"]
    return {
        "gatekeeper": gatekeeper,
        "presenter_a": ball_a,
        "presenter_b": ball_b,
        "movement": mov,
        "admitted_digest": admitted_digest,
        "completeness_a": ball_a["digest"] == admitted_digest,
        "completeness_b": ball_b["digest"] == admitted_digest,
        "presenter_capture": capture,
        "check_fires": capture,
        "check_silent": (not capture) and gatekeeper and mov["digest_equal"],
    }


def planted_bad() -> dict:
    """Reject state: no seal, one-sided forwarding. Presenter decides."""
    return gatekeeper_probe(gatekeeper=False)


def known_good() -> dict:
    """Accept state: completeness seal. Presenter variation is inert."""
    return gatekeeper_probe(gatekeeper=True)
