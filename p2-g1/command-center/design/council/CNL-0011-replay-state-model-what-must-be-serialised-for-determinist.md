{
 "anchors": {
  "AXES": "command-center/p2-wave/probes/CNL-0011/replay_engine.py:19",
  "clock_never_wall": "command-center/p2-wave/probes/CNL-0011/replay_engine.py:80",
  "decorative_mutant": "command-center/p2-wave/probes/CNL-0011/replay_engine.py:269",
  "draw_u32": "command-center/p2-wave/probes/CNL-0011/replay_engine.py:39",
  "resume": "command-center/p2-wave/probes/CNL-0011/replay_engine.py:244",
  "serialize": "command-center/p2-wave/probes/CNL-0011/replay_engine.py:219"
 },
 "answer": "Minimal pause blob is cnl-0011.replay-state.v1: frozen spec+pool, four named seeds with their draw cursors, clock_origin_ms, roster, transcript prefix, pending/flush tool queues, scheduler cursors (turn_i, round_i, sub, want_stop), remaining budgets, and stop flags. Sampling temperature, tool-call ordering, wall-clock origin, and participant recruitment MUST be captured as seeds (plus the clock origin value). They must not be re-derived from time.time(), live availability, hash(dict), or unordered sets. Observed transcript bytes are part of the blob because a real vendor completion cannot be regenerated from a seed. spec_hash/pool_hash and vote/stop results are integrity or derived views, not sources of truth. Same seeds twice and pause/resume both yielded sha256=11913978b7db24a47f09b6802ed39f02a31115c5eaa991673bb694d9ef688442 over 20 events. Perturbing any one seed changed the transcript; a mutant that ignores sampling left it unchanged, so the seed check is not vacuous.",
 "dependencies_note": "CNL-0001 (CouncilSpec v2 envelope) and CNL-0008 (budget exhaustion semantics) are not delivered on this tree. This unit ships a $defs.replay_state fragment and serialises remaining budgets rather than recomputing them from wall-clock. It does not invent a v2 root envelope.",
 "engine": "command-center/p2-wave/probes/CNL-0011/replay_engine.py",
 "evidence": [
  {
   "claim": "Same seeds twice and pause/resume are byte-identical (scripted-participant replay oracle).",
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0011/probe1_replay_identical.py",
   "exit_code": 0,
   "mechanism": "command-plus-output",
   "snippet": [
    "two_run_identical=True events=20 sha=11913978b7db24a47f09b6802ed39f02a31115c5eaa991673bb694d9ef688442 line_join_match=True",
    "pause_resume_5 match=True unint=11913978b7db24a47f09b6802ed39f02a31115c5eaa991673bb694d9ef688442 resumed=11913978b7db24a47f09b6802ed39f02a31115c5eaa991673bb694d9ef688442",
    "pause_resume_11 match=True unint=11913978b7db24a47f09b6802ed39f02a31115c5eaa991673bb694d9ef688442 resumed=11913978b7db24a47f09b6802ed39f02a31115c5eaa991673bb694d9ef688442",
    "SUCCESS:CNL-0011-probe1 same-seed replay and pause/resume identity"
   ]
  },
  {
   "claim": "Independent recount from transcript events (not engine internals) gives event_count=20 kinds={'recruit': 1, 'utter': 6, 'tool_call': 6, 'tool_result': 6, 'stop': 1} roster=['p.auditor', 'p.historian', 'p.skeptic'] ticks_strictly_increasing=True.",
   "line": 219,
   "mechanism": "file:line plus independent recount",
   "path": "command-center/p2-wave/probes/CNL-0011/replay_engine.py",
   "recount": {
    "actor_sequence": [
     "runtime",
     "p.auditor",
     "p.auditor",
     "p.historian",
     "p.historian",
     "p.skeptic",
     "p.skeptic",
     "runtime",
     "runtime",
     "runtime",
     "p.auditor",
     "p.auditor",
     "p.historian",
     "p.historian",
     "p.skeptic",
     "p.skeptic",
     "runtime",
     "runtime",
     "runtime",
     "runtime"
    ],
    "event_count": 20,
    "kinds": {
     "recruit": 1,
     "stop": 1,
     "tool_call": 6,
     "tool_result": 6,
     "utter": 6
    },
    "roster": [
     "p.auditor",
     "p.historian",
     "p.skeptic"
    ],
    "t_ms": [
     7613000,
     7614000,
     7615000,
     7616000,
     7617000,
     7618000,
     7619000,
     7620000,
     7621000,
     7622000,
     7623000,
     7624000,
     7625000,
     7626000,
     7627000,
     7628000,
     7629000,
     7630000,
     7631000,
     7632000
    ],
    "ticks_strictly_increasing": true,
    "tool_result_sequence": [
     "cite:75",
     "trace:68",
     "archive:3",
     "archive:4",
     "trace:55",
     "cite:51"
    ]
   },
   "snippet": "def serialize(self) -> dict:"
  },
  {
   "claim": "Each of the four seeds is load-bearing; decorative sampling mutant fires.",
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0011/probe2_seed_perturbation.py",
   "exit_code": 0,
   "mechanism": "command-plus-output",
   "snippet": [
    "perturb axis=sampling changed=True base=101 pert=102 sha_base=11913978b7db24a4 sha_pert=7aeed3113fcc0f8b first_diff_index=1 kind_base=utter kind_pert=utter",
    "perturb axis=tool_order changed=True base=202 pert=203 sha_base=11913978b7db24a4 sha_pert=b0d69a384ff95c19 first_diff_index=7 kind_base=tool_result kind_pert=tool_result",
    "perturb axis=clock changed=True base=303 pert=304 sha_base=11913978b7db24a4 sha_pert=81aa38971634d954 first_diff_index=0 kind_base=recruit kind_pert=recruit",
    "perturb axis=recruitment changed=True base=404 pert=405 sha_base=11913978b7db24a4 sha_pert=1f4b89df38632b5a first_diff_index=0 kind_base=recruit kind_pert=recruit",
    "NEGATIVE CONTROL (verbatim): perturb sampling seed +1 on the real engine; the check requires sha_base != sha_perturbed. Observed real_changes=True sha_base=11913978b7db24a47f09b6802ed39f02a31115c5eaa991673bb694d9ef688442 sha_perturbed=7aeed3113fcc0f8ba651f5b264635366600909f2d9b04be54e4d459997623154.",
    "NEGATIVE CONTROL (planted-bad mutant DecorativeSamplingCouncil): the same sampling perturbation must leave the transcript UNCHANGED, proving the check fires when a seed is serialised but unused. Observed mutant_changes=False check_fires_on_mutant=True mutant_sha_base=77b6633f41933abeb88f6c21ee2511182ee752aaca91a0018be1917107df4686 mutant_sha_perturbed=77b6633f41933abeb88f6c21ee2511182ee752aaca91a0018be1917107df4686.",
    "SUCCESS:CNL-0011-probe2 all four seeds load-bearing; decorative mutant fires"
   ]
  }
 ],
 "fixture": "command-center/p2-wave/probes/CNL-0011/fixtures/scenario.json",
 "minimal_state": {
  "integrity_only": [
   "spec_hash",
   "pool_hash"
  ],
  "must_not_rereive": [
   "time.time() / datetime.utcnow for event timestamps",
   "live participant availability or mounted-vendor roster",
   "PYTHONHASHSEED / salted hash() for ordering",
   "uuid4 or random.Random",
   "unordered dict/set iteration as tool order",
   "vote tallies and stopping-expression results (pure functions of transcript; store transcript, recompute views)"
  ],
  "must_serialize": [
   {
    "field": "seeds.{sampling,tool_order,clock,recruitment}",
    "why": "The four named nondeterminism axes. Re-deriving any of them from the live estate changes the transcript (probe2)."
   },
   {
    "field": "cursors",
    "why": "Resume must continue each SHA-256(seed:cursor) stream, not restart at 0."
   },
   {
    "field": "clock_origin_ms",
    "why": "Frozen origin drawn from the clock seed. Never time.time()."
   },
   {
    "field": "spec (temperature, tick_ms, max_rounds, n_recruit, initial_budgets)",
    "why": "Parameters the scheduler branches on. temperature>0 makes sampling load-bearing."
   },
   {
    "field": "pool snapshot + roster",
    "why": "Live recruitment would re-query availability. Roster is the frozen draw; pool is the frame it was drawn from."
   },
   {
    "field": "transcript prefix",
    "why": "Observed events (in production: vendor completion bytes) cannot be regenerated from a seed unless the vendor guarantees it."
   },
   {
    "field": "pending + flush_queue",
    "why": "In-flight tool calls and the already-permuted remaining results."
   },
   {
    "field": "turn_i, round_i, sub, want_stop",
    "why": "Scheduler phase so the next step() emits the same event."
   },
   {
    "field": "budgets remaining",
    "why": "Must not be recomputed from wall-clock (CNL-0008: exhaustion must not masquerade as a time-derived stop)."
   },
   {
    "field": "stopped, stop_reason",
    "why": "Terminal flag; stop is an event, not a re-derived predicate on resume."
   }
  ],
  "serialized_keys_live": [
   "budgets",
   "clock_origin_ms",
   "cursors",
   "flush_queue",
   "pending",
   "pool",
   "pool_hash",
   "roster",
   "round_i",
   "schema",
   "seeds",
   "spec",
   "spec_hash",
   "stop_reason",
   "stopped",
   "sub",
   "transcript",
   "turn_i",
   "want_stop"
  ]
 },
 "named_probes": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0011/probe1_replay_identical.py",
   "exit_code": 0,
   "id": "probe1",
   "raw_output": "{\"identity\": {\"events\": 20, \"line_join_sha_a\": \"1da4e098b9e6dbf17cd5e49a630c023dfa45d9d4ecf5144c1077a0000e7fc5c7\", \"line_join_sha_b\": \"1da4e098b9e6dbf17cd5e49a630c023dfa45d9d4ecf5144c1077a0000e7fc5c7\", \"match\": true, \"sha_a\": \"11913978b7db24a47f09b6802ed39f02a31115c5eaa991673bb694d9ef688442\", \"sha_b\": \"11913978b7db24a47f09b6802ed39f02a31115c5eaa991673bb694d9ef688442\"}, \"pause_11\": {\"match\": true, \"pause_after\": 11, \"resumed_events\": 20, \"resumed_sha\": \"11913978b7db24a47f09b6802ed39f02a31115c5eaa991673bb694d9ef688442\", \"serialized_keys\": [\"budgets\", \"clock_origin_ms\", \"cursors\", \"flush_queue\", \"pending\", \"pool\", \"pool_hash\", \"roster\", \"round_i\", \"schema\", \"seeds\", \"spec\", \"spec_hash\", \"stop_reason\", \"stopped\", \"sub\", \"transcript\", \"turn_i\", \"want_stop\"], \"uninterrupted_events\": 20, \"uninterrupted_sha\": \"11913978b7db24a47f09b6802ed39f02a31115c5eaa991673bb694d9ef688442\"}, \"pause_5\": {\"match\": true, \"pause_after\": 5, \"resumed_events\": 20, \"resumed_sha\": \"11913978b7db24a47f09b6802ed39f02a31115c5eaa991673bb694d9ef688442\", \"serialized_keys\": [\"budgets\", \"clock_origin_ms\", \"cursors\", \"flush_queue\", \"pending\", \"pool\", \"pool_hash\", \"roster\", \"round_i\", \"schema\", \"seeds\", \"spec\", \"spec_hash\", \"stop_reason\", \"stopped\", \"sub\", \"transcript\", \"turn_i\", \"want_stop\"], \"uninterrupted_events\": 20, \"uninterrupted_sha\": \"11913978b7db24a47f09b6802ed39f02a31115c5eaa991673bb694d9ef688442\"}}\ntwo_run_identical=True events=20 sha=11913978b7db24a47f09b6802ed39f02a31115c5eaa991673bb694d9ef688442 line_join_match=True\npause_resume_5 match=True unint=11913978b7db24a47f09b6802ed39f02a31115c5eaa991673bb694d9ef688442 resumed=11913978b7db24a47f09b6802ed39f02a31115c5eaa991673bb694d9ef688442\npause_resume_11 match=True unint=11913978b7db24a47f09b6802ed39f02a31115c5eaa991673bb694d9ef688442 resumed=11913978b7db24a47f09b6802ed39f02a31115c5eaa991673bb694d9ef688442\nSUCCESS:CNL-0011-probe1 same-seed replay and pause/resume identity"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0011/probe2_seed_perturbation.py",
   "exit_code": 0,
   "id": "probe2",
   "raw_output": "{\"mutant\": {\"check_fires_on_mutant\": true, \"check_silent_on_real\": true, \"mutant_changes\": false, \"mutant_sha_base\": \"77b6633f41933abeb88f6c21ee2511182ee752aaca91a0018be1917107df4686\", \"mutant_sha_perturbed\": \"77b6633f41933abeb88f6c21ee2511182ee752aaca91a0018be1917107df4686\", \"real_changes\": true, \"real_sha_base\": \"11913978b7db24a47f09b6802ed39f02a31115c5eaa991673bb694d9ef688442\", \"real_sha_perturbed\": \"7aeed3113fcc0f8ba651f5b264635366600909f2d9b04be54e4d459997623154\"}, \"perturbations\": [{\"axis\": \"sampling\", \"base_seed\": 101, \"changed\": true, \"first_diff_index\": 1, \"first_diff_kind_base\": \"utter\", \"first_diff_kind_perturbed\": \"utter\", \"perturbed_seed\": 102, \"sha_base\": \"11913978b7db24a47f09b6802ed39f02a31115c5eaa991673bb694d9ef688442\", \"sha_perturbed\": \"7aeed3113fcc0f8ba651f5b264635366600909f2d9b04be54e4d459997623154\"}, {\"axis\": \"tool_order\", \"base_seed\": 202, \"changed\": true, \"first_diff_index\": 7, \"first_diff_kind_base\": \"tool_result\", \"first_diff_kind_perturbed\": \"tool_result\", \"perturbed_seed\": 203, \"sha_base\": \"11913978b7db24a47f09b6802ed39f02a31115c5eaa991673bb694d9ef688442\", \"sha_perturbed\": \"b0d69a384ff95c195e949bd913a4479fcc53d65890e7a2c4f6f21327068192e5\"}, {\"axis\": \"clock\", \"base_seed\": 303, \"changed\": true, \"first_diff_index\": 0, \"first_diff_kind_base\": \"recruit\", \"first_diff_kind_perturbed\": \"recruit\", \"perturbed_seed\": 304, \"sha_base\": \"11913978b7db24a47f09b6802ed39f02a31115c5eaa991673bb694d9ef688442\", \"sha_perturbed\": \"81aa38971634d95415cae6e748ebe08ae3d5c6ab1eb98ed50953828ff26a2bb9\"}, {\"axis\": \"recruitment\", \"base_seed\": 404, \"changed\": true, \"first_diff_index\": 0, \"first_diff_kind_base\": \"recruit\", \"first_diff_kind_perturbed\": \"recruit\", \"perturbed_seed\": 405, \"sha_base\": \"11913978b7db24a47f09b6802ed39f02a31115c5eaa991673bb694d9ef688442\", \"sha_perturbed\": \"1f4b89df38632b5a02beb0f193352beb75f14a3eb6d82ef571342340586904c0\"}], \"recount\": {\"actor_sequence\": [\"runtime\", \"p.auditor\", \"p.auditor\", \"p.historian\", \"p.historian\", \"p.skeptic\", \"p.skeptic\", \"runtime\", \"runtime\", \"runtime\", \"p.auditor\", \"p.auditor\", \"p.historian\", \"p.historian\", \"p.skeptic\", \"p.skeptic\", \"runtime\", \"runtime\", \"runtime\", \"runtime\"], \"event_count\": 20, \"kinds\": {\"recruit\": 1, \"stop\": 1, \"tool_call\": 6, \"tool_result\": 6, \"utter\": 6}, \"roster\": [\"p.auditor\", \"p.historian\", \"p.skeptic\"], \"t_ms\": [7613000, 7614000, 7615000, 7616000, 7617000, 7618000, 7619000, 7620000, 7621000, 7622000, 7623000, 7624000, 7625000, 7626000, 7627000, 7628000, 7629000, 7630000, 7631000, 7632000], \"ticks_strictly_increasing\": true, \"tool_result_sequence\": [\"cite:75\", \"trace:68\", \"archive:3\", \"archive:4\", \"trace:55\", \"cite:51\"]}}\nperturb axis=sampling changed=True base=101 pert=102 sha_base=11913978b7db24a4 sha_pert=7aeed3113fcc0f8b first_diff_index=1 kind_base=utter kind_pert=utter\nperturb axis=tool_order changed=True base=202 pert=203 sha_base=11913978b7db24a4 sha_pert=b0d69a384ff95c19 first_diff_index=7 kind_base=tool_result kind_pert=tool_result\nperturb axis=clock changed=True base=303 pert=304 sha_base=11913978b7db24a4 sha_pert=81aa38971634d954 first_diff_index=0 kind_base=recruit kind_pert=recruit\nperturb axis=recruitment changed=True base=404 pert=405 sha_base=11913978b7db24a4 sha_pert=1f4b89df38632b5a first_diff_index=0 kind_base=recruit kind_pert=recruit\nNEGATIVE CONTROL (verbatim): perturb sampling seed +1 on the real engine; the check requires sha_base != sha_perturbed. Observed real_changes=True sha_base=11913978b7db24a47f09b6802ed39f02a31115c5eaa991673bb694d9ef688442 sha_perturbed=7aeed3113fcc0f8ba651f5b264635366600909f2d9b04be54e4d459997623154.\nNEGATIVE CONTROL (planted-bad mutant DecorativeSamplingCouncil): the same sampling perturbation must leave the transcript UNCHANGED, proving the check fires when a seed is serialised but unused. Observed mutant_changes=False check_fires_on_mutant=True mutant_sha_base=77b6633f41933abeb88f6c21ee2511182ee752aaca91a0018be1917107df4686 mutant_sha_perturbed=77b6633f41933abeb88f6c21ee2511182ee752aaca91a0018be1917107df4686.\nrecount events=20 kinds={'recruit': 1, 'utter': 6, 'tool_call': 6, 'tool_result': 6, 'stop': 1} roster=['p.auditor', 'p.historian', 'p.skeptic'] ticks_ok=True\nSUCCESS:CNL-0011-probe2 all four seeds load-bearing; decorative mutant fires"
  }
 ],
 "oracles_used": [
  "scripted-participant replay (probe1 two-run + pause/resume)",
  "transcript diff (probe2 first differing event per axis)",
  "counter assertion (independent_recount event_count/kinds/roster)"
 ],
 "output_schema_catalog": "command-center/schema/councilspec.v2.schema.json",
 "output_schema_note": "Catalog names councilspec.v2.schema.json (CNL-0001). That file is absent. This artifact is a design note plus a replay_state schema fragment; G-1 measures JSON parse + sentinel + probes, not Draft 2020-12 validation against the missing v2 root.",
 "question": "What is the minimal serialised state such that a paused council resumes to a byte-identical transcript, and which sources of nondeterminism (sampling temperature, tool-call ordering, wall-clock, participant recruitment) must be captured as seeds rather than re-derived?",
 "replay_state_schema": {
  "$id": "cnl-0011.replay-state.v1",
  "additionalProperties": false,
  "properties": {
   "budgets": {
    "type": "object"
   },
   "clock_origin_ms": {
    "type": [
     "integer",
     "null"
    ]
   },
   "cursors": {
    "type": "object"
   },
   "flush_queue": {
    "type": "array"
   },
   "pending": {
    "type": "array"
   },
   "pool": {
    "type": "array"
   },
   "pool_hash": {
    "maxLength": 64,
    "minLength": 64,
    "type": "string"
   },
   "roster": {
    "type": [
     "array",
     "null"
    ]
   },
   "round_i": {
    "type": "integer"
   },
   "schema": {
    "const": "cnl-0011.replay-state.v1"
   },
   "seeds": {
    "additionalProperties": false,
    "properties": {
     "clock": {
      "type": "integer"
     },
     "recruitment": {
      "type": "integer"
     },
     "sampling": {
      "type": "integer"
     },
     "tool_order": {
      "type": "integer"
     }
    },
    "required": [
     "sampling",
     "tool_order",
     "clock",
     "recruitment"
    ],
    "type": "object"
   },
   "spec": {
    "type": "object"
   },
   "spec_hash": {
    "maxLength": 64,
    "minLength": 64,
    "type": "string"
   },
   "stop_reason": {
    "type": [
     "string",
     "null"
    ]
   },
   "stopped": {
    "type": "boolean"
   },
   "sub": {
    "type": "string"
   },
   "transcript": {
    "type": "array"
   },
   "turn_i": {
    "type": "integer"
   },
   "want_stop": {
    "type": "boolean"
   }
  },
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
   "want_stop"
  ],
  "title": "CouncilSpec $defs.replay_state fragment",
  "type": "object"
 },
 "reviewer": {
  "agrees_with_engine_len": true,
  "event_count": 20,
  "kinds": {
   "recruit": 1,
   "stop": 1,
   "tool_call": 6,
   "tool_result": 6,
   "utter": 6
  },
  "method": "Re-tabulate event_count, kind histogram, roster, and tool_result_sequence from the transcript list without reading the author's prose.",
  "reviewer_id": "CNL-0011-independent-recount",
  "roster": [
   "p.auditor",
   "p.historian",
   "p.skeptic"
  ],
  "tool_result_sequence": [
   "cite:75",
   "trace:68",
   "archive:3",
   "archive:4",
   "trace:55",
   "cite:51"
  ],
  "verdict": "PASS"
 },
 "seeds_not_rereived": [
  {
   "axis": "sampling",
   "captures": "temperature sampling among scripted phrase variants and tool nonces",
   "first_diff_kind": "utter",
   "must_seed": true,
   "probe2_changed": true,
   "rereive_forbidden": "re-sample from temperature without a seed; T=0 would make this seed decorative"
  },
  {
   "axis": "tool_order",
   "captures": "permutation of concurrent tool results",
   "first_diff_kind": "tool_result",
   "must_seed": true,
   "probe2_changed": true,
   "rereive_forbidden": "order-by-completion-wall-time or dict insertion order"
  },
  {
   "axis": "clock",
   "captures": "origin_ms for logical timestamps (origin + i*tick_ms)",
   "first_diff_kind": "recruit",
   "must_seed": true,
   "probe2_changed": true,
   "rereive_forbidden": "time.time() on resume or pause"
  },
  {
   "axis": "recruitment",
   "captures": "Fisher-Yates draw of n_recruit seats from the frozen pool",
   "first_diff_kind": "recruit",
   "must_seed": true,
   "probe2_changed": true,
   "rereive_forbidden": "re-query who is reachable on this machine now"
  }
 ],
 "sentinel": "SUCCESS:CNL-0011",
 "state": "SUCCESS",
 "tests": {
  "negative_control_one_seed": {
   "pass": true,
   "required": "perturbing ONE captured seed must change the transcript",
   "result": {
    "clock": {
     "changed": true,
     "first_diff_index": 0
    },
    "recruitment": {
     "changed": true,
     "first_diff_index": 0
    },
    "sampling": {
     "changed": true,
     "first_diff_index": 1
    },
    "tool_order": {
     "changed": true,
     "first_diff_index": 7
    }
   }
  },
  "negative_control_verbatim": {
   "pass": true,
   "rejects": "a seed that is serialised but unused (decorative sampling stream)",
   "required": "negative control recorded verbatim: state what the check does on the state it is meant to reject",
   "verbatim": "NEGATIVE CONTROL (verbatim): perturb sampling seed +1 on the real engine; the check requires sha_base != sha_perturbed. Observed real_changes=True sha_base=11913978b7db24a47f09b6802ed39f02a31115c5eaa991673bb694d9ef688442 sha_perturbed=7aeed3113fcc0f8ba651f5b264635366600909f2d9b04be54e4d459997623154. On DecorativeSamplingCouncil (sampling draws ignored) the same perturbation MUST leave the transcript unchanged, which FIRES the check. Observed mutant_changes=False check_fires_on_mutant=True mutant_sha_base=77b6633f41933abeb88f6c21ee2511182ee752aaca91a0018be1917107df4686 mutant_sha_perturbed=77b6633f41933abeb88f6c21ee2511182ee752aaca91a0018be1917107df4686."
  },
  "replay_same_seed": {
   "pass": true,
   "pause_resume": {
    "match": true,
    "pause_after": 5,
    "resumed_events": 20,
    "resumed_sha": "11913978b7db24a47f09b6802ed39f02a31115c5eaa991673bb694d9ef688442",
    "serialized_keys": [
     "budgets",
     "clock_origin_ms",
     "cursors",
     "flush_queue",
     "pending",
     "pool",
     "pool_hash",
     "roster",
     "round_i",
     "schema",
     "seeds",
     "spec",
     "spec_hash",
     "stop_reason",
     "stopped",
     "sub",
     "transcript",
     "turn_i",
     "want_stop"
    ],
    "uninterrupted_events": 20,
    "uninterrupted_sha": "11913978b7db24a47f09b6802ed39f02a31115c5eaa991673bb694d9ef688442"
   },
   "required": "a replay test: same seed twice yields byte-identical transcripts",
   "result": {
    "events": 20,
    "line_join_sha_a": "1da4e098b9e6dbf17cd5e49a630c023dfa45d9d4ecf5144c1077a0000e7fc5c7",
    "line_join_sha_b": "1da4e098b9e6dbf17cd5e49a630c023dfa45d9d4ecf5144c1077a0000e7fc5c7",
    "match": true,
    "sha_a": "11913978b7db24a47f09b6802ed39f02a31115c5eaa991673bb694d9ef688442",
    "sha_b": "11913978b7db24a47f09b6802ed39f02a31115c5eaa991673bb694d9ef688442"
   }
  }
 },
 "title": "Replay state model: what must be serialised for deterministic replay",
 "unit_id": "CNL-0011"
}
