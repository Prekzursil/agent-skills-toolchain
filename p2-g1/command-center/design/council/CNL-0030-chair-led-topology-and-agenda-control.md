{
  "answer": "Chair-led replaces all-to-all full-text flow with a hub that spends a 1-token nomination on every other seat and then buys compact agenda slots load-bearing-first. Under declared metric load_bearing_recovery and parameters read_budget=12, flat_statement=4, nomination=1, slot=2, the crossover roster size is 5: at n=3 and n=4 both topologies recover all load-bearing claims (chair-led is only tidier in message count); at n=5 flat recovery falls to 2/3 while chair-led stays 3/3, so chair-led becomes necessary rather than merely tidier.",
  "artifacts": [
    {
      "exists": true,
      "path": "command-center/design/council/CNL-0030-chair-led-topology-and-agenda-control.md",
      "role": "primary"
    },
    {
      "exists": true,
      "path": "command-center/schema/council-design-note.schema.json",
      "role": "supporting"
    },
    {
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0030/sim.py",
      "role": "supporting"
    }
  ],
  "catalog_dependency_cnl_0025": {
    "artifact_present": false,
    "assumed": "even-handed chair; capture-resistance is CNL-0025 and is not answered here",
    "blocks_this_unit": false
  },
  "catalog_output_schema": {
    "overwritten": false,
    "path": "command-center/schema/council-design-note.schema.json",
    "reason": "The catalog path is a generated $ref shim into platform/schema/artifact-class-profiles.schema.json. Bare Draft7Validator against it raises RefResolutionError on ast-integrate.invalid. This unit validates against UNIT_SCHEMA in emit_note.py and does not rewrite the shared shim."
  },
  "completion_sentinel": "SUCCESS:CNL-0030",
  "declared_metric": {
    "chair_beats_when": "chair fraction is strictly greater than flat fraction (Fraction compare, not float)",
    "formula": "|load-bearing seats present in synthesis| / |load-bearing seats|",
    "name": "load_bearing_recovery"
  },
  "evidence": [
    {
      "anchor": "command-center/p2-wave/probes/CNL-0030/sim.py:129",
      "claim": "Author path crossover_forward walks sweep rows and returns the first n with chair_recovery > flat_recovery; measured 5.",
      "mechanism": "file:line (forward scan of simulated rows)",
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0030/sim.py:137",
      "claim": "Reviewer path crossover_by_min rebuilds recovered_flat_set and recovered_chair_set per n, then min() of winning n; measured 5. Different mechanism than the author walk.",
      "mechanism": "file:line (min of independently rebuilt recovered sets)",
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0030/fixtures/params.json",
      "claim": "Catalog inputs 11-COUNCIL-SPECIFICATION.schema.json and 12-COUNCIL-PROTOCOLS-AND-PRESETS.json were read from disk on this worktree.",
      "verdict": "REFUTED"
    }
  ],
  "information_flow": {
    "chair_led": "Star plus one synthesis broadcast: n-1 nomination flags (1 token), then compact slots scheduled load-bearing-first from flags actually read, then one synthesis artifact. Members do not read n-1 full statements.",
    "flat": "Complete graph: n*(n-1) full-statement hops. Recorder seat 0 reads other statements in unprioritized seat order until the token budget is spent. No agenda, so importance is invisible to the cursor.",
    "what_changes": "Who must read whom, and whether importance has a cheaper channel than full text. Flat: every member is a reader of every other; synthesis is the recorder's truncated inbound set. Chair-led: only the hub must cover the roster, and a 1-token flag lets remaining budget prefer load-bearing seats."
  },
  "inputs_on_this_tree": {
    "11-COUNCIL-SPECIFICATION.schema.json": false,
    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": false,
    "probe_fixtures": true
  },
  "kind": "council-design-note",
  "markdown": "# CNL-0030 Chair-led topology and agenda control\n\nWhat does a chair-led topology change about information flow versus a flat council, and at what roster size does chair-led become necessary rather than merely tidier?\n\n**Crossover roster size (declared metric `load_bearing_recovery`): 5.**\n\n## Information flow\n\nFlat council is a complete graph. Every seat publishes a full statement. A designated recorder (seat 0) reads other full statements in unprioritized seat order 1,2,3,... until a per-reader token budget is spent. There is no agenda, so a load-bearing claim at a high seat index costs the same as filler and is the first thing the cursor drops.\n\nChair-led council is a star plus one synthesis broadcast. Every other seat spends 1 token on a nomination flag (load-bearing or not). Remaining budget buys compact agenda slots, scheduled load-bearing-first among flags the chair actually read. Members do not read n-1 full statements. The hub is the only reader who must cover the roster, and agenda order is the mechanism that changes which claims survive when the budget is short.\n\n```\nflat:      member_i --full statement--> every member_j (including recorder)\n           synthesis = whatever recorder seat 0 actually read\nchair-led: member_i --1-token flag--> chair; chair --recognition--> compact slot\n           chair --one synthesis artifact--> roster\n```\n\n## Declared metric\n\n`|load-bearing seats present in synthesis| / |load-bearing seats|`. Chair-led beats flat when that fraction is strictly greater (fractions.Fraction, not float).\n\n- Tidier: recoveries equal; chair-led uses fewer messages.\n- Necessary: chair-led recovery strictly exceeds flat recovery. Flat has already dropped at least one load-bearing claim that the agenda still recovers.\n\n## Parameters (fixtures/params.json)\n\n- read_budget_tokens = 12\n- flat_statement_tokens = 4\n- nomination_tokens = 1\n- chair_slot_tokens = 2\n- sweep_n = [3, 4, 5, 6, 7, 8, 9, 10]\n- load-bearing seats = {0, n-2, n-1} (own claim plus two highest seats).\n  Placement at the far end of the unprioritized cursor is intentional: putting   load-bearing claims at seats 0,1,2 would make flat never drop them under this   budget and would game the metric.\n\n## Size sweep\n\n| n | LB seats | flat recovered LB | chair recovered LB | flat recovery | chair recovery | chair beats | flat msgs | chair msgs |\n|---|----------|-------------------|--------------------|---------------|----------------|-------------|-----------|------------|\n| 3 | [0, 1, 2] | [0, 1, 2] | [0, 1, 2] | 3/3 (1/1) | 3/3 (1/1) | False | 6 | 5 |\n| 4 | [0, 2, 3] | [0, 2, 3] | [0, 2, 3] | 3/3 (1/1) | 3/3 (1/1) | False | 12 | 7 |\n| 5 | [0, 3, 4] | [0, 3] | [0, 3, 4] | 2/3 (2/3) | 3/3 (1/1) | True | 20 | 9 |\n| 6 | [0, 4, 5] | [0] | [0, 4, 5] | 1/3 (1/3) | 3/3 (1/1) | True | 30 | 9 |\n| 7 | [0, 5, 6] | [0] | [0, 5, 6] | 1/3 (1/3) | 3/3 (1/1) | True | 42 | 10 |\n| 8 | [0, 6, 7] | [0] | [0, 6, 7] | 1/3 (1/3) | 3/3 (1/1) | True | 56 | 10 |\n| 9 | [0, 7, 8] | [0] | [0, 7, 8] | 1/3 (1/3) | 3/3 (1/1) | True | 72 | 11 |\n| 10 | [0, 8, 9] | [0] | [0, 8] | 1/3 (1/3) | 2/3 (2/3) | True | 90 | 11 |\n\nSmallest n with chair_recovery > flat_recovery is **5**.\nAt n=3 and n=4 both recover 3/3 (reduced 1/1): chair-led is only tidier (6 vs 5 messages at n=3; 12 vs 7 at n=4). At n=5 flat recovers 2/3 (misses seat 4) while chair-led recovers 3/3. That is the necessity threshold.\nAt n=10 chair-led also drops a load-bearing claim (2/3) because nominations have consumed enough budget that only one compact slot remains; it still beats flat (1/3) but is no longer lossless. Chair-led is not magic.\n\n## Negative control\n\nCheck: check_crossover_claim(claimed, mechanical) returns FIRE when claimed != mechanical and SILENT when they match.\nReject state: planted claim crossover_n=3 (tidy-only region).\nOn that state the check FIRES. On the true crossover it is SILENT.\n\n## Residual\n\nCNL-0025 (chair powers and capture resistance) is a catalog dependency and is not delivered on this tree. This note assumes an even-handed chair that schedules by nomination flags, not a captured preference. Capture is out of scope; a captured chair would change which seats the agenda prefers and could move or erase the crossover. Catalog inputs 11-COUNCIL-SPECIFICATION.schema.json and 12-COUNCIL-PROTOCOLS-AND-PRESETS.json are absent on this worktree; the crossover is derived from the fixtures in probes/CNL-0030/, not from those files.\n\nSUCCESS:CNL-0030\n",
  "min_bytes_threshold": 2048,
  "negative_controls": [
    {
      "check": "check_crossover_claim(claimed, mechanical) -> FIRE|SILENT",
      "fired_on_bad_state": true,
      "id": "CNL0030-C1",
      "known_good_claim": 5,
      "planted_bad_claim": 3,
      "silent_on_good_state": true,
      "verbatim_on_reject_state": "claimed_crossover=3 vs mechanical=5 -> FIRE",
      "what_the_check_does_on_the_state_it_is_meant_to_reject": "FIRE. Planted claim crossover_n=3 is in the tidy-only region (recoveries equal at n=3); mechanical crossover is 5."
    }
  ],
  "produced_by": {
    "execution_substrate": "local-linux",
    "role": "council-systems-designer"
  },
  "question": "What does a chair-led topology change about information flow versus a flat council, and at what roster size does chair-led become necessary rather than merely tidier?",
  "report": {
    "control_ids": [
      "CNL0030-C1"
    ],
    "kind": "council-design-note",
    "observations": [
      {
        "anchor": "command-center/p2-wave/probes/CNL-0030/sim.py:129",
        "measured": 5,
        "method": "crossover_forward walk of simulated rows",
        "name": "author_crossover_n"
      },
      {
        "anchor": "command-center/p2-wave/probes/CNL-0030/sim.py:137",
        "measured": 5,
        "method": "crossover_by_min rebuilt recovered sets then min()",
        "name": "reviewer_crossover_n"
      },
      {
        "anchor": "command-center/p2-wave/probes/CNL-0030/sim.py:44",
        "measured": "flat recovered set from unprioritized cursor; chair from command-center/p2-wave/probes/CNL-0030/sim.py:52",
        "method": "recovered_flat_set vs recovered_chair_set",
        "name": "information_flow_recovery_sets"
      }
    ]
  },
  "report_kind": "council-design-note",
  "reviewer": {
    "independent": true,
    "method": "Rebuild recovered_flat_set and recovered_chair_set per n from params, compare Fraction recoveries, collect winning n, take min(). Does not read the author's crossover_forward result.",
    "recounted_crossover_n": 5,
    "reviewer_id": "CNL-0030-independent-recount",
    "verdict": "PASS"
  },
  "schema_version": 1,
  "sentinel": "SUCCESS:CNL-0030",
  "size_sweep": {
    "crossover_n": 5,
    "necessary_means": "Smallest sweep n at which chair load_bearing_recovery is strictly greater than flat: flat has dropped a load-bearing claim the agenda still recovers.",
    "parameters": {
      "chair_slot_tokens": 2,
      "flat_statement_tokens": 4,
      "nomination_tokens": 1,
      "read_budget_tokens": 12,
      "sweep_n": [
        3,
        4,
        5,
        6,
        7,
        8,
        9,
        10
      ]
    },
    "rows": [
      {
        "chair_beats_flat": false,
        "chair_lb_recovered": [
          0,
          1,
          2
        ],
        "chair_messages": 5,
        "chair_recovered_seats": [
          0,
          1,
          2
        ],
        "chair_recovery": "1/1",
        "chair_tidier_messages": true,
        "flat_lb_recovered": [
          0,
          1,
          2
        ],
        "flat_messages": 6,
        "flat_recovered_seats": [
          0,
          1,
          2
        ],
        "flat_recovery": "1/1",
        "load_bearing_seats": [
          0,
          1,
          2
        ],
        "n": 3
      },
      {
        "chair_beats_flat": false,
        "chair_lb_recovered": [
          0,
          2,
          3
        ],
        "chair_messages": 7,
        "chair_recovered_seats": [
          0,
          1,
          2,
          3
        ],
        "chair_recovery": "1/1",
        "chair_tidier_messages": true,
        "flat_lb_recovered": [
          0,
          2,
          3
        ],
        "flat_messages": 12,
        "flat_recovered_seats": [
          0,
          1,
          2,
          3
        ],
        "flat_recovery": "1/1",
        "load_bearing_seats": [
          0,
          2,
          3
        ],
        "n": 4
      },
      {
        "chair_beats_flat": true,
        "chair_lb_recovered": [
          0,
          3,
          4
        ],
        "chair_messages": 9,
        "chair_recovered_seats": [
          0,
          1,
          2,
          3,
          4
        ],
        "chair_recovery": "1/1",
        "chair_tidier_messages": true,
        "flat_lb_recovered": [
          0,
          3
        ],
        "flat_messages": 20,
        "flat_recovered_seats": [
          0,
          1,
          2,
          3
        ],
        "flat_recovery": "2/3",
        "load_bearing_seats": [
          0,
          3,
          4
        ],
        "n": 5
      },
      {
        "chair_beats_flat": true,
        "chair_lb_recovered": [
          0,
          4,
          5
        ],
        "chair_messages": 9,
        "chair_recovered_seats": [
          0,
          1,
          4,
          5
        ],
        "chair_recovery": "1/1",
        "chair_tidier_messages": true,
        "flat_lb_recovered": [
          0
        ],
        "flat_messages": 30,
        "flat_recovered_seats": [
          0,
          1,
          2,
          3
        ],
        "flat_recovery": "1/3",
        "load_bearing_seats": [
          0,
          4,
          5
        ],
        "n": 6
      },
      {
        "chair_beats_flat": true,
        "chair_lb_recovered": [
          0,
          5,
          6
        ],
        "chair_messages": 10,
        "chair_recovered_seats": [
          0,
          1,
          5,
          6
        ],
        "chair_recovery": "1/1",
        "chair_tidier_messages": true,
        "flat_lb_recovered": [
          0
        ],
        "flat_messages": 42,
        "flat_recovered_seats": [
          0,
          1,
          2,
          3
        ],
        "flat_recovery": "1/3",
        "load_bearing_seats": [
          0,
          5,
          6
        ],
        "n": 7
      },
      {
        "chair_beats_flat": true,
        "chair_lb_recovered": [
          0,
          6,
          7
        ],
        "chair_messages": 10,
        "chair_recovered_seats": [
          0,
          6,
          7
        ],
        "chair_recovery": "1/1",
        "chair_tidier_messages": true,
        "flat_lb_recovered": [
          0
        ],
        "flat_messages": 56,
        "flat_recovered_seats": [
          0,
          1,
          2,
          3
        ],
        "flat_recovery": "1/3",
        "load_bearing_seats": [
          0,
          6,
          7
        ],
        "n": 8
      },
      {
        "chair_beats_flat": true,
        "chair_lb_recovered": [
          0,
          7,
          8
        ],
        "chair_messages": 11,
        "chair_recovered_seats": [
          0,
          7,
          8
        ],
        "chair_recovery": "1/1",
        "chair_tidier_messages": true,
        "flat_lb_recovered": [
          0
        ],
        "flat_messages": 72,
        "flat_recovered_seats": [
          0,
          1,
          2,
          3
        ],
        "flat_recovery": "1/3",
        "load_bearing_seats": [
          0,
          7,
          8
        ],
        "n": 9
      },
      {
        "chair_beats_flat": true,
        "chair_lb_recovered": [
          0,
          8
        ],
        "chair_messages": 11,
        "chair_recovered_seats": [
          0,
          8
        ],
        "chair_recovery": "2/3",
        "chair_tidier_messages": true,
        "flat_lb_recovered": [
          0
        ],
        "flat_messages": 90,
        "flat_recovered_seats": [
          0,
          1,
          2,
          3
        ],
        "flat_recovery": "1/3",
        "load_bearing_seats": [
          0,
          8,
          9
        ],
        "n": 10
      }
    ],
    "tidier_means": "Recoveries equal and chair_messages < flat_messages. Observed at n=3 and n=4."
  },
  "state": "SUCCESS",
  "tests": [
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0030/probe1_size_sweep.py",
      "id": "T1-size-sweep-crossover",
      "result": "PASS"
    },
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0030/probe2_negative_control.py",
      "id": "T2-negative-control-false-crossover",
      "result": "PASS"
    }
  ],
  "timestamps": {
    "emitted_at": "2026-08-25T00:55:49Z"
  },
  "title": "Chair-led topology and agenda control",
  "unit_id": "CNL-0030"
}
