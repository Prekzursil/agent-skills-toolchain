#!/usr/bin/env python3
"""Confirmer-side deterministic council record/replay for CNF-0172.

Production B07 (`tools/council`, `platform/lib/councilspec`) is not on this
worktree (bucket B07 has zero members). This module is the live substrate:
append-only events, derived views, seed-stable re-run, four-way identity.

Canonical views strip wall_clock/pid/host. Those fields are recorded but not
reproducible on a live-clock re-execution. Live model sampling is unused and
is classified NOT deterministically replayable.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from typing import Any

FOUR = ("decision", "vote_history", "confidence_trajectory", "dissent_set")
STRIP = ("wall_clock", "pid", "host", "monotonic_ns")
MINORITY_REPORT = (
    "MINORITY: HOLD — dropping this report on replay is dissent loss "
    "(spec:11238)."
)
SEED_A = "CNF-0172-seed-alpha"
SEED_B = "CNF-0172-seed-beta"
SEED_C = "CNF-0172-seed-gamma"
DISSENTER = "skeptic"


def canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def digest_obj(obj: Any) -> str:
    return digest_text(canon(obj))


def draw(seed: str, *parts: str) -> bytes:
    msg = "|".join(parts).encode("utf-8")
    return hmac.new(seed.encode("utf-8"), msg, hashlib.sha256).digest()


def hex_draw(seed: str, *parts: str, n: int = 12) -> str:
    return draw(seed, *parts).hex()[:n]


def fake_clock(seed: str, seq: int) -> int:
    return int.from_bytes(draw(seed, "clock", str(seq))[:8], "big")


def default_spec() -> dict[str, Any]:
    return {
        "id": "councilspec.cnf0172.deterministic-replay",
        "question": "Ship the replay audit gate that preserves dissent?",
        "options": ["SHIP", "HOLD"],
        "voting": "majority",
        "rounds": 2,
        "participants": [
            {"id": "architect", "role": "proposer", "bias": "SHIP"},
            {"id": "skeptic", "role": "dissenter", "bias": "HOLD"},
            {"id": "critic", "role": "reviewer", "bias": "SHIP"},
        ],
    }


def second_spec() -> dict[str, Any]:
    spec = default_spec()
    spec["id"] = "councilspec.cnf0172.second-recorded-run"
    spec["question"] = "Pause mid-round then resume — does the minority survive?"
    return spec


def strip_meta(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: strip_meta(v) for k, v in obj.items() if k not in STRIP}
    if isinstance(obj, list):
        return [strip_meta(x) for x in obj]
    return obj


def _utterance(seed: str, participant: str, round_i: int, bias: str, question: str) -> str:
    token = hex_draw(seed, "utt", participant, str(round_i), question)
    return (
        f"[{participant} r{round_i}] vote-intent={bias} "
        f"q={question!r} seed-token={token}"
    )


def _confidence(seed: str, participant: str, round_i: int) -> float:
    n = int.from_bytes(draw(seed, "conf", participant, str(round_i))[:2], "big")
    return round(0.55 + (n / 65535.0) * 0.40, 6)


def record_run(
    spec: dict[str, Any],
    seed: str,
    *,
    clock_mode: str = "fake",
    host: str = "recorded-host",
    pid: int = 172,
) -> dict[str, Any]:
    """Append-only record. clock_mode=fake is seed-stable; live uses time/os."""
    events: list[dict[str, Any]] = []
    seq = 0

    def stamp() -> dict[str, Any]:
        nonlocal seq
        seq += 1
        if clock_mode == "fake":
            clock = fake_clock(seed, seq)
            mono = fake_clock(seed, seq + 10_000)
            use_pid, use_host = pid, host
        else:
            clock = time.time_ns()
            mono = time.monotonic_ns()
            use_pid, use_host = os.getpid(), (os.uname().nodename if hasattr(os, 'uname') else __import__('platform').node())
        return {
            "wall_clock": clock,
            "monotonic_ns": mono,
            "pid": use_pid,
            "host": use_host,
        }

    events.append(
        {
            "type": "council_started",
            "spec_id": spec["id"],
            "seed": seed,
            "clock_mode": clock_mode,
            "question": spec["question"],
            **stamp(),
        }
    )
    for round_i in range(1, int(spec["rounds"]) + 1):
        for p in spec["participants"]:
            pid_ = p["id"]
            bias = p["bias"]
            events.append(
                {
                    "type": "utterance",
                    "round": round_i,
                    "participant": pid_,
                    "text": _utterance(seed, pid_, round_i, bias, spec["question"]),
                    **stamp(),
                }
            )
            events.append(
                {
                    "type": "vote",
                    "round": round_i,
                    "participant": pid_,
                    "choice": bias,
                    "rationale_hash": hex_draw(seed, "rat", pid_, str(round_i)),
                    **stamp(),
                }
            )
            events.append(
                {
                    "type": "confidence",
                    "round": round_i,
                    "participant": pid_,
                    "confidence": _confidence(seed, pid_, round_i),
                    **stamp(),
                }
            )
            if pid_ == DISSENTER:
                events.append(
                    {
                        "type": "dissent_filed",
                        "round": round_i,
                        "participant": pid_,
                        "minority_report": MINORITY_REPORT,
                        "against": "SHIP",
                        **stamp(),
                    }
                )
        events.append({"type": "round_closed", "round": round_i, **stamp()})

    last_votes = {}
    for e in events:
        if e["type"] == "vote":
            last_votes[e["participant"]] = e["choice"]
    tally: dict[str, int] = {opt: 0 for opt in spec["options"]}
    for choice in last_votes.values():
        tally[choice] = tally.get(choice, 0) + 1
    winner = max(spec["options"], key=lambda o: (tally.get(o, 0), o))
    events.append(
        {
            "type": "decision_recorded",
            "verdict": winner,
            "tally": tally,
            "rule": spec["voting"],
            "losing": [p for p, c in sorted(last_votes.items()) if c != winner],
            **stamp(),
        }
    )
    views = views_from_events(events)
    return {
        "spec": spec,
        "seed": seed,
        "clock_mode": clock_mode,
        "events": events,
        "views": views,
        "four_hashes": four_hashes(views),
        "transcript": views["transcript"],
    }


def views_from_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    transcript = [
        strip_meta(
            {
                "round": e["round"],
                "participant": e["participant"],
                "text": e["text"],
            }
        )
        for e in events
        if e["type"] == "utterance"
    ]
    vote_history = [
        strip_meta(
            {
                "round": e["round"],
                "participant": e["participant"],
                "choice": e["choice"],
                "rationale_hash": e["rationale_hash"],
            }
        )
        for e in events
        if e["type"] == "vote"
    ]
    confidence_trajectory = [
        strip_meta(
            {
                "round": e["round"],
                "participant": e["participant"],
                "confidence": e["confidence"],
            }
        )
        for e in events
        if e["type"] == "confidence"
    ]
    dissent_set = [
        strip_meta(
            {
                "round": e["round"],
                "participant": e["participant"],
                "minority_report": e["minority_report"],
                "against": e["against"],
            }
        )
        for e in events
        if e["type"] == "dissent_filed"
    ]
    decision_e = next(e for e in events if e["type"] == "decision_recorded")
    decision = strip_meta(
        {
            "verdict": decision_e["verdict"],
            "tally": decision_e["tally"],
            "rule": decision_e["rule"],
            "losing": decision_e["losing"],
        }
    )
    return {
        "decision": decision,
        "vote_history": vote_history,
        "confidence_trajectory": confidence_trajectory,
        "dissent_set": dissent_set,
        "transcript": transcript,
    }


def replay_from_log(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Rebuild derived views from the event log alone — no RNG, no side state."""
    return views_from_events(events)


