"""Blind-first council round: no peer text until the legitimate barrier. IMP-0290."""
from __future__ import annotations


class BlindFirstError(RuntimeError):
    pass


class LogicalClock:
    def __init__(self, start: float = 0.0):
        self.now = float(start)

    def advance(self, step: float = 1.0) -> float:
        self.now += step
        return self.now


class BlindFirstRound:
    def __init__(self, seats, *, shared_brief: str, deadline: float, clock: LogicalClock):
        self.seats = tuple(seats)
        self.shared_brief = shared_brief
        self.deadline = float(deadline)
        self.clock = clock
        self._sealed: dict[str, str] = {}
        self._streams: dict[str, str] = {}
        self._submit_ts: dict[str, float] = {}
        self._barrier: float | None = None
        self._timed_out: set[str] = set()
        self._events: list[dict] = []
        self._delivered_before: list[str] = []
        self._forced = False
        self._assembled: list[tuple[str, str]] = []
        self._actual_opened_at: float | None = None
        self._prompt_log: list = []

    def assemble_prompt(self, seat: str) -> str:
        parts = [self.shared_brief]
        if self._forced and self._barrier is None:
            for other, text in self._sealed.items():
                if other != seat:
                    parts.append(text)
                    self._events.append({"kind": "DELIVER", "to": seat, "from": other, "ts": self.clock.now, "early": True})
            out = "\n".join(parts)
            self._assembled.append((seat, out))
            self._log_prompt(seat, out)
            return out
        if self._barrier is None:
            if seat in self._timed_out:
                parts.append("TIMEOUT")
            out = "\n".join(parts)
            self._assembled.append((seat, out))
            self._log_prompt(seat, out)
            return out
        if seat in self._timed_out or seat not in self._sealed:
            parts.append("TIMEOUT")
            return "\n".join(parts)
        for other, text in self._sealed.items():
            if other == seat:
                continue
            parts.append(text)
            self._events.append({"kind": "DELIVER", "to": seat, "from": other, "ts": self.clock.now})
        out = "\n".join(parts)
        self._log_prompt(seat, out)
        return out

    def _log_prompt(self, seat: str, text: str) -> None:
        class Rec:
            def __init__(self, seat: str, text: str, ts: float) -> None:
                self.seat = seat
                self.text = text
                self.ts = ts

        self._prompt_log.append(Rec(seat, text, float(self.clock.now)))

    def prompt_log(self) -> list:
        return list(self._prompt_log)

    def submit(self, seat: str, text: str) -> None:
        if self._barrier is not None:
            raise BlindFirstError("submit after legitimate barrier")
        if self.clock.now >= self.deadline:
            raise BlindFirstError("submit after deadline")
        self._sealed[seat] = text
        self._submit_ts[seat] = self.clock.now
        self._events.append({"kind": "SUBMIT", "seat": seat, "ts": self.clock.now})
        if set(self._sealed) == set(self.seats):
            self._barrier = self.clock.now

    def submit_chunk(self, seat: str, chunk: str) -> None:
        if self._barrier is not None:
            raise BlindFirstError("stream after barrier")
        self._streams[seat] = self._streams.get(seat, "") + chunk

    def finalize_stream(self, seat: str) -> None:
        text = self._streams.get(seat, "")
        if text:
            self.submit(seat, text)

    def tick(self) -> None:
        if self._barrier is not None:
            return
        if self.clock.now >= self.deadline:
            self._barrier = self.deadline
            for seat in self.seats:
                if seat not in self._sealed:
                    self._timed_out.add(seat)

    def open_barrier(self, force: bool = False) -> float | None:
        if force:
            self._forced = True
            self._actual_opened_at = float(self.clock.now)
            return True
        if set(self._sealed) == set(self.seats):
            self._barrier = self.clock.now
            self._actual_opened_at = float(self.clock.now)
        return self._barrier

    def legitimate_barrier_at(self) -> float | None:
        return self._barrier

    def barrier_actually_open(self) -> bool:
        return self._barrier is not None or self._forced

    def scan_delivered_prompts(self) -> list:
        leaks = []

        class Hit:
            def __init__(self, peer_seat: str, prompt_seat: str):
                self.peer_seat = peer_seat
                self.prompt_seat = prompt_seat

        for seat, prompt in self._assembled:
            for other, text in self._sealed.items():
                if other == seat:
                    continue
                if self._barrier is None or (self._forced and self._barrier is None):
                    if text and text in prompt:
                        leaks.append(Hit(other, seat))
                elif self._forced:
                    if text and text in prompt:
                        leaks.append(Hit(other, seat))
        if self._forced:
            for seat, prompt in self._assembled:
                for other, text in self._sealed.items():
                    if other != seat and any(tok in prompt for tok in text.split()[-1:]):
                        hit = Hit(other, seat)
                        if not any(h.peer_seat == other and h.prompt_seat == seat for h in leaks):
                            leaks.append(hit)
        return leaks

    def audit_event_order(self) -> dict:
        delivers = [e for e in self._events if e["kind"] == "DELIVER"]
        submits = [e for e in self._events if e["kind"] == "SUBMIT"]
        violations = []
        for e in delivers:
            if e.get("early") or self._barrier is None or e["ts"] < (self._barrier or 0):
                if e.get("early") or self._barrier is None:
                    violations.append(e)
                elif self._barrier is not None and e["ts"] < self._barrier:
                    violations.append(e)
        return {
            "ok": not violations,
            "violations": violations,
            "deliver_events": len(delivers),
            "submit_events": len(submits),
        }
