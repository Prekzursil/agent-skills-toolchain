#!/usr/bin/env python3
"""Leak check that proves an InformationPartition held.

Two mechanically independent signals:
  1. canary / paraphrase string search over event text
  2. declared atom_refs set-minus the seat's view at that stage

A finding from either signal is a leak. Silence on both, plus a live
detector-control that finds an allowed canary, is the proof the partition held.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable, Mapping, Sequence

from lattice import Atom, Partition


@dataclass(frozen=True)
class Event:
    kind: str  # deliver | produce
    seat: str
    stage: int
    carrier: str
    text: str
    atom_refs: tuple[str, ...] = ()

    def to_json(self) -> dict:
        return {
            "kind": self.kind,
            "seat": self.seat,
            "stage": self.stage,
            "carrier": self.carrier,
            "text": self.text,
            "atom_refs": list(self.atom_refs),
        }


def event_from_json(row: Mapping) -> Event:
    return Event(
        kind=str(row["kind"]),
        seat=str(row["seat"]),
        stage=int(row["stage"]),
        carrier=str(row["carrier"]),
        text=str(row.get("text") or ""),
        atom_refs=tuple(row.get("atom_refs") or ()),
    )


def normalize(text: str) -> str:
    return " ".join(text.lower().split())


def scan_text(text: str, atoms: Iterable[Atom]) -> frozenset[str]:
    """Signal 1: canary token or registered paraphrase stem in text."""
    found: set[str] = set()
    if not text:
        return frozenset()
    raw = text
    norm = normalize(text)
    for atom in atoms:
        if atom.canary and atom.canary in raw:
            found.add(atom.atom_id)
            continue
        if atom.canary and atom.canary.lower() in norm:
            found.add(atom.atom_id)
            continue
        for stem in atom.paraphrase_stems:
            if stem and normalize(stem) in norm:
                found.add(atom.atom_id)
                break
    return frozenset(found)


@dataclass(frozen=True)
class Finding:
    seat: str
    stage: int
    carrier: str
    kind: str
    atom_id: str
    signal: str  # canary_or_paraphrase | atom_ref
    detail: str

    def to_json(self) -> dict:
        return asdict(self)


def check_transcript(
    partition: Partition, events: Sequence[Event | Mapping]
) -> list[Finding]:
    findings: list[Finding] = []
    atoms = tuple(partition.atoms.values())
    for raw in events:
        event = raw if isinstance(raw, Event) else event_from_json(raw)
        in_text = scan_text(event.text, atoms)
        declared = frozenset(event.atom_refs)
        for atom_id in sorted(in_text):
            if not partition.visible(event.seat, event.stage, atom_id):
                findings.append(
                    Finding(
                        seat=event.seat,
                        stage=event.stage,
                        carrier=event.carrier,
                        kind=event.kind,
                        atom_id=atom_id,
                        signal="canary_or_paraphrase",
                        detail=(
                            f"{event.kind} to {event.seat} at stage {event.stage} "
                            f"via {event.carrier} contains withheld atom {atom_id}"
                        ),
                    )
                )
        for atom_id in sorted(declared):
            if not partition.visible(event.seat, event.stage, atom_id):
                findings.append(
                    Finding(
                        seat=event.seat,
                        stage=event.stage,
                        carrier=event.carrier,
                        kind=event.kind,
                        atom_id=atom_id,
                        signal="atom_ref",
                        detail=(
                            f"{event.kind} to {event.seat} at stage {event.stage} "
                            f"declares withheld atom_ref {atom_id}"
                        ),
                    )
                )
    return findings


def detector_control_search_live(
    partition: Partition, events: Sequence[Event | Mapping]
) -> dict:
    """Prove the string search is not dead: an allowed canary must be found."""
    atoms = tuple(partition.atoms.values())
    hits = []
    for raw in events:
        event = raw if isinstance(raw, Event) else event_from_json(raw)
        for atom_id in scan_text(event.text, atoms):
            if partition.visible(event.seat, event.stage, atom_id):
                hits.append(
                    {
                        "seat": event.seat,
                        "stage": event.stage,
                        "carrier": event.carrier,
                        "atom_id": atom_id,
                        "canary": partition.atoms[atom_id].canary,
                    }
                )
    return {"live": bool(hits), "hits": hits}


def inject_violation(
    events: Sequence[Event],
    *,
    partition: Partition,
    seat: str,
    stage: int,
    carrier: str,
    atom_id: str,
    mode: str,
) -> list[Event]:
    """Plant a partition-violating reference into a scripted transcript.

    mode:
      canary_only — text carries the canary; atom_refs stay empty (signal 1)
      refs_only   — atom_refs names the atom; text stays clean (signal 2)
      both        — both signals
    """
    if partition.visible(seat, stage, atom_id):
        raise ValueError(
            f"injection of {atom_id} is not a violation for {seat}@{stage}"
        )
    atom = partition.atoms[atom_id]
    stem = atom.paraphrase_stems[0] if atom.paraphrase_stems else atom.atom_id
    if mode == "canary_only":
        text = (
            f"Moderator recap (summary path): {atom.canary} — paraphrased as {stem}."
        )
        refs: tuple[str, ...] = ()
    elif mode == "refs_only":
        text = "Moderator recap (summary path): no canary token in this body."
        refs = (atom_id,)
    elif mode == "both":
        text = (
            f"Moderator recap (summary path): {atom.canary} — paraphrased as {stem}."
        )
        refs = (atom_id,)
    else:
        raise ValueError(f"unknown inject mode {mode}")
    planted = Event(
        kind="deliver",
        seat=seat,
        stage=stage,
        carrier=carrier,
        text=text,
        atom_refs=refs,
    )
    return [*events, planted]
