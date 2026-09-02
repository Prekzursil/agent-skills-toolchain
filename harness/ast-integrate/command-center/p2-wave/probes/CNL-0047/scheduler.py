"""Turn-taking / speaking-order engine as one shared primitive (CNL-0047).

Four dials, one next_offer machine:

  1. order          — round-robin cursor over the roster
  2. speaking_right — a seat without the right is never offered a turn
  3. turn_length    — per-offer token cap
  4. quota          — per-seat spoken-token budget

A seat that is entitled (right + remaining quota + cursor) but has nothing
to add MUST YIELD: the cursor advances, quota is not consumed, the seat is
not marked disengaged. Throttle fires only when remaining quota is 0.
A remainder smaller than turn_length is still offered (partial turn).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable


SPEAK = "SPEAK"
YIELD = "YIELD"
THROTTLE = "THROTTLE"
HALT = "HALT"

Speaker = Callable[[int], dict]


@dataclass
class Seat:
    id: str
    speaking_right: bool
    quota_tokens: int
    spoken_tokens: int = 0
    yield_count: int = 0
    throttle_count: int = 0

    def remaining(self) -> int:
        return max(0, int(self.quota_tokens) - int(self.spoken_tokens))


@dataclass
class Offer:
    kind: str
    seat_id: str | None
    allowed_tokens: int
    tokens_used: int
    reason: str
    cursor_before: int
    cursor_after: int


@dataclass
class Scheduler:
    """Single primitive. Protocols do not implement their own airtime logic."""

    seats: list[Seat]
    turn_length_tokens: int
    order: str = "round-robin"
    cursor: int = 0
    log: list[Offer] = field(default_factory=list)

    def seat_by_id(self, seat_id: str) -> Seat:
        for s in self.seats:
            if s.id == seat_id:
                return s
        raise KeyError(seat_id)

    def allowed(self, seat: Seat) -> int:
        if not seat.speaking_right:
            return 0
        return min(int(self.turn_length_tokens), seat.remaining())

    def next_offer(self, speakers: dict[str, Speaker]) -> Offer:
        if self.order != "round-robin":
            raise ValueError(f"unsupported order strategy: {self.order}")
        n = len(self.seats)
        if n == 0:
            offer = Offer(HALT, None, 0, 0, "empty-roster", self.cursor, self.cursor)
            self.log.append(offer)
            return offer
        cursor_before = self.cursor
        for step in range(n):
            idx = (cursor_before + step) % n
            seat = self.seats[idx]
            if not seat.speaking_right:
                continue
            cap = self.allowed(seat)
            if cap == 0:
                seat.throttle_count += 1
                self.cursor = (idx + 1) % n
                offer = Offer(
                    THROTTLE,
                    seat.id,
                    0,
                    0,
                    "quota-exhausted",
                    cursor_before,
                    self.cursor,
                )
                self.log.append(offer)
                return offer
            fn = speakers.get(seat.id)
            if fn is None:
                act: dict = {"act": YIELD, "tokens": 0}
            else:
                act = dict(fn(cap) or {})
            kind = str(act.get("act") or YIELD).upper()
            want = int(act.get("tokens") or 0)
            if kind != SPEAK or want <= 0:
                seat.yield_count += 1
                self.cursor = (idx + 1) % n
                offer = Offer(
                    YIELD,
                    seat.id,
                    cap,
                    0,
                    "nothing-to-add",
                    cursor_before,
                    self.cursor,
                )
                self.log.append(offer)
                return offer
            used = min(want, cap)
            seat.spoken_tokens += used
            self.cursor = (idx + 1) % n
            offer = Offer(
                SPEAK,
                seat.id,
                cap,
                used,
                "spoken",
                cursor_before,
                self.cursor,
            )
            self.log.append(offer)
            return offer
        offer = Offer(HALT, None, 0, 0, "no-eligible-seat", cursor_before, cursor_before)
        self.log.append(offer)
        return offer

    def run(
        self,
        speakers: dict[str, Speaker],
        *,
        max_steps: int = 64,
        halt_on_idle_cycle: bool = True,
    ) -> list[Offer]:
        """Drive the engine until idle (a full roster pass with no SPEAK) or max_steps."""
        n = max(1, len(self.seats))
        idle = 0
        for _ in range(max_steps):
            offer = self.next_offer(speakers)
            if offer.kind == HALT:
                break
            if offer.kind == SPEAK:
                idle = 0
            else:
                idle += 1
                if halt_on_idle_cycle and idle >= n:
                    break
        return list(self.log)

    def spoken(self) -> dict[str, int]:
        return {s.id: s.spoken_tokens for s in self.seats}

    def yields(self) -> dict[str, int]:
        return {s.id: s.yield_count for s in self.seats}

    def throttles(self) -> dict[str, int]:
        return {s.id: s.throttle_count for s in self.seats}


def greedy_speaker(want_per_turn: int) -> Speaker:
    def fn(cap: int) -> dict:
        n = min(int(want_per_turn), int(cap))
        if n <= 0:
            return {"act": YIELD, "tokens": 0}
        return {"act": SPEAK, "tokens": n}

    return fn


def bag_speaker(bag: list[int]) -> Speaker:
    remaining = list(bag)

    def fn(cap: int) -> dict:
        if not remaining:
            return {"act": YIELD, "tokens": 0}
        n = min(int(remaining[0]), int(cap))
        if n <= 0:
            return {"act": YIELD, "tokens": 0}
        leftover = remaining[0] - n
        if leftover <= 0:
            remaining.pop(0)
        else:
            remaining[0] = leftover
        return {"act": SPEAK, "tokens": n}

    return fn


def yield_speaker() -> Speaker:
    return lambda cap: {"act": YIELD, "tokens": 0}


def clone_seats(rows: Iterable[dict]) -> list[Seat]:
    seats = []
    for row in rows:
        seats.append(
            Seat(
                id=str(row["id"]),
                speaking_right=bool(row.get("speaking_right", True)),
                quota_tokens=int(row["quota_tokens"]),
            )
        )
    return seats
