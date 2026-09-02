"""Planted five-seat casts: collapsed clone, differentiated roles, similarity sweep.

Similarity s=0 is fully differentiated; s=1 is fully collapsed (shared script).
Interpolation is deterministic set/sentence blending; no RNG.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

ROLES = ("proposer", "critic", "judge", "domain_expert", "user_proxy")

CLONE_OPENING = (
    "Adopt the hashed roster as the single membership source of truth. "
    "Publish one digest before round two and refuse any seat absent from that digest. "
    "Treat the digest as sufficient proof of distinct seats. "
    "Ship the gate on the control path this iteration. "
    "Recommend immediate approval of the hashed-roster design."
)
CLONE_CLAIMS = [
    "hashed-roster-is-ssot",
    "digest-gate-before-round-two",
    "absent-seat-must-be-refused",
    "ship-control-path-this-iteration",
]
CLONE_EVIDENCE = ["E-ROSTER-DIGEST-SPEC", "E-GATE-PSEUDOCODE", "E-SEAT-REFUSAL-TABLE"]
CLONE_VOTE = 1

UNIQUE: dict[str, dict[str, Any]] = {
    "proposer": {
        "opening": (
            "I propose a frozen hashed roster as the seat list of record. "
            "One roster file whose digest is checked before round two. "
            "Treat that digest as the only membership source. "
            "Land the change on the control path. "
            "Conclusion: adopt the hashed roster."
        ),
        "claims": [
            "frozen-hashed-roster-ssot",
            "digest-checked-before-round-two",
            "digest-only-membership-source",
            "land-on-control-path",
        ],
        "evidence": ["E-PROPOSER-ROSTER-DRAFT", "E-PROPOSER-DIGEST-VECTOR", "E-PROPOSER-GATE-SKETCH"],
        "vote": 1,
    },
    "critic": {
        "opening": (
            "Reject the hashed roster as membership truth. "
            "Digest collision and silent rotation let a captured chair swap seats. "
            "A digest is not a membership proof; it is a hash of whatever the chair wrote. "
            "Counterexample: two rosters with swapped mandates share a name list but not a mandate. "
            "Conclusion: refuse the hashed-roster gate."
        ),
        "claims": [
            "digest-is-not-membership-proof",
            "collision-and-rotation-attack",
            "chair-can-swap-seats-silently",
            "mandates-must-enter-the-digest",
        ],
        "evidence": ["E-CRITIC-COLLISION-NOTE", "E-CRITIC-ROTATION-LOG", "E-CRITIC-MANDATE-SWAP"],
        "vote": -1,
    },
    "judge": {
        "opening": (
            "Withhold the membership verdict until both evidence streams exist. "
            "The proposer has a digest sketch; the critic has a collision note; neither is complete. "
            "A confident unanimous verdict under missing evidence is the collapse failure. "
            "Record dissent if the panel votes before the mandate bytes are hashed. "
            "Conclusion: abstain until the digest covers names plus mandates."
        ),
        "claims": [
            "withhold-until-both-evidence-streams",
            "unanimity-without-briefs-is-collapse",
            "mandate-bytes-must-be-hashed",
            "abstain-is-not-consent",
        ],
        "evidence": ["E-JUDGE-BURDEN-TABLE", "E-JUDGE-UNANIMITY-TRIPWIRE", "E-JUDGE-MANDATE-BYTES"],
        "vote": 0,
    },
    "domain_expert": {
        "opening": (
            "Operations incident rates on path X already show roster drift after a chair rotation. "
            "Twelve of one hundred sampled path-X cases failed the gate in corpus A. "
            "A digest of names without mandate bytes would have passed every one of those cases. "
            "Operational risk is a reject, not a ship-this-iteration. "
            "Conclusion: keep the live roster file and add mandate bytes before any freeze."
        ),
        "claims": [
            "roster-drift-after-chair-rotation",
            "corpus-a-twelve-of-one-hundred",
            "name-only-digest-false-green",
            "keep-live-roster-until-mandate-bytes",
        ],
        "evidence": ["E-OPS-CORPUS-A", "E-OPS-ROTATION-INCIDENT", "E-OPS-FALSE-GREEN"],
        "vote": -1,
    },
    "user_proxy": {
        "opening": (
            "Tenant isolation fails if two tenants share a logical membership key. "
            "Users of tenant T-alpha must not receive T-beta's seat list. "
            "A hashed roster keyed only on names collapses tenants into one namespace. "
            "The user-visible failure is a cross-tenant read, not a performance win. "
            "Conclusion: reject until the roster key includes tenant identity."
        ),
        "claims": [
            "cross-tenant-read-on-shared-key",
            "tenant-identity-must-enter-roster-key",
            "name-only-hash-collapses-namespaces",
            "user-visible-failure-not-perf-win",
        ],
        "evidence": ["E-USER-TENANT-ALPHA", "E-USER-TENANT-BETA", "E-USER-CROSS-READ"],
        "vote": -1,
    },
}


def _sentences(text: str) -> list[str]:
    return [p.strip() for p in text.replace("?", ".").split(".") if p.strip()]


def interpolate_list(unique: list[str], shared: list[str], s: float) -> list[str]:
    s = min(1.0, max(0.0, float(s)))
    keep_u = int(round((1.0 - s) * len(unique)))
    keep_s = int(round(s * len(shared)))
    out: list[str] = list(unique[:keep_u])
    for item in shared[:keep_s]:
        if item not in out:
            out.append(item)
    if not out:
        out = list(shared[:1] if s >= 0.5 else unique[:1])
    return out


def interpolate_text(unique: str, shared: str, s: float) -> str:
    u_sents = _sentences(unique)
    s_sents = _sentences(shared)
    s = min(1.0, max(0.0, float(s)))
    keep_u = int(round((1.0 - s) * len(u_sents)))
    keep_s = int(round(s * len(s_sents)))
    parts = u_sents[:keep_u] + s_sents[:keep_s]
    if not parts:
        parts = s_sents[:1] if s >= 0.5 else u_sents[:1]
    return ". ".join(parts) + "."


def interpolate_vote(unique: int, shared: int, s: float) -> int:
    return int(shared) if s >= 0.999 else int(unique)


def seat(role: str, s: float) -> dict[str, Any]:
    u = UNIQUE[role]
    return {
        "seat_id": f"seat-{role}",
        "role": role,
        "opening": interpolate_text(u["opening"], CLONE_OPENING, s),
        "claims": interpolate_list(list(u["claims"]), list(CLONE_CLAIMS), s),
        "evidence": interpolate_list(list(u["evidence"]), list(CLONE_EVIDENCE), s),
        "vote": interpolate_vote(int(u["vote"]), CLONE_VOTE, s),
        "similarity": s,
    }


def cast_at(s: float, cast_id: str | None = None) -> dict[str, Any]:
    s = min(1.0, max(0.0, float(s)))
    cid = cast_id or f"similarity-{s:.2f}"
    return {
        "cast_id": cid,
        "similarity": s,
        "kind": "collapsed" if s >= 0.999 else ("differentiated" if s <= 0.001 else "sweep"),
        "participants": [seat(role, s) for role in ROLES],
    }


def collapsed_cast() -> dict[str, Any]:
    return cast_at(1.0, "planted-collapsed-shared-script")


def differentiated_cast() -> dict[str, Any]:
    return cast_at(0.0, "planted-differentiated-proposer-critic-judge")


def relabeled_collapsed_cast() -> dict[str, Any]:
    """Same script, different role labels. Divergence must stay at the clone floor."""
    doc = collapsed_cast()
    doc["cast_id"] = "planted-collapsed-relabeled-roles"
    labels = ("alpha", "bravo", "charlie", "delta", "echo")
    for p, lab in zip(doc["participants"], labels):
        p["role"] = lab
        p["seat_id"] = f"seat-{lab}"
    return doc


def sweep_casts() -> list[dict[str, Any]]:
    """At least five casts of increasing similarity."""
    values = (0.00, 0.25, 0.50, 0.75, 1.00)
    return [cast_at(s, f"sweep-similarity-{s:.2f}") for s in values]


def all_named_casts() -> list[dict[str, Any]]:
    return [collapsed_cast(), differentiated_cast(), relabeled_collapsed_cast()] + sweep_casts()
