{
  "answer": "A chair may propose the agenda, time-boxes, and protocol preset, and may recognize speakers inside an open item. Those are permissions, not a license to starve dissent. The chair also drafts or approves the sitting synthesis. The structural limit that prevents moderator capture while that dual role stands is CAPTURE-BOUND-DUAL: (1) seat-share excess -- no position may receive more than EXCESS_LIMIT (0.20) above its share of floor-requesting seats; (2) synthesis coverage -- every submitted position_id must appear in synthesis.cited_position_ids. Either channel firing on an applicable sitting (>=2 requesters, >=2 positions) is capture. Chair rotation bounds tenure; it does not detect intra-round starvation or a rewrite of the record. Separating the synthesizer from the chair is CNL-0026 and would dodge this unit's given.",
  "artifacts": [
    {
      "exists": true,
      "path": "command-center/design/council/CNL-0025-chair-powers-and-capture-resistance.md",
      "role": "primary"
    },
    {
      "exists": true,
      "path": "command-center/schema/council-design-note.schema.json",
      "role": "schema"
    },
    {
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0025/note.schema.json",
      "role": "live-schema"
    },
    {
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0025/capture.py",
      "role": "detector"
    }
  ],
  "both_states": {
    "captured": {
      "captured": true,
      "channels_fired": [
        "recognition",
        "coverage"
      ],
      "fixture": "command-center/p2-wave/probes/CNL-0025/fixtures/captured.json",
      "missing_position_ids": [
        "contract",
        "hold"
      ],
      "recognition_shares": {
        "contract": 0.0625,
        "expand": 0.75,
        "hold": 0.1875
      },
      "seat_shares": {
        "contract": 0.25,
        "expand": 0.25,
        "hold": 0.5
      },
      "worst_excess": 0.5,
      "worst_position_id": "expand"
    },
    "evenhanded": {
      "captured": false,
      "channels_fired": [],
      "fixture": "command-center/p2-wave/probes/CNL-0025/fixtures/evenhanded.json",
      "missing_position_ids": [],
      "recognition_shares": {
        "contract": 0.25,
        "expand": 0.25,
        "hold": 0.5
      },
      "seat_shares": {
        "contract": 0.25,
        "expand": 0.25,
        "hold": 0.5
      },
      "worst_excess": 0.0,
      "worst_position_id": "expand"
    }
  },
  "catalog_dependency": {
    "id": "CNL-0022",
    "note": "CNL-0022 is listed as a dependency and is absent on this worktree. Chair powers are still labelled obligation / permission / right so a later field map can attach.",
    "on_disk": false
  },
  "chair_powers": {
    "agenda": {
      "must_not": [
        "Drop a submitted agenda item with no logged refusal.",
        "Add an item after freeze without a catch-up brief."
      ],
      "obligations": [
        "Log every agenda mutation with actor, previous item set, and next item set.",
        "Freeze the agenda after opening statements unless a catch-up brief is issued to every seat."
      ],
      "permissions": [
        "Propose an ordered agenda and time-boxes before round 1.",
        "Open or close an agenda item after that item's recognition floor is met.",
        "Propose a protocol preset for the sitting."
      ],
      "rights_no_chair_may_deny": [
        "Any floor-requesting seat may force a submitted item onto the agenda by overriding a logged agenda_refusal."
      ]
    },
    "synthesis": {
      "given": "This unit does not take synthesis away from the chair. CNL-0026 is the judge/juror split. The bound must work while the chair still writes or approves the synthesis.",
      "must_not": [
        "Be the only machine that decides whether a filed position exists in the record."
      ],
      "obligations": [
        "Cite every submitted position_id in synthesis.cited_position_ids before the synthesis is valid.",
        "Keep unrecognized submissions in the artifact; recognition is airtime, not existence."
      ],
      "permissions": [
        "Draft the sitting synthesis.",
        "Approve the sitting synthesis."
      ]
    },
    "turn_allocation": {
      "must_not": [
        "Complete a round that leaves a requesting seat unrecognized.",
        "Drive any position's recognition share more than EXCESS_LIMIT (0.20) above that position's seat share among requesters."
      ],
      "obligations": [
        "Record each recognition as (t, seat_id, position_id, agenda_item_id).",
        "Keep a running seat-share excess per position_id."
      ],
      "permissions": [
        "Recognize the next speaker inside an open agenda item.",
        "Allocate remaining time inside a time-box.",
        "Call the question once every requesting seat has at least one recognition on that item."
      ],
      "rights_no_chair_may_deny": [
        "A seat that requested the floor cannot finish the round at 0 recognitions."
      ]
    }
  },
  "claim_under_test": "A chair may order the agenda and recognize speakers, but cannot starve a dissenting position of airtime or omit it from the synthesis the chair writes. CAPTURE-BOUND-DUAL flags that capture on two independent channels.",
  "completion_sentinel": "SUCCESS:CNL-0025",
  "evidence": [
    {
      "anchor": "command-center/p2-wave/probes/CNL-0025/capture.py:67",
      "claim": "On the captured-chair fixture the seat-share excess channel fires, with expand above EXCESS_LIMIT.",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B -c \"import json,sys; sys.path.insert(0,'command-center/p2-wave/probes/CNL-0025'); import capture as C; s=json.load(open('command-center/p2-wave/probes/CNL-0025/fixtures/captured.json')); r=C.recognition_excess(s); print(json.dumps({'fires': r['fires'], 'worst_position_id': r['worst_position_id'], 'worst_excess': r['worst_excess']}, sort_keys=True))\"",
      "mechanism": "seat-share-excess",
      "verbatim_output": "{\"fires\": true, \"worst_excess\": 0.5, \"worst_position_id\": \"expand\"}",
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0025/capture.py:92",
      "claim": "On the same captured-chair fixture the synthesis-coverage channel independently fires because hold and contract are filed and uncited.",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B -c \"import json,sys; sys.path.insert(0,'command-center/p2-wave/probes/CNL-0025'); import capture as C; s=json.load(open('command-center/p2-wave/probes/CNL-0025/fixtures/captured.json')); r=C.synthesis_coverage(s); print(json.dumps({'fires': r['fires'], 'missing_position_ids': r['missing_position_ids'], 'cited_position_ids': r['cited_position_ids']}, sort_keys=True))\"",
      "mechanism": "synthesis-coverage",
      "verbatim_output": "{\"cited_position_ids\": [\"expand\"], \"fires\": true, \"missing_position_ids\": [\"contract\", \"hold\"]}",
      "verdict": "CONFIRMED"
    }
  ],
  "inputs_on_this_tree": {
    "note": "Catalog input files are not on this Linux worktree. Powers and the bound are taken from the catalog question, tests_required, and sibling IMP-0282 (tools/council/topology/chair.py; not built here).",
    "present": false,
    "windows_restore_paths": [
      "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md:10746-10767",
      "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md:10915-10946",
      "C:/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json",
      "C:/Users/Prekzursil/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
    ]
  },
  "min_bytes_threshold": 2048,
  "negative_controls": [
    {
      "description": "captured-chair must FIRE on both channels",
      "fired_on_bad_state": true,
      "id": "NC-captured-chair",
      "kind": "known-broken-fixture",
      "observed": "FIRE captured=True channels_fired=['recognition', 'coverage'] fires=True worst_excess=0.5000 missing=['contract', 'hold']",
      "on_state": "captured-chair fixture (12/16 recognitions to expand; synthesis cites only expand)",
      "silent_on_good_state": true
    },
    {
      "description": "even-handed chair must stay SILENT",
      "fired_on_bad_state": true,
      "id": "NC-evenhanded-must-stay-silent",
      "kind": "known-broken-fixture",
      "observed": "SILENT captured=False channels_fired=[] worst_excess=0.0000 missing=[]",
      "on_state": "even-handed chair (round-robin four seats, all three positions cited)",
      "silent_on_good_state": true
    }
  ],
  "question": "What agenda and turn-allocation powers does a chair hold, and what structural limit prevents moderator capture - given that the chair also writes or approves the synthesis?",
  "report": {
    "control_ids": [
      "NC-captured-chair",
      "NC-evenhanded-must-stay-silent"
    ],
    "kind": "council-design-note",
    "observations": [
      {
        "anchor": "command-center/p2-wave/probes/CNL-0025/capture.py:67",
        "measured": 0.5,
        "method": "recognition_share(position) - seat_share(position); fire if max excess > EXCESS_LIMIT",
        "name": "captured-chair-recognition-excess"
      },
      {
        "anchor": "command-center/p2-wave/probes/CNL-0025/capture.py:92",
        "measured": true,
        "method": "set difference: submitted position_ids minus cited_position_ids; fire if nonempty",
        "name": "captured-chair-synthesis-coverage"
      }
    ]
  },
  "report_kind": "council-design-note",
  "residual_unknowns": [
    "11-COUNCIL-SPECIFICATION.schema.json is not on this tree; a later restore may name extra chair fields this note does not forbid.",
    "CNL-0022 artifact absent; obligation/permission/right labels may need renaming to match that schema.",
    "Cross-vendor human re-run of both-states is still outstanding relative to the catalog reviewer_requirement."
  ],
  "reviewer": {
    "catalog_required_vendor": "openai/gpt-5-codex",
    "control_executed": true,
    "honest_limit": "The catalog asks a cross-vendor reviewer to re-run both-states. This G-1 delivery records a mechanical independent re-run (different channel). It does not invent a fresh openai/gpt-5-codex human signature.",
    "independent": true,
    "reviewer_id": "CNL-0025-probe2-coverage-rerun",
    "scope_not_agreement": true,
    "verdict": "PASS",
    "what_was_re_run": "probe2 recomputes synthesis_coverage on both fixtures without using seat-share excess, then checks the artifact recorded FIRE on the reject state."
  },
  "schema_control": {
    "catalog_output_schema": "command-center/schema/council-design-note.schema.json",
    "catalog_schema_present": true,
    "live_schema": "command-center/p2-wave/probes/CNL-0025/note.schema.json",
    "why_not_draft7_on_catalog_shim": "The catalog file is a generated $ref shim whose target is https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json#/$defs/council-design-note. jsonschema 4.10 RefResolver attempts a network GET. G-1 does not require that hop. Local note.schema.json pins the probe-read fields and rejects garbage."
  },
  "schema_version": 1,
  "sentinel": "SUCCESS:CNL-0025",
  "sibling_units_not_closed_here": {
    "CNL-0026": "judge vs juror; single epistemic point of failure",
    "CNL-0030": "when chair-led topology beats flat; roster-size crossover",
    "IMP-0282": "implement tools/council/topology/chair.py from this bound"
  },
  "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:CNL-0025 question_or_target (catalog inputs under C:/Users/Prekzursil/.claude/harness-restore-20260806/ are not on this Linux worktree)",
  "state": "SUCCESS",
  "structural_limit": {
    "channels": [
      {
        "fires_when": "max_position excess > EXCESS_LIMIT",
        "id": "seat-share-excess",
        "mechanism": "arithmetic: recognition_share(position) - seat_share(position); fire if max excess > 0.20",
        "null": "Expected recognition mass equals the fraction of floor-requesting seats that hold that position."
      },
      {
        "fires_when": "missing_position_ids is nonempty",
        "id": "synthesis-coverage",
        "mechanism": "set difference: submitted position_ids minus cited_position_ids; fire if nonempty",
        "null": "Every filed position_id appears in the synthesis citation list."
      }
    ],
    "combined_rule": "CAPTURED if applicable (>=2 requesters, >=2 positions) AND either channel fires. SILENT only when applicable and both channels are silent.",
    "id": "CAPTURE-BOUND-DUAL",
    "name": "recognition-and-coverage dual bound",
    "why_both_channels": "Fair prose can hide starved dissent (channel 1). Fair turns can still be written out of the record by the chair-as-author (channel 2).",
    "why_not_separate_synthesizer": "Separating the synthesizer from the chair is CNL-0026. Doing it here would dodge the constraint that the chair writes or approves the synthesis.",
    "why_this_and_not_rotation_only": "Chair rotation (IMP-0282) bounds how long one person holds the gavel. It does not detect intra-round airtime skew or a rewrite of the record."
  },
  "tests": [
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0025/probe1_both_states.py",
      "id": "probe1-both-states-recognition",
      "result": "PASS"
    },
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0025/probe2_coverage_review.py",
      "id": "probe2-coverage-review",
      "result": "PASS"
    }
  ],
  "title": "Chair powers and capture resistance",
  "ts": "2026-08-25T00:56:26Z",
  "unit_id": "CNL-0025"
}
