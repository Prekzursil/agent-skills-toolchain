"""Deterministic council fixtures for CNL-0092.

Required competencies are explicit inputs (not inferred from prose). Scores
and evidence pointers are pre-registered so the detector cannot invent them.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

CRYPTO = "crypto-protocol-design"
THREAT = "threat-modeling"
PRODUCT = "product-management"
FRONTEND = "frontend-engineering"
LAW = "employment-law"

REQUIRED = [CRYPTO, THREAT]


def _seat(seat_id: str, declared, evidenced, scores) -> dict[str, Any]:
    return {
        "seat_id": seat_id,
        "declared_competencies": list(declared),
        "evidenced_competencies": dict(evidenced),
        "probe_scores": dict(scores),
    }


def _council(cid: str, seats, *, required=None, votes=None, claims=None, extra_required=None) -> dict[str, Any]:
    req = list(required if required is not None else REQUIRED)
    if extra_required:
        req = list(dict.fromkeys(req + list(extra_required)))
    unanimous_yes = [
        {"seat_id": s["seat_id"], "position": "APPROVE", "confidence": 0.97} for s in seats
    ]
    return {
        "id": cid,
        "question": {
            "question_id": f"q-{cid}",
            "text": "Should we ship the custom TLS 1.3 resumption plus session-ticket rotation design?",
            "required_competencies": req,
        },
        "seats": seats,
        "votes": votes if votes is not None else unanimous_yes,
        "claim_ids": list(claims or [f"{cid}-c1", f"{cid}-c2"]),
    }


def planted_bad() -> dict[str, Any]:
    """Pathology present: nobody evidenced+scored on CRYPTO or THREAT; still unanimous yes."""
    return _council(
        "bad-uncovered-unanimous",
        [
            _seat("pm", [PRODUCT, CRYPTO], {PRODUCT: "ev-pm-1"}, {PRODUCT: 0.91, CRYPTO: 0.22, THREAT: 0.18}),
            _seat("fe", [FRONTEND], {FRONTEND: "ev-fe-1"}, {FRONTEND: 0.88, CRYPTO: 0.31, THREAT: 0.20}),
            _seat("gen", [PRODUCT], {PRODUCT: "ev-gen-1"}, {PRODUCT: 0.80, CRYPTO: 0.40, THREAT: 0.35}),
        ],
        claims=["bad-claim-ship-it", "bad-claim-users-want-it"],
    )


def declared_only() -> dict[str, Any]:
    """Seats declare CRYPTO/THREAT in prose tags but have no evidence pointer."""
    return _council(
        "bad-declared-only",
        [
            _seat("a", [CRYPTO, THREAT], {PRODUCT: "ev-a-prod"}, {PRODUCT: 0.9, CRYPTO: 0.91, THREAT: 0.92}),
            _seat("b", [CRYPTO], {}, {CRYPTO: 0.95, THREAT: 0.11}),
        ],
    )


def evidence_without_behavior() -> dict[str, Any]:
    """Evidence pointers exist; known-answer scores do not beat the baseline."""
    return _council(
        "bad-evidence-low-score",
        [
            _seat("a", [CRYPTO], {CRYPTO: "ev-stale-crypto", THREAT: "ev-stale-threat"}, {CRYPTO: 0.50, THREAT: 0.49}),
            _seat("b", [THREAT], {THREAT: "ev-stale-threat-2"}, {CRYPTO: 0.40, THREAT: 0.50}),
        ],
    )


def behavior_without_evidence() -> dict[str, Any]:
    """High probe scores without an evidence_record_id do not cover (CNL-0015)."""
    return _council(
        "bad-score-no-evidence",
        [
            _seat("a", [CRYPTO, THREAT], {}, {CRYPTO: 0.99, THREAT: 0.99}),
            _seat("b", [PRODUCT], {PRODUCT: "ev-b"}, {PRODUCT: 0.9, CRYPTO: 0.12, THREAT: 0.10}),
        ],
    )


def sharpened_required() -> dict[str, Any]:
    """Mid-run the required set grows to include employment-law; roster does not cover it."""
    return _council(
        "bad-sharpen-law",
        [
            _seat(
                "crypto",
                [CRYPTO, THREAT],
                {CRYPTO: "ev-c1", THREAT: "ev-t1"},
                {CRYPTO: 0.84, THREAT: 0.81, LAW: 0.20},
            ),
            _seat("pm", [PRODUCT], {PRODUCT: "ev-p1"}, {PRODUCT: 0.9, LAW: 0.33}),
        ],
        extra_required=[LAW],
    )


def known_good() -> dict[str, Any]:
    """Pathology absent: split cover, evidenced + above baseline on every required competency."""
    return _council(
        "good-split-cover",
        [
            _seat("cryptographer", [CRYPTO], {CRYPTO: "ev-crypto-cal-07"}, {CRYPTO: 0.86, THREAT: 0.41, PRODUCT: 0.2}),
            _seat("threat-analyst", [THREAT], {THREAT: "ev-threat-cal-03"}, {THREAT: 0.90, CRYPTO: 0.44, PRODUCT: 0.3}),
            _seat("pm", [PRODUCT], {PRODUCT: "ev-pm-2"}, {PRODUCT: 0.88, CRYPTO: 0.21, THREAT: 0.19}),
        ],
        claims=["good-ticket-bound", "good-rotation-window", "good-threat-model"],
    )


def good_exact() -> dict[str, Any]:
    return _council(
        "good-exact",
        [
            _seat("one", [CRYPTO, THREAT], {CRYPTO: "ev-x1", THREAT: "ev-x2"}, {CRYPTO: 0.71, THREAT: 0.73}),
        ],
    )


def good_overcover() -> dict[str, Any]:
    return _council(
        "good-overcover",
        [
            _seat(
                "poly",
                [CRYPTO, THREAT, PRODUCT],
                {CRYPTO: "ev-o1", THREAT: "ev-o2", PRODUCT: "ev-o3"},
                {CRYPTO: 0.93, THREAT: 0.91, PRODUCT: 0.80},
            ),
            _seat("spare", [FRONTEND], {FRONTEND: "ev-fe-9"}, {FRONTEND: 0.95, CRYPTO: 0.10, THREAT: 0.10}),
        ],
    )


def good_redundant() -> dict[str, Any]:
    return _council(
        "good-redundant",
        [
            _seat("c1", [CRYPTO], {CRYPTO: "ev-r1", THREAT: "ev-r2"}, {CRYPTO: 0.66, THREAT: 0.70}),
            _seat("c2", [CRYPTO, THREAT], {CRYPTO: "ev-r3", THREAT: "ev-r4"}, {CRYPTO: 0.81, THREAT: 0.77}),
        ],
    )


def good_barely_above() -> dict[str, Any]:
    return _council(
        "good-barely-above-baseline",
        [
            _seat("c", [CRYPTO], {CRYPTO: "ev-b1"}, {CRYPTO: 0.5001, THREAT: 0.10}),
            _seat("t", [THREAT], {THREAT: "ev-b2"}, {THREAT: 0.5001, CRYPTO: 0.10}),
        ],
    )


def good_declared_noise() -> dict[str, Any]:
    """Unrelated declarations must not cause a fire when evidenced cover exists."""
    return _council(
        "good-declared-noise",
        [
            _seat(
                "c",
                [CRYPTO, LAW, FRONTEND],
                {CRYPTO: "ev-n1", THREAT: "ev-n2"},
                {CRYPTO: 0.77, THREAT: 0.74, LAW: 0.12, FRONTEND: 0.20},
            )
        ],
    )


def good_dissent() -> dict[str, Any]:
    """Genuine disagreement with full cover must stay silent (not role-collapse, not missing expertise)."""
    seats = [
        _seat("c", [CRYPTO], {CRYPTO: "ev-d1", THREAT: "ev-d2"}, {CRYPTO: 0.88, THREAT: 0.80}),
        _seat("t", [THREAT], {THREAT: "ev-d3", CRYPTO: "ev-d4"}, {THREAT: 0.85, CRYPTO: 0.79}),
    ]
    votes = [
        {"seat_id": "c", "position": "APPROVE", "confidence": 0.6},
        {"seat_id": "t", "position": "REJECT", "confidence": 0.7},
    ]
    return _council("good-dissent-covered", seats, votes=votes)


def good_fixtures() -> list[dict[str, Any]]:
    return [
        known_good(),
        good_exact(),
        good_overcover(),
        good_redundant(),
        good_barely_above(),
        good_declared_noise(),
        good_dissent(),
    ]


def bad_fixtures() -> list[dict[str, Any]]:
    return [
        planted_bad(),
        declared_only(),
        evidence_without_behavior(),
        behavior_without_evidence(),
        sharpened_required(),
    ]


def pool_qualified() -> list[dict[str, Any]]:
    return [
        {
            "id": "recruited-cryptographer",
            "declared_competencies": [CRYPTO, THREAT],
            "evidenced_competencies": {CRYPTO: "ev-pool-crypto", THREAT: "ev-pool-threat"},
            "probe_scores": {CRYPTO: 0.89, THREAT: 0.83},
            "new_claims": ["ticket-binding-must-cover-0-rtt", "rotation-needs-epoch-mac"],
        }
    ]


def pool_cosmetic() -> list[dict[str, Any]]:
    cand = deepcopy(pool_qualified()[0])
    cand["id"] = "rubber-stamp"
    cand["new_claims"] = ["bad-claim-ship-it"]  # already in planted_bad claim_ids
    return [cand]


def pool_empty() -> list[dict[str, Any]]:
    return []


def pool_unqualified() -> list[dict[str, Any]]:
    return [
        {
            "id": "self-described-expert",
            "declared_competencies": [CRYPTO, THREAT],
            "evidenced_competencies": {},
            "probe_scores": {CRYPTO: 0.99, THREAT: 0.99},
            "new_claims": ["looks-fine-to-me"],
        }
    ]