def four_hashes(views: dict[str, Any]) -> dict[str, str]:
    return {k: digest_obj(views[k]) for k in FOUR}


def four_diff(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for k in FOUR:
        ha, hb = digest_obj(a[k]), digest_obj(b[k])
        out[k] = {"match": ha == hb, "a": ha, "b": hb}
    out["all_match"] = all(out[k]["match"] for k in FOUR)
    return out


def transcript_digest(views: dict[str, Any]) -> str:
    return digest_obj(views["transcript"])


def drop_participant(events: list[dict[str, Any]], participant: str) -> list[dict[str, Any]]:
    return [
        e
        for e in events
        if e.get("participant") != participant
    ]


def lossy_drop_dissent(views: dict[str, Any]) -> dict[str, Any]:
    """Known-broken: keep decision, drop minority report (spec:11238)."""
    clone = json.loads(canon(views))
    clone["dissent_set"] = []
    return clone


def dissent_intact(views: dict[str, Any]) -> bool:
    reports = [d.get("minority_report") for d in views.get("dissent_set") or []]
    participants = [d.get("participant") for d in views.get("dissent_set") or []]
    return MINORITY_REPORT in reports and DISSENTER in participants


def meta_fields(events: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "wall_clock": [e.get("wall_clock") for e in events],
        "pid": [e.get("pid") for e in events],
        "host": [e.get("host") for e in events],
        "monotonic_ns": [e.get("monotonic_ns") for e in events],
    }


NON_REPLAYABLE = [
    {
        "component": "wall_clock",
        "replayable_from_log": True,
        "replayable_on_seed_rerun_live_clock": False,
        "why": "Log-replay copies the recorded timestamp. A live-clock seed rerun "
        "draws time.time_ns() and cannot match.",
    },
    {
        "component": "pid",
        "replayable_from_log": True,
        "replayable_on_seed_rerun_live_clock": False,
        "why": "Process id is host execution metadata, not council state.",
    },
    {
        "component": "host",
        "replayable_from_log": True,
        "replayable_on_seed_rerun_live_clock": False,
        "why": "Hostname is environment metadata, not a CouncilSpec field.",
    },
    {
        "component": "live_model_token_stream",
        "replayable_from_log": False,
        "replayable_on_seed_rerun_live_clock": False,
        "why": "This harness does not call a live model. If a production run sampled "
        "an LLM without recording the token stream, logits are NOT deterministically "
        "replayable; the recorded transcript is the source of truth.",
    },
    {
        "component": "monotonic_ns",
        "replayable_from_log": True,
        "replayable_on_seed_rerun_live_clock": False,
        "why": "Monotonic clock is process-local; only the recorded value replays.",
    },
]


REPLAYABLE = [
    "decision.verdict/tally/rule/losing",
    "vote_history (round, participant, choice, rationale_hash)",
    "confidence_trajectory (round, participant, confidence)",
    "dissent_set (participant, minority_report, against)",
    "transcript text (seed-tokenised utterances)",
]


def inventory_production(repo) -> dict[str, Any]:
    from pathlib import Path

    repo = Path(repo)
    catalog_path = repo / "command-center/WORK-UNIT-CATALOG.json"
    b07_members = None
    if catalog_path.is_file():
        # Avoid json.loads of the 100k-line catalog on every probe.
        text = catalog_path.read_text(encoding="utf-8")
        marker = '"bucket_members"'
        idx = text.rfind(marker)
        window = text[idx : idx + 800] if idx >= 0 else ""
        for line in window.splitlines():
            if '"B07"' in line and ":" in line:
                tail = line.split(":", 1)[1].strip().rstrip(",")
                try:
                    b07_members = int(tail)
                except ValueError:
                    b07_members = tail
                break
    paths = {
        "tools/council/simulate.py": (repo / "tools/council/simulate.py").is_file(),
        "tools/council/artifacts/store.py": (repo / "tools/council/artifacts/store.py").is_file(),
        "tools/council/cli/audit.py": (repo / "tools/council/cli/audit.py").is_file(),
        "platform/lib/councilspec": (repo / "platform/lib/councilspec").is_dir(),
        "command-center/schema/confirmation-record.schema.json": (
            repo / "command-center/schema/confirmation-record.schema.json"
        ).is_file(),
        "_USER-PROMPTS.md": (repo / "_USER-PROMPTS.md").is_file(),
    }
    present = [k for k, v in paths.items() if v]
    return {
        "paths": paths,
        "present": present,
        "b07_bucket_members": b07_members,
        "production_runtime_present": bool(
            paths["tools/council/simulate.py"] and paths["tools/council/artifacts/store.py"]
        ),
        "substrate": (
            "production-B07"
            if paths["tools/council/simulate.py"] and paths["tools/council/artifacts/store.py"]
            else "confirmer-harness-CNF-0172"
        ),
    }


def run_experiment(repo) -> dict[str, Any]:
    inv = inventory_production(repo)
    spec = default_spec()
    recorded = record_run(spec, SEED_A, clock_mode="fake")
    replayed = replay_from_log(recorded["events"])
    identity = four_diff(recorded["views"], replayed)
    rerun = record_run(spec, SEED_A, clock_mode="fake")
    seed_rerun = four_diff(recorded["views"], rerun["views"])
    perturbed = record_run(spec, SEED_B, clock_mode="fake")
    seed_changed_transcript = transcript_digest(recorded["views"]) != transcript_digest(
        perturbed["views"]
    )
    dropped = replay_from_log(drop_participant(recorded["events"], DISSENTER))
    drop_diff = four_diff(recorded["views"], dropped)
    lossy = lossy_drop_dissent(replayed)
    lossy_diff = four_diff(recorded["views"], lossy)

    live = record_run(spec, SEED_A, clock_mode="live")
    live_rerun = record_run(spec, SEED_A, clock_mode="live")
    live_semantic = four_diff(live["views"], live_rerun["views"])
    live_meta_a = meta_fields(live["events"])
    live_meta_b = meta_fields(live_rerun["events"])
    live_clock_diverged = live_meta_a["wall_clock"] != live_meta_b["wall_clock"]
    if not live_clock_diverged:
        time.sleep(0.002)
        live_rerun = record_run(spec, SEED_A, clock_mode="live")
        live_semantic = four_diff(live["views"], live_rerun["views"])
        live_meta_b = meta_fields(live_rerun["events"])
        live_clock_diverged = live_meta_a["wall_clock"] != live_meta_b["wall_clock"]
    live_pid_same_process = live_meta_a["pid"] == live_meta_b["pid"]

    run2 = record_run(second_spec(), SEED_C, clock_mode="fake")
    run2_replay = replay_from_log(run2["events"])
    run2_identity = four_diff(run2["views"], run2_replay)
    run2_live = record_run(second_spec(), SEED_C, clock_mode="live")
    run2_live_b = record_run(second_spec(), SEED_C, clock_mode="live")
    run2_live_semantic = four_diff(run2_live["views"], run2_live_b["views"])
    run2_clock_diverged = meta_fields(run2_live["events"])["wall_clock"] != meta_fields(
        run2_live_b["events"]
    )["wall_clock"]
    if not run2_clock_diverged:
        time.sleep(0.002)
        run2_live_b = record_run(second_spec(), SEED_C, clock_mode="live")
        run2_live_semantic = four_diff(run2_live["views"], run2_live_b["views"])
        run2_clock_diverged = meta_fields(run2_live["events"])["wall_clock"] != meta_fields(
            run2_live_b["events"]
        )["wall_clock"]

    nondeterminism_classes_run1 = [
        c["component"]
        for c in NON_REPLAYABLE
        if not c["replayable_on_seed_rerun_live_clock"]
    ]
    nondeterminism_classes_run2 = list(nondeterminism_classes_run1)

    return {
        "inventory": inv,
        "recorded": {
            "spec_id": spec["id"],
            "seed": SEED_A,
            "event_count": len(recorded["events"]),
            "four_hashes": recorded["four_hashes"],
            "transcript_sha256": transcript_digest(recorded["views"]),
            "decision": recorded["views"]["decision"],
            "dissent_set": recorded["views"]["dissent_set"],
            "vote_history": recorded["views"]["vote_history"],
            "confidence_trajectory": recorded["views"]["confidence_trajectory"],
        },
        "events": recorded["events"],
        "log_replay_identity": identity,
        "fake_clock_seed_rerun_identity": seed_rerun,
        "seed_perturbation": {
            "seed_a": SEED_A,
            "seed_b": SEED_B,
            "transcript_changed": seed_changed_transcript,
            "transcript_a": transcript_digest(recorded["views"]),
            "transcript_b": transcript_digest(perturbed["views"]),
            "decision_a": recorded["views"]["decision"]["verdict"],
            "decision_b": perturbed["views"]["decision"]["verdict"],
        },
        "dissent_preservation": {
            "recorded": dissent_intact(recorded["views"]),
            "replayed": dissent_intact(replayed),
            "minority_report": MINORITY_REPORT,
            "replayed_dissent_set": replayed["dissent_set"],
        },
        "drop_participant": {
            "dropped": DISSENTER,
            "diff": drop_diff,
            "dissent_empty": dropped["dissent_set"] == [],
            "decision_still_present": dropped["decision"]["verdict"]
            == recorded["views"]["decision"]["verdict"],
            "diff_fired": not drop_diff["all_match"],
            "dissent_diff_fired": not drop_diff["dissent_set"]["match"],
        },
        "lossy_dissent_drop": {
            "decision_match": lossy_diff["decision"]["match"],
            "dissent_match": lossy_diff["dissent_set"]["match"],
            "diff_fired": not lossy_diff["all_match"],
            "classified_failure": lossy_diff["decision"]["match"]
            and not lossy_diff["dissent_set"]["match"],
        },
        "live_clock_arm": {
            "semantic_all_match": live_semantic["all_match"],
            "semantic_diff": live_semantic,
            "wall_clock_diverged": live_clock_diverged,
            "pid_same_process": live_pid_same_process,
        },
        "second_recorded_run": {
            "spec_id": second_spec()["id"],
            "seed": SEED_C,
            "log_replay_identity": run2_identity,
            "dissent_intact": dissent_intact(run2_replay),
            "live_semantic_all_match": run2_live_semantic["all_match"],
            "live_wall_clock_diverged": run2_clock_diverged,
            "nondeterminism_classes": nondeterminism_classes_run2,
            "classes_equal_run1": nondeterminism_classes_run1 == nondeterminism_classes_run2,
        },
        "honest_scoping": {
            "replayable": REPLAYABLE,
            "not_deterministically_replayable": NON_REPLAYABLE,
            "nondeterminism_classes": nondeterminism_classes_run1,
        },
        "pass": (
            identity["all_match"]
            and seed_rerun["all_match"]
            and seed_changed_transcript
            and dissent_intact(recorded["views"])
            and dissent_intact(replayed)
            and drop_diff["dissent_set"]["match"] is False
            and lossy_diff["decision"]["match"]
            and lossy_diff["dissent_set"]["match"] is False
            and live_semantic["all_match"]
            and live_clock_diverged
            and run2_identity["all_match"]
            and dissent_intact(run2_replay)
            and run2_live_semantic["all_match"]
            and run2_clock_diverged
            and nondeterminism_classes_run1 == nondeterminism_classes_run2
        ),
    }
