"""Independent recount for CNL-0021.

Probe 1 groups with defaultdict by canonical_model and walks the event log.
This module re-tabulates with nested pairwise comparison and a ballot table
keyed by (round_id, seat_id, option) — a different mechanism, not a re-read
of the author's summary dict.
"""
from __future__ import annotations

from runtime import Ballot, Council, Seat, canonical_model


def pairwise_duplicate_seat_ids(seats: list[Seat]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    n = len(seats)
    for i in range(n):
        ki = canonical_model(seats[i].model)
        if ki is None:
            continue
        for j in range(i + 1, n):
            kj = canonical_model(seats[j].model)
            if kj is None:
                continue
            if ki == kj:
                a, b = sorted((seats[i].seat_id, seats[j].seat_id))
                pairs.append((a, b))
    return sorted(set(pairs))


def unattested_seat_ids(seats: list[Seat]) -> list[str]:
    return sorted(s.seat_id for s in seats if canonical_model(s.model) is None)


def ballot_table(council: Council) -> dict[tuple[int, str, str], int]:
    table: dict[tuple[int, str, str], int] = {}
    for b in council.ballots:
        key = (b.round_id, b.seat_id, b.option)
        table[key] = table.get(key, 0) + 1
    return table


def ballots_for_seat(table: dict[tuple[int, str, str], int], seat_id: str) -> int:
    return sum(n for (rnd, sid, _opt), n in table.items() if sid == seat_id)


def inherited_count_from_table(
    table: dict[tuple[int, str, str], int],
    dead_id: str,
    replacement_id: str,
) -> int:
    dead_rounds = {rnd for (rnd, sid, _opt) in table if sid == dead_id}
    total = 0
    for (rnd, sid, _opt), n in table.items():
        if sid == replacement_id and rnd in dead_rounds:
            total += n
    return total


def idea_origin_table(council: Council) -> dict[str, str]:
    return {i.idea_id: i.originator_seat_id for i in council.ideas}


def recount_death(council: Council, dead_id: str, replacement_id: str) -> dict:
    table = ballot_table(council)
    return {
        "status": council.status,
        "steps": council.steps,
        "hung": council.status == "HUNG",
        "dead_ballots": ballots_for_seat(table, dead_id),
        "replacement_ballots": ballots_for_seat(table, replacement_id),
        "inherited": inherited_count_from_table(table, dead_id, replacement_id),
        "idea_origins": idea_origin_table(council),
        "living": sorted(s.seat_id for s in council.seats if s.alive),
        "replacement_map": dict(sorted(council.replacement_of.items())),
    }
