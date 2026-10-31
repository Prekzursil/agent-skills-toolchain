{
 "answer": "The fake-participant substrate is a fixture of scripted acts (position, vote, refusal) consumed by an injected CouncilRuntime; no model is called. Determinism is the tuple (roster_order, script_digest, round_ceiling, tally_method) plus a canonical JSON transcript with no wall-clock. The harness is not under test: the same check is silent on HonestRuntime and fires on DropRefusalRuntime, which omits the scripted skeptic refusal. Recorded transcript sha256=9dc334e4cf19020c7100e5bae3f1a690c6a463955160b0b0050b1d5b92a5c363 reproduced twice (two_run_identical=True). EmptyRuntime is two-run-identical and still fails the recount. SUCCESS:CNL-0117",
 "artifacts": [
  {
   "exists": true,
   "path": "command-center/design/council/CNL-0117-deterministic-scripted-participant-simulation-harness.md",
   "role": "primary"
  },
  {
   "exists": true,
   "path": "command-center/schema/council-simulation-spec.schema.json",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0117/harness.py",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0117/fixtures/scenario.json",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0117/fixtures/recorded-transcript.json",
   "role": "supporting"
  }
 ],
 "dependency_status": {
  "CNL-0011": {
   "artifact_present": false,
   "how_this_unit_proceeds": "Replay-state seeds implemented here are script_digest, roster_order, round_ceiling, tally_method. Full CNL-0011 serialisation (tool-call order, recruitment, temperature) is not claimed. Wall-clock and sampling are forbidden rather than captured.",
   "required_by_catalog": true,
   "verdict": "NOT-CHECKED"
  },
  "CNL-0076": {
   "artifact_present": false,
   "how_this_unit_proceeds": "Stop reason is round_ceiling or script_exhausted. SEM-tree stopping-expression evaluation is out of scope (CNL-0121).",
   "required_by_catalog": true,
   "verdict": "NOT-CHECKED"
  },
  "catalog_inputs_on_this_tree": {
   "11-COUNCIL-SPECIFICATION.schema.json": false,
   "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": false,
   "platform/lib/councilspec": true,
   "platform/schema/councilspec.schema.json": true
  }
 },
 "downstream_consumers": [
  {
   "artifact_path": "command-center/design/council/CNL-0117-deterministic-scripted-participant-simulation-harness.md",
   "consumer": "CNL-0118 role-enforcement simulation",
   "note": "Swap HonestRuntime for a mandate-enforcing runtime; keep scripts."
  },
  {
   "artifact_path": "command-center/design/council/CNL-0117-deterministic-scripted-participant-simulation-harness.md",
   "consumer": "command-center/p2-wave/_measure_one_delivered.py CNL-0117",
   "executed": false,
   "note": "Measure runs after this emit and after named probes."
  }
 ],
 "evidence": [
  {
   "anchor": "command-center/p2-wave/probes/CNL-0117/harness.py:39",
   "claim": "Two HonestRuntime runs over the same fixture are byte-identical and match the recorded recount snapshot.",
   "mechanism": "live-sha256-two-run",
   "verbatim": "two_run_identical=True live_sha256=9dc334e4cf19020c7100e5bae3f1a690c6a463955160b0b0050b1d5b92a5c363 recorded_sha256=9dc334e4cf19020c7100e5bae3f1a690c6a463955160b0b0050b1d5b92a5c363",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0117/recount.py:12",
   "claim": "An independent flatten-then-sort recount of the fixture agrees with HonestRuntime and disagrees with DropRefusalRuntime on the missing skeptic refusal.",
   "mechanism": "fixture-flatten-sort-recount",
   "verbatim": "recount_sha256=9dc334e4cf19020c7100e5bae3f1a690c6a463955160b0b0050b1d5b92a5c363 drop_missing=[[1, 'skeptic', 'refusal']] fired_on_bad=True silent_on_good=True",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0117/harness.py:73",
   "claim": "Flipping one scripted vote changes script_digest and the transcript digest, so the recorded bytes are not a constant.",
   "mechanism": "script-seed-perturbation",
   "verbatim": "perturbed_diverges=True seed_changed=True perturbed_sha256=e7193c569d44faeda58900358d703bc74c8d3d98326da8fc8365566ade1cee1e",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "dependency_status.catalog_inputs_on_this_tree",
   "claim": "11-COUNCIL-SPECIFICATION.schema.json and 12-COUNCIL-PROTOCOLS-AND-PRESETS.json were read from this worktree.",
   "mechanism": "path-exists",
   "verdict": "REFUTED"
  },
  {
   "anchor": "dependency_status",
   "claim": "CNL-0011 replay-state artifact and CNL-0076 stopping-expression artifact are on disk and were executed as oracles for this unit.",
   "mechanism": "path-exists",
   "verdict": "REFUTED"
  }
 ],
 "fake_participant_substrate": {
  "event_count": 6,
  "fixture": "command-center/p2-wave/probes/CNL-0117/fixtures/scenario.json",
  "kinds_observed": [
   "position",
   "refusal",
   "vote"
  ],
  "participants_are_llms": false,
  "protocol": "deliberate-then-vote",
  "roster": [
   {
    "id": "architect",
    "mandate": "propose a single option with an evidence anchor",
    "role": "architect"
   },
   {
    "id": "skeptic",
    "mandate": "refuse any endorsement that lacks a second independent mechanism",
    "role": "skeptic"
   },
   {
    "id": "critic",
    "mandate": "place a dissenting option and vote last",
    "role": "critic"
   }
  ],
  "round_ceiling": 2,
  "sampling_temperature_captured": false,
  "sampling_temperature_forbidden": true,
  "script_digest": "c398f73ea3d21cec9199b3c7eb9e8e0f9fe8dbd0057ebfbe24c300d93458e4d3",
  "script_is_the_seed": true,
  "tally_method": "plurality",
  "wall_clock_forbidden": true,
  "winner": "B"
 },
 "harness_contract": {
  "act_kinds": [
   "position",
   "vote",
   "refusal",
   "death",
   "silence"
  ],
  "canonical_form": "json.dumps(sort_keys=True, separators=(',', ':'), ensure_ascii=True) plus a trailing newline; LF only",
  "import_path": "command-center/p2-wave/probes/CNL-0117/harness.py",
  "recorded_transcript": "command-center/p2-wave/probes/CNL-0117/fixtures/recorded-transcript.json",
  "required_kinds_in_this_fixture": [
   "position",
   "vote",
   "refusal"
  ],
  "runtime_protocol": "runtime.run(scenario) -> transcript dict",
  "statement": "The harness loads a scenario fixture, injects a runtime, canonicalizes the transcript, and checks invariants derived from the fixture. It does not propose, vote, or refuse."
 },
 "manifest_registration": {
  "global_catalog_write": false,
  "manifest_path": "command-center/p2-wave/probes/CNL-0117/UNIT-ARTIFACT-MANIFEST.json",
  "registered": true
 },
 "measurements": {
  "probe1": {
   "empty_runtime_identical": true,
   "empty_runtime_ok": false,
   "empty_runtime_sha256": "d12d83e530cdd284f5883d77725a40c974c46e271a59bf8a676ada665df0a2ea",
   "event_count": 6,
   "kinds": [
    "position",
    "refusal",
    "vote"
   ],
   "live_sha256": "9dc334e4cf19020c7100e5bae3f1a690c6a463955160b0b0050b1d5b92a5c363",
   "live_vs_recorded": true,
   "ok": true,
   "perturbed_diverges": true,
   "perturbed_sha256": "e7193c569d44faeda58900358d703bc74c8d3d98326da8fc8365566ade1cee1e",
   "probe": "probe1-byte-identical",
   "recorded_path": "command-center/p2-wave/probes/CNL-0117/fixtures/recorded-transcript.json",
   "recorded_sha256": "9dc334e4cf19020c7100e5bae3f1a690c6a463955160b0b0050b1d5b92a5c363",
   "recount_sha256": "9dc334e4cf19020c7100e5bae3f1a690c6a463955160b0b0050b1d5b92a5c363",
   "recount_vs_recorded": true,
   "run_b_sha256": "9dc334e4cf19020c7100e5bae3f1a690c6a463955160b0b0050b1d5b92a5c363",
   "script_digest": "c398f73ea3d21cec9199b3c7eb9e8e0f9fe8dbd0057ebfbe24c300d93458e4d3",
   "seed_changed_on_vote_flip": true,
   "two_run_identical": true,
   "unit_id": "CNL-0117",
   "winner": "B"
  },
  "probe2": {
   "cached_constant_matches_recorded_on_unmutated": true,
   "cached_constant_rejected_when_script_flipped": true,
   "drop_missing_acts": [
    [
     1,
     "skeptic",
     "refusal"
    ]
   ],
   "drop_ok": false,
   "empty_ok": false,
   "fired_on_bad_state": true,
   "honest_missing_acts": [],
   "honest_ok": true,
   "negative_control": "On DropRefusalRuntime the harness check sets ok=false because the scripted (round=1, actor=skeptic, kind=refusal) act is missing from the transcript; HonestRuntime is silent (ok=true, missing_acts=[]).",
   "ok": true,
   "probe": "probe2-broken-runtime",
   "silent_on_good_state": true,
   "unit_id": "CNL-0117",
   "winner_drop": "B",
   "winner_honest": "B",
   "winner_recount": "B"
  }
 },
 "min_bytes_threshold": 4096,
 "named_probes": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0117/probe1_byte_identical.py",
   "id": "probe1",
   "role": "recorded-transcript-replay"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0117/probe2_broken_runtime.py",
   "id": "probe2",
   "role": "broken-runtime-self-test"
  }
 ],
 "negative_controls": [
  {
   "bad_state_output": "DropRefusalRuntime ok=False missing_acts=[[1, 'skeptic', 'refusal']]",
   "description": "On DropRefusalRuntime the harness check sets ok=false because the scripted (round=1, actor=skeptic, kind=refusal) act is missing from the transcript; HonestRuntime is silent (ok=true, missing_acts=[]).",
   "fired_on_bad_state": true,
   "good_state_output": "HonestRuntime ok=True missing_acts=[]",
   "id": "CNL0117-C1-drop-refusal",
   "kind": "known-broken-runtime",
   "rejects": "a runtime that silently omits a scripted refusal",
   "silent_on_good_state": true
  },
  {
   "bad_state_output": "empty_ok=False empty_identical=True",
   "description": "EmptyRuntime yields two-run byte-identical empty transcripts. The harness still sets ok=false because six scripted acts are missing. Two-run identity alone is the state this control rejects.",
   "fired_on_bad_state": true,
   "good_state_output": "honest two_run_identical=True event_count=6",
   "id": "CNL0117-C2-empty-runtime-identity-is-not-a-pass",
   "kind": "known-broken-runtime",
   "rejects": "treating two-run identity of an empty transcript as delivery",
   "silent_on_good_state": true
  }
 ],
 "not_under_test": {
  "harness": "Invariant check, canonicalization, fixture load, freeze of the recount snapshot.",
  "proof": "DropRefusalRuntime is accepted by two-run identity of itself but rejected by the harness recount; EmptyRuntime is also two-run-identical and rejected. Identity alone is not a pass.",
  "thing_under_test": "The injected CouncilRuntime (HonestRuntime for this unit; later units swap in role-enforcement, stopping, fan-in)."
 },
 "output_schema": "command-center/schema/council-simulation-spec.schema.json",
 "phase": "2C",
 "question": "What is the fake-participant substrate that makes every later council simulation deterministic - scripted positions, scripted votes, scripted refusals - and what proves the harness itself is not the thing under test?",
 "residual_unknowns": [
  {
   "claim": "Full CNL-0011 replay-state serialisation including tool-call order.",
   "settling_experiment": "Deliver CNL-0011, then pause/resume a scripted council (CNL-0122) with a single-seed perturbation.",
   "verdict": "NOT-CHECKED"
  },
  {
   "claim": "SEM-tree stopping-expression evaluation (CNL-0076 / CNL-0121).",
   "settling_experiment": "Deliver CNL-0076 and populate the 6x2 both-states table in CNL-0121.",
   "verdict": "NOT-CHECKED"
  }
 ],
 "retry": {
  "count": 0,
  "policy": "up to 3 attempts, each with a MECHANICALLY DIFFERENT oracle (scripted-participant replay, transcript diff, counter assertion)"
 },
 "reviewer": {
  "fresh_context": true,
  "independent": true,
  "method": "Named probe2 re-derives expected (round, actor, kind) tuples by flattening fixture scripts and sorting; it does not read the author's answer field. A disagreement in event count or the missing refusal blocks the unit.",
  "recount_sha256": "9dc334e4cf19020c7100e5bae3f1a690c6a463955160b0b0050b1d5b92a5c363",
  "reviewer_id": "CNL-0117-probe2-independent-recount",
  "scope_not_agreement": true,
  "verdict": "PASS",
  "winner_from_fixture_votes": "B"
 },
 "scenario": {
  "fixture_path": "command-center/p2-wave/probes/CNL-0117/fixtures/scenario.json",
  "id": "cnl-0117-scripted-three-seat",
  "recorded_path": "command-center/p2-wave/probes/CNL-0117/fixtures/recorded-transcript.json",
  "refusal": {
   "actor": "skeptic",
   "reason": "no-second-mechanism",
   "round": 1
  },
  "stop_from_recount": {
   "reason": "round_ceiling",
   "round": 2
  },
  "tally_from_recount": {
   "ballots": [
    {
     "actor": "architect",
     "option": "A",
     "weight": 1
    },
    {
     "actor": "skeptic",
     "option": "B",
     "weight": 1
    },
    {
     "actor": "critic",
     "option": "B",
     "weight": 1
    }
   ],
   "counts": {
    "A": 1,
    "B": 2
   },
   "method": "plurality",
   "winner": "B"
  }
 },
 "seeds_captured": {
  "roster_order": [
   "architect",
   "skeptic",
   "critic"
  ],
  "round_ceiling": 2,
  "script_digest": "c398f73ea3d21cec9199b3c7eb9e8e0f9fe8dbd0057ebfbe24c300d93458e4d3",
  "tally_method": "plurality"
 },
 "sentinel": "SUCCESS:CNL-0117",
 "state": "SUCCESS",
 "tests": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0117/probe1_byte_identical.py",
   "id": "T1-recorded-transcript-byte-identical-twice",
   "name": "The harness must reproduce a recorded transcript byte-identically twice",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0117/probe2_broken_runtime.py",
   "id": "T2-broken-runtime-fails-harness",
   "name": "A deliberately broken runtime must FAIL the harness, proving the harness is not vacuously green",
   "result": "PASS"
  }
 ],
 "timestamps": {
  "ended_at": "2026-08-25T00:54:36Z",
  "started_at": "2026-08-24T18:39:00Z"
 },
 "title": "Deterministic scripted-participant simulation harness",
 "unit_id": "CNL-0117"
}
