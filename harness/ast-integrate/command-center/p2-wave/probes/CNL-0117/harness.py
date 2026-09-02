"""Scripted-participant simulation harness.

The harness feeds fixtures, canonicalizes transcripts, and checks invariants.
It is not the council runtime. Inject a runtime; do not ask the harness to
deliberate.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import recount
import runtime as R
from scenario import load_scenario, roster_ids
from transcript import canonical_bytes, digest_bytes, digest_doc, script_digest

HERE = Path(__file__).resolve().parent
RECORDED = HERE / "fixtures" / "recorded-transcript.json"


def freeze_recorded(scenario: dict | None = None) -> dict:
    """Snapshot the independent recount to disk. Not a runtime output."""
    scenario = scenario or load_scenario()
    expected = recount.expected_transcript(scenario)
    RECORDED.parent.mkdir(parents=True, exist_ok=True)
    RECORDED.write_text(
        json.dumps(expected, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return expected


def load_recorded() -> dict:
    if not RECORDED.is_file() or RECORDED.stat().st_size <= 0:
        raise FileNotFoundError(f"recorded transcript missing: {RECORDED}")
    return json.loads(RECORDED.read_text(encoding="utf-8"))


def two_run(runtime, scenario: dict) -> tuple[dict, dict, bool]:
    a = runtime.run(scenario)
    b = runtime.run(scenario)
    return a, b, canonical_bytes(a) == canonical_bytes(b)


def check(transcript: dict, scenario: dict) -> dict:
    """Invariant detector derived from the fixture, not from runtime.self_report."""
    expected = recount.expected_transcript(scenario)
    want = recount.act_keys(expected)
    got = recount.act_keys(transcript)
    want_set, got_set = set(want), set(got)
    missing = sorted(want_set - got_set)
    extra = sorted(got_set - want_set)
    order_ok = got == [k for k in want if k in got_set] and not extra
    bytes_match = canonical_bytes(transcript) == canonical_bytes(expected)
    tally_ok = transcript.get("tally") == expected.get("tally")
    ok = (not missing) and (not extra) and order_ok and bytes_match
    return {
        "bytes_match_recount": bytes_match,
        "event_count": len(transcript.get("events") or []),
        "expected_event_count": len(expected.get("events") or []),
        "extra_acts": [list(x) for x in extra],
        "missing_acts": [list(x) for x in missing],
        "ok": ok,
        "order_ok": order_ok,
        "recount_sha256": digest_doc(expected),
        "tally_agrees_with_recount": tally_ok,
        "transcript_sha256": digest_doc(transcript),
        "winner_live": (transcript.get("tally") or {}).get("winner"),
        "winner_recount": (expected.get("tally") or {}).get("winner"),
    }


def perturb_one_vote(scenario: dict) -> dict:
    """Clone fixture and flip the architect's ballot. Load-bearing seed check."""
    mutated = copy.deepcopy(scenario)
    flipped = False
    for act in mutated["scripts"]["architect"]:
        if act.get("kind") == "vote":
            act["payload"]["option"] = "B" if act["payload"].get("option") == "A" else "A"
            flipped = True
            break
    if not flipped:
        raise RuntimeError("architect vote missing; perturbation cannot run")
    return mutated


def kinds_present(transcript: dict) -> set[str]:
    return {str(e.get("kind")) for e in transcript.get("events") or []}


