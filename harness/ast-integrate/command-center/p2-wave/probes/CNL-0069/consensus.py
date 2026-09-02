"""CNL-0069: what number is 0.95 consensus.

Naive formula (the one the stopping example currently implies):

    naive = n_explicit_agree / n_frozen_population

Silent seats are not counted as agree, so 19 agree + 1 silent and
19 agree + 1 reasoned dissent both yield 19/20 = 0.95. That is the
collision this unit closes.

Qualified stopping predicate consensus_ge(threshold):

    ok iff naive >= threshold
       AND silence_count == 0
       AND reasoned_dissent_count == 0
       AND token_dissent_count == 0
       AND abstain_count == 0

The comparable number for `consensus >= 0.95` is therefore not a
lone float. It is a predicate over a record whose population is the
frozen declared-seat set. Silence and reasoned dissent produce
different blocking_codes; they are not interchangeable 0.95s.
"""
from __future__ import annotations

from fractions import Fraction
from typing import Any

AGREE = "agree"
DISSENT = "dissent"
ABSTAIN = "abstain"

CLASS_AGREE = "explicit_agree"
CLASS_SILENT = "silent"
CLASS_REASONED = "reasoned_dissent"
CLASS_TOKEN = "token_dissent"
CLASS_ABSTAIN = "abstain"

BLOCK_RATIO = "RATIO_BELOW_THRESHOLD"
BLOCK_SILENCE = "SILENCE_IN_FROZEN_POPULATION"
BLOCK_REASONED = "REASONED_DISSENT_UNRESOLVED"
BLOCK_TOKEN = "TOKEN_DISSENT_UNRESOLVED"
BLOCK_ABSTAIN = "ABSTAIN_IN_FROZEN_POPULATION"

THRESHOLD = Fraction(95, 100)

NEGATIVE_CONTROL_VERBATIM = (
    "On fixture naive-095-silent (19 explicit_agree, 1 silent, n=20), "
    "naive_ratio=19/20=0.95 and consensus_ge(0.95) returns ok=False "
    "blocking_codes=['SILENCE_IN_FROZEN_POPULATION']. The check REJECTS a "
    "naive 0.95 that includes a silent seat. "
    "On fixture naive-095-reasoned-dissent (19 explicit_agree, 1 reasoned_dissent, "
    "n=20), naive_ratio=19/20=0.95 and consensus_ge(0.95) returns ok=False "
    "blocking_codes=['REASONED_DISSENT_UNRESOLVED']. The check REJECTS a naive "
    "0.95 that treats reasoned dissent as a rounding error. "
    "On fixture known-good-unanimous (20 explicit_agree, n=20), naive_ratio=20/20=1 "
    "and consensus_ge(0.95) returns ok=True blocking_codes=[]. The check is SILENT "
    "on unanimous explicit agreement."
)


def population_ids(n: int = 20) -> list[str]:
    return [f"S{i:02d}" for i in range(1, n + 1)]


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def classify_ballot(ballot: Any) -> str:
    """Mutually exclusive class for one seat's recorded ballot.

    Missing / null / empty / unknown vote => silent.
    dissent with both claim and evidence_anchor => reasoned_dissent.
    dissent otherwise => token_dissent.
    """
    if not isinstance(ballot, dict):
        return CLASS_SILENT
    vote = ballot.get("vote")
    if vote == AGREE:
        return CLASS_AGREE
    if vote == ABSTAIN:
        return CLASS_ABSTAIN
    if vote == DISSENT:
        rationale = ballot.get("rationale") or {}
        if not isinstance(rationale, dict):
            rationale = {}
        if _nonempty(rationale.get("claim")) and _nonempty(
            rationale.get("evidence_anchor")
        ):
            return CLASS_REASONED
        return CLASS_TOKEN
    return CLASS_SILENT


def tally_author(fixture: dict) -> dict:
    """Author tally: explicit loop over frozen population, if/elif classes."""
    population = list(fixture["population"])
    ballots = fixture.get("ballots") or {}
    classes: dict[str, str] = {}
    counts = {
        CLASS_AGREE: 0,
        CLASS_SILENT: 0,
        CLASS_REASONED: 0,
        CLASS_TOKEN: 0,
        CLASS_ABSTAIN: 0,
    }
    for seat in population:
        klass = classify_ballot(ballots.get(seat))
        classes[seat] = klass
        counts[klass] += 1
    n = len(population)
    if n == 0:
        raise ValueError("empty population")
    n_agree = counts[CLASS_AGREE]
    naive = Fraction(n_agree, n)
    blocking: list[str] = []
    if naive < THRESHOLD:
        blocking.append(BLOCK_RATIO)
    if counts[CLASS_SILENT] > 0:
        blocking.append(BLOCK_SILENCE)
    if counts[CLASS_REASONED] > 0:
        blocking.append(BLOCK_REASONED)
    if counts[CLASS_TOKEN] > 0:
        blocking.append(BLOCK_TOKEN)
    if counts[CLASS_ABSTAIN] > 0:
        blocking.append(BLOCK_ABSTAIN)
    return {
        "id": fixture.get("id"),
        "candidate_id": fixture.get("candidate_id"),
        "n_population": n,
        "n_explicit_agree": n_agree,
        "n_silent": counts[CLASS_SILENT],
        "n_reasoned_dissent": counts[CLASS_REASONED],
        "n_token_dissent": counts[CLASS_TOKEN],
        "n_abstain": counts[CLASS_ABSTAIN],
        "naive_numerator": n_agree,
        "naive_denominator": n,
        "naive_fraction": f"{n_agree}/{n}",
        "naive_ge_095": naive >= THRESHOLD,
        "blocking_codes": blocking,
        "stopping_ok": len(blocking) == 0,
        "seat_classes": classes,
    }


