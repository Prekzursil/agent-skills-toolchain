"""Scripted four-seat councils for CNL-0088 dominance both-states + quality."""
from __future__ import annotations

from typing import Any

SEATS = ["loud", "second", "third", "fourth"]


def _turn(
    seat: str,
    tokens: int,
    text: str,
    claims: list[str] | None = None,
    proposed_answer: str | None = None,
    evidence_cites: list[str] | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "seat": seat,
        "tokens": int(tokens),
        "text": text,
        "claims": list(claims or []),
    }
    if proposed_answer is not None:
        row["proposed_answer"] = proposed_answer
    if evidence_cites:
        row["evidence_cites"] = list(evidence_cites)
    return row


def _council(
    cid: str,
    turns: list[dict],
    accepted: list[str],
    *,
    gold: str | None = None,
    answer: str | None = None,
    attestation: dict | None = None,
    expected_fire: bool | None,
    label: str,
) -> dict[str, Any]:
    if attestation is None and expected_fire is not None:
        attestation = {
            "balanced": not expected_fire,
            "no_dominance": not expected_fire,
        }
    syn: dict[str, Any] = {
        "accepted_claims": list(accepted),
        "self_attestation": attestation or {},
    }
    if answer is not None:
        syn["answer"] = answer
    doc: dict[str, Any] = {
        "id": cid,
        "label": label,
        "expected_fire": expected_fire,
        "seats": list(SEATS),
        "turns": turns,
        "synthesis": syn,
    }
    if gold is not None:
        doc["gold_answer"] = gold
    return doc


def planted_bad_airtime() -> dict:
    """Pathology present: 70% tokens and 80% surviving claims on one seat."""
    turns = []
    for i in range(7):
        turns.append(
            _turn(
                "loud",
                10,
                f"Loud restates the ship-tonight frame at length ({i}).",
                claims=[f"L{i}"],
                proposed_answer="WRONG",
            )
        )
    turns.append(
        _turn(
            "second",
            10,
            "Second: rollback testing is still missing.",
            claims=["S1"],
            proposed_answer="CORRECT",
        )
    )
    turns.append(
        _turn(
            "third",
            10,
            "Third: feature flag coverage is still missing.",
            claims=["T1"],
            proposed_answer="CORRECT",
        )
    )
    turns.append(
        _turn(
            "fourth",
            10,
            "Fourth: the maintenance window cannot absorb a failed migration.",
            claims=["F1"],
            proposed_answer="CORRECT",
        )
    )
    return _council(
        "planted-bad-airtime",
        turns,
        accepted=["L0", "L1", "L2", "L3", "S1"],
        gold="CORRECT",
        answer="WRONG",
        attestation={"balanced": True, "no_dominance": True},
        expected_fire=True,
        label="planted-bad",
    )


def planted_bad_claims_only() -> dict:
    """Even tokens (0.25 each); 4/5 surviving claims first-uttered by loud."""
    turns = [
        _turn(
            "loud",
            25,
            "Loud bundles four surviving claims into one even-airtime turn.",
            ["C1", "C2", "C3", "C4"],
            "WRONG",
        ),
        _turn(
            "second",
            25,
            "Second offers one surviving claim.",
            ["C5"],
            "CORRECT",
        ),
        _turn(
            "third",
            25,
            "Third offers a non-surviving aside.",
            ["C6"],
            "CORRECT",
        ),
        _turn(
            "fourth",
            25,
            "Fourth offers a non-surviving aside.",
            ["C7"],
            "CORRECT",
        ),
    ]
    return _council(
        "planted-bad-claims-only",
        turns,
        accepted=["C1", "C2", "C3", "C4", "C5"],
        gold="CORRECT",
        answer="WRONG",
        expected_fire=True,
        label="planted-bad",
    )


def known_present_control() -> dict:
    """Detector-control copy: known-present airtime capture. Must FIRE first."""
    doc = planted_bad_airtime()
    doc["id"] = "known-present-airtime-control"
    doc["label"] = "detector-control"
    return doc


def known_good_balanced() -> dict:
    """Pathology absent: 0.25 token and 0.25 surviving-claim share each."""
    turns = []
    for seat in SEATS:
        turns.append(
            _turn(
                seat,
                10,
                f"{seat} offers a distinct rollback check.",
                claims=[f"{seat}-a"],
                proposed_answer="CORRECT",
            )
        )
        turns.append(
            _turn(
                seat,
                10,
                f"{seat} seconds the tested-rollback requirement.",
                claims=[f"{seat}-b"],
                proposed_answer="CORRECT",
            )
        )
    accepted = [f"{s}-a" for s in SEATS]
    return _council(
        "known-good-balanced",
        turns,
        accepted=accepted,
        gold="CORRECT",
        answer="CORRECT",
        attestation={"balanced": True, "no_dominance": True},
        expected_fire=False,
        label="known-good",
    )


def attestation_cries_wolf() -> dict:
    """Balanced transcript; synthesizer attests dominance. Must stay SILENT."""
    doc = known_good_balanced()
    doc["id"] = "attestation-cries-wolf"
    doc["label"] = "negative-control"
    doc["expected_fire"] = False
    doc["synthesis"] = dict(doc["synthesis"])
    doc["synthesis"]["self_attestation"] = {
        "balanced": False,
        "no_dominance": False,
        "dominated_by": "loud",
    }
    return doc


