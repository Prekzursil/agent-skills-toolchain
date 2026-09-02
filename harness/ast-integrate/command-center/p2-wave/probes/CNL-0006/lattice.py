#!/usr/bin/env python3
"""InformationPartition lattice: Seat × Stage × Atom visibility.

This module is pattern-agnostic. Named protocol instances are Grant lists
constructed elsewhere — they are not branches in visible().
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Iterable, Mapping

CARRIERS = ("prompt", "tool_result", "scratchpad", "summary", "transcript")


@dataclass(frozen=True)
class Atom:
    atom_id: str
    kind: str
    producer: str | None
    canary: str
    paraphrase_stems: tuple[str, ...] = ()


@dataclass(frozen=True)
class Grant:
    """Compact generator of a visibility upset.

    From ``from_stage`` inclusive to ``until_stage`` exclusive (None = open),
    every seat in ``audience`` may see ``atom_id``.
    """

    atom_id: str
    audience: frozenset[str]
    from_stage: int
    until_stage: int | None = None
    carriers: frozenset[str] = field(default_factory=lambda: frozenset(CARRIERS))


@dataclass(frozen=True)
class Partition:
    """One element of the information-partition lattice."""

    seats: tuple[str, ...]
    stage_count: int
    atoms: Mapping[str, Atom]
    grants: tuple[Grant, ...]
    type_name: str = "InformationPartition"

    def visible(self, seat: str, stage: int, atom_id: str) -> bool:
        if atom_id not in self.atoms:
            return False
        if stage < 0 or stage >= self.stage_count:
            return False
        for grant in self.grants:
            if grant.atom_id != atom_id:
                continue
            if seat not in grant.audience:
                continue
            if stage < grant.from_stage:
                continue
            if grant.until_stage is not None and stage >= grant.until_stage:
                continue
            return True
        return False

    def view(self, seat: str, stage: int) -> frozenset[str]:
        return frozenset(
            atom_id for atom_id in self.atoms if self.visible(seat, stage, atom_id)
        )

    def audience_at(self, atom_id: str, stage: int) -> frozenset[str]:
        return frozenset(
            seat for seat in self.seats if self.visible(seat, stage, atom_id)
        )


def well_formed(partition: Partition) -> list[str]:
    errors: list[str] = []
    if partition.type_name != "InformationPartition":
        errors.append("type_name must be InformationPartition")
    if partition.stage_count < 1:
        errors.append("stage_count < 1")
    seat_set = set(partition.seats)
    if len(seat_set) != len(partition.seats):
        errors.append("duplicate seat id")
    for atom_id, atom in partition.atoms.items():
        if atom.atom_id != atom_id:
            errors.append(f"atom key/id mismatch {atom_id}")
        if not atom.canary:
            errors.append(f"atom {atom_id} missing canary")
        if atom.producer is not None and atom.producer not in seat_set:
            errors.append(f"atom {atom_id} producer not a seat")
        if atom.producer is not None and not partition.visible(
            atom.producer, 0, atom_id
        ):
            errors.append(f"self-blind producer {atom.producer} on {atom_id}")
        # "self-blind" above is a well-formedness label, not a protocol name.
    for i, grant in enumerate(partition.grants):
        if grant.atom_id not in partition.atoms:
            errors.append(f"grant[{i}] unknown atom {grant.atom_id}")
        unknown = grant.audience - seat_set
        if unknown:
            errors.append(f"grant[{i}] unknown audience {sorted(unknown)}")
        if grant.from_stage < 0:
            errors.append(f"grant[{i}] from_stage < 0")
        if grant.until_stage is not None and grant.until_stage <= grant.from_stage:
            errors.append(f"grant[{i}] empty interval")
        bad_c = grant.carriers - set(CARRIERS)
        if bad_c:
            errors.append(f"grant[{i}] unknown carriers {sorted(bad_c)}")
    return errors


def to_json(partition: Partition) -> dict:
    return {
        "type_name": partition.type_name,
        "seats": list(partition.seats),
        "stage_count": partition.stage_count,
        "atoms": {
            atom_id: {
                "atom_id": atom.atom_id,
                "kind": atom.kind,
                "producer": atom.producer,
                "canary": atom.canary,
                "paraphrase_stems": list(atom.paraphrase_stems),
            }
            for atom_id, atom in partition.atoms.items()
        },
        "grants": [
            {
                "atom_id": grant.atom_id,
                "audience": sorted(grant.audience),
                "from_stage": grant.from_stage,
                "until_stage": grant.until_stage,
                "carriers": sorted(grant.carriers),
            }
            for grant in partition.grants
        ],
    }


def from_json(doc: Mapping) -> Partition:
    atoms = {
        atom_id: Atom(
            atom_id=row["atom_id"],
            kind=row["kind"],
            producer=row.get("producer"),
            canary=row["canary"],
            paraphrase_stems=tuple(row.get("paraphrase_stems") or ()),
        )
        for atom_id, row in (doc.get("atoms") or {}).items()
    }
    grants = tuple(
        Grant(
            atom_id=row["atom_id"],
            audience=frozenset(row["audience"]),
            from_stage=int(row["from_stage"]),
            until_stage=(
                None if row.get("until_stage") is None else int(row["until_stage"])
            ),
            carriers=frozenset(row.get("carriers") or CARRIERS),
        )
        for row in (doc.get("grants") or [])
    )
    return Partition(
        seats=tuple(doc["seats"]),
        stage_count=int(doc["stage_count"]),
        atoms=atoms,
        grants=grants,
        type_name=str(doc.get("type_name") or "InformationPartition"),
    )


def leq(left: Partition, right: Partition) -> bool:
    """left ≤ right iff every visibility of left is a visibility of right."""
    seats = tuple(dict.fromkeys((*left.seats, *right.seats)))
    stage_count = max(left.stage_count, right.stage_count)
    atoms = tuple(dict.fromkeys((*left.atoms, *right.atoms)))
    for seat in seats:
        for stage in range(stage_count):
            for atom_id in atoms:
                if left.visible(seat, stage, atom_id) and not right.visible(
                    seat, stage, atom_id
                ):
                    return False
    return True


def _merge_atoms(*parts: Partition) -> dict[str, Atom]:
    merged: dict[str, Atom] = {}
    for part in parts:
        for atom_id, atom in part.atoms.items():
            if atom_id in merged and merged[atom_id] != atom:
                raise ValueError(f"atom conflict on {atom_id}")
            merged[atom_id] = atom
    return merged


def join(*parts: Partition) -> Partition:
    """Lattice join: pointwise OR (more public)."""
    if not parts:
        raise ValueError("join of empty family")
    seats = tuple(dict.fromkeys(seat for part in parts for seat in part.seats))
    return Partition(
        seats=seats,
        stage_count=max(part.stage_count for part in parts),
        atoms=_merge_atoms(*parts),
        grants=tuple(grant for part in parts for grant in part.grants),
    )


def meet(left: Partition, right: Partition) -> Partition:
    """Lattice meet: pointwise AND (more secret), still a Grant list."""
    seats = tuple(dict.fromkeys((*left.seats, *right.seats)))
    stage_count = max(left.stage_count, right.stage_count)
    atoms = _merge_atoms(left, right)
    grants: list[Grant] = []
    for atom_id in atoms:
        for stage in range(stage_count):
            audience = left.audience_at(atom_id, stage) & right.audience_at(
                atom_id, stage
            )
            if audience:
                grants.append(
                    Grant(
                        atom_id=atom_id,
                        audience=frozenset(audience),
                        from_stage=stage,
                        until_stage=stage + 1,
                    )
                )
    return Partition(
        seats=seats,
        stage_count=stage_count,
        atoms=atoms,
        grants=tuple(grants),
    )


def bottom(seats: Iterable[str], stage_count: int) -> Partition:
    return Partition(
        seats=tuple(seats),
        stage_count=stage_count,
        atoms={},
        grants=(),
    )


def visible_method_protocol_tokens() -> list[str]:
    """Return protocol-name tokens if they appear inside Partition.visible.

    A non-empty result means visibility grew a named-protocol branch and the
    three catalogue patterns are no longer one lattice type.
    """
    source = inspect.getsource(Partition.visible).lower()
    tokens = ("blind", "staged", "fishbowl", "observer")
    return [tok for tok in tokens if tok in source]
