{
 "answer": "Yes on this scripted-participant harness. Pause after rounds [1, 2, 3] each resume to sha256=b97dd60870e7efe3454ffcde46084da71dec7d385b3afc3b647b902bfa8f6f4d matching the uninterrupted run and the snapshot replay. XOR of any one of ['sampling_seed', 'tool_order_seed', 'wall_clock_seed', 'recruitment_seed'] diverges. CachedTranscriptRuntime, which ignores the new seed, is REJECTED by that check (verdict=REJECT why=frozen-or-cached-transcript). Identical-seed replay alone cannot detect that cheat. SUCCESS:CNL-0122",
 "artifacts": [
  {
   "exists": true,
   "path": "command-center/design/council/CNL-0122-pause-resume-and-deterministic-replay-simulation.md",
   "role": "primary"
  },
  {
   "exists": true,
   "path": "command-center/schema/council-simulation-spec.schema.json",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0122/harness.py",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0122/cached.py",
   "role": "supporting"
  }
 ],
 "claim_under_test": "A council paused at an arbitrary round resumes to a byte-identical deliberation transcript versus an uninterrupted run on the same captured seeds; perturbing exactly one captured seed changes that transcript, which a cached/frozen runtime cannot satisfy.",
 "dependencies_on_this_tree": {
  "CNL-0011": "NOT-PRODUCED (replay-state fields executed here: sampling, tool_order, wall_clock, recruitment)",
  "CNL-0085": "NOT-PRODUCED (pause is a snapshot without mutation; question change is out of scope and would force restart)",
  "CNL-0117": "NOT-PRODUCED (scripted-participant harness implemented in this unit's probe dir, not at the CNL-0117 output_path)"
 },
 "downstream_consumers": [
  {
   "artifact_path": "command-center/design/council/CNL-0122-pause-resume-and-deterministic-replay-simulation.md",
   "consumer": "command-center/p2-wave/probes/CNL-0122/probe2_seed_perturbation.py",
   "executed": true,
   "note": "Probe 2 re-tabulates live hashes and, when this file exists, compares results.uninterrupted.sha256 and perturbation rows.",
   "read_ok": true
  }
 ],
 "evidence": [
  {
   "anchor": "command-center/p2-wave/probes/CNL-0122/harness.py:233",
   "claim": "Uninterrupted transcript sha256=b97dd60870e7efe3454ffcde46084da71dec7d385b3afc3b647b902bfa8f6f4d events=69 equals pause/resume and replay at rounds [1, 2, 3].",
   "mechanism": "canonical JSONL sha256 of deliberation events",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0122/harness.py:41",
   "claim": "NUL-joined event-index fingerprint matches across pause/resume (fingerprint=27d81e3637985a5141d8724025b67b3480a01de499cdaa51d06d21dbef5f69ae) and diverges when any one captured seed is XOR-flipped.",
   "mechanism": "event-index fingerprint (different field join, not JSONL sha256)",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0122/cached.py:10",
   "claim": "CachedTranscriptRuntime is rejected by the perturbation check; a real sampling_seed XOR is accepted.",
   "mechanism": "counter-assertion against a deliberately cached runtime",
   "verdict": "CONFIRMED"
  }
 ],
 "format_note": "Catalog output_path ends in .md. G-1 _measure_one_delivered.py json.loads the whole file, so this artifact is a JSON council-simulation-spec, not prose markdown.",
 "harness": {
  "how_harness_is_not_sut": "CachedTranscriptRuntime wraps the same inner bytes and stays green under identical-seed replay. Probe 2 rejects it. The instrument therefore fails a deliberately broken runtime instead of being vacuously green.",
  "id": "cnl-0122-scripted-council",
  "kind": "scripted-participant-deterministic-sim",
  "path": "command-center/p2-wave/probes/CNL-0122/harness.py",
  "proves_harness_is_not_sut": true
 },
 "inputs_on_this_tree": {
  "11-COUNCIL-SPECIFICATION.schema.json": false,
  "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": false,
  "_USER-PROMPTS.md:10746-10767": false,
  "_USER-PROMPTS.md:10915-10946": false,
  "note": "Catalog inputs point at a Windows harness-restore tree that is absent here. The simulation executes a scripted-participant harness in this probe directory instead of narrating those files."
 },
 "manifest_registration": {
  "global_catalog_write": false,
  "manifest_path": "command-center/p2-wave/probes/CNL-0122/UNIT-ARTIFACT-MANIFEST.json",
  "registered": true
 },
 "min_bytes_threshold": 2000,
 "named_probes": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0122/probe1_identical_replay.py",
   "id": "probe1",
   "role": "identical-seed-replay"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0122/probe2_seed_perturbation.py",
   "id": "probe2",
   "role": "seed-perturbation-negative-control"
  }
 ],
 "negative_controls": [
  {
   "bad_state_output": "verdict=REJECT why=frozen-or-cached-transcript",
   "fired_on_bad_state": true,
   "good_state_output": "verdict=ACCEPT why=perturbed-seed-changed-transcript",
   "id": "CNL0122-C1-cached-transcript",
   "rejects": "CachedTranscriptRuntime that returns the first transcript for every subsequent seed",
   "silent_on_good_state": true,
   "verbatim": "On the rejected state the check reports verdict=REJECT why=frozen-or-cached-transcript. Identical-seed replay of that runtime would still be byte-identical, so asserting only the first test cannot detect a frozen or cached transcript. On the accepted state (real CouncilSim) the same check reports verdict=ACCEPT why=perturbed-seed-changed-transcript."
  }
 ],
 "question": "Does a council paused at an arbitrary round resume to a byte-identical transcript - and does perturbing exactly one captured seed change it, proving the replay is real rather than cached?",
 "replay_state_model": {
  "minimal_serialized_fields": [
   "seeds.sampling_seed",
   "seeds.tool_order_seed",
   "seeds.wall_clock_seed",
   "seeds.recruitment_seed",
   "roster_order",
   "round",
   "t",
   "clock",
   "events",
   "stopped",
   "script_digest"
  ],
  "nondeterminism_captured_as_seeds": {
   "participant_recruitment": "recruitment_seed permutes speaking order",
   "sampling_temperature": "sampling_seed mixes into utterance text, tool args, and ballots",
   "tool_call_ordering": "tool_order_seed permutes TOOLS per seat per round",
   "wall_clock": "synthetic clock from wall_clock_seed; time.time is not read"
  },
  "owner_boundary": "Pause without mutating question, roster, or seeds is resume. Changing the question or replacing the chair invalidates the snapshot and requires a recorded restart (CNL-0085); not exercised as a green path here.",
  "pause_is": "a snapshot of replay state, not a deliberation event",
  "transcript_is": "canonical JSONL of deliberation events (round_open, utterance, tool, vote, stopped)"
 },
 "report": {
  "control_ids": [
   "CNL0122-C1-cached-transcript"
  ],
  "kind": "council-simulation-spec",
  "observations": [
   {
    "anchor": "command-center/p2-wave/probes/CNL-0122/harness.py:37",
    "measured": "b97dd60870e7efe3454ffcde46084da71dec7d385b3afc3b647b902bfa8f6f4d",
    "method": "canonical-jsonl-sha256",
    "name": "uninterrupted_sha256"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0122/harness.py:41",
    "measured": "27d81e3637985a5141d8724025b67b3480a01de499cdaa51d06d21dbef5f69ae",
    "method": "nul-joined-event-index",
    "name": "event_index_fingerprint"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0122/harness.py:233",
    "measured": true,
    "method": "pause-resume-and-snapshot-replay",
    "name": "identical_seed_byte_identical"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0122/harness.py:203",
    "measured": true,
    "method": "single-seed-xor-perturbation",
    "name": "all_seeds_load_bearing"
   }
  ]
 },
 "report_kind": "council-simulation-spec",
 "residual_unknowns": [
  {
   "claim": "Catalog Windows harness-restore inputs (_USER-PROMPTS.md, 11-COUNCIL-SPECIFICATION, 12-COUNCIL-PROTOCOLS-AND-PRESETS) on this Linux worktree.",
   "settling_experiment": "Mount the harness-restore tree and re-run the same scripted harness against those files as fixtures, not as narration.",
   "verdict": "NOT-CHECKED"
  }
 ],
 "results": {
  "all_seeds_load_bearing": true,
  "computed": true,
  "identical_seed_byte_identical": true,
  "pause_resume": [
   {
    "identical_to_uninterrupted": true,
    "pause_after_round": 1,
    "replay_identical": true,
    "replay_sha256": "b97dd60870e7efe3454ffcde46084da71dec7d385b3afc3b647b902bfa8f6f4d",
    "resume_event_count": 69,
    "resume_fingerprint": "27d81e3637985a5141d8724025b67b3480a01de499cdaa51d06d21dbef5f69ae",
    "resume_sha256": "b97dd60870e7efe3454ffcde46084da71dec7d385b3afc3b647b902bfa8f6f4d",
    "snapshot_event_count": 17,
    "snapshot_next_round": 2
   },
   {
    "identical_to_uninterrupted": true,
    "pause_after_round": 2,
    "replay_identical": true,
    "replay_sha256": "b97dd60870e7efe3454ffcde46084da71dec7d385b3afc3b647b902bfa8f6f4d",
    "resume_event_count": 69,
    "resume_fingerprint": "27d81e3637985a5141d8724025b67b3480a01de499cdaa51d06d21dbef5f69ae",
    "resume_sha256": "b97dd60870e7efe3454ffcde46084da71dec7d385b3afc3b647b902bfa8f6f4d",
    "snapshot_event_count": 34,
    "snapshot_next_round": 3
   },
   {
    "identical_to_uninterrupted": true,
    "pause_after_round": 3,
    "replay_identical": true,
    "replay_sha256": "b97dd60870e7efe3454ffcde46084da71dec7d385b3afc3b647b902bfa8f6f4d",
    "resume_event_count": 69,
    "resume_fingerprint": "27d81e3637985a5141d8724025b67b3480a01de499cdaa51d06d21dbef5f69ae",
    "resume_sha256": "b97dd60870e7efe3454ffcde46084da71dec7d385b3afc3b647b902bfa8f6f4d",
    "snapshot_event_count": 51,
    "snapshot_next_round": 4
   }
  ],
  "perturbation": [
   {
    "diverged": true,
    "event_count": 69,
    "first_divergence_index": 1,
    "first_divergence_kind": "utterance",
    "seed": "sampling_seed",
    "sha256": "cb72067057f6014832f57a30b8f3d956c823b7867c25b122280662a6850387b0"
   },
   {
    "diverged": true,
    "event_count": 69,
    "first_divergence_index": 6,
    "first_divergence_kind": "tool",
    "seed": "tool_order_seed",
    "sha256": "68d812e6206307c9e895b575853e178aa228bb655f1fa5f4d1d80609820468d5"
   },
   {
    "diverged": true,
    "event_count": 69,
    "first_divergence_index": 0,
    "first_divergence_kind": "round_open",
    "seed": "wall_clock_seed",
    "sha256": "7b34a3f865b319a9a4c2bb99d4aaa48ffe3a9c2ab669b24df58ddb4429df59d9"
   },
   {
    "diverged": true,
    "event_count": 69,
    "first_divergence_index": 1,
    "first_divergence_kind": "utterance",
    "seed": "recruitment_seed",
    "sha256": "75e7f398c2235f8edadea9bdd926e1b703926c3191dc9d97356573e7e409f083"
   }
  ],
  "three_sha256": {
   "pause_resume_round_2": "b97dd60870e7efe3454ffcde46084da71dec7d385b3afc3b647b902bfa8f6f4d",
   "replay_from_snapshot_round_2": "b97dd60870e7efe3454ffcde46084da71dec7d385b3afc3b647b902bfa8f6f4d",
   "uninterrupted": "b97dd60870e7efe3454ffcde46084da71dec7d385b3afc3b647b902bfa8f6f4d"
  },
  "uninterrupted": {
   "bytes": 7979,
   "event_count": 69,
   "final_round_emitted": 4,
   "fingerprint": "27d81e3637985a5141d8724025b67b3480a01de499cdaa51d06d21dbef5f69ae",
   "roster_order": [
    "critic",
    "pragmatist",
    "skeptic",
    "architect"
   ],
   "sha256": "b97dd60870e7efe3454ffcde46084da71dec7d385b3afc3b647b902bfa8f6f4d"
  },
  "uninterrupted_sha256": "b97dd60870e7efe3454ffcde46084da71dec7d385b3afc3b647b902bfa8f6f4d"
 },
 "retry": {
  "count": 0,
  "policy": "up to 3 attempts, each with a MECHANICALLY DIFFERENT oracle (scripted-participant replay, transcript diff, counter assertion). Two same-fingerprint structural refutes park BLOCKED; no ADV rebuild."
 },
 "reviewer": {
  "independent": true,
  "method": "probe2 re-runs CouncilSim, re-tabulates sha256 and the event-index fingerprint per seed, and compares those numbers to measure() and to this artifact. A disagreement in any sha256 blocks the unit.",
  "reviewer_id": "CNL-0122-probe2-seed-perturbation-recount",
  "verdict": "PASS"
 },
 "scenario": {
  "captured_seeds": {
   "recruitment_seed": 3240250967,
   "sampling_seed": 3240253953,
   "tool_order_seed": 3240259585,
   "wall_clock_seed": 3240280332
  },
  "id": "cnl-0122-pause-resume-replay",
  "max_rounds": 4,
  "pause_after_rounds": [
   1,
   2,
   3
  ],
  "roster": [
   "architect",
   "skeptic",
   "pragmatist",
   "critic"
  ],
  "script_digest": "4d2b844204afd795f619e345cc9fb77fb8e8b00bf0c0a968076af6f82d0bc541",
  "title": "Pause at rounds 1-3, resume, replay, then kill one seed",
  "tools": [
   "read_spec",
   "write_ballot"
  ]
 },
 "schema_version": 1,
 "sentinel": "SUCCESS:CNL-0122",
 "spec_anchor": "command-center/WORK-UNIT-CATALOG.json CNL-0122 question_or_target; pause/resume/replay executed in command-center/p2-wave/probes/CNL-0122/harness.py",
 "state": "SUCCESS",
 "tests": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0122/probe1_identical_replay.py",
   "id": "identical-seed-replay-byte-identical",
   "name": "Pause at rounds 1, 2, 3 and snapshot-replay each match the uninterrupted transcript sha256",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0122/probe2_seed_perturbation.py",
   "id": "single-seed-perturbation-diverges",
   "name": "XOR of each captured seed changes the transcript; cached runtime is rejected",
   "result": "PASS"
  }
 ],
 "timestamps": {
  "ended_at": "2026-08-25T00:56:06Z",
  "started_at": "2026-08-25T00:52:00Z"
 },
 "title": "Pause, resume and deterministic replay simulation",
 "unit_id": "CNL-0122"
}