def tally_reviewer(fixture: dict) -> dict:
    """Independent recount: comprehensions + Counter, no call to tally_author.

    Classification is re-derived from raw vote/rationale fields, not by
    reading the author's blocking_codes.
    """
    from collections import Counter

    population = list(fixture["population"])
    ballots = fixture.get("ballots") or {}
    labels: list[str] = []
    for seat in population:
        raw = ballots.get(seat)
        vote = raw.get("vote") if isinstance(raw, dict) else None
        if vote == AGREE:
            labels.append(CLASS_AGREE)
            continue
        if vote == ABSTAIN:
            labels.append(CLASS_ABSTAIN)
            continue
        if vote == DISSENT:
            rat = raw.get("rationale") if isinstance(raw, dict) else None
            claim = ""
            anchor = ""
            if isinstance(rat, dict):
                claim = str(rat.get("claim") or "")
                anchor = str(rat.get("evidence_anchor") or "")
            if claim.strip() and anchor.strip():
                labels.append(CLASS_REASONED)
            else:
                labels.append(CLASS_TOKEN)
            continue
        labels.append(CLASS_SILENT)
    c = Counter(labels)
    n = len(population)
    n_agree = c[CLASS_AGREE]
    naive = Fraction(n_agree, n) if n else Fraction(0, 1)
    blocking: list[str] = []
    if naive < THRESHOLD:
        blocking.append(BLOCK_RATIO)
    if c[CLASS_SILENT]:
        blocking.append(BLOCK_SILENCE)
    if c[CLASS_REASONED]:
        blocking.append(BLOCK_REASONED)
    if c[CLASS_TOKEN]:
        blocking.append(BLOCK_TOKEN)
    if c[CLASS_ABSTAIN]:
        blocking.append(BLOCK_ABSTAIN)
    return {
        "id": fixture.get("id"),
        "n_population": n,
        "n_explicit_agree": n_agree,
        "n_silent": c[CLASS_SILENT],
        "n_reasoned_dissent": c[CLASS_REASONED],
        "n_token_dissent": c[CLASS_TOKEN],
        "n_abstain": c[CLASS_ABSTAIN],
        "naive_fraction": f"{n_agree}/{n}",
        "naive_ge_095": naive >= THRESHOLD,
        "blocking_codes": blocking,
        "stopping_ok": len(blocking) == 0,
    }


def build_fixture(fid: str, last: dict | None) -> dict:
    population = population_ids(20)
    ballots = {seat: {"vote": AGREE} for seat in population[:-1]}
    if last is not None:
        ballots[population[-1]] = last
    return {
        "id": fid,
        "candidate_id": "candidate.synthesis.v1",
        "round_id": "R3",
        "population": population,
        "ballots": ballots,
    }


def fixtures() -> dict[str, dict]:
    reasoned = {
        "vote": DISSENT,
        "rationale": {
            "claim": (
                "The candidate omits the negative-control fixture required "
                "by tests_required item 2."
            ),
            "evidence_anchor": (
                "command-center/p2-wave/probes/CNL-0069/fixtures/"
                "naive-095-reasoned-dissent.json#S20"
            ),
        },
    }
    token = {"vote": DISSENT}
    return {
        "naive-095-silent": build_fixture("naive-095-silent", None),
        "naive-095-reasoned-dissent": build_fixture(
            "naive-095-reasoned-dissent", reasoned
        ),
        "naive-095-token-dissent": build_fixture("naive-095-token-dissent", token),
        "known-good-unanimous": build_fixture(
            "known-good-unanimous", {"vote": AGREE}
        ),
    }


COUNT_FIELDS = (
    "n_population",
    "n_explicit_agree",
    "n_silent",
    "n_reasoned_dissent",
    "n_token_dissent",
    "n_abstain",
    "naive_fraction",
    "naive_ge_095",
    "stopping_ok",
)


def counts_match(a: dict, b: dict) -> tuple[bool, str]:
    for key in COUNT_FIELDS:
        if a.get(key) != b.get(key):
            return False, f"{key}: author={a.get(key)!r} reviewer={b.get(key)!r}"
    if list(a.get("blocking_codes") or []) != list(b.get("blocking_codes") or []):
        return (
            False,
            f"blocking_codes: author={a.get('blocking_codes')!r} "
            f"reviewer={b.get('blocking_codes')!r}",
        )
    return True, "match"
