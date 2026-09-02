#!/usr/bin/env python3
"""Emit CNL-0011 replay-state design artifact (JSON at the catalog .md path)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import replay_engine as E  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0011-replay-state-model-what-must-be-serialised-for-determinist.md"
)
ENGINE = "command-center/p2-wave/probes/CNL-0011/replay_engine.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0011/probe1_replay_identical.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0011/probe2_seed_perturbation.py"
)
QUESTION = (
    "What is the minimal serialised state such that a paused council resumes "
    "to a byte-identical transcript, and which sources of nondeterminism "
    "(sampling temperature, tool-call ordering, wall-clock, participant "
    "recruitment) must be captured as seeds rather than re-derived?"
)


def run(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def line_of(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:CNL-0011 snippet missing in {rel}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def main() -> int:
    rc1, out1 = run(P1)
    rc2, out2 = run(P2)
    if rc1 != 0 or rc2 != 0:
        print("FAILED:CNL-0011 named probes")
        print(out1[-1500:])
        print(out2[-1500:])
        return 1

    ident = E.two_run_identity()
    pause = E.pause_resume_match(5)
    pert = {axis: E.perturb_axis(axis) for axis in E.AXES}
    mutant = E.mutant_sampling_is_decorative()
    council = E.run_from_seeds()
    recount = E.independent_recount(council.transcript)
    blob = council.serialize()

    loc_axes = line_of(ENGINE, 'AXES = ("sampling", "tool_order", "clock", "recruitment")')
    loc_draw = line_of(ENGINE, "def draw_u32(seed: int, cursor: int) -> int:")
    loc_clock = line_of(ENGINE, "Never time.time()")
    loc_ser = line_of(ENGINE, "def serialize(self) -> dict:")
    loc_resume = line_of(ENGINE, "def resume(cls, blob: dict")
    loc_mutant = line_of(ENGINE, "class DecorativeSamplingCouncil")

    artifact = {
        "unit_id": "CNL-0011",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0011",
        "title": "Replay state model: what must be serialised for deterministic replay",
        "question": QUESTION,
        "answer": (
            "Minimal pause blob is cnl-0011.replay-state.v1: frozen spec+pool, "
            "four named seeds with their draw cursors, clock_origin_ms, roster, "
            "transcript prefix, pending/flush tool queues, scheduler cursors "
            "(turn_i, round_i, sub, want_stop), remaining budgets, and stop "
            "flags. Sampling temperature, tool-call ordering, wall-clock origin, "
            "and participant recruitment MUST be captured as seeds (plus the "
            "clock origin value). They must not be re-derived from time.time(), "
            "live availability, hash(dict), or unordered sets. Observed "
            "transcript bytes are part of the blob because a real vendor "
            "completion cannot be regenerated from a seed. spec_hash/pool_hash "
            "and vote/stop results are integrity or derived views, not sources "
            "of truth. Same seeds twice and pause/resume both yielded sha256="
            f"{ident['sha_a']} over {ident['events']} events. Perturbing any "
            "one seed changed the transcript; a mutant that ignores sampling "
            "left it unchanged, so the seed check is not vacuous."
        ),
        "dependencies_note": (
            "CNL-0001 (CouncilSpec v2 envelope) and CNL-0008 (budget exhaustion "
            "semantics) are not delivered on this tree. This unit ships a "
            "$defs.replay_state fragment and serialises remaining budgets "
            "rather than recomputing them from wall-clock. It does not invent "
            "a v2 root envelope."
        ),
        "output_schema_catalog": "command-center/schema/councilspec.v2.schema.json",
        "output_schema_note": (
            "Catalog names councilspec.v2.schema.json (CNL-0001). That file is "
            "absent. This artifact is a design note plus a replay_state schema "
            "fragment; G-1 measures JSON parse + sentinel + probes, not Draft "
            "2020-12 validation against the missing v2 root."
        ),
        "replay_state_schema": {
            "$id": "cnl-0011.replay-state.v1",
            "title": "CouncilSpec $defs.replay_state fragment",
            "type": "object",
            "additionalProperties": False,
            "required": [
                "schema",
                "spec",
                "pool",
                "seeds",
                "cursors",
                "clock_origin_ms",
                "roster",
                "transcript",
                "pending",
                "flush_queue",
                "turn_i",
                "round_i",
                "sub",
                "budgets",
                "stopped",
                "want_stop",
            ],
            "properties": {
                "schema": {"const": "cnl-0011.replay-state.v1"},
                "spec": {"type": "object"},
                "spec_hash": {"type": "string", "minLength": 64, "maxLength": 64},
                "pool": {"type": "array"},
                "pool_hash": {"type": "string", "minLength": 64, "maxLength": 64},
                "seeds": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["sampling", "tool_order", "clock", "recruitment"],
                    "properties": {
                        "sampling": {"type": "integer"},
                        "tool_order": {"type": "integer"},
                        "clock": {"type": "integer"},
                        "recruitment": {"type": "integer"},
                    },
                },
                "cursors": {"type": "object"},
                "clock_origin_ms": {"type": ["integer", "null"]},
                "roster": {"type": ["array", "null"]},
                "transcript": {"type": "array"},
                "pending": {"type": "array"},
                "flush_queue": {"type": "array"},
                "turn_i": {"type": "integer"},
                "round_i": {"type": "integer"},
                "sub": {"type": "string"},
                "budgets": {"type": "object"},
                "stopped": {"type": "boolean"},
                "stop_reason": {"type": ["string", "null"]},
                "want_stop": {"type": "boolean"},
            },
        },
        "minimal_state": {
            "must_serialize": [
                {
                    "field": "seeds.{sampling,tool_order,clock,recruitment}",
                    "why": "The four named nondeterminism axes. Re-deriving any of them from the live estate changes the transcript (probe2).",
                },
                {
                    "field": "cursors",
                    "why": "Resume must continue each SHA-256(seed:cursor) stream, not restart at 0.",
                },
                {
                    "field": "clock_origin_ms",
                    "why": "Frozen origin drawn from the clock seed. Never time.time().",
                },
                {
                    "field": "spec (temperature, tick_ms, max_rounds, n_recruit, initial_budgets)",
                    "why": "Parameters the scheduler branches on. temperature>0 makes sampling load-bearing.",
                },
                {
                    "field": "pool snapshot + roster",
                    "why": "Live recruitment would re-query availability. Roster is the frozen draw; pool is the frame it was drawn from.",
                },
                {
                    "field": "transcript prefix",
                    "why": "Observed events (in production: vendor completion bytes) cannot be regenerated from a seed unless the vendor guarantees it.",
                },
                {
                    "field": "pending + flush_queue",
                    "why": "In-flight tool calls and the already-permuted remaining results.",
                },
                {
                    "field": "turn_i, round_i, sub, want_stop",
                    "why": "Scheduler phase so the next step() emits the same event.",
                },
                {
                    "field": "budgets remaining",
                    "why": "Must not be recomputed from wall-clock (CNL-0008: exhaustion must not masquerade as a time-derived stop).",
                },
                {
                    "field": "stopped, stop_reason",
                    "why": "Terminal flag; stop is an event, not a re-derived predicate on resume.",
                },
            ],
            "must_not_rereive": [
                "time.time() / datetime.utcnow for event timestamps",
                "live participant availability or mounted-vendor roster",
                "PYTHONHASHSEED / salted hash() for ordering",
                "uuid4 or random.Random",
                "unordered dict/set iteration as tool order",
                "vote tallies and stopping-expression results (pure functions of transcript; store transcript, recompute views)",
            ],
            "integrity_only": [
                "spec_hash",
                "pool_hash",
            ],
            "serialized_keys_live": sorted(blob.keys()),
        },
        "seeds_not_rereived": [
            {
                "axis": "sampling",
                "captures": "temperature sampling among scripted phrase variants and tool nonces",
                "must_seed": True,
                "rereive_forbidden": "re-sample from temperature without a seed; T=0 would make this seed decorative",
                "probe2_changed": pert["sampling"]["changed"],
                "first_diff_kind": pert["sampling"]["first_diff_kind_base"],
            },
            {
                "axis": "tool_order",
                "captures": "permutation of concurrent tool results",
                "must_seed": True,
                "rereive_forbidden": "order-by-completion-wall-time or dict insertion order",
                "probe2_changed": pert["tool_order"]["changed"],
                "first_diff_kind": pert["tool_order"]["first_diff_kind_base"],
            },
            {
                "axis": "clock",
                "captures": "origin_ms for logical timestamps (origin + i*tick_ms)",
                "must_seed": True,
                "rereive_forbidden": "time.time() on resume or pause",
                "probe2_changed": pert["clock"]["changed"],
                "first_diff_kind": pert["clock"]["first_diff_kind_base"],
            },
            {
                "axis": "recruitment",
                "captures": "Fisher-Yates draw of n_recruit seats from the frozen pool",
                "must_seed": True,
                "rereive_forbidden": "re-query who is reachable on this machine now",
                "probe2_changed": pert["recruitment"]["changed"],
                "first_diff_kind": pert["recruitment"]["first_diff_kind_base"],
            },
        ],
        "tests": {
            "replay_same_seed": {
                "required": "a replay test: same seed twice yields byte-identical transcripts",
                "result": ident,
                "pause_resume": pause,
                "pass": ident["match"] is True and pause["match"] is True,
            },
            "negative_control_one_seed": {
                "required": "perturbing ONE captured seed must change the transcript",
                "result": {k: {"changed": v["changed"], "first_diff_index": v["first_diff_index"]} for k, v in pert.items()},
                "pass": all(v["changed"] for v in pert.values()),
            },
            "negative_control_verbatim": {
                "required": "negative control recorded verbatim: state what the check does on the state it is meant to reject",
                "rejects": "a seed that is serialised but unused (decorative sampling stream)",
                "verbatim": (
                    "NEGATIVE CONTROL (verbatim): perturb sampling seed +1 on the real engine; "
                    "the check requires sha_base != sha_perturbed. "
                    f"Observed real_changes={mutant['real_changes']} "
                    f"sha_base={mutant['real_sha_base']} "
                    f"sha_perturbed={mutant['real_sha_perturbed']}. "
                    "On DecorativeSamplingCouncil (sampling draws ignored) the same "
                    "perturbation MUST leave the transcript unchanged, which FIRES "
                    f"the check. Observed mutant_changes={mutant['mutant_changes']} "
                    f"check_fires_on_mutant={mutant['check_fires_on_mutant']} "
                    f"mutant_sha_base={mutant['mutant_sha_base']} "
                    f"mutant_sha_perturbed={mutant['mutant_sha_perturbed']}."
                ),
                "pass": mutant["check_silent_on_real"] is True
                and mutant["check_fires_on_mutant"] is True,
            },
        },
        "evidence": [
            {
                "mechanism": "command-plus-output",
                "command": P1,
                "exit_code": rc1,
                "snippet": [ln for ln in out1.splitlines() if ln.startswith("two_run_identical") or ln.startswith("pause_resume") or ln.startswith("SUCCESS:")] ,
                "claim": "Same seeds twice and pause/resume are byte-identical (scripted-participant replay oracle).",
            },
            {
                "mechanism": "file:line plus independent recount",
                "path": ENGINE,
                "line": loc_ser,
                "snippet": "def serialize(self) -> dict:",
                "recount": recount,
                "claim": (
                    "Independent recount from transcript events (not engine internals) "
                    f"gives event_count={recount['event_count']} kinds={recount['kinds']} "
                    f"roster={recount['roster']} ticks_strictly_increasing="
                    f"{recount['ticks_strictly_increasing']}."
                ),
            },
            {
                "mechanism": "command-plus-output",
                "command": P2,
                "exit_code": rc2,
                "snippet": [ln for ln in out2.splitlines() if ln.startswith("perturb ") or ln.startswith("NEGATIVE") or ln.startswith("SUCCESS:")],
                "claim": "Each of the four seeds is load-bearing; decorative sampling mutant fires.",
            },
        ],
        "anchors": {
            "AXES": f"{ENGINE}:{loc_axes}",
            "draw_u32": f"{ENGINE}:{loc_draw}",
            "clock_never_wall": f"{ENGINE}:{loc_clock}",
            "serialize": f"{ENGINE}:{loc_ser}",
            "resume": f"{ENGINE}:{loc_resume}",
            "decorative_mutant": f"{ENGINE}:{loc_mutant}",
        },
        "reviewer": {
            "reviewer_id": "CNL-0011-independent-recount",
            "method": "Re-tabulate event_count, kind histogram, roster, and tool_result_sequence from the transcript list without reading the author's prose.",
            "event_count": recount["event_count"],
            "kinds": recount["kinds"],
            "roster": recount["roster"],
            "tool_result_sequence": recount["tool_result_sequence"],
            "agrees_with_engine_len": recount["event_count"] == ident["events"],
            "verdict": "PASS" if recount["event_count"] == ident["events"] else "BLOCK",
        },
        "oracles_used": [
            "scripted-participant replay (probe1 two-run + pause/resume)",
            "transcript diff (probe2 first differing event per axis)",
            "counter assertion (independent_recount event_count/kinds/roster)",
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": rc1, "raw_output": out1},
            {"id": "probe2", "command": P2, "exit_code": rc2, "raw_output": out2},
        ],
        "engine": ENGINE,
        "fixture": "command-center/p2-wave/probes/CNL-0011/fixtures/scenario.json",
    }

    tests_ok = (
        artifact["tests"]["replay_same_seed"]["pass"]
        and artifact["tests"]["negative_control_one_seed"]["pass"]
        and artifact["tests"]["negative_control_verbatim"]["pass"]
        and artifact["reviewer"]["verdict"] == "PASS"
    )
    if not tests_ok:
        print("FAILED:CNL-0011 live tests did not all pass; refusing SUCCESS artifact")
        return 1

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(artifact, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    print("SUCCESS:CNL-0011")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
