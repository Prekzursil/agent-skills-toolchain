#!/usr/bin/env python3
"""Scripted transcripts and both-states control for CNL-0006."""
from __future__ import annotations

import json
from pathlib import Path

from instances import all_instances
from lattice import Partition, join, leq, meet, to_json, well_formed, visible_method_protocol_tokens
from leak import Event, check_transcript, detector_control_search_live, inject_violation

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"

INJECTIONS = {
    "blind_first_pass": {
        "seat": "bob",
        "stage": 0,
        "carrier": "summary",
        "atom_id": "draft.alice",
    },
    "staged_evidence_release": {
        "seat": "bob",
        "stage": 0,
        "carrier": "summary",
        "atom_id": "ev.alice_only",
    },
    "fishbowl_observer_ring": {
        "seat": "speaker.a",
        "stage": 0,
        "carrier": "summary",
        "atom_id": "note.x",
    },
}


def _deliver(seat: str, stage: int, carrier: str, atoms: list, extra: str = "") -> Event:
    parts = [f"{atom.canary}" for atom in atoms]
    if extra:
        parts.append(extra)
    return Event(
        kind="deliver",
        seat=seat,
        stage=stage,
        carrier=carrier,
        text=" | ".join(parts),
        atom_refs=tuple(atom.atom_id for atom in atoms),
    )


def _produce(seat: str, stage: int, atom) -> Event:
    return Event(
        kind="produce",
        seat=seat,
        stage=stage,
        carrier="transcript",
        text=f"{seat} writes {atom.canary}",
        atom_refs=(atom.atom_id,),
    )


def good_events(name: str, partition: Partition) -> list[Event]:
    a = partition.atoms
    if name == "blind_first_pass":
        return [
            _deliver("alice", 0, "prompt", [a["brief.shared"], a["draft.alice"]]),
            _deliver("bob", 0, "prompt", [a["brief.shared"], a["draft.bob"]]),
            _deliver("chair", 0, "prompt", [a["brief.shared"]]),
            _produce("alice", 0, a["draft.alice"]),
            _produce("bob", 0, a["draft.bob"]),
            _deliver(
                "alice",
                1,
                "prompt",
                [a["brief.shared"], a["draft.alice"], a["draft.bob"]],
            ),
            _deliver(
                "bob",
                1,
                "prompt",
                [a["brief.shared"], a["draft.alice"], a["draft.bob"]],
            ),
        ]
    if name == "staged_evidence_release":
        return [
            _deliver("alice", 0, "prompt", [a["ev.early"], a["ev.alice_only"]]),
            _deliver("bob", 0, "prompt", [a["ev.early"]]),
            _deliver("alice", 1, "prompt", [a["ev.early"], a["ev.mid"], a["ev.alice_only"]]),
            _deliver("bob", 1, "prompt", [a["ev.early"], a["ev.mid"]]),
            _deliver(
                "alice",
                2,
                "prompt",
                [a["ev.early"], a["ev.mid"], a["ev.late"], a["ev.alice_only"]],
            ),
            _deliver("bob", 2, "prompt", [a["ev.early"], a["ev.mid"], a["ev.late"]]),
        ]
    if name == "fishbowl_observer_ring":
        return [
            _deliver("speaker.a", 0, "prompt", [a["utterance.a"], a["utterance.b"]]),
            _deliver("speaker.b", 0, "prompt", [a["utterance.a"], a["utterance.b"]]),
            _deliver(
                "observer.x",
                0,
                "prompt",
                [a["utterance.a"], a["utterance.b"], a["note.x"], a["note.y"]],
            ),
            _deliver(
                "observer.y",
                0,
                "prompt",
                [a["utterance.a"], a["utterance.b"], a["note.x"], a["note.y"]],
            ),
            _produce("speaker.a", 0, a["utterance.a"]),
            _produce("observer.x", 0, a["note.x"]),
        ]
    raise KeyError(name)


