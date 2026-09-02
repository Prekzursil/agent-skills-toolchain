"""Fixture candidate-synthesis corpus for SYN-0014.

Named SYN-0011 adjudications and SYN-0008 candidate syntheses are absent
on this worktree. CLAIM-REGISTRY.json is present and is scanned as live.
This corpus is the stand-in synthesis stratum, labeled as fixture, sized
so the stratified read of anchored claims is at least 30.
"""
from __future__ import annotations

from copy import deepcopy

from bands import DECLARED_BANDS

# Real on-disk files used as supporting anchors.
SUPPORTING = [
    (
        "command-center/p2-wave/_measure_one_delivered.py",
        "SUCCESS:delivered",
        "direct-measurement",
    ),
    (
        "command-center/schema/coverage-matrix.schema.json",
        "coverage-matrix",
        "direct-measurement",
    ),
    (
        "command-center/p2-wave/probes/BLD-0063/matrix.py",
        "compute_matrix",
        "direct-measurement",
    ),
    (
        "command-center/p2-wave/probes/BLD-0063/questions.py",
        "ELEVEN",
        "single-inference",
    ),
    (
        "command-center/receipts/BLD-0063.json",
        "UNCOVERED",
        "direct-measurement",
    ),
    (
        "command-center/WORK-UNIT-CATALOG.json",
        "SYN-0014",
        "direct-measurement",
    ),
]


def _claim(
    cid: str,
    text: str,
    *,
    confidence: str | None = None,
    anchors: list[dict] | None = None,
    note: str = "",
) -> dict:
    return {
        "id": cid,
        "text": text,
        "confidence": confidence,
        "anchors": list(anchors or []),
        "source": "fixture:candidate-syntheses",
        "stratum": "fixture",
        "note": note,
    }


def _anchor(path: str, snippet: str, et: str) -> dict:
    return {"path": path, "snippet": snippet, "evidence_type": et}


def known_present_claim() -> dict:
    return _claim(
        "PLANT-U-01",
        "Delivery of the remaining synthesis units is almost certain.",
        confidence="almost-certain",
        anchors=[],
        note="known-present control: band with zero anchors",
    )


def both_states_claim() -> dict:
    path, snippet, et = SUPPORTING[0]
    return _claim(
        "PLANT-OK-01",
        "The delivery measure emitting SUCCESS:delivered is almost-certain given the live probe contract.",
        confidence="almost-certain",
        anchors=[_anchor(path, snippet, et)],
        note="both-states control: banded and supported",
    )


def unknown_hedge_claims() -> list[dict]:
    return [
        _claim(
            "PLANT-H-01",
            "The remaining work should work without a calibrated band.",
            note="unknown hedge: should work",
        ),
        _claim(
            "PLANT-H-02",
            "The dashboard looks fine from here.",
            note="unknown hedge: looks fine",
        ),
        _claim(
            "PLANT-H-03",
            "The rollout is likely fine even though no measurement was attached.",
            note="unknown hedge: likely fine (must not map to likely)",
        ),
        _claim(
            "PLANT-H-04",
            "Convergence is guaranteed by the majority vote.",
            note="unknown hedge: guaranteed",
        ),
    ]


def mention_claims() -> list[dict]:
    return [
        _claim(
            "PLANT-Q-01",
            "AGENTS.md defines the token 'almost-certain' as the 90-99 percent band.",
            note="use-vs-mention: quoted band name is not a use",
        ),
        _claim(
            "PLANT-Q-02",
            'The phrase "almost certain" appears in the planted known-present control.',
            note="use-vs-mention: quoted phrase is not a use",
        ),
    ]


