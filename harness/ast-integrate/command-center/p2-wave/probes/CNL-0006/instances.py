#!/usr/bin/env python3
"""Three catalogue patterns as Grant lists of ONE InformationPartition type."""
from __future__ import annotations

from lattice import Atom, Grant, Partition, CARRIERS

ALL = frozenset(CARRIERS)


def _atom(
    atom_id: str,
    kind: str,
    producer: str | None,
    nonce: str,
    *stems: str,
) -> Atom:
    return Atom(
        atom_id=atom_id,
        kind=kind,
        producer=producer,
        canary=f"CNL6-CANARY-{nonce}",
        paraphrase_stems=tuple(stems),
    )


def blind_first_pass() -> Partition:
    """Independent first pass, then a reveal stage.

    Stage 0: each speaker sees the shared brief and their own draft only.
    Stage 1: drafts are released to the speaking set. Same Grant type.
    """
    seats = ("alice", "bob", "chair")
    speakers = frozenset(seats)
    brief = _atom(
        "brief.shared",
        "brief",
        None,
        "BRIEF-SHARED-A1",
        "shared opening brief for all speakers",
    )
    draft_a = _atom(
        "draft.alice",
        "draft",
        "alice",
        "DRAFT-ALICE-7F3A",
        "alice's unreleased independent draft",
    )
    draft_b = _atom(
        "draft.bob",
        "draft",
        "bob",
        "DRAFT-BOB-9C21",
        "bob's unreleased independent draft",
    )
    atoms = {a.atom_id: a for a in (brief, draft_a, draft_b)}
    grants = (
        Grant(brief.atom_id, speakers, 0),
        Grant(draft_a.atom_id, frozenset({"alice"}), 0, 1),
        Grant(draft_a.atom_id, speakers, 1),
        Grant(draft_b.atom_id, frozenset({"bob"}), 0, 1),
        Grant(draft_b.atom_id, speakers, 1),
    )
    return Partition(seats=seats, stage_count=2, atoms=atoms, grants=grants)


def staged_evidence_release() -> Partition:
    """Evidence atoms differ only in from_stage and audience.

    ev.late is withheld from everyone until stage 2.
    ev.alice_only never enters bob's view.
    """
    seats = ("alice", "bob")
    both = frozenset(seats)
    ev0 = _atom(
        "ev.early",
        "evidence",
        None,
        "EV-EARLY-11AA",
        "early public evidence bundle",
    )
    ev1 = _atom(
        "ev.mid",
        "evidence",
        None,
        "EV-MID-22BB",
        "mid-round released evidence bundle",
    )
    ev2 = _atom(
        "ev.late",
        "evidence",
        None,
        "EV-LATE-33CC",
        "late withheld evidence bundle",
    )
    ev_a = _atom(
        "ev.alice_only",
        "evidence",
        "alice",
        "EV-ALICE-44DD",
        "alice-partitioned evidence bundle",
    )
    atoms = {a.atom_id: a for a in (ev0, ev1, ev2, ev_a)}
    grants = (
        Grant(ev0.atom_id, both, 0),
        Grant(ev1.atom_id, both, 1),
        Grant(ev2.atom_id, both, 2),
        Grant(ev_a.atom_id, frozenset({"alice"}), 0),
    )
    return Partition(seats=seats, stage_count=3, atoms=atoms, grants=grants)


def fishbowl_observer_ring() -> Partition:
    """Inner speaking ring, outer observers.

    Observer notes never enter a speaker's view. Speaker utterances enter
    the observer view. Asymmetry is audience membership, not a third type.
    """
    speakers = ("speaker.a", "speaker.b")
    observers = ("observer.x", "observer.y")
    seats = speakers + observers
    bowl = frozenset(seats)
    speak = frozenset(speakers)
    watch = frozenset(observers)
    utt_a = _atom(
        "utterance.a",
        "utterance",
        "speaker.a",
        "UTT-A-55EE",
        "speaker a bowl utterance",
    )
    utt_b = _atom(
        "utterance.b",
        "utterance",
        "speaker.b",
        "UTT-B-66FF",
        "speaker b bowl utterance",
    )
    note_x = _atom(
        "note.x",
        "observer_note",
        "observer.x",
        "NOTE-X-77GG",
        "observer x private note",
    )
    note_y = _atom(
        "note.y",
        "observer_note",
        "observer.y",
        "NOTE-Y-88HH",
        "observer y private note",
    )
    atoms = {a.atom_id: a for a in (utt_a, utt_b, note_x, note_y)}
    grants = (
        Grant(utt_a.atom_id, bowl, 0),
        Grant(utt_b.atom_id, bowl, 0),
        Grant(note_x.atom_id, watch, 0),
        Grant(note_y.atom_id, watch, 0),
        Grant(utt_a.atom_id, speak, 0),  # redundant subset; join-safe
    )
    return Partition(seats=seats, stage_count=2, atoms=atoms, grants=grants)


INSTANCES = {
    "blind_first_pass": blind_first_pass,
    "staged_evidence_release": staged_evidence_release,
    "fishbowl_observer_ring": fishbowl_observer_ring,
}


def all_instances() -> dict[str, Partition]:
    return {name: factory() for name, factory in INSTANCES.items()}