def dump_fixtures() -> None:
    FIX.mkdir(parents=True, exist_ok=True)
    for name, partition in all_instances().items():
        good = good_events(name, partition)
        spec = INJECTIONS[name]
        bad_canary = inject_violation(
            good, partition=partition, mode="canary_only", **spec
        )
        bad_refs = inject_violation(
            good, partition=partition, mode="refs_only", **spec
        )
        payload = {
            "instance": name,
            "injection": spec,
            "good": [e.to_json() for e in good],
            "bad_canary": [e.to_json() for e in bad_canary],
            "bad_refs": [e.to_json() for e in bad_refs],
        }
        (FIX / f"{name}.json").write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )


def both_states_for(name: str, partition: Partition) -> dict:
    spec = INJECTIONS[name]
    good = good_events(name, partition)
    silent = check_transcript(partition, good)
    ctrl = detector_control_search_live(partition, good)
    bad_canary = inject_violation(
        good, partition=partition, mode="canary_only", **spec
    )
    bad_refs = inject_violation(good, partition=partition, mode="refs_only", **spec)
    fire_canary = check_transcript(partition, bad_canary)
    fire_refs = check_transcript(partition, bad_refs)
    canary_signals = {f.signal for f in fire_canary}
    ref_signals = {f.signal for f in fire_refs}
    return {
        "instance": name,
        "well_formed": well_formed(partition),
        "type_name": partition.type_name,
        "injection": spec,
        "good_event_count": len(good),
        "silent_on_good": silent == [],
        "good_findings": [f.to_json() for f in silent],
        "detector_control_live": ctrl["live"],
        "detector_control_hit": (ctrl["hits"] or [None])[0],
        "fired_on_bad_canary": bool(fire_canary),
        "bad_canary_findings": [f.to_json() for f in fire_canary],
        "bad_canary_signals": sorted(canary_signals),
        "fired_on_bad_refs": bool(fire_refs),
        "bad_refs_findings": [f.to_json() for f in fire_refs],
        "bad_refs_signals": sorted(ref_signals),
        "negative_control": {
            "rejected_state": (
                f"deliver {spec['atom_id']} to {spec['seat']} at stage "
                f"{spec['stage']} via {spec['carrier']}"
            ),
            "check_does": (
                "FIRES a Finding naming the withheld atom, seat, stage, and "
                "carrier; canary_only fires signal=canary_or_paraphrase; "
                "refs_only fires signal=atom_ref"
            ),
            "verbatim_canary_finding": fire_canary[0].to_json() if fire_canary else None,
            "verbatim_refs_finding": fire_refs[0].to_json() if fire_refs else None,
        },
        "pass": (
            silent == []
            and ctrl["live"] is True
            and bool(fire_canary)
            and "canary_or_paraphrase" in canary_signals
            and bool(fire_refs)
            and "atom_ref" in ref_signals
            and well_formed(partition) == []
        ),
    }


def lattice_laws(instances: dict[str, Partition]) -> dict:
    names = list(instances)
    parts = [instances[n] for n in names]
    joined = join(*parts)
    meets = meet(parts[0], parts[1])
    tokens = visible_method_protocol_tokens()
    same_type = all(p.type_name == "InformationPartition" for p in parts)
    no_pattern_field = all("pattern" not in to_json(p) for p in parts)
    return {
        "same_type": same_type,
        "type_names": [p.type_name for p in parts],
        "no_pattern_discriminant_field": no_pattern_field,
        "visible_method_protocol_tokens": tokens,
        "visible_method_is_pattern_agnostic": tokens == [],
        "leq_reflexive": all(leq(p, p) for p in parts),
        "each_leq_join": all(leq(p, joined) for p in parts),
        "meet_leq_left": leq(meets, parts[0]),
        "meet_leq_right": leq(meets, parts[1]),
        "join_well_formed": well_formed(joined) == [],
        "join_type_name": joined.type_name,
        "pass": (
            same_type
            and no_pattern_field
            and tokens == []
            and all(leq(p, p) for p in parts)
            and all(leq(p, joined) for p in parts)
            and leq(meets, parts[0])
            and leq(meets, parts[1])
            and well_formed(joined) == []
        ),
    }


def run_report() -> dict:
    instances = all_instances()
    rows = [both_states_for(name, part) for name, part in instances.items()]
    return {
        "rows": rows,
        "all_pass": all(row["pass"] for row in rows),
        "lattice": lattice_laws(instances),
        "instances_json": {name: to_json(part) for name, part in instances.items()},
    }