def prolific_not_dominant() -> dict:
    """0.40 token share, even surviving claims. Below TAU. Must stay SILENT."""
    alloc = {"loud": 8, "second": 4, "third": 4, "fourth": 4}
    turns = []
    for seat, tok in alloc.items():
        turns.append(
            _turn(
                seat,
                tok,
                f"{seat} speaks {tok} tokens with one accepted idea.",
                claims=[f"{seat}-c"],
                proposed_answer="CORRECT",
            )
        )
    return _council(
        "prolific-not-dominant-0.40",
        turns,
        accepted=[f"{s}-c" for s in SEATS],
        gold="CORRECT",
        answer="CORRECT",
        expected_fire=False,
        label="clean",
    )


def quality_wrong_dominant() -> dict:
    """Loud is wrong and owns airtime. Throttle should restore CORRECT."""
    doc = planted_bad_airtime()
    doc["id"] = "quality-wrong-dominant"
    doc["label"] = "quality"
    return doc


def quality_expert_dominant() -> dict:
    """Loud is the sole correct expert. Throttle should degrade to WRONG."""
    turns = []
    for i in range(7):
        turns.append(
            _turn(
                "loud",
                10,
                f"Expert cites the rollback-window invariant ({i}).",
                claims=[f"E{i}"],
                proposed_answer="CORRECT",
            )
        )
    for seat, msg in (
        ("second", "Ship anyway."),
        ("third", "Customer pressure first."),
        ("fourth", "Rollback later."),
    ):
        turns.append(
            _turn(seat, 10, msg, claims=[f"{seat}-w"], proposed_answer="WRONG")
        )
    return _council(
        "quality-expert-dominant",
        turns,
        accepted=["E0", "E1", "E2", "E3", "second-w"],
        gold="CORRECT",
        answer="CORRECT",
        expected_fire=True,
        label="quality",
    )


def _split20(a: int, b: int, c: int, d: int) -> dict:
    alloc = [a, b, c, d]
    if sum(alloc) != 20:
        raise ValueError(f"split must sum to 20, got {alloc}")
    turns = []
    accepted = []
    for seat, tok in zip(SEATS, alloc):
        if tok <= 0:
            continue
        cid = f"{seat}-c"
        turns.append(
            _turn(
                seat,
                tok,
                f"{seat} balanced-jitter {tok} tokens.",
                claims=[cid],
                proposed_answer="CORRECT",
            )
        )
        accepted.append(cid)
    return _council(
        f"fp-balanced-{a}-{b}-{c}-{d}",
        turns,
        accepted=accepted,
        gold="CORRECT",
        answer="CORRECT",
        expected_fire=False,
        label="clean",
    )


def fp_suite() -> list[dict]:
    splits = [
        (5, 5, 5, 5),
        (6, 5, 5, 4),
        (6, 6, 4, 4),
        (7, 5, 4, 4),
        (6, 6, 5, 3),
        (7, 6, 4, 3),
        (7, 5, 5, 3),
        (6, 5, 6, 3),
        (8, 4, 4, 4),
        (7, 7, 3, 3),
        (6, 6, 6, 2),
        (8, 5, 4, 3),
    ]
    return [_split20(*split) for split in splits]


def token_concentrated(share: float, total: int = 20) -> dict:
    d = int(round(share * total))
    rest = total - d
    others = [rest // 3] * 3
    others[0] += rest - sum(others)
    alloc = [d, *others]
    turns = []
    accepted = []
    for seat, tok in zip(SEATS, alloc):
        if tok <= 0:
            continue
        cid = f"{seat}-c"
        turns.append(
            _turn(seat, tok, f"{seat} token-sweep {tok}.", [cid], "CORRECT")
        )
        accepted.append(cid)
    return _council(
        f"sweep-token-{d}-of-{total}",
        turns,
        accepted=accepted,
        expected_fire=None,
        label="sweep",
    )


def claim_concentrated(k_loud: int, n_claims: int = 8, tokens_each: int = 5) -> dict:
    loud_ids = [f"K{i}" for i in range(k_loud)]
    other_ids = [f"K{i}" for i in range(k_loud, n_claims)]
    turns = [
        _turn(
            "loud",
            tokens_each,
            f"loud claim-sweep {loud_ids}.",
            loud_ids,
            "CORRECT",
        )
    ]
    chunks = [other_ids[i::3] for i in range(3)]
    for seat, chunk in zip(SEATS[1:], chunks):
        turns.append(
            _turn(
                seat,
                tokens_each,
                f"{seat} claim-sweep {chunk}.",
                chunk,
                "CORRECT",
            )
        )
    return _council(
        f"sweep-claims-loud-{k_loud}-of-{n_claims}",
        turns,
        accepted=[f"K{i}" for i in range(n_claims)],
        expected_fire=None,
        label="sweep",
    )


PLANTED = {
    "planted-bad-airtime": planted_bad_airtime,
    "planted-bad-claims-only": planted_bad_claims_only,
}
CLEAN = {
    "known-good-balanced": known_good_balanced,
    "attestation-cries-wolf": attestation_cries_wolf,
    "prolific-not-dominant-0.40": prolific_not_dominant,
}
CONTROL = {
    "known-present-airtime-control": known_present_control,
}
QUALITY = {
    "quality-wrong-dominant": quality_wrong_dominant,
    "quality-expert-dominant": quality_expert_dominant,
}


def all_named() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for mapping in (PLANTED, CLEAN, CONTROL, QUALITY):
        for name, builder in mapping.items():
            out[name] = builder()
    for doc in fp_suite():
        out[doc["id"]] = doc
    return out
