#!/usr/bin/env python3
"""Probe 1: pause-at-k / resume vs uninterrupted, plus replay-from-state.

Evidence: three sha256 values (uninterrupted, pause-resume, replay). Any
divergence is attributed to a named canonical field. A second seed must
diverge, proving the transcript is not a frozen constant.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import simulate as S  # noqa: E402

SEED_A = S.DEFAULT_SEED
SEED_B = S.DEFAULT_SEED + "-perturbed"
OUT = HERE / "probe1-pause-resume.json"


def _run_pair(seed: str, tmp: Path) -> dict:
    unint_path = tmp / f"{seed}-unint.clog"
    pause_path = tmp / f"{seed}-pause.clog"
    unint = S.run_uninterrupted(seed, unint_path)
    paused = S.pause_at(seed, S.PAUSE_AFTER, pause_path)
    resumed = S.resume(pause_path)
    replayed = S.replay_from_log(pause_path)
    h_unint = S.transcript_sha256(unint)
    h_resume = S.transcript_sha256(resumed)
    h_replay = S.transcript_sha256(replayed)
    return {
        "seed": seed,
        "pause_after": S.PAUSE_AFTER,
        "uninterrupted_rounds": [e["round"] for e in unint if e.get("kind") == "round_tallied"],
        "paused_rounds": [e["round"] for e in paused if e.get("kind") == "round_tallied"],
        "resumed_rounds": [e["round"] for e in resumed if e.get("kind") == "round_tallied"],
        "uninterrupted_sha256": h_unint,
        "pause_resume_sha256": h_resume,
        "replay_from_state_sha256": h_replay,
        "uninterrupted_bytes": len(S.transcript_bytes(unint)),
        "pause_markers_in_resume_log": sum(1 for e in resumed if e.get("kind") in {"run_paused", "run_resumed"}),
        "dissenters_final": next(
            (
                e["tally"]["dissenters"]
                for e in reversed(resumed)
                if e.get("kind") == "round_tallied"
            ),
            [],
        ),
        "decision": next(
            (e["decision"] for e in reversed(resumed) if e.get("kind") == "run_completed"),
            None,
        ),
        "divergence_unint_vs_resume": S.first_divergence(unint, resumed),
        "divergence_resume_vs_replay": S.first_divergence(resumed, replayed),
        "hashes_equal": h_unint == h_resume == h_replay,
        "child_events": sum(1 for e in resumed if str(e.get("kind", "")).startswith("child_")),
        "replacement_events": sum(1 for e in resumed if e.get("kind") == "persona_replaced"),
        "unint_path": str(unint_path),
        "pause_path": str(pause_path),
    }


def evaluate() -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="tst-0286-p1-"))
    a = _run_pair(SEED_A, tmp)
    b = _run_pair(SEED_B, tmp)
    named = None
    if a["uninterrupted_sha256"] != a["pause_resume_sha256"]:
        named = a["divergence_unint_vs_resume"] or "unattributed-unint-vs-resume"
    elif a["pause_resume_sha256"] != a["replay_from_state_sha256"]:
        named = a["divergence_resume_vs_replay"] or "unattributed-resume-vs-replay"
    seed_field = S.first_divergence(
        S.replay_from_log(Path(a["pause_path"])),
        S.replay_from_log(Path(b["pause_path"])),
    )
    paused_only_early = a["paused_rounds"] == list(range(1, S.PAUSE_AFTER + 1))
    resumed_caught_up = a["resumed_rounds"] == a["uninterrupted_rounds"]
    ok = (
        a["hashes_equal"]
        and named is None
        and a["uninterrupted_sha256"] != b["uninterrupted_sha256"]
        and bool(seed_field)
        and paused_only_early
        and resumed_caught_up
        and a["pause_markers_in_resume_log"] >= 2
        and a["child_events"] >= 1
        and a["replacement_events"] >= 1
        and "skeptic" in list(a["dissenters_final"] or [])
    )
    return {
        "pass": ok,
        "seed_a": a,
        "seed_b": {
            "seed": b["seed"],
            "uninterrupted_sha256": b["uninterrupted_sha256"],
            "pause_resume_sha256": b["pause_resume_sha256"],
            "replay_from_state_sha256": b["replay_from_state_sha256"],
            "hashes_equal": b["hashes_equal"],
        },
        "three_sha256": {
            "uninterrupted": a["uninterrupted_sha256"],
            "pause_resume": a["pause_resume_sha256"],
            "replay_from_state": a["replay_from_state_sha256"],
        },
        "divergence_attribution": named,
        "seed_perturbation": {
            "diverged": a["uninterrupted_sha256"] != b["uninterrupted_sha256"],
            "first_differing_field": seed_field,
            "hash_a": a["uninterrupted_sha256"],
            "hash_b": b["uninterrupted_sha256"],
        },
        "tmp": str(tmp),
    }


def main() -> int:
    result = evaluate()
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    three = result["three_sha256"]
    print(f"uninterrupted_sha256={three['uninterrupted']}")
    print(f"pause_resume_sha256={three['pause_resume']}")
    print(f"replay_from_state_sha256={three['replay_from_state']}")
    print(f"hashes_equal={result['seed_a']['hashes_equal']}")
    print(f"seed_perturbation_field={result['seed_perturbation']['first_differing_field']}")
    print(f"pause_after={S.PAUSE_AFTER} paused_rounds={result['seed_a']['paused_rounds']}")
    if not result["pass"]:
        print("FAILED:TST-0286-probe1 pause/resume/replay contract")
        return 1
    print("SUCCESS:TST-0286-probe1 pause-resume replay byte-identical")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
