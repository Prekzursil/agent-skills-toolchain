{
 "artifacts": [
  {
   "bytes": 1179,
   "eol": "CRLF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0036/fixtures.json",
   "role": "fixture",
   "sha256": "2be5e1c8fd73fcecf977ea0e010bc89a21d01f58f1f94478d1799464aa7f4e3c"
  },
  {
   "bytes": 6248,
   "eol": "CRLF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0036/bracket.py",
   "role": "supporting",
   "sha256": "50f8253fdf522f0116152ff7d40dabfe98fca1892ff081cfa5ff85451ec124af"
  },
  {
   "bytes": 1118,
   "eol": "LF",
   "exists": true,
   "path": "command-center/schema/council-design-note.schema.json",
   "role": "supporting",
   "sha256": "e66edc40156c6abcad6b2e27d5e6ebc32a37e72559967fa1fc3ce53e5b245755"
  }
 ],
 "downstream_consumers": [
  {
   "artifact_path": "command-center/design/council/CNL-0036-pairwise-tournament-topology-bracket-seeding-and-tie-break.md",
   "consumer": "platform/lib/schema_resolver.py validate_artifact",
   "executed": true,
   "exit_code": 0,
   "probe": {
    "command": "schema_resolver.validate_artifact(doc, 'command-center/schema/council-design-note.schema.json')",
    "exit_code": 0,
    "fingerprint": "4b8a84b0c5e6aa20c60d302643e0a215",
    "method": "schema-validate",
    "raw_output": "validated before write; emitter refuses to persist an invalid artifact",
    "role": "verifier"
   },
   "read_ok": true
  }
 ],
 "evidence": [
  {
   "anchor": "command-center/p2-wave/probes/CNL-0036/fixtures.json:7",
   "claim": "On cyclic-plus-dummy, all 24 seedings of {W,X,Y,Z} produce three distinct knockout winners W,X,Y with 8 seedings each (invariance_rate=1/3); Z never wins.",
   "confidence": "almost-certain",
   "probes": [
    {
     "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0036/probe1_seeding_sweep.py",
     "exit_code": 0,
     "fingerprint": "9aa55cc580654648f2711054cfcc26b6",
     "method": "command",
     "raw_output": "PLANTED-BAD cyclic4: n_perm=24 n_distinct=3 counts={'W': 8, 'X': 8, 'Y': 8} invariance_rate=0.333333333333 fires=True publication=SEEDING-DEPENDENT-REFUSED",
     "role": "source"
    },
    {
     "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0036/probe2_independent_recount.py",
     "exit_code": 0,
     "fingerprint": "6226e690d11dbfa75cc1948bab7f45c4",
     "method": "test-run",
     "raw_output": "recount cyclic4: n_perm=24 n_distinct=3 counts={'W': 8, 'X': 8, 'Y': 8} invariance_rate=0.333333333333",
     "role": "verifier"
    }
   ],
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0036/bracket.py:181",
   "claim": "The invariance gate refuses a unique published winner on cyclic4 and permits W on transitive4, where W wins all 24 seedings.",
   "confidence": "almost-certain",
   "probes": [
    {
     "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0036/probe1_seeding_sweep.py",
     "exit_code": 0,
     "fingerprint": "9aa55cc580654648f2711054cfcc26b6",
     "method": "command",
     "raw_output": "KNOWN-GOOD transitive4: n_perm=24 n_distinct=1 counts={'W': 24} invariance_rate=1.000000000000 fires=False publication=INVARIANT-UNIQUE-WINNER published_winner=W",
     "role": "source"
    },
    {
     "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0036/probe2_independent_recount.py",
     "exit_code": 0,
     "fingerprint": "6226e690d11dbfa75cc1948bab7f45c4",
     "method": "test-run",
     "raw_output": "recount transitive4: n_perm=24 n_distinct=1 counts={'W': 24} invariance_rate=1.000000000000",
     "role": "verifier"
    }
   ],
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0036/bracket.py:33",
   "claim": "Using left_slot as the W/X match tie-break splits winners 12/12; lexicographic_id yields W on all 24. Slot-dependent tie-break is not an invariance-preserving rule.",
   "confidence": "almost-certain",
   "probes": [
    {
     "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B -c \"import json,sys; sys.path.insert(0,'command-center/p2-wave/probes/CNL-0036'); import bracket as B; fx=json.load(open('command-center/p2-wave/probes/CNL-0036/fixtures.json')); print(B.sweep(fx['options'], B.beats_set(fx['tied_wx']['beats']), B.tie_set(fx['tied_wx']['ties']), 'left_slot')['counts'])\"",
     "exit_code": 0,
     "fingerprint": "c075c7cc766b8a349a062adf71eea042",
     "method": "command",
     "raw_output": "left_slot counts={'W': 12, 'X': 12}",
     "role": "source"
    },
    {
     "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0036/probe2_independent_recount.py",
     "exit_code": 0,
     "fingerprint": "6226e690d11dbfa75cc1948bab7f45c4",
     "method": "test-run",
     "raw_output": "left_slot counts={'W': 12, 'X': 12}",
     "role": "verifier"
    }
   ],
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "source_inputs_on_this_tree",
   "claim": "Harness-restore 11-COUNCIL-SPECIFICATION.schema.json and 12-COUNCIL-PROTOCOLS-AND-PRESETS.json were read on this worktree and the bracket rule was copied from them.",
   "confidence": "almost-certain",
   "probes": [
    {
     "command": "python3 -c \"from pathlib import Path; print(Path('C:/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json').is_file())\"",
     "exit_code": 0,
     "fingerprint": "de852d36fd42de16dd2249d4956a21e5",
     "method": "file-read",
     "raw_output": "False",
     "role": "source"
    },
    {
     "command": "python3 -c \"from pathlib import Path; print(Path('C:/Users/Prekzursil/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json').is_file())\"",
     "exit_code": 0,
     "fingerprint": "faf3cd8648707f613459077216089506",
     "method": "command",
     "raw_output": "False",
     "role": "verifier"
    }
   ],
   "verdict": "REFUTED"
  }
 ],
 "manifest_registration": {
  "entry_id": "CNL-0036",
  "manifest_path": "command-center/p2-wave/probes/CNL-0036/UNIT-ARTIFACT-MANIFEST.json",
  "registered": true
 },
 "min_bytes_threshold": 2048,
 "negative_controls": [
  {
   "bad_state_output": "PLANTED-BAD cyclic4: n_perm=24 n_distinct=3 counts={'W': 8, 'X': 8, 'Y': 8} invariance_rate=0.333333333333 fires=True publication=SEEDING-DEPENDENT-REFUSED",
   "description": "Refuse publishing the knockout winner of a single seed order on the cyclic-plus-dummy oracle as if it were seeding-invariant. Must FIRE on cyclic4 and stay SILENT on transitive4.",
   "fired_on_bad_state": true,
   "good_state_output": "KNOWN-GOOD transitive4: n_perm=24 n_distinct=1 counts={'W': 24} invariance_rate=1.000000000000 fires=False publication=INVARIANT-UNIQUE-WINNER published_winner=W",
   "id": "NC-CYCLIC-UNIQUE-WINNER",
   "kind": "known-broken-fixture",
   "silent_on_good_state": true
  },
  {
   "bad_state_output": "left_slot counts={'W': 12, 'X': 12}",
   "description": "Refuse using the left bracket slot to break a declared W vs X tie. Must FIRE (split 12/12) on left_slot and stay SILENT (W x24) on lexicographic_id.",
   "fired_on_bad_state": true,
   "good_state_output": "lexicographic counts={'W': 24}",
   "id": "NC-LEFT-SLOT-TIE-BREAK",
   "kind": "known-broken-fixture",
   "silent_on_good_state": true
  }
 ],
 "produced_by": {
  "execution_substrate": "local-parallel",
  "model": "opus",
  "role": "council-systems-designer",
  "vendor": "anthropic"
 },
 "profile": "council-design-note",
 "report": {
  "answer": "Options are placed by a seed list that is exogenous to the pairwise oracle: seed_order[0] is seed 1. Seeds occupy a standard single-elimination slotting of the next power of two (1 plays n, 2 plays n-1, recursive construction in bracket.standard_slot_seeds); unfilled seeds are BYEs. Each match is resolved by the pairwise oracle; a declared pairwise tie uses lexicographic option id, never the left bracket slot. The well-known seeding dependence is stopped from silently picking the winner by a mandatory permutation sweep: the same oracle is replayed under all n! seed orders (here n=4, N=24). A unique winner may be published only if invariance_rate == 1. On cyclic-plus-dummy the sweep yields n_distinct=3 counts={'W': 8, 'X': 8, 'Y': 8} invariance_rate=0.333333333333; the gate FIRES and publication is SEEDING-DEPENDENT-REFUSED. On linear-strength the sweep yields counts={'W': 24} invariance_rate=1.000000000000; the gate is SILENT and W may be published. Left-slot tie-break on the W/X tie splits W/X 12/12, which is why that rule is forbidden for an invariance claim. Condorcet cycle completion is CNL-0063; this unit treats the pairwise matrix as an oracle and reports knockout seeding dependence instead of silently completing a cycle. SUCCESS:CNL-0036",
  "answers": {
   "how_match_ties_are_broken": "Declared pairwise ties use lexicographic option id (min(id_a, id_b)), which is independent of bracket slot. left_slot is forbidden: on tied_wx it yields W=12,X=12 across the 24 seedings, reintroducing seeding into a tie.",
   "how_options_are_seeded": "A pre-registered seed_order places option i as seed rank i+1 into standard single-elim slots of size next_pow2(n) with BYEs on unused seeds. Pairing is 1 vs n, 2 vs n-1 via the recursive slot list, not an ad-hoc shuffle of names.",
   "how_seeding_dependence_is_prevented": "Before a unique knockout winner is published, replay the same pairwise oracle under all n! seed orders. Publish a unique winner only if n_distinct_winners==1 (invariance_rate == 1.0). cyclic4 measures n_distinct=3, rate=0.333333333333 and is refused. The number is required; a stability claim without it is refused."
  },
  "both_states": {
   "known_good": "transitive4",
   "known_good_silent": true,
   "planted_bad": "cyclic4",
   "planted_bad_fires": true,
   "verbatim_bad": "PLANTED-BAD cyclic4: n_perm=24 n_distinct=3 counts={'W': 8, 'X': 8, 'Y': 8} invariance_rate=0.333333333333 fires=True publication=SEEDING-DEPENDENT-REFUSED",
   "verbatim_good": "KNOWN-GOOD transitive4: n_perm=24 n_distinct=1 counts={'W': 24} invariance_rate=1.000000000000 fires=False publication=INVARIANT-UNIQUE-WINNER published_winner=W"
  },
  "completion_sentinel": "SUCCESS:CNL-0036",
  "control_ids": [
   "NC-CYCLIC-UNIQUE-WINNER",
   "NC-LEFT-SLOT-TIE-BREAK"
  ],
  "dependency_cnl_0063": {
   "consumed_as_blocker": false,
   "id": "CNL-0063",
   "role": "Pairwise/Condorcet cycle completion. This unit consumes a complete pairwise oracle and reports seeding dependence; it does not choose a cycle completion after seeing who would win."
  },
  "gate": {
   "cyclic4": {
    "fires": true,
    "invariance_rate": 0.3333333333333333,
    "n_distinct_winners": 3,
    "publication": "SEEDING-DEPENDENT-REFUSED",
    "published_winner": null,
    "threshold_reject_below": 1.0
   },
   "tied_wx": {
    "fires": false,
    "invariance_rate": 1.0,
    "n_distinct_winners": 1,
    "publication": "INVARIANT-UNIQUE-WINNER",
    "published_winner": "W",
    "threshold_reject_below": 1.0
   },
   "transitive4": {
    "fires": false,
    "invariance_rate": 1.0,
    "n_distinct_winners": 1,
    "publication": "INVARIANT-UNIQUE-WINNER",
    "published_winner": "W",
    "threshold_reject_below": 1.0
   }
  },
  "kind": "council-design-note",
  "measurement": {
   "coverage_alone_insufficient": true,
   "coverage_definition": "Running one seeding is coverage of a single pairing, not evidence the winner is seeding-invariant.",
   "formula": "invariance_rate = max(winner_counts) / n! over all seed permutations of a fixed pairwise oracle; n_distinct_winners = |{winners}|. Unique-winner publication is rejected when invariance_rate < 1.0.",
   "name": "seeding_invariance_rate",
   "threshold_reject_below": 1.0
  },
  "observations": [
   {
    "anchor": "command-center/p2-wave/probes/CNL-0036/fixtures.json:7",
    "measured": 3,
    "method": "bracket.sweep over 4! seed orders",
    "name": "cyclic4_n_distinct_winners"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0036/bracket.py:181",
    "measured": 0.3333333333333333,
    "method": "max(winner_counts)/n!",
    "name": "cyclic4_invariance_rate"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0036/bracket.py:181",
    "measured": 24,
    "method": "bracket.sweep over 4! seed orders",
    "name": "transitive4_w_wins"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0036/bracket.py:33",
    "measured": "W=12,X=12",
    "method": "bracket.sweep with tie_break=left_slot",
    "name": "left_slot_split"
   }
  ],
  "question": "How are options seeded into a pairwise bracket, and how is the well-known dependence of bracket outcomes on seeding order prevented from silently determining the winner?",
  "source_inputs_on_this_tree": {
   "11-COUNCIL-SPECIFICATION.schema.json": false,
   "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": false,
   "_USER-PROMPTS.md": false,
   "note": "Catalog inputs are Windows harness-restore paths not present here. Pairwise beats are operational fixtures this unit supplies. CNL-0063's tabulate.py exists as a neighbor oracle for cycle completion; this unit does not silently apply it to hide knockout seeding dependence."
  },
  "sweep": {
   "cyclic4": {
    "counts": {
     "W": 8,
     "X": 8,
     "Y": 8
    },
    "invariance_rate": 0.3333333333333333,
    "modal_winner": "W",
    "n_distinct_winners": 3,
    "n_permutations": 24,
    "reason": "seeding-dependent",
    "tie_break": "lexicographic_id"
   },
   "tied_wx": {
    "counts": {
     "W": 24
    },
    "invariance_rate": 1.0,
    "modal_winner": "W",
    "n_distinct_winners": 1,
    "n_permutations": 24,
    "reason": "seeding-invariant",
    "tie_break": "lexicographic_id"
   },
   "tied_wx_left_slot": {
    "counts": {
     "W": 12,
     "X": 12
    },
    "invariance_rate": 0.5,
    "modal_winner": "W",
    "n_distinct_winners": 2,
    "n_permutations": 24,
    "reason": "seeding-dependent",
    "tie_break": "left_slot"
   },
   "transitive4": {
    "counts": {
     "W": 24
    },
    "invariance_rate": 1.0,
    "modal_winner": "W",
    "n_distinct_winners": 1,
    "n_permutations": 24,
    "reason": "seeding-invariant",
    "tie_break": "lexicographic_id"
   }
  },
  "taxonomy": {
   "categories": [
    {
     "description": "n_distinct_winners==1; unique winner may be published with the sweep number.",
     "id": "INVARIANT-UNIQUE-WINNER"
    },
    {
     "description": "n_distinct_winners>1; unique winner publication is refused; the sweep table is the result.",
     "id": "SEEDING-DEPENDENT-REFUSED"
    }
   ],
   "closed": true,
   "id": "council.knockout-publication.v1",
   "range_rule": "A knockout result is published as a unique winner only when the permutation sweep reports invariance_rate == 1.0. One observed seeding is not a new publication category."
  },
  "title": "Pairwise tournament topology: bracket, seeding and tie-break"
 },
 "residual_unknowns": [
  {
   "claim": "Whether a later CouncilSpec on another tree already names a different standard slotting (e.g. adjacent pairing without 1-vs-n). This note's operational slotting is bracket.standard_slot_seeds. Large n where n! cannot be enumerated would need a declared sample size; n=4 is fully enumerated here (24).",
   "settling_experiment": "When a CouncilSpec with an explicit slotting enum lands on this tree, re-run the 24-permutation sweep under that slotting and compare n_distinct to this note.",
   "verdict": "NOT-CHECKED"
  }
 ],
 "retry": {
  "count": 0,
  "policy": "two strikes then pivot: after the 2nd failure on the same hypothesis, enumerate >=2 alternative mechanisms before a 3rd attempt (AGENTS.md 4b). Max 3 attempts."
 },
 "reviewer": {
  "fresh_context": true,
  "independent": true,
  "notes": "4-team closed form play(play(s1,s4), play(s2,s3)); match winners by scanning beats/ties lists. Does not call bracket.sweep or bracket.run_bracket.",
  "reviewer_id": "CNL-0036-probe2-independent-recount",
  "verdict": "PASS"
 },
 "schema_version": 1,
 "sentinel": "SUCCESS:CNL-0036",
 "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:36067",
 "state": "SUCCESS",
 "tests": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0036/probe1_seeding_sweep.py",
   "id": "T-SEEDING-SWEEP",
   "name": "same option set under all 24 seedings; report how often the winner changes; a stable claim requires the number",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0036/probe2_independent_recount.py",
   "id": "T-INDEPENDENT-RECOUNT",
   "name": "reviewer re-derives winners via the 4-team closed form (s1 vs s4, s2 vs s3) by scanning beats lists",
   "result": "PASS"
  }
 ],
 "timestamps": {
  "ended_at": "2026-08-25T00:58:30Z",
  "started_at": "2026-08-24T18:50:00Z"
 },
 "sweep": {
  "cyclic4": {
   "counts": {
    "W": 8,
    "X": 8,
    "Y": 8
   },
   "invariance_rate": 0.3333333333333333,
   "n_distinct_winners": 3,
   "n_permutations": 24
  },
  "transitive4": {
   "counts": {
    "W": 24
   },
   "invariance_rate": 1.0,
   "n_distinct_winners": 1,
   "n_permutations": 24
  },
  "tied_wx": {
   "counts": {
    "W": 24
   },
   "invariance_rate": 1.0,
   "n_distinct_winners": 1,
   "n_permutations": 24,
   "tie_break": "lexicographic_id"
  }
 },
 "unit_id": "CNL-0036"
}
