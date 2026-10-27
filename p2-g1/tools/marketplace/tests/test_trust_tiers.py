"""IMP-0158 tests: tier from evidence; unknown refused; assignment deterministic."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from marketplace.trust_tiers import (  # noqa: E402
    AUTO_ADMIT, CONDITIONAL, REFUSED, assign_tier, decide_admission,
)

UNKNOWN_EV = {"publisher_id": "stranger", "publisher_repo": "", "identity_verified": False, "signature_verified": False}
FP_EV = {"publisher_id": "prekzursil", "publisher_repo": "Prekzursil/ast-integrate", "identity_verified": True, "signature_verified": True}


def test_unknown_tier_cannot_be_auto_adopted_first_party_twin_can():
    cand = {"id": "w@1", "trust_evidence": dict(UNKNOWN_EV)}
    assert decide_admission(cand).verdict == REFUSED
    twin = {"id": "w@1", "trust_evidence": dict(FP_EV)}
    assert decide_admission(twin).verdict == AUTO_ADMIT
    assert assign_tier(cand).tier == "unknown"
    assert assign_tier(twin).tier == "first-party"


def test_tier_assignment_deterministic_across_runs():
    cand = {"trust_evidence": dict(FP_EV)}
    a1 = assign_tier(cand)
    a2 = assign_tier(dict(cand))
    assert a1.tier == a2.tier
    assert a1.evidence_sha256 == a2.evidence_sha256
    # and the digest tracks the evidence, not the clock
    flipped = {"trust_evidence": {**FP_EV, "signature_verified": False}}
    assert assign_tier(flipped).evidence_sha256 != a1.evidence_sha256


def test_unknown_paths_require_clean_room_or_owner():
    ev = dict(UNKNOWN_EV)
    base = {"trust_evidence": ev}
    assert decide_admission(base).verdict == REFUSED
    owner = {"trust_evidence": {**ev, "owner_approval": True}}
    assert decide_admission(owner).verdict == CONDITIONAL
    clean = {"trust_evidence": {**ev, "clean_room_reimplementation": True}}
    assert decide_admission(clean).verdict == CONDITIONAL
