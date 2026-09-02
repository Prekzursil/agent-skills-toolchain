#!/usr/bin/env python3
"""Deterministic scripted-participant council for CNL-0011 replay-state.

Four named RNG streams (sampling, tool_order, clock, recruitment) are the
only sources of choice. Draws are SHA-256(seed:cursor) so they do not depend
on PYTHONHASHSEED or random.Random. Wall-clock is never read.

The serialised blob is the claimed minimal pause/resume state. Resume must
produce a transcript byte-identical to an uninterrupted run.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

AXES = ("sampling", "tool_order", "clock", "recruitment")
HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "scenario.json"


def canonical_bytes(obj: Any) -> bytes:
    return (
        json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n"
    ).encode("ascii")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_obj(obj: Any) -> str:
    return sha256_bytes(canonical_bytes(obj))


def draw_u32(seed: int, cursor: int) -> int:
    material = f"{int(seed)}:{int(cursor)}".encode("ascii")
    return int.from_bytes(hashlib.sha256(material).digest()[:4], "big")


def load_scenario(path: Path | None = None) -> dict:
    p = path or FIXTURE
    return json.loads(p.read_text(encoding="utf-8"))


class ReplayCouncil:
    """Scripted council whose pause blob is the CNL-0011 replay-state model."""

    def __init__(self, scenario: dict | None = None, seeds: dict | None = None):
        sc = deepcopy(scenario or load_scenario())
        self.spec = deepcopy(sc["spec"])
        self.pool = deepcopy(sc["pool"])
        self.seeds = {k: int((seeds or sc["seeds"])[k]) for k in AXES}
        self.cursors = {k: 0 for k in AXES}
        self.clock_origin_ms: int | None = None
        self.roster: list[str] | None = None
        self.transcript: list[dict] = []
        self.pending: list[dict] = []
        self.flush_queue: list[dict] = []
        self.turn_i = 0
        self.round_i = 0
        self.sub = "utter"  # utter | call
        self.budgets = deepcopy(self.spec["initial_budgets"])
        self.stopped = False
        self.stop_reason: str | None = None
        self._want_stop = False

    def draw(self, axis: str) -> int:
        if axis not in AXES:
            raise ValueError(axis)
        value = draw_u32(self.seeds[axis], self.cursors[axis])
        self.cursors[axis] += 1
        return value

    def _t_ms(self) -> int:
        if self.clock_origin_ms is None:
            # Clock seed is captured once as origin. Never time.time().
            self.clock_origin_ms = self.draw("clock") % 10_000 * 1000
        return int(self.clock_origin_ms) + len(self.transcript) * int(
            self.spec["tick_ms"]
        )

    def _emit(self, kind: str, actor: str, body: str, extra: dict | None = None) -> dict:
        event = {
            "i": len(self.transcript),
            "t_ms": self._t_ms(),
            "kind": kind,
            "actor": actor,
            "body": body,
        }
        if extra:
            event.update(extra)
        self.transcript.append(event)
        return event

    def _pool_by_id(self) -> dict[str, dict]:
        return {p["id"]: p for p in self.pool}

    def _do_recruit(self) -> None:
        ids = [p["id"] for p in self.pool]
        n = len(ids)
        for i in range(n - 1, 0, -1):
            j = self.draw("recruitment") % (i + 1)
            ids[i], ids[j] = ids[j], ids[i]
        k = int(self.spec["n_recruit"])
        self.roster = ids[:k]
        self._emit(
            "recruit",
            "runtime",
            ",".join(self.roster),
            {"roster": list(self.roster)},
        )

    def _do_utter(self, speaker: str) -> None:
        rec = self._pool_by_id()[speaker]
        phrases = list(rec["phrases"])
        # temperature > 0 makes sampling seed load-bearing (T=0 would pick [0]).
        idx = self.draw("sampling") % len(phrases) if self.spec["temperature"] > 0 else 0
        phrase = phrases[idx]
        self.budgets["turns_remaining"] -= 1
        self.budgets["tokens_remaining"] -= len(phrase)
        self._emit(
            "utter",
            speaker,
            phrase,
            {"phrase_index": idx, "budgets": deepcopy(self.budgets)},
        )

    def _do_tool_call(self, speaker: str) -> None:
        rec = self._pool_by_id()[speaker]
        # Sampling also chooses a nonce so the sampling axis is not decorative
        # even if phrase collision were ever to occur.
        nonce = self.draw("sampling") % 97
        call = {
            "speaker": speaker,
            "tool": rec["tool"],
            "nonce": nonce,
        }
        self.pending.append(call)
        self._emit(
            "tool_call",
            speaker,
            rec["tool"],
            {"tool": rec["tool"], "nonce": nonce},
        )

    def _permute_pending(self) -> None:
        items = list(self.pending)
        self.pending = []
        for i in range(len(items) - 1, 0, -1):
            j = self.draw("tool_order") % (i + 1)
            items[i], items[j] = items[j], items[i]
        self.flush_queue = items

    def _do_tool_result(self, call: dict) -> None:
        self._emit(
            "tool_result",
            "runtime",
            f"{call['tool']}:{call['nonce']}",
            {"tool": call["tool"], "nonce": call["nonce"], "speaker": call["speaker"]},
        )

    def _do_stop(self) -> None:
        if self.budgets["turns_remaining"] <= 0:
            self.stop_reason = "budget"
        else:
            self.stop_reason = "complete"
        self.stopped = True
        self._emit("stop", "runtime", self.stop_reason, {"reason": self.stop_reason})

    def step(self) -> bool:
        """Append exactly one event. Return False if already finished."""
        if self.stopped:
            return False
        if self._want_stop:
            self._do_stop()
            return True
        if self.roster is None:
            self._do_recruit()
            return True
        if self.flush_queue:
            self._do_tool_result(self.flush_queue.pop(0))
            if not self.flush_queue:
                self.round_i += 1
                self.turn_i = 0
                self.sub = "utter"
                if self.round_i >= int(self.spec["max_rounds"]) or self.budgets[
                    "turns_remaining"
                ] <= 0:
                    self._want_stop = True
            return True
        if self.turn_i < len(self.roster):
            speaker = self.roster[self.turn_i]
            if self.sub == "utter":
                self._do_utter(speaker)
                self.sub = "call"
            else:
                self._do_tool_call(speaker)
                self.turn_i += 1
                self.sub = "utter"
                if self.turn_i >= len(self.roster):
                    self._permute_pending()
            return True
        self._want_stop = True
        self._do_stop()
        return True

    def run_n(self, n: int) -> None:
        while len(self.transcript) < n and self.step():
            pass

    def run_complete(self) -> None:
        while self.step():
            pass

    def serialize(self) -> dict:
        """Minimal pause blob. See CNL-0011 artifact for the field table."""
        return {
            "schema": "cnl-0011.replay-state.v1",
            "spec": deepcopy(self.spec),
            "spec_hash": sha256_obj(self.spec),
            "pool": deepcopy(self.pool),
            "pool_hash": sha256_obj(self.pool),
            "seeds": dict(self.seeds),
            "cursors": dict(self.cursors),
            "clock_origin_ms": self.clock_origin_ms,
            "roster": None if self.roster is None else list(self.roster),
            "transcript": deepcopy(self.transcript),
            "pending": deepcopy(self.pending),
            "flush_queue": deepcopy(self.flush_queue),
            "turn_i": self.turn_i,
            "round_i": self.round_i,
            "sub": self.sub,
            "budgets": deepcopy(self.budgets),
            "stopped": self.stopped,
            "stop_reason": self.stop_reason,
            "want_stop": self._want_stop,
        }

    @classmethod
    def resume(cls, blob: dict, scenario: dict | None = None) -> "ReplayCouncil":
        sc = deepcopy(scenario or load_scenario())
        inst = cls(sc, seeds=blob["seeds"])
        inst.spec = deepcopy(blob["spec"])
        inst.pool = deepcopy(blob["pool"])
        inst.seeds = {k: int(blob["seeds"][k]) for k in AXES}
        inst.cursors = {k: int(blob["cursors"][k]) for k in AXES}
        inst.clock_origin_ms = blob["clock_origin_ms"]
        inst.roster = None if blob["roster"] is None else list(blob["roster"])
        inst.transcript = deepcopy(blob["transcript"])
        inst.pending = deepcopy(blob["pending"])
        inst.flush_queue = deepcopy(blob["flush_queue"])
        inst.turn_i = int(blob["turn_i"])
        inst.round_i = int(blob["round_i"])
        inst.sub = str(blob["sub"])
        inst.budgets = deepcopy(blob["budgets"])
        inst.stopped = bool(blob["stopped"])
        inst.stop_reason = blob["stop_reason"]
        inst._want_stop = bool(blob.get("want_stop", False))
        return inst

    def transcript_sha(self) -> str:
        return sha256_obj(self.transcript)


class DecorativeSamplingCouncil(ReplayCouncil):
    """Mutant: sampling draws are ignored. Probe 2 must FIRE on this."""

    def draw(self, axis: str) -> int:
        if axis == "sampling":
            self.cursors[axis] += 1
            return 0
        return super().draw(axis)


def run_from_seeds(seeds: dict | None = None) -> ReplayCouncil:
    c = ReplayCouncil(seeds=seeds)
    c.run_complete()
    return c


def pause_resume_match(pause_after: int = 5) -> dict:
    a = ReplayCouncil()
    a.run_complete()
    b = ReplayCouncil()
    b.run_n(pause_after)
    blob = json.loads(json.dumps(b.serialize(), sort_keys=True))
    c = ReplayCouncil.resume(blob)
    c.run_complete()
    return {
        "pause_after": pause_after,
        "uninterrupted_sha": a.transcript_sha(),
        "resumed_sha": c.transcript_sha(),
        "uninterrupted_events": len(a.transcript),
        "resumed_events": len(c.transcript),
        "match": a.transcript_sha() == c.transcript_sha()
        and a.transcript == c.transcript,
        "serialized_keys": sorted(blob.keys()),
    }


def two_run_identity() -> dict:
    a = run_from_seeds()
    b = run_from_seeds()
    return {
        "sha_a": a.transcript_sha(),
        "sha_b": b.transcript_sha(),
        "events": len(a.transcript),
        "match": a.transcript == b.transcript and a.transcript_sha() == b.transcript_sha(),
        "line_join_sha_a": sha256_bytes(
            ("\n".join(json.dumps(e, sort_keys=True, separators=(",", ":")) for e in a.transcript) + "\n").encode("ascii")
        ),
        "line_join_sha_b": sha256_bytes(
            ("\n".join(json.dumps(e, sort_keys=True, separators=(",", ":")) for e in b.transcript) + "\n").encode("ascii")
        ),
    }


def first_diff(left: list, right: list) -> dict:
    n = min(len(left), len(right))
    for i in range(n):
        if left[i] != right[i]:
            return {
                "index": i,
                "left": left[i],
                "right": right[i],
                "length_left": len(left),
                "length_right": len(right),
            }
    if len(left) != len(right):
        return {
            "index": n,
            "left": None if len(left) <= n else left[n],
            "right": None if len(right) <= n else right[n],
            "length_left": len(left),
            "length_right": len(right),
        }
    return {
        "index": None,
        "left": None,
        "right": None,
        "length_left": len(left),
        "length_right": len(right),
    }


def perturb_axis(axis: str, delta: int = 1) -> dict:
    base_seeds = dict(load_scenario()["seeds"])
    other = dict(base_seeds)
    other[axis] = int(other[axis]) + delta
    a = run_from_seeds(base_seeds)
    b = run_from_seeds(other)
    diff = first_diff(a.transcript, b.transcript)
    return {
        "axis": axis,
        "base_seed": base_seeds[axis],
        "perturbed_seed": other[axis],
        "sha_base": a.transcript_sha(),
        "sha_perturbed": b.transcript_sha(),
        "changed": a.transcript_sha() != b.transcript_sha(),
        "first_diff_index": diff["index"],
        "first_diff_kind_base": None if diff["left"] is None else diff["left"].get("kind"),
        "first_diff_kind_perturbed": None
        if diff["right"] is None
        else diff["right"].get("kind"),
    }


def mutant_sampling_is_decorative() -> dict:
    """Both-states: real engine changes; mutant that ignores sampling does not."""
    base = dict(load_scenario()["seeds"])
    other = dict(base)
    other["sampling"] = int(base["sampling"]) + 1
    real_a = run_from_seeds(base)
    real_b = run_from_seeds(other)
    mut_a = DecorativeSamplingCouncil(seeds=base)
    mut_a.run_complete()
    mut_b = DecorativeSamplingCouncil(seeds=other)
    mut_b.run_complete()
    return {
        "real_changes": real_a.transcript_sha() != real_b.transcript_sha(),
        "mutant_changes": mut_a.transcript_sha() != mut_b.transcript_sha(),
        "real_sha_base": real_a.transcript_sha(),
        "real_sha_perturbed": real_b.transcript_sha(),
        "mutant_sha_base": mut_a.transcript_sha(),
        "mutant_sha_perturbed": mut_b.transcript_sha(),
        "check_silent_on_real": real_a.transcript_sha() != real_b.transcript_sha(),
        "check_fires_on_mutant": mut_a.transcript_sha() == mut_b.transcript_sha(),
    }


def independent_recount(transcript: list[dict]) -> dict:
    """Second mechanism: recount from events, not from engine internals."""
    kinds: dict[str, int] = {}
    actors: list[str] = []
    t_ms: list[int] = []
    roster = None
    tool_results: list[str] = []
    for e in transcript:
        kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
        actors.append(e["actor"])
        t_ms.append(e["t_ms"])
        if e["kind"] == "recruit":
            roster = list(e.get("roster") or [])
        if e["kind"] == "tool_result":
            tool_results.append(e["body"])
    ticks_ok = all(t_ms[i] < t_ms[i + 1] for i in range(len(t_ms) - 1)) if t_ms else True
    return {
        "event_count": len(transcript),
        "kinds": kinds,
        "actor_sequence": actors,
        "t_ms": t_ms,
        "ticks_strictly_increasing": ticks_ok,
        "roster": roster,
        "tool_result_sequence": tool_results,
    }
