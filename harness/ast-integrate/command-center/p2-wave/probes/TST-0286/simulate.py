#!/usr/bin/env python3
"""Deterministic council simulator with pause/resume and event-sourced replay.

Catalog input `tools/council/simulate.py` is absent on this worktree, as is the
B07 persistence module. TST-0286 vendors this local runtime so the pause/resume
and replay contract can be measured rather than parked on predicate:absent.

Scripted personas are seeded state machines (TST-0257 shape): they emit
pre-authored positions, votes and dissent. They are not live model calls.

Canonical transcript hashing strips recorded-but-not-reproducible live-model
fields. Pause at round k + resume must match an uninterrupted run on the same
seed. Replay rebuilds the transcript from the event log alone.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from store import StoreError, TornWriteError, load, persist_atomic

ROUNDS = 5
PAUSE_AFTER = 2
CHILD_ROUNDS = 2
DEFAULT_SEED = "tst-0286-seed-v1"
SPEC_ID = "council.spec.tst-0286.pause-resume"
PERSONAS = ("architect", "skeptic", "pragmatist", "critic")
CHILD_PERSONAS = ("child-architect", "child-skeptic")

LIVE_FIELDS = ("live_model_text", "wall_clock_utc", "latency_ms", "sampler_draw")
REPRODUCIBLE_FIELDS = (
    "kind",
    "round",
    "persona_id",
    "text",
    "vote",
    "dissent",
    "confidence",
    "tally",
    "stopping",
    "decision",
    "replaced",
    "replacement",
    "child_id",
    "parent_round",
    "seed",
    "spec_id",
    "mode",
)


def _mix(seed: str, *parts: Any) -> str:
    material = "|".join([seed, *[str(p) for p in parts]])
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _vote_for(seed: str, round_i: int, persona_id: str) -> str:
    digest = _mix(seed, "vote", round_i, persona_id)
    return "approve" if int(digest[:2], 16) >= 0x40 else "reject"


def _confidence(seed: str, round_i: int, persona_id: str) -> int:
    digest = _mix(seed, "conf", round_i, persona_id)
    return 40 + (int(digest[:2], 16) % 51)


def _position_text(seed: str, round_i: int, persona_id: str, dissent: bool) -> str:
    tag = _mix(seed, "text", round_i, persona_id)[:12]
    stance = "dissent" if dissent else "brief"
    return f"{persona_id} r{round_i} {stance} {tag}"


def _scripted_dissent(persona_id: str, round_i: int) -> bool:
    if persona_id == "skeptic":
        return True
    if persona_id == "child-skeptic":
        return round_i == 1
    return False


def emit_position(seed: str, round_i: int, persona_id: str, mode: str) -> dict:
    dissent = _scripted_dissent(persona_id, round_i)
    vote = "reject" if dissent else _vote_for(seed, round_i, persona_id)
    event = {
        "kind": "position",
        "round": round_i,
        "persona_id": persona_id,
        "text": _position_text(seed, round_i, persona_id, dissent),
        "vote": vote,
        "dissent": dissent,
        "confidence": _confidence(seed, round_i, persona_id),
    }
    if mode == "live":
        # Recorded-but-not-reproducible: must not enter the canonical transcript.
        draw = _mix(seed, "live-draw-placeholder", round_i, persona_id)
        event["live_model_text"] = f"LIVE-NONREPRO {draw}"
        event["wall_clock_utc"] = "PLACEHOLDER"
        event["latency_ms"] = -1
        event["sampler_draw"] = "PLACEHOLDER"
    return event


def _tally(positions: list[dict]) -> dict:
    approve = sum(1 for p in positions if p.get("vote") == "approve")
    reject = sum(1 for p in positions if p.get("vote") == "reject")
    dissenters = [p["persona_id"] for p in positions if p.get("dissent")]
    return {
        "approve": approve,
        "reject": reject,
        "dissenters": dissenters,
        "majority": "approve" if approve > reject else "reject",
    }


def _stopping(round_i: int, tally: dict, last_round: int) -> dict:
    decisive = abs(tally["approve"] - tally["reject"]) >= 2
    halt = round_i >= last_round
    if halt:
        reason = "last-round"
    elif decisive:
        reason = "margin-observed-not-binding"
    else:
        reason = "continue"
    return {"halt": halt, "reason": reason, "decisive": decisive}


def _attach_live_noise(event: dict, noise_source: str) -> dict:
    out = dict(event)
    if "live_model_text" not in out:
        return out
    token = _mix(
        noise_source,
        os.getpid(),
        time.time_ns(),
        out.get("persona_id"),
        out.get("round"),
    )
    out["live_model_text"] = f"LIVE-NONREPRO {token}"
    out["wall_clock_utc"] = f"live-{token[:16]}"
    out["latency_ms"] = int(token[16:18], 16)
    out["sampler_draw"] = token[18:34]
    return out


def _run_child(seed: str, parent_round: int, mode: str, noise_source: str) -> list[dict]:
    events: list[dict] = []
    child_seed = _mix(seed, "child", parent_round)
    events.append(
        {
            "kind": "child_opened",
            "child_id": "subcouncil-0",
            "parent_round": parent_round,
            "seed": child_seed[:16],
            "mode": mode,
        }
    )
    last_tally: dict | None = None
    for r in range(1, CHILD_ROUNDS + 1):
        round_pos: list[dict] = []
        for pid in CHILD_PERSONAS:
            pos = emit_position(child_seed, r, pid, mode)
            if mode == "live":
                pos = _attach_live_noise(pos, noise_source)
            events.append(pos)
            round_pos.append(pos)
        last_tally = _tally(round_pos)
        events.append(
            {
                "kind": "child_tallied",
                "child_id": "subcouncil-0",
                "parent_round": parent_round,
                "round": r,
                "tally": last_tally,
            }
        )
    events.append(
        {
            "kind": "child_closed",
            "child_id": "subcouncil-0",
            "parent_round": parent_round,
            "decision": (last_tally or {}).get("majority", "reject"),
        }
    )
    return events


def _round_events(
    seed: str,
    round_i: int,
    personas: tuple[str, ...],
    last_round: int,
    mode: str,
    noise_source: str,
) -> list[dict]:
    events: list[dict] = [{"kind": "round_opened", "round": round_i}]
    if round_i == 4:
        events.append(
            {
                "kind": "persona_replaced",
                "round": round_i,
                "replaced": "critic",
                "replacement": "critic-alt",
            }
        )
        personas = tuple("critic-alt" if p == "critic" else p for p in personas)
    round_pos: list[dict] = []
    for pid in personas:
        pos = emit_position(seed, round_i, pid, mode)
        if mode == "live":
            pos = _attach_live_noise(pos, noise_source)
        events.append(pos)
        round_pos.append(pos)
    if round_i == 3:
        events.extend(_run_child(seed, round_i, mode, noise_source))
    tally = _tally(round_pos)
    stopping = _stopping(round_i, tally, last_round)
    events.append(
        {"kind": "round_tallied", "round": round_i, "tally": tally, "stopping": stopping}
    )
    return events


def _decision_from(events: list[dict]) -> str:
    tallies = [e for e in events if e.get("kind") == "round_tallied"]
    if not tallies:
        return "undecided"
    return str(tallies[-1]["tally"]["majority"])


def new_run(seed: str, mode: str = "scripted") -> list[dict]:
    return [
        {
            "kind": "run_started",
            "seed": seed,
            "spec_id": SPEC_ID,
            "personas": list(PERSONAS),
            "mode": mode,
            "rounds": ROUNDS,
        }
    ]


def step_until(
    events: list[dict],
    seed: str,
    stop_after_round: int | None,
    mode: str,
    noise_source: str = "live-noise",
) -> list[dict]:
    out = list(events)
    started = next(e for e in out if e.get("kind") == "run_started")
    personas = tuple(started["personas"])
    for e in out:
        if e.get("kind") == "persona_replaced":
            personas = tuple(
                e["replacement"] if p == e["replaced"] else p for p in personas
            )
    done_rounds = {e["round"] for e in out if e.get("kind") == "round_tallied"}
    next_round = 1
    while next_round in done_rounds:
        next_round += 1
    last_round = int(started.get("rounds") or ROUNDS)
    while next_round <= last_round:
        if stop_after_round is not None and next_round > stop_after_round:
            break
        chunk = _round_events(seed, next_round, personas, last_round, mode, noise_source)
        out.extend(chunk)
        for e in chunk:
            if e.get("kind") == "persona_replaced":
                personas = tuple(
                    e["replacement"] if p == e["replaced"] else p for p in personas
                )
        if any(
            e.get("kind") == "round_tallied" and e.get("round") == next_round and e["stopping"]["halt"]
            for e in chunk
        ):
            break
        next_round += 1
    completed = any(
        e.get("kind") == "round_tallied" and e.get("stopping", {}).get("halt") for e in out
    )
    if completed and not any(e.get("kind") == "run_completed" for e in out):
        out.append(
            {
                "kind": "run_completed",
                "decision": _decision_from(out),
                "seed": seed,
            }
        )
    return out


def persist(path: Path, events: list[dict]) -> None:
    persist_atomic(path, events)


def pause_at(seed: str, round_k: int, log_path: Path, mode: str = "scripted") -> list[dict]:
    events = step_until(new_run(seed, mode), seed, round_k, mode)
    events.append({"kind": "run_paused", "round": round_k, "seed": seed})
    persist(log_path, events)
    return events


def resume(log_path: Path, mode: str = "scripted", noise_source: str = "live-noise") -> list[dict]:
    events = load(log_path)
    started = next(e for e in events if e.get("kind") == "run_started")
    seed = str(started["seed"])
    paused = [e for e in events if e.get("kind") == "run_paused"]
    if not paused:
        raise StoreError("not-paused", str(log_path))
    events.append({"kind": "run_resumed", "round": paused[-1]["round"], "seed": seed})
    events = step_until(events, seed, None, mode, noise_source)
    persist(log_path, events)
    return events


def run_uninterrupted(
    seed: str, log_path: Path, mode: str = "scripted", noise_source: str = "live-noise"
) -> list[dict]:
    events = step_until(new_run(seed, mode), seed, None, mode, noise_source)
    persist(log_path, events)
    return events


def replay_from_log(log_path: Path) -> list[dict]:
    """Rebuild events from the persisted log; no persona re-emit, no side state."""
    return load(log_path)


def _strip_live(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            k: _strip_live(v)
            for k, v in obj.items()
            if k not in LIVE_FIELDS
        }
    if isinstance(obj, list):
        return [_strip_live(x) for x in obj]
    return obj


def canonical_events(events: list[dict]) -> list[dict]:
    """Events that enter the reproducible transcript (live fields stripped)."""
    keep_kinds = {
        "run_started",
        "round_opened",
        "position",
        "round_tallied",
        "persona_replaced",
        "child_opened",
        "child_tallied",
        "child_closed",
        "run_completed",
    }
    out = []
    for e in events:
        if e.get("kind") not in keep_kinds:
            continue
        stripped = _strip_live(e)
        out.append(stripped)
    return out


def transcript_bytes(events: list[dict]) -> bytes:
    body = canonical_events(events)
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def transcript_sha256(events: list[dict]) -> str:
    return hashlib.sha256(transcript_bytes(events)).hexdigest()


def first_divergence(a: list[dict], b: list[dict]) -> str | None:
    ca, cb = canonical_events(a), canonical_events(b)
    na, nb = len(ca), len(cb)
    for i in range(min(na, nb)):
        if ca[i] != cb[i]:
            ka, kb = ca[i], cb[i]
            keys = sorted(set(ka) | set(kb))
            for key in keys:
                if ka.get(key) != kb.get(key):
                    return f"canonical_events[{i}].{key}"
            return f"canonical_events[{i}]"
    if na != nb:
        return "canonical_events.length"
    return None


def dump_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


__all__ = [
    "CHILD_ROUNDS",
    "DEFAULT_SEED",
    "LIVE_FIELDS",
    "PAUSE_AFTER",
    "PERSONAS",
    "REPRODUCIBLE_FIELDS",
    "ROUNDS",
    "SPEC_ID",
    "StoreError",
    "TornWriteError",
    "canonical_events",
    "first_divergence",
    "pause_at",
    "persist",
    "replay_from_log",
    "resume",
    "run_uninterrupted",
    "transcript_bytes",
    "transcript_sha256",
]