def fixture_claims() -> list[dict]:
    claims: list[dict] = [
        known_present_claim(),
        _claim(
            "FIX-U-02",
            "Independent syntheses will likely agree once SYN-0011 lands.",
            confidence="likely",
            anchors=[],
        ),
        _claim(
            "FIX-U-03",
            "The chance the missing registry is recovered from another tree is roughly-even.",
            confidence="roughly-even",
            anchors=[],
        ),
        _claim(
            "FIX-U-04",
            "It is almost certain that every Phase 14 lens will find zero defects.",
            # band from text, no confidence field, no anchors
        ),
        _claim(
            "FIX-U-05",
            "A full CLAIM-REGISTRY.json is likely already on disk.",
            confidence="likely",
            anchors=[],
        ),
        _claim(
            "FIX-U-06",
            "Remote chance that the named adjudications file appears mid-run.",
            confidence="remote",
            anchors=[],
        ),
        both_states_claim(),
    ]

    # Supporting anchored claims: at least four per declared band.
    n = 1
    for band in DECLARED_BANDS:
        et_for = {
            "almost-certain": "direct-measurement",
            "likely": "single-inference",
            "roughly-even": "analogy",
            "unlikely": "analogy",
            "remote": "analogy",
        }[band]
        for i in range(4):
            path, snippet, _ = SUPPORTING[i % len(SUPPORTING)]
            n += 1
            claims.append(
                _claim(
                    f"FIX-S-{n:02d}",
                    f"On the measured path {path} the stated outcome is {band}.",
                    confidence=band,
                    anchors=[_anchor(path, snippet, et_for)],
                    note="supported",
                )
            )
    # Two extra almost-certain + direct-measurement so the sample is >30.
    for extra in (1, 2):
        path, snippet, et = SUPPORTING[extra]
        n += 1
        claims.append(
            _claim(
                f"FIX-S-{n:02d}",
                f"Re-reading {path} makes the file-present claim almost-certain.",
                confidence="almost-certain",
                anchors=[_anchor(path, snippet, et)],
                note="supported-extra",
            )
        )

    # Anchored but unsupported (band above evidence ceiling, or unresolved).
    claims.extend(
        [
            _claim(
                "FIX-M-01",
                "Every digest boundary is almost-certain to preserve URLs.",
                confidence="almost-certain",
                anchors=[
                    _anchor(
                        "command-center/WORK-UNIT-CATALOG.json",
                        "by analogy with a prior estate 100 percent of URLs died",
                        "analogy",
                    )
                ],
                note="almost-certain above analogy ceiling",
            ),
            _claim(
                "FIX-M-02",
                "The missing SYN-0011 file is almost-certain to contain 40 adjudications.",
                confidence="almost-certain",
                anchors=[
                    _anchor(
                        "command-center/synthesis/SYN-0011.adjudications.json",
                        "file not on this worktree",
                        "none",
                    )
                ],
                note="unresolved path + evidence_type none",
            ),
            _claim(
                "FIX-M-03",
                "Candidate syntheses likely already enumerate every claim id.",
                confidence="likely",
                anchors=[
                    _anchor(
                        "command-center/synthesis/SYN-0008.candidate-syntheses.json",
                        "unverified n=1 glance",
                        "none",
                    )
                ],
            ),
            _claim(
                "FIX-M-04",
                "The lens is almost-certain to be silent on live receipts.",
                confidence="almost-certain",
                anchors=[
                    _anchor(
                        "command-center/receipts/BLD-0063.json",
                        "n=1 unverified sample of one receipt",
                        "single-inference",
                    )
                ],
                note="weak snippet + ceiling likely < almost-certain",
            ),
            _claim(
                "FIX-M-05",
                "A second-vendor reviewer is almost-certain to have filed already.",
                confidence="almost-certain",
                anchors=[
                    _anchor(
                        "command-center/synthesis/SYN-0026.cross-vendor-meta-review.json",
                        "maybe later",
                        "single-inference",
                    )
                ],
            ),
            _claim(
                "FIX-M-06",
                "Agreement is likely total because three agents said so.",
                confidence="likely",
                anchors=[
                    _anchor(
                        "command-center/WORK-UNIT-CATALOG.json",
                        "similar to a previous majority vote",
                        "analogy",
                    )
                ],
                note="likely above analogy ceiling",
            ),
            _claim(
                "FIX-M-07",
                "The five-band vocabulary is almost-certain to match a missing AGENTS.md.",
                confidence="almost-certain",
                anchors=[
                    _anchor(
                        "AGENTS.md",
                        "section 7 not on this worktree",
                        "single-inference",
                    )
                ],
            ),
            _claim(
                "FIX-M-08",
                "Live CLAIM-REGISTRY coverage is roughly-even.",
                confidence="roughly-even",
                anchors=[
                    _anchor(
                        "command-center/CLAIM-REGISTRY.json",
                        "todo unknown",
                        "none",
                    )
                ],
            ),
        ]
    )
    claims.extend(unknown_hedge_claims())
    claims.extend(mention_claims())
    return claims


def fixture_document() -> dict:
    claims = fixture_claims()
    return {
        "id": "SYN-0014-fixture-candidate-syntheses",
        "role": "stand-in-because-named-SYN-0011-inputs-absent",
        "stratum": "fixture",
        "claims": deepcopy(claims),
    }


def known_present_document() -> dict:
    return {"claims": [known_present_claim()]}


def both_states_document() -> dict:
    return {"claims": [both_states_claim()]}


def unknown_hedge_document() -> dict:
    return {"claims": unknown_hedge_claims()}
