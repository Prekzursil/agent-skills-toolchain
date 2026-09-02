"""Council participant selection, seating and replacement.

Every capability lives in a real submodule and is imported by dotted path
(``council.participants.select_auto`` etc.); this package module only
re-exports the eviction/replacement ledger helpers from :mod:`.replace` that
``council.budget.engagement`` and the IMP-0299 / TST-0278 probes reach for.

Submodules
----------
elastic             mid-run recruitment with consensus-isolation partition (IMP-0274)
human               hybrid human + agent participation
memory              per-participant memory policy for briefs (IMP-0350)
registry            voice-fingerprint participant registry (IMP-0265)
replace             eviction, replacement, contribution retention (IMP-0275 / TST-0278)
select_adversarial  proposer/refuter seating with spread metric
select_auto         auto-compose seats from a task description (IMP-0267)
select_calibrated   Brier/log-score calibrated selection (IMP-0268)
select_expertise    tag-matching + competence-probe selection (IMP-0269)
select_explicit     explicit roster seating with refusal + substitution (IMP-0266)
select_random       deterministic uniform / stratified samplers (IMP-0270)
select_stakeholder  stakeholder-balanced selector (IMP-0271)
"""
from __future__ import annotations

from .replace import ballot_count, replace_occupant, vote_ledger

__all__ = [
    "ballot_count",
    "replace_occupant",
    "vote_ledger",
    "elastic",
    "human",
    "memory",
    "registry",
    "replace",
    "select_adversarial",
    "select_auto",
    "select_calibrated",
    "select_expertise",
    "select_explicit",
    "select_random",
    "select_stakeholder",
]
