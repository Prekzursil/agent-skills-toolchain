"""Deterministic scripted-participant council with pause/resume snapshots.

Pause is a serialized replay state, not a deliberation event. Resume continues
from that state. The comparable artifact is the canonical JSONL transcript of
deliberation events. Wall-clock is synthetic; nothing reads time.time().
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from scenario import (
    DEFAULT_SEEDS,
    MAX_ROUNDS,
    PAUSE_ROUNDS,
    ROSTER,
    SCRIPTS,
    SEED_NAMES,
    TOOLS,
)


def canonical_event(event: dict[str, Any]) -> str:
    return json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def transcript_bytes(events: list[dict[str, Any]]) -> bytes:
    lines = [canonical_event(e) for e in events]
    return ("".join(line + "\n" for line in lines)).encode("utf-8")


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def digest_events(events: list[dict[str, Any]]) -> str:
    return digest_bytes(transcript_bytes(events))


def event_index_fingerprint(events: list[dict[str, Any]]) -> str:
    """Second mechanism: NUL-joined index, not JSONL sha256."""
    parts = []
    for e in events:
        parts.append(
            f"{e.get('t')}:{e.get('kind')}:{e.get('round')}:{e.get('seat', '')}:"
            f"{e.get('tool', '')}:{e.get('clock')}"
        )
    payload = "\0".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _u32(seed: int, *parts: object) -> int:
    h = hashlib.sha256()
    h.update(str(int(seed)).encode("ascii"))
    for p in parts:
        h.update(b"|")
        h.update(str(p).encode("utf-8"))
    return int.from_bytes(h.digest()[:4], "big")


def permute(items: tuple[str, ...] | list[str], seed: int, *salt: object) -> list[str]:
    arr = list(items)
    for i in range(len(arr) - 1, 0, -1):
        j = _u32(seed, "permute", i, *salt) % (i + 1)
        arr[i], arr[j] = arr[j], arr[i]
    return arr


def utterance(seat: str, round_no: int, sampling_seed: int) -> str:
    base = SCRIPTS[seat][round_no - 1]
    mix = hashlib.sha256(
        f"{sampling_seed}|{seat}|{round_no}|{base}".encode("utf-8")
    ).hexdigest()[:16]
    return f"{base} [{mix}]"


def ballot(seat: str, round_no: int, sampling_seed: int) -> str:
    n = _u32(sampling_seed, "ballot", seat, round_no)
    return "advance" if n % 2 == 0 else "hold"


def tool_args(tool: str, seat: str, round_no: int, sampling_seed: int) -> str:
    return hashlib.sha256(
        f"{sampling_seed}|tool|{tool}|{seat}|{round_no}".encode("utf-8")
    ).hexdigest()[:12]


def script_digest() -> str:
    blob = json.dumps(
        {"roster": ROSTER, "scripts": SCRIPTS, "tools": TOOLS, "max_rounds": MAX_ROUNDS},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


class CouncilSim:
    def __init__(self, seeds: dict[str, int] | None = None) -> None:
        self.seeds = {k: int(seeds[k]) for k in SEED_NAMES} if seeds else dict(DEFAULT_SEEDS)
        self.t = 0
        self.round = 1
        self.clock = 1_700_000_000 + (self.seeds["wall_clock_seed"] % 10_000)
        self.events: list[dict[str, Any]] = []
        self.stopped = False
        self.roster_order = permute(ROSTER, self.seeds["recruitment_seed"], "roster")
        self.script_digest = script_digest()

    def snapshot(self) -> dict[str, Any]:
        return {
            "clock": self.clock,
            "events": list(self.events),
            "roster_order": list(self.roster_order),
            "round": self.round,
            "script_digest": self.script_digest,
            "seeds": dict(self.seeds),
            "stopped": self.stopped,
            "t": self.t,
        }

    @classmethod
    def from_snapshot(cls, snap: dict[str, Any]) -> "CouncilSim":
        sim = cls(snap["seeds"])
        if sim.script_digest != snap["script_digest"]:
            raise ValueError("snapshot script_digest does not match this harness")
        sim.t = int(snap["t"])
        sim.round = int(snap["round"])
        sim.clock = int(snap["clock"])
        sim.events = [dict(e) for e in snap["events"]]
        sim.stopped = bool(snap["stopped"])
        sim.roster_order = list(snap["roster_order"])
        return sim

    def emit(self, payload: dict[str, Any]) -> None:
        self.t += 1
        self.clock += 1 + (_u32(self.seeds["wall_clock_seed"], "clock", self.t) % 5)
        event = {"clock": self.clock, "t": self.t, **payload}
        self.events.append(event)

    def step_round(self) -> bool:
        if self.stopped or self.round > MAX_ROUNDS:
            self.stopped = True
            return False
        r = self.round
        self.emit({"kind": "round_open", "round": r})
        for seat in self.roster_order:
            self.emit(
                {
                    "kind": "utterance",
                    "round": r,
                    "seat": seat,
                    "text": utterance(seat, r, self.seeds["sampling_seed"]),
                }
            )
            tools = permute(TOOLS, self.seeds["tool_order_seed"], seat, r)
            for tool in tools:
                self.emit(
                    {
                        "kind": "tool",
                        "round": r,
                        "seat": seat,
                        "tool": tool,
                        "args": tool_args(tool, seat, r, self.seeds["sampling_seed"]),
                    }
                )
            self.emit(
                {
                    "kind": "vote",
                    "round": r,
                    "seat": seat,
                    "ballot": ballot(seat, r, self.seeds["sampling_seed"]),
                }
            )
        if r >= MAX_ROUNDS:
            self.emit({"kind": "stopped", "reason": "max_rounds", "round": r})
            self.stopped = True
        self.round = r + 1
        return not self.stopped

    def run_to_end(self) -> "CouncilSim":
        while self.step_round():
            pass
        return self

    def run_until_round(self, pause_after_round: int) -> "CouncilSim":
        if pause_after_round < 1 or pause_after_round >= MAX_ROUNDS:
            raise ValueError("pause_after_round must be in 1..MAX_ROUNDS-1")
        while self.round <= pause_after_round and not self.stopped:
            self.step_round()
        return self

    def transcripts(self) -> dict[str, Any]:
        raw = transcript_bytes(self.events)
        return {
            "bytes": len(raw),
            "event_count": len(self.events),
            "fingerprint": event_index_fingerprint(self.events),
            "sha256": digest_bytes(raw),
        }


def perturb_seeds(seeds: dict[str, int], name: str) -> dict[str, int]:
    if name not in SEED_NAMES:
        raise KeyError(name)
    out = dict(seeds)
    out[name] = int(out[name]) ^ 0xA5A5A5A5
    return out


def first_divergence(
    a: list[dict[str, Any]], b: list[dict[str, Any]]
) -> dict[str, Any]:
    n = min(len(a), len(b))
    for i in range(n):
        if canonical_event(a[i]) != canonical_event(b[i]):
            return {
                "index": i,
                "t": a[i].get("t"),
                "kind": a[i].get("kind"),
                "a": a[i],
                "b": b[i],
            }
    if len(a) != len(b):
        return {"index": n, "kind": "length", "len_a": len(a), "len_b": len(b)}
    return {"index": None, "kind": "identical"}


def uninterrupted(seeds: dict[str, int] | None = None) -> CouncilSim:
    return CouncilSim(seeds).run_to_end()


def pause_resume(pause_after_round: int, seeds: dict[str, int] | None = None) -> CouncilSim:
    paused = CouncilSim(seeds).run_until_round(pause_after_round)
    snap = paused.snapshot()
    return CouncilSim.from_snapshot(snap).run_to_end()


def replay_from_snapshot(pause_after_round: int, seeds: dict[str, int] | None = None) -> CouncilSim:
    return pause_resume(pause_after_round, seeds)


def measure() -> dict[str, Any]:
    seeds = dict(DEFAULT_SEEDS)
    base = uninterrupted(seeds)
    base_t = base.transcripts()
    pause_rows = []
    for k in PAUSE_ROUNDS:
        resumed = pause_resume(k, seeds)
        rt = resumed.transcripts()
        snap = CouncilSim(seeds).run_until_round(k).snapshot()
        replayed = CouncilSim.from_snapshot(snap).run_to_end()
        rpt = replayed.transcripts()
        pause_rows.append(
            {
                "identical_to_uninterrupted": rt["sha256"] == base_t["sha256"],
                "pause_after_round": k,
                "replay_identical": rpt["sha256"] == base_t["sha256"],
                "replay_sha256": rpt["sha256"],
                "resume_event_count": rt["event_count"],
                "resume_fingerprint": rt["fingerprint"],
                "resume_sha256": rt["sha256"],
                "snapshot_event_count": len(snap["events"]),
                "snapshot_next_round": snap["round"],
            }
        )
    pert_rows = []
    for name in SEED_NAMES:
        psim = uninterrupted(perturb_seeds(seeds, name))
        pt = psim.transcripts()
        div = first_divergence(base.events, psim.events)
        pert_rows.append(
            {
                "diverged": pt["sha256"] != base_t["sha256"],
                "event_count": pt["event_count"],
                "first_divergence_index": div.get("index"),
                "first_divergence_kind": div.get("kind"),
                "seed": name,
                "sha256": pt["sha256"],
            }
        )
    identical = all(r["identical_to_uninterrupted"] and r["replay_identical"] for r in pause_rows)
    all_seeds_load_bearing = all(r["diverged"] for r in pert_rows)
    return {
        "all_seeds_load_bearing": all_seeds_load_bearing,
        "captured_seeds": seeds,
        "identical_seed_byte_identical": identical,
        "pause_resume": pause_rows,
        "perturbation": pert_rows,
        "script_digest": script_digest(),
        "uninterrupted": {
            **base_t,
            "final_round_emitted": MAX_ROUNDS,
            "roster_order": list(base.roster_order),
        },
    }


def main() -> int:
    doc = measure()
    print(json.dumps(doc, indent=2, sort_keys=True))
    if not doc["identical_seed_byte_identical"]:
        print("FAILED:CNL-0122-harness pause/resume or replay diverged")
        return 1
    if not doc["all_seeds_load_bearing"]:
        print("FAILED:CNL-0122-harness a captured seed was decorative")
        return 1
    print("SUCCESS:CNL-0122-harness")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
