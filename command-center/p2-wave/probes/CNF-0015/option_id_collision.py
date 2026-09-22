"""CNF-0015 — option-id collision detector (both-states repro).

Fails if and only if the literal shared-id count between 07-OPTION-UNIVERSE
family M and 13-ARCHITECTURE-CANDIDATES bare M-NN mechanisms is non-zero.
Also reports whether 17-DECISION-LOG.md carries zero MECH tokens while stating
the collision in the present tense (the residual stale-premise half).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

BARE_M = re.compile(r"(?<![A-Za-z0-9_-])M-(\d{1,3})(?![0-9])")
MECH_NN = re.compile(r"MECH-\d{1,3}")
FAMILY_M_HEADING = re.compile(r"^#{2,6}\s*`?(M-\d{1,3})`?", re.M)
FAMILY_M_CARD = re.compile(r"####\s+`(M-\d{1,3})`")
PRESENT_TENSE_COLLISION = re.compile(
    r"(collision is live|resolve to two unrelated|Queued as P2-09)", re.I
)


@dataclass(frozen=True)
class CollisionReport:
    family_m_ids: frozenset[str]
    doc13_bare_m_ids: frozenset[str]
    shared_id_count: int
    mech_token_count: int
    decision_present_tense_collision: bool
    collision_live: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "family_m_count": len(self.family_m_ids),
            "doc13_bare_m_count": len(self.doc13_bare_m_ids),
            "shared_id_count": self.shared_id_count,
            "mech_token_count": self.mech_token_count,
            "decision_present_tense_collision": self.decision_present_tense_collision,
            "collision_live": self.collision_live,
        }


def family_m_ids(doc07: str) -> set[str]:
    found = set(FAMILY_M_CARD.findall(doc07))
    if not found:
        found = set(FAMILY_M_HEADING.findall(doc07))
    return found


def doc13_bare_m_ids(doc13: str) -> set[str]:
    """Bare M-NN tokens in doc 13 that are NOT part of a MECH-NN token."""
    # Strip MECH-NN first so the bare-M regex cannot see inside MECH-12.
    scrubbed = MECH_NN.sub("", doc13)
    return {f"M-{n}" for n in BARE_M.findall(scrubbed)}


def measure(doc07: str, doc13: str, decision: str) -> CollisionReport:
    fam = family_m_ids(doc07)
    bare = doc13_bare_m_ids(doc13)
    shared = fam & bare
    # Substring count matches the OPTION-ID-RESOLUTION residual probe.
    mech_substr = decision.count("MECH")
    present = bool(PRESENT_TENSE_COLLISION.search(decision))
    return CollisionReport(
        family_m_ids=frozenset(fam),
        doc13_bare_m_ids=frozenset(bare),
        shared_id_count=len(shared),
        mech_token_count=mech_substr,
        decision_present_tense_collision=present and mech_substr == 0,
        collision_live=len(shared) > 0,
    )


def measure_dir(directory: Path) -> CollisionReport:
    d07 = (directory / "07-OPTION-UNIVERSE.md").read_text(encoding="utf-8")
    d13 = (directory / "13-ARCHITECTURE-CANDIDATES.md").read_text(encoding="utf-8")
    dec = (directory / "17-DECISION-LOG.md").read_text(encoding="utf-8")
    return measure(d07, d13, dec)


def collision_is_live(directory: Path) -> bool:
    """Detector callable for TST-0328 / both-states: truthy iff collision is live."""
    return measure_dir(directory).collision_live