def measure_probe1(scenario: dict | None = None) -> dict:
    scenario = scenario or load_scenario()
    recorded = load_recorded()
    runtime = R.HonestRuntime()
    run_a, run_b, identical = two_run(runtime, scenario)
    live_vs_recorded = canonical_bytes(run_a) == canonical_bytes(recorded)
    recount_vs_recorded = canonical_bytes(
        recount.expected_transcript(scenario)
    ) == canonical_bytes(recorded)
    inv = check(run_a, scenario)
    mutated = perturb_one_vote(scenario)
    mutated_run = runtime.run(mutated)
    perturbed_diverges = canonical_bytes(mutated_run) != canonical_bytes(run_a)
    seed_changed = script_digest(mutated) != script_digest(scenario)
    kinds = kinds_present(run_a)
    empty = R.EmptyRuntime()
    empty_a, empty_b, empty_identical = two_run(empty, scenario)
    empty_inv = check(empty_a, scenario)
    ok = (
        identical
        and live_vs_recorded
        and recount_vs_recorded
        and inv["ok"] is True
        and perturbed_diverges
        and seed_changed
        and kinds >= {"position", "vote", "refusal"}
        and len(run_a["events"]) == len(roster_ids(scenario)) * int(
            scenario["round_ceiling"]
        )
        and empty_identical is True
        and empty_inv["ok"] is False
    )
    return {
        "empty_runtime_identical": empty_identical,
        "empty_runtime_ok": empty_inv["ok"],
        "empty_runtime_sha256": digest_doc(empty_a),
        "event_count": len(run_a["events"]),
        "kinds": sorted(kinds),
        "live_sha256": digest_doc(run_a),
        "live_vs_recorded": live_vs_recorded,
        "ok": ok,
        "perturbed_diverges": perturbed_diverges,
        "perturbed_sha256": digest_doc(mutated_run),
        "probe": "probe1-byte-identical",
        "recorded_path": recorded_rel(),
        "recorded_sha256": digest_doc(recorded),
        "recount_sha256": inv["recount_sha256"],
        "recount_vs_recorded": recount_vs_recorded,
        "run_b_sha256": digest_doc(run_b),
        "script_digest": script_digest(scenario),
        "seed_changed_on_vote_flip": seed_changed,
        "two_run_identical": identical,
        "unit_id": "CNL-0117",
        "winner": run_a["tally"]["winner"],
    }


def measure_probe2(scenario: dict | None = None) -> dict:
    scenario = scenario or load_scenario()
    honest = check(R.HonestRuntime().run(scenario), scenario)
    dropped = check(R.DropRefusalRuntime().run(scenario), scenario)
    empty = check(R.EmptyRuntime().run(scenario), scenario)
    recorded = load_recorded()
    cached = check(R.CachedConstantRuntime(recorded).run(scenario), scenario)
    mutated = perturb_one_vote(scenario)
    cached_on_mutated = check(
        R.CachedConstantRuntime(recorded).run(mutated), mutated
    )
    # Negative control text: what the check does on the state it rejects.
    reject_text = (
        "On DropRefusalRuntime the harness check sets ok=false because the "
        "scripted (round=1, actor=skeptic, kind=refusal) act is missing from "
        "the transcript; HonestRuntime is silent (ok=true, missing_acts=[])."
    )
    fired = dropped["ok"] is False and dropped["missing_acts"] == [
        [1, "skeptic", "refusal"]
    ]
    silent = honest["ok"] is True and honest["missing_acts"] == []
    empty_fired = empty["ok"] is False and empty["event_count"] == 0
    cached_honest_pass = cached["ok"] is True
    cached_mutant_fail = cached_on_mutated["ok"] is False
    ok = (
        fired
        and silent
        and empty_fired
        and cached_honest_pass
        and cached_mutant_fail
        and dropped["tally_agrees_with_recount"] is True
    )
    return {
        "cached_constant_matches_recorded_on_unmutated": cached_honest_pass,
        "cached_constant_rejected_when_script_flipped": cached_mutant_fail,
        "drop_missing_acts": dropped["missing_acts"],
        "drop_ok": dropped["ok"],
        "empty_ok": empty["ok"],
        "fired_on_bad_state": fired,
        "honest_missing_acts": honest["missing_acts"],
        "honest_ok": honest["ok"],
        "negative_control": reject_text,
        "ok": ok,
        "probe": "probe2-broken-runtime",
        "silent_on_good_state": silent,
        "unit_id": "CNL-0117",
        "winner_drop": dropped["winner_live"],
        "winner_honest": honest["winner_live"],
        "winner_recount": honest["winner_recount"],
    }


def recorded_rel() -> str:
    repo = HERE.parents[3]
    return RECORDED.relative_to(repo).as_posix()
