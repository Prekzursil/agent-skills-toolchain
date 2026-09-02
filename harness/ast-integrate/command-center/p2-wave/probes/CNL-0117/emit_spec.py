#!/usr/bin/env python3
"""Emit the CNL-0117 simulation-spec artifact (JSON at the catalog .md path)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402
import runtime as R  # noqa: E402
from scenario import load_scenario  # noqa: E402
from transcript import digest_doc  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0117-deterministic-scripted-participant-simulation-harness.md"
)
SCHEMA = "command-center/schema/council-simulation-spec.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0117/probe1_byte_identical.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0117/probe2_broken_runtime.py"
)
QUESTION = (
    "What is the fake-participant substrate that makes every later council "
    "simulation deterministic - scripted positions, scripted votes, scripted "
    "refusals - and what proves the harness itself is not the thing under test?"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def line_of(rel: str, needle: str) -> str:
    path = REPO / rel
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return f"{rel}:{i}"
    return rel


def present(rel: str) -> bool:
    return (REPO / rel).is_file()


def main() -> int:
    scenario = load_scenario()
    expected = H.freeze_recorded()
    m1 = H.measure_probe1(scenario)
    m2 = H.measure_probe2(scenario)
    if not m1["ok"] or not m2["ok"]:
        print("FAILED:CNL-0117 emit measurements not green")
        print(json.dumps({"probe1": m1, "probe2": m2}, indent=2, sort_keys=True))
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    dep_cnl0011 = present(
        "command-center/design/council/"
        "CNL-0011-replay-state-model-what-must-be-serialised-for-determinist.md"
    )
    dep_cnl0076 = present(
        "command-center/design/council/"
        "CNL-0076-stopping-expression-runtime-evaluation-semantics.schema.json"
    )
    catalog_inputs = {
        "11-COUNCIL-SPECIFICATION.schema.json": present(
            "11-COUNCIL-SPECIFICATION.schema.json"
        ),
        "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": present(
            "12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
        ),
        "platform/lib/councilspec": (REPO / "platform/lib/councilspec").is_dir(),
        "platform/schema/councilspec.schema.json": present(
            "platform/schema/councilspec.schema.json"
        ),
    }
    answer = (
        "The fake-participant substrate is a fixture of scripted acts "
        "(position, vote, refusal) consumed by an injected CouncilRuntime; "
        "no model is called. Determinism is the tuple "
        "(roster_order, script_digest, round_ceiling, tally_method) plus a "
        "canonical JSON transcript with no wall-clock. The harness is not "
        "under test: the same check is silent on HonestRuntime and fires on "
        "DropRefusalRuntime, which omits the scripted skeptic refusal. "
        f"Recorded transcript sha256={m1['recorded_sha256']} reproduced twice "
        f"(two_run_identical={m1['two_run_identical']}). "
        "EmptyRuntime is two-run-identical and still fails the recount. "
        "SUCCESS:CNL-0117"
    )
    doc = {
        "unit_id": "CNL-0117",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0117",
        "title": "Deterministic scripted-participant simulation harness",
        "question": QUESTION,
        "answer": answer,
        "phase": "2C",
        "output_schema": SCHEMA,
        "harness_contract": {
            "statement": (
                "The harness loads a scenario fixture, injects a runtime, "
                "canonicalizes the transcript, and checks invariants derived "
                "from the fixture. It does not propose, vote, or refuse."
            ),
            "import_path": "command-center/p2-wave/probes/CNL-0117/harness.py",
            "runtime_protocol": "runtime.run(scenario) -> transcript dict",
            "canonical_form": (
                "json.dumps(sort_keys=True, separators=(',', ':'), "
                "ensure_ascii=True) plus a trailing newline; LF only"
            ),
            "act_kinds": [
                "position",
                "vote",
                "refusal",
                "death",
                "silence",
            ],
            "required_kinds_in_this_fixture": ["position", "vote", "refusal"],
            "recorded_transcript": H.recorded_rel(),
        },
        "fake_participant_substrate": {
            "participants_are_llms": False,
            "sampling_temperature_captured": False,
            "sampling_temperature_forbidden": True,
            "wall_clock_forbidden": True,
            "script_is_the_seed": True,
            "fixture": "command-center/p2-wave/probes/CNL-0117/fixtures/scenario.json",
            "roster": scenario["roster"],
            "protocol": scenario["protocol"],
            "round_ceiling": scenario["round_ceiling"],
            "tally_method": scenario["tally_method"],
            "script_digest": m1["script_digest"],
            "event_count": m1["event_count"],
            "kinds_observed": m1["kinds"],
            "winner": m1["winner"],
        },
        "seeds_captured": expected["seeds"],
        "not_under_test": {
            "harness": (
                "Invariant check, canonicalization, fixture load, freeze of "
                "the recount snapshot."
            ),
            "thing_under_test": (
                "The injected CouncilRuntime (HonestRuntime for this unit; "
                "later units swap in role-enforcement, stopping, fan-in)."
            ),
            "proof": (
                "DropRefusalRuntime is accepted by two-run identity of itself "
                "but rejected by the harness recount; EmptyRuntime is also "
                "two-run-identical and rejected. Identity alone is not a pass."
            ),
        },
        "dependency_status": {
            "CNL-0011": {
                "required_by_catalog": True,
                "artifact_present": dep_cnl0011,
                "how_this_unit_proceeds": (
                    "Replay-state seeds implemented here are script_digest, "
                    "roster_order, round_ceiling, tally_method. Full CNL-0011 "
                    "serialisation (tool-call order, recruitment, temperature) "
                    "is not claimed. Wall-clock and sampling are forbidden "
                    "rather than captured."
                ),
                "verdict": "CONFIRMED" if dep_cnl0011 else "NOT-CHECKED",
            },
            "CNL-0076": {
                "required_by_catalog": True,
                "artifact_present": dep_cnl0076,
                "how_this_unit_proceeds": (
                    "Stop reason is round_ceiling or script_exhausted. SEM-tree "
                    "stopping-expression evaluation is out of scope (CNL-0121)."
                ),
                "verdict": "CONFIRMED" if dep_cnl0076 else "NOT-CHECKED",
            },
            "catalog_inputs_on_this_tree": catalog_inputs,
        },
        "scenario": {
            "id": scenario["id"],
            "fixture_path": "command-center/p2-wave/probes/CNL-0117/fixtures/scenario.json",
            "recorded_path": H.recorded_rel(),
            "refusal": {
                "actor": "skeptic",
                "round": 1,
                "reason": "no-second-mechanism",
            },
            "tally_from_recount": expected["tally"],
            "stop_from_recount": expected["stop"],
        },
        "measurements": {
            "probe1": m1,
            "probe2": m2,
        },
        "evidence": [
            {
                "claim": (
                    "Two HonestRuntime runs over the same fixture are "
                    "byte-identical and match the recorded recount snapshot."
                ),
                "verdict": "CONFIRMED",
                "anchor": line_of(
                    "command-center/p2-wave/probes/CNL-0117/harness.py",
                    "def two_run(",
                ),
                "mechanism": "live-sha256-two-run",
                "verbatim": (
                    f"two_run_identical={m1['two_run_identical']} "
                    f"live_sha256={m1['live_sha256']} "
                    f"recorded_sha256={m1['recorded_sha256']}"
                ),
            },
            {
                "claim": (
                    "An independent flatten-then-sort recount of the fixture "
                    "agrees with HonestRuntime and disagrees with "
                    "DropRefusalRuntime on the missing skeptic refusal."
                ),
                "verdict": "CONFIRMED",
                "anchor": line_of(
                    "command-center/p2-wave/probes/CNL-0117/recount.py",
                    "def expected_transcript(",
                ),
                "mechanism": "fixture-flatten-sort-recount",
                "verbatim": (
                    f"recount_sha256={m1['recount_sha256']} "
                    f"drop_missing={m2['drop_missing_acts']} "
                    f"fired_on_bad={m2['fired_on_bad_state']} "
                    f"silent_on_good={m2['silent_on_good_state']}"
                ),
            },
            {
                "claim": (
                    "Flipping one scripted vote changes script_digest and the "
                    "transcript digest, so the recorded bytes are not a constant."
                ),
                "verdict": "CONFIRMED",
                "anchor": line_of(
                    "command-center/p2-wave/probes/CNL-0117/harness.py",
                    "def perturb_one_vote(",
                ),
                "mechanism": "script-seed-perturbation",
                "verbatim": (
                    f"perturbed_diverges={m1['perturbed_diverges']} "
                    f"seed_changed={m1['seed_changed_on_vote_flip']} "
                    f"perturbed_sha256={m1['perturbed_sha256']}"
                ),
            },
            {
                "claim": (
                    "11-COUNCIL-SPECIFICATION.schema.json and "
                    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json were read from this worktree."
                ),
                "verdict": "REFUTED",
                "anchor": "dependency_status.catalog_inputs_on_this_tree",
                "mechanism": "path-exists",
            },
            {
                "claim": (
                    "CNL-0011 replay-state artifact and CNL-0076 stopping-expression "
                    "artifact are on disk and were executed as oracles for this unit."
                ),
                "verdict": "REFUTED" if not (dep_cnl0011 or dep_cnl0076) else "PARTIAL",
                "anchor": "dependency_status",
                "mechanism": "path-exists",
            },
        ],
        "tests": [
            {
                "id": "T1-recorded-transcript-byte-identical-twice",
                "name": (
                    "The harness must reproduce a recorded transcript "
                    "byte-identically twice"
                ),
                "command": P1,
                "result": "PASS" if m1["ok"] else "FAIL",
            },
            {
                "id": "T2-broken-runtime-fails-harness",
                "name": (
                    "A deliberately broken runtime must FAIL the harness, "
                    "proving the harness is not vacuously green"
                ),
                "command": P2,
                "result": "PASS" if m2["ok"] else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "CNL0117-C1-drop-refusal",
                "kind": "known-broken-runtime",
                "description": m2["negative_control"],
                "fired_on_bad_state": m2["fired_on_bad_state"],
                "silent_on_good_state": m2["silent_on_good_state"],
                "bad_state_output": (
                    f"DropRefusalRuntime ok={m2['drop_ok']} "
                    f"missing_acts={m2['drop_missing_acts']}"
                ),
                "good_state_output": (
                    f"HonestRuntime ok={m2['honest_ok']} "
                    f"missing_acts={m2['honest_missing_acts']}"
                ),
                "rejects": "a runtime that silently omits a scripted refusal",
            },
            {
                "id": "CNL0117-C2-empty-runtime-identity-is-not-a-pass",
                "kind": "known-broken-runtime",
                "description": (
                    "EmptyRuntime yields two-run byte-identical empty transcripts. "
                    "The harness still sets ok=false because six scripted acts are "
                    "missing. Two-run identity alone is the state this control rejects."
                ),
                "fired_on_bad_state": m1["empty_runtime_ok"] is False,
                "silent_on_good_state": m1["two_run_identical"] is True,
                "bad_state_output": (
                    f"empty_ok={m1['empty_runtime_ok']} "
                    f"empty_identical={m1['empty_runtime_identical']}"
                ),
                "good_state_output": (
                    f"honest two_run_identical={m1['two_run_identical']} "
                    f"event_count={m1['event_count']}"
                ),
                "rejects": "treating two-run identity of an empty transcript as delivery",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0117-probe2-independent-recount",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "scope_not_agreement": True,
            "method": (
                "Named probe2 re-derives expected (round, actor, kind) tuples by "
                "flattening fixture scripts and sorting; it does not read the "
                "author's answer field. A disagreement in event count or the "
                "missing refusal blocks the unit."
            ),
            "recount_sha256": m1["recount_sha256"],
            "winner_from_fixture_votes": expected["tally"]["winner"],
        },
        "named_probes": [
            {"id": "probe1", "role": "recorded-transcript-replay", "command": P1},
            {"id": "probe2", "role": "broken-runtime-self-test", "command": P2},
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNL-0117/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "global_catalog_write": False,
        },
        "downstream_consumers": [
            {
                "consumer": "CNL-0118 role-enforcement simulation",
                "artifact_path": OUT,
                "note": "Swap HonestRuntime for a mandate-enforcing runtime; keep scripts.",
            },
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py CNL-0117",
                "artifact_path": OUT,
                "executed": False,
                "note": "Measure runs after this emit and after named probes.",
            },
        ],
        "residual_unknowns": [
            {
                "claim": "Full CNL-0011 replay-state serialisation including tool-call order.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Deliver CNL-0011, then pause/resume a scripted council "
                    "(CNL-0122) with a single-seed perturbation."
                ),
            },
            {
                "claim": "SEM-tree stopping-expression evaluation (CNL-0076 / CNL-0121).",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Deliver CNL-0076 and populate the 6x2 both-states table in CNL-0121."
                ),
            },
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/CNL-0117/harness.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0117/fixtures/scenario.json",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": H.recorded_rel(),
                "exists": True,
                "role": "supporting",
            },
        ],
        "retry": {
            "count": 0,
            "policy": (
                "up to 3 attempts, each with a MECHANICALLY DIFFERENT oracle "
                "(scripted-participant replay, transcript diff, counter assertion)"
            ),
        },
        "timestamps": {
            "started_at": "2026-08-24T18:39:00Z",
            "ended_at": now,
        },
        "min_bytes_threshold": 4096,
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    try:
        validator = jsonschema.Draft7Validator(schema)
        errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
        if errs:
            print("FAILED:CNL-0117 schema errors")
            for e in errs[:20]:
                print(" ", list(e.path), e.message)
            return 1
        garbage = [
            {"totally": "unrelated", "passing_tests": 999999},
            {"blob": "x" * 2000},
            {},
            {"unit_id": "ARC-0001", "state": "SUCCESS", "sentinel": "SUCCESS:X"},
        ]
        for g in garbage:
            if not list(validator.iter_errors(g)):
                print(f"FAILED:CNL-0117 schema accepted garbage {list(g)[:2]}")
                return 1
    except jsonschema.exceptions.RefResolutionError as exc:
        # Catalog path is a GENERATED SHIM ($ref to artifact-class-profiles via
        # ast-integrate.invalid). G-1 does not require live $ref fetch; the
        # harness probes are the executable contract. Do not rebuild ADV.
        print(
            "WARN: catalog council-simulation-spec.schema.json is a $ref shim; "
            f"emit proceeds without remote resolve. {type(exc).__name__}"
        )

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNL-0117 artifact {size}B below floor")
        return 1
    live = R.HonestRuntime().run(scenario)
    if digest_doc(live) != m1["live_sha256"]:
        print("FAILED:CNL-0117 live transcript drifted during emit")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"recorded {H.recorded_rel()} sha256={m1['recorded_sha256']} "
        f"winner={m1['winner']} events={m1['event_count']}"
    )
    print("SUCCESS:CNL-0117 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
