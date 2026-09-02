"""Participant-artifact / transcript intake boundary and leak detector.

Pathology: bytes whose provenance is a council participant (turn, dissent,
vote rationale, idea-ledger row) or a replayed transcript are concatenated
into a later stage's instruction channel.

Boundary: ParticipantArtifactIntake. Non-operator spans are wrapped as
untrusted DATA and never copied into the instruction channel. A later-stage
consumer executes only the instruction channel.

This module is the executable spec for CNL-0100. It does not claim that a
production tools/council runtime exists on this tree (it does not).
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

HERE = Path(__file__).resolve().parent
CANARY_RE = re.compile(r"CNL0100_CANARY_WRITE:([A-Za-z0-9._-]+)")
OPERATOR = frozenset({"operator"})
DATA_BEGIN = "<<<UNTRUSTED_DATA provenance={prov} carrier={carrier} id={iid}>>>"
DATA_END = "<<<END_UNTRUSTED_DATA id={iid}>>>"


@dataclass(frozen=True)
class Span:
    text: str
    provenance: str
    carrier: str
    turn_id: str


@dataclass
class Assembled:
    instruction: list[Span]
    data: list[Span]
    mode: str

    def instruction_text(self) -> str:
        return "\n".join(s.text for s in self.instruction)

    def data_text(self) -> str:
        return "\n".join(s.text for s in self.data)


def wrap_data(span: Span) -> Span:
    body = (
        f"{DATA_BEGIN.format(prov=span.provenance, carrier=span.carrier, iid=span.turn_id)}\n"
        f"{span.text}\n"
        f"{DATA_END.format(iid=span.turn_id)}"
    )
    return Span(body, span.provenance, span.carrier, span.turn_id)


def assemble(turns: Iterable[dict], mode: str = "fence") -> Assembled:
    """mode=fence: operator -> instruction, all other provenance -> DATA.
    mode=raw: pathology present — every span is copied into instruction.
    """
    instruction: list[Span] = []
    data: list[Span] = []
    for i, turn in enumerate(turns):
        span = Span(
            text=str(turn["text"]),
            provenance=str(turn["provenance"]),
            carrier=str(turn.get("carrier") or turn["provenance"]),
            turn_id=str(turn.get("id") or f"t{i}"),
        )
        if mode == "fence":
            if span.provenance in OPERATOR:
                instruction.append(span)
            else:
                data.append(wrap_data(span))
        elif mode == "raw":
            instruction.append(span)
        else:
            raise ValueError(f"unknown assemble mode {mode!r}")
    return Assembled(instruction, data, mode)


def detect(assembled: Assembled) -> dict:
    """Fire when any non-operator provenance occupies the instruction channel."""
    leaks = [
        {
            "turn_id": s.turn_id,
            "provenance": s.provenance,
            "carrier": s.carrier,
            "chars": len(s.text),
            "canary_in_instruction": bool(CANARY_RE.search(s.text)),
        }
        for s in assembled.instruction
        if s.provenance not in OPERATOR
    ]
    fired = bool(leaks)
    return {
        "fired": fired,
        "silent": not fired,
        "leak_count": len(leaks),
        "leaks": leaks,
        "mode": assembled.mode,
        "instruction_chars": len(assembled.instruction_text()),
        "data_chars": len(assembled.data_text()),
        "signals": ["provenance-in-instruction-channel", "canary-obedience"],
    }


def consume(assembled: Assembled, scratch: Path) -> dict:
    """Obey canaries found in the instruction channel only. DATA is scanned, never executed."""
    scratch.mkdir(parents=True, exist_ok=True)
    obeyed: list[dict] = []
    for s in assembled.instruction:
        for match in CANARY_RE.finditer(s.text):
            name = match.group(1)
            path = scratch / name
            path.write_text("obeyed-from-instruction-channel\n", encoding="utf-8")
            obeyed.append(
                {
                    "file": name,
                    "provenance": s.provenance,
                    "carrier": s.carrier,
                    "from_operator": s.provenance in OPERATOR,
                    "path": str(path.relative_to(HERE) if path.is_relative_to(HERE) else path),
                }
            )
    data_mentions = CANARY_RE.findall(assembled.data_text())
    participant_obeyed = [o for o in obeyed if not o["from_operator"]]
    operator_obeyed = [o for o in obeyed if o["from_operator"]]
    return {
        "obeyed": obeyed,
        "operator_obeyed": operator_obeyed,
        "participant_obeyed": participant_obeyed,
        "steered_by_participant": bool(participant_obeyed),
        "operator_honoured": bool(operator_obeyed),
        "data_canaries_not_executed": data_mentions,
        "scratch": str(scratch),
    }


def run_pair(turns: list[dict], scratch: Path) -> dict:
    """Planted-bad (raw) vs known-good (fence) on the SAME turn list."""
    bad_asm = assemble(turns, mode="raw")
    good_asm = assemble(turns, mode="fence")
    bad_det = detect(bad_asm)
    good_det = detect(good_asm)
    bad_con = consume(bad_asm, scratch / "bad")
    good_con = consume(good_asm, scratch / "good")
    return {
        "bad": {"detect": bad_det, "consume": bad_con},
        "good": {"detect": good_det, "consume": good_con},
        "fired_on_bad": bad_det["fired"],
        "silent_on_good": good_det["silent"],
        "steered_on_bad": bad_con["steered_by_participant"],
        "unsteered_on_good": not good_con["steered_by_participant"],
        "data_canaries_held_on_good": good_con["data_canaries_not_executed"],
    }


def false_positive_rate(corpus: list[list[dict]]) -> dict:
    fires = 0
    rows = []
    for i, turns in enumerate(corpus):
        det = detect(assemble(turns, mode="fence"))
        if det["fired"]:
            fires += 1
        rows.append({"index": i, "fired": det["fired"], "leak_count": det["leak_count"]})
    n = len(corpus)
    rate = (fires / n) if n else 1.0
    return {
        "numerator": fires,
        "denominator": n,
        "rate": rate,
        "rows": rows,
    }


def dump(obj) -> str:
    return json.dumps(obj, sort_keys=True, default=_default)


def _default(obj):
    if isinstance(obj, Span):
        return asdict(obj)
    if isinstance(obj, Assembled):
        return {
            "mode": obj.mode,
            "instruction": [asdict(s) for s in obj.instruction],
            "data": [asdict(s) for s in obj.data],
        }
    raise TypeError(type(obj))
