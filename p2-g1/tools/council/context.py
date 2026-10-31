"""Per-seat context assembly with a declared eviction order (IMP-0338)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

EVICTION_ORDER = ("filler", "history", "optional-evidence", "elaboration")


@dataclass
class Dropped:
    kind: str
    rank: int
    sequence: int = 0
    text: str = ""
    ident: str = ""


@dataclass
class Seat:
    seat_id: str
    role: dict[str, Any]
    partition: dict[str, Any]
    task: str
    filler: str
    history: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    budget_tokens: int | None = None

    def required_anchor_ids(self) -> list[str]:
        return [str(e.get("id")) for e in self.evidence if e.get("required") and e.get("id")]


@dataclass
class Assembly:
    seat_id: str
    prompt: str
    tokens: int
    budget_tokens: int
    dropped: list[Dropped] = field(default_factory=list)
    survived: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    kind: str = "assembled"

    def __iter__(self):
        return iter(self.dropped)


@dataclass
class Retention:
    fired: bool
    survived: list[str]
    missing: list[str]
    present: list[str]


def count_tokens(text: str) -> int:
    return len([p for p in str(text).split() if p])


def eviction_policy() -> dict[str, Any]:
    return {
        "drop_first_to_last": list(EVICTION_ORDER),
        "answers": {
            "what_is_dropped_first": "filler",
            "can_required_anchors_be_evicted": False,
        },
    }


def seat_from_mapping(raw: dict[str, Any] | Seat) -> Seat:
    if isinstance(raw, Seat):
        return raw
    hist = list(raw.get("history") or [])
    return Seat(
        seat_id=str(raw.get("seat_id") or raw.get("id") or "seat"),
        role=dict(raw.get("role") or {}),
        partition=dict(raw.get("partition") or {}),
        task=str(raw.get("task") or ""),
        filler=str(raw.get("filler") or ""),
        history=hist,
        evidence=list(raw.get("evidence") or []),
        budget_tokens=raw.get("budget_tokens"),
    )


def _evidence_block(item: dict[str, Any]) -> str:
    required = bool(item.get("required"))
    ident = str(item.get("id") or "")
    body = str(item.get("body") or "")
    flag = "true" if required else "false"
    return f"[EVIDENCE required={flag} id={ident}]\n{body}\n[/EVIDENCE]\n"


def _history_block(turn: dict[str, Any]) -> str:
    idx = int(turn.get("turn_index") or turn.get("sequence") or 0)
    text = str(turn.get("text") or "")
    return f"[HISTORY seq={idx}]\n{text}\n[/HISTORY]\n"


def _render(seat: Seat, include: dict[str, Any]) -> str:
    parts: list[str] = []
    role = seat.role
    parts.append(f"[ROLE id={role.get('id','')}]\n{role.get('identity','')}\n")
    if include.get("elaboration"):
        parts.append(str(role.get("elaboration") or "") + "\n")
    parts.append("[/ROLE]\n")
    part = seat.partition
    parts.append(f"[PARTITION id={part.get('id','')}]\n{part.get('body','')}\n[/PARTITION]\n")
    parts.append(f"[TASK]\n{seat.task}\n[/TASK]\n")
    if include.get("filler") and seat.filler:
        parts.append(f"[FILLER]\n{seat.filler}\n[/FILLER]\n")
    for turn in include.get("history") or []:
        parts.append(_history_block(turn))
    for ev in include.get("evidence") or []:
        parts.append(_evidence_block(ev))
    return "".join(parts)


def _segments(seat: Seat) -> list[dict[str, Any]]:
    segs: list[dict[str, Any]] = []
    if seat.filler:
        segs.append({"kind": "filler", "rank": 0, "sequence": 0, "payload": seat.filler})
    history = sorted(seat.history, key=lambda t: int(t.get("turn_index") or 0))
    for turn in history:
        segs.append(
            {
                "kind": "history",
                "rank": 1,
                "sequence": int(turn.get("turn_index") or 0),
                "payload": turn,
            }
        )
    for ev in seat.evidence:
        if not ev.get("required"):
            segs.append(
                {
                    "kind": "optional-evidence",
                    "rank": 2,
                    "sequence": 0,
                    "payload": ev,
                    "ident": str(ev.get("id") or ""),
                }
            )
    if seat.role.get("elaboration"):
        segs.append(
            {
                "kind": "elaboration",
                "rank": 3,
                "sequence": 0,
                "payload": seat.role.get("elaboration"),
            }
        )
    return segs


def ranks_are_non_decreasing(dropped: Sequence[Dropped]) -> bool:
    last = -1
    for item in dropped:
        if item.rank < last:
            return False
        last = item.rank
    return True


def present_required_ids(prompt: str) -> list[str]:
    found: list[str] = []
    token = "id="
    start = 0
    text = prompt
    while True:
        i = text.find("[EVIDENCE", start)
        if i < 0:
            break
        j = text.find("]", i)
        if j < 0:
            break
        header = text[i:j]
        if "required=true" in header and token in header:
            ident = header.split(token, 1)[1].split()[0].strip()
            found.append(ident)
        start = j + 1
    return found


def retention_check(prompt: str, required_ids: Iterable[str]) -> Retention:
    required = [str(x) for x in required_ids]
    present = []
    missing = []
    for ident in required:
        needle = f"[EVIDENCE required=true id={ident}"
        if needle in prompt:
            present.append(ident)
        else:
            missing.append(ident)
    return Retention(
        fired=bool(missing),
        survived=list(present),
        missing=list(missing),
        present=list(present),
    )


def assemble_seat(seat: Seat | dict[str, Any], budget_tokens: int | None = None) -> Assembly:
    s = seat_from_mapping(seat if isinstance(seat, dict) else seat)
    budget = budget_tokens if budget_tokens is not None else s.budget_tokens
    if budget is None:
        budget = 10**6
    include: dict[str, Any] = {
        "filler": True,
        "elaboration": True,
        "history": list(sorted(s.history, key=lambda t: int(t.get("turn_index") or 0))),
        "evidence": list(s.evidence),
    }
    dropped: list[Dropped] = []
    prompt = _render(s, include)
    segs = _segments(s)
    idx = 0
    while count_tokens(prompt) > budget and idx < len(segs):
        seg = segs[idx]
        idx += 1
        kind = seg["kind"]
        if kind == "filler":
            include["filler"] = False
        elif kind == "history":
            turn = seg["payload"]
            include["history"] = [t for t in include["history"] if t is not turn]
        elif kind == "optional-evidence":
            ev = seg["payload"]
            include["evidence"] = [e for e in include["evidence"] if e is not ev]
        elif kind == "elaboration":
            include["elaboration"] = False
        dropped.append(
            Dropped(
                kind=kind,
                rank=int(seg["rank"]),
                sequence=int(seg["sequence"]),
                ident=str(seg.get("ident") or ""),
            )
        )
        prompt = _render(s, include)
    tokens = count_tokens(prompt)
    required = [str(e.get("id")) for e in s.evidence if e.get("required")]
    check = retention_check(prompt, required)
    return Assembly(
        seat_id=s.seat_id,
        prompt=prompt,
        tokens=tokens,
        budget_tokens=int(budget),
        dropped=dropped,
        survived=check.survived,
        missing=check.missing,
    )


def assemble_council(
    seats: Sequence[Seat | dict[str, Any]],
    default_budget: int | None = None,
) -> list[Assembly]:
    out: list[Assembly] = []
    for raw in seats:
        s = seat_from_mapping(raw if isinstance(raw, dict) else raw)
        budget = s.budget_tokens if s.budget_tokens is not None else default_budget
        out.append(assemble_seat(s, budget_tokens=budget))
    return out


def measure_token_counts(assemblies: Sequence[Assembly]) -> list[dict[str, Any]]:
    return [
        {
            "seat_id": a.seat_id,
            "tokens": a.tokens,
            "budget_tokens": a.budget_tokens,
            "dropped_kinds": [d.kind for d in a.dropped],
        }
        for a in assemblies
    ]
