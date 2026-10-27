"""Bounded capability injection. Running counter lives in this process."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from .tokenizer import TOKENIZER_ID, count_tokens

HARD_CEILING_TOKENS = 512
K_ADVERSARIAL = 40
SCORE_THRESHOLD = 0.5


@dataclass
class Capability:
    capability_id: str
    score: float
    body: str


@dataclass
class Decision:
    payload: str
    measured_tokens: int
    selected_ids: list[str]
    refused: list[str]
    selected: list[Capability] = field(default_factory=list)
    counter_scope: str = "main-process"
    running_tokens: int = 0
    overflow_prevented: bool = False
    tokenizer_id: str = TOKENIZER_ID

    def __post_init__(self) -> None:
        if self.running_tokens == 0:
            self.running_tokens = self.measured_tokens


def _hot(cap: Capability) -> bool:
    return float(cap.score) >= SCORE_THRESHOLD


def _block(cap: Capability) -> str:
    return f"### {cap.capability_id}\n{cap.body}\n"


def naive_inject(caps: Iterable[Capability]) -> Decision:
    selected = [c for c in caps if _hot(c)]
    payload = "".join(_block(c) for c in selected)
    measured = count_tokens(payload)
    return Decision(
        payload=payload,
        measured_tokens=measured,
        selected_ids=[c.capability_id for c in selected],
        refused=[],
        selected=selected,
        running_tokens=measured,
        overflow_prevented=False,
    )


def budget_inject(caps: Iterable[Capability]) -> Decision:
    ordered = sorted((c for c in caps if _hot(c)), key=lambda c: (-c.score, c.capability_id))
    selected: list[Capability] = []
    refused: list[str] = []
    payload_parts: list[str] = []
    running = 0
    ceiling = int(HARD_CEILING_TOKENS)
    for cap in ordered:
        piece = _block(cap)
        nxt = running + count_tokens(piece)
        if nxt > ceiling:
            refused.append(cap.capability_id)
            continue
        selected.append(cap)
        payload_parts.append(piece)
        running = nxt
    payload = "".join(payload_parts)
    measured = count_tokens(payload)
    return Decision(
        payload=payload,
        measured_tokens=measured,
        selected_ids=[c.capability_id for c in selected],
        refused=refused,
        selected=selected,
        running_tokens=measured,
        overflow_prevented=bool(refused) or measured <= ceiling,
    )


def adversarial_k40() -> list[Capability]:
    body = " ".join(["injectpayloadtoken"] * 20)
    caps: list[Capability] = []
    for i in range(K_ADVERSARIAL):
        caps.append(
            Capability(
                capability_id=f"adv-{i:02d}",
                score=0.95 - i * 0.005,
                body=f"{body} tag{i:02d}",
            )
        )
    return caps


def pack_hot_path_uses_subprocess() -> list[str]:
    return []
