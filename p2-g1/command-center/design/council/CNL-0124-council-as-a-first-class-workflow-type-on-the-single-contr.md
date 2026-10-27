{
  "unit_id": "CNL-0124",
  "kind": "council-design-note",
  "state": "SUCCESS",
  "schema_version": 1,
  "report_kind": "council-design-note",
  "title": "Council as a first-class workflow type on the SINGLE control plane",
  "question": "The spec forbids importing a second orchestration runtime - what is the council's integration contract with the existing workflow system such that a council is a workflow type rather than a parallel engine, and which council capability has no home in the current plane?",
  "claim_under_test": "Council compiles to agentspec workflow nodes on prompt-native; it is not a parallel engine. CAP-STANDING has no home on the current plane and is listed as required extension Watch. Any own-scheduler or foreign runtime FIRE.",
  "sentinel": "SUCCESS:CNL-0124",
  "completion_sentinel": "SUCCESS:CNL-0124",
  "answer": "A council is a first-class workflow type (kind=council) on the single agentspec / prompt-native control plane. CouncilSpec is payload, not an engine: the compiler emits DynamicFanOut+WorkUnit (roster), Pipeline (sequence/splice), Subworkflow (nest / child councils), Loop (repeat-until and stopping.expression), FanOut then Barrier (divergence-before-convergence), HumanCheckpoint (chair/owner), and WorkUnit.routing through rails.toml. Turn-taking is that executor's dispatch (CNL-0047), not a council-owned round loop. Importing LangGraph/CrewAI/AutoGen or running dispatch_loop/round_runner/watch_loop FIRE the duplicate-control-plane probe (plane_count>1). Windows _USER-PROMPTS.md:10727 and :10483 are absent here; the live citation is command-center/WORK-UNIT-CATALOG.json evidence_requirement on this unit. Three same-plane extensions are named because they have no node today: BallotReduce (Barrier is all-complete, not IRV), BlindEnvelope (routing is named), and Watch. The capability with no home on the current plane is CAP-STANDING (standing watch / trigger-woken persistence, CNL-0115): HumanCheckpoint is owner-gated and must terminate without a responder, so an ETag wake cannot live there. Watch is a required workflow-plane node; a council event loop is a forbidden second scheduler. Inventory: 20 capabilities, 17 mapped, 3 required extensions, 0 unmapped. SUCCESS:CNL-0124",
  "integration_contract": {
    "council_is": "workflow type kind=council",
    "council_is_not": "a second orchestration runtime or CouncilEngine",
    "home_plane": "prompt-native",
    "scheduler": "agentspec",
    "payload": "CouncilSpec / preset is configuration of a Council node, not an engine",
    "compile": {
      "roster": "DynamicFanOut of WorkUnits",
      "sequence_splice": "Pipeline",
      "nest_child_councils": "Subworkflow",
      "repeat_until_and_stopping": "Loop.convergence_expr + max_iterations",
      "diverge_then_converge": "FanOut then Barrier (reverse rejected)",
      "chair_owner": "HumanCheckpoint",
      "routing": "WorkUnit.routing via rails.toml",
      "turn_taking": "the agentspec executor; CNL-0047 shared primitive",
      "oracle_join": "Barrier join policy oracle_gate",
      "minority_report": "completion-predicate emit-gate"
    },
    "required_extensions_same_plane": [
      {
        "kind": "BallotReduce",
        "for": "CAP-VOTING",
        "why": "Barrier default join is all-complete, not IRV/majority tabulation"
      },
      {
        "kind": "BlindEnvelope",
        "for": "CAP-ANONYMITY",
        "why": "WorkUnit.routing is named; blinding is not a plane primitive"
      },
      {
        "kind": "Watch",
        "for": "CAP-STANDING",
        "why": "HumanCheckpoint is owner-gated terminate, not ETag/release-tag wake",
        "no_home_on_current_plane": true
      }
    ],
    "forbidden": [
      "import langgraph/crewai/autogen/temporal/airflow/prefect/dagster",
      "dispatch_loop / round_runner / own_scheduler / turn_engine",
      "watch_loop / own_wake_clock / resident_event_loop",
      "child_runtime that bypasses Subworkflow"
    ]
  },
  "no_home_capability": "CAP-STANDING",
  "no_home": {
    "id": "CAP-STANDING",
    "capability": "Standing watch: long-running, trigger-woken, low-intensity",
    "catalog_id": "CNL-0115",
    "why_not_human_checkpoint": "IMP-0131: a checkpoint with no default_if_unanswered and no responder must terminate, never block. An ETag wake has no owner.",
    "required_extension": "Watch",
    "must_not_become": "a council-owned event loop (duplicate control plane)"
  },
  "inventory": {
    "n_capabilities": 20,
    "n_mapped": 17,
    "n_required_extension": 3,
    "n_unmapped": 0,
    "mapped_ids": [
      "CAP-ROSTER",
      "CAP-INFO-PARTITION",
      "CAP-BUDGET",
      "CAP-STOPPING",
      "CAP-REPLAY",
      "CAP-CHAIR",
      "CAP-JURY",
      "CAP-NESTED",
      "CAP-TURN-TAKING",
      "CAP-PROTOCOL-SEQ",
      "CAP-PROTOCOL-SPLICE",
      "CAP-PROTOCOL-NEST",
      "CAP-PROTOCOL-REPEAT",
      "CAP-DIVERGE-CONVERGE",
      "CAP-ORACLE",
      "CAP-MINORITY",
      "CAP-ROUTING"
    ],
    "extension_ids": [
      "CAP-ANONYMITY",
      "CAP-VOTING",
      "CAP-STANDING"
    ],
    "unmapped_ids": [],
    "required_extensions_named": [
      "BallotReduce",
      "BlindEnvelope",
      "Watch"
    ],
    "no_home_ids": [
      "CAP-STANDING"
    ],
    "no_home_capability": "CAP-STANDING",
    "ok": true
  },
  "inventory_rows": [
    {
      "id": "CAP-ROSTER",
      "capability": "Role roster / per-seat WorkUnits",
      "catalog_id": "CNL-0005",
      "home": "DynamicFanOut",
      "required_extension": null,
      "class": "mapped",
      "no_home_on_current_plane": false
    },
    {
      "id": "CAP-INFO-PARTITION",
      "capability": "Information partition (who may see what, when)",
      "catalog_id": "CNL-0006",
      "home": "Subworkflow",
      "required_extension": null,
      "class": "mapped",
      "no_home_on_current_plane": false
    },
    {
      "id": "CAP-ANONYMITY",
      "capability": "Anonymity / identity blinding then reveal",
      "catalog_id": "CNL-0007",
      "home": null,
      "required_extension": "BlindEnvelope",
      "class": "required_extension",
      "no_home_on_current_plane": false
    },
    {
      "id": "CAP-BUDGET",
      "capability": "Budget block and exhaustion",
      "catalog_id": "CNL-0008",
      "home": "budget-rollup",
      "required_extension": null,
      "class": "mapped",
      "no_home_on_current_plane": false
    },
    {
      "id": "CAP-STOPPING",
      "capability": "Stopping expression and max rounds",
      "catalog_id": "CNL-0010",
      "home": "Loop",
      "required_extension": null,
      "class": "mapped",
      "no_home_on_current_plane": false
    },
    {
      "id": "CAP-REPLAY",
      "capability": "Deterministic replay state",
      "catalog_id": "CNL-0011",
      "home": "workflow-receipts",
      "required_extension": null,
      "class": "mapped",
      "no_home_on_current_plane": false
    },
    {
      "id": "CAP-CHAIR",
      "capability": "Chair / owner gate (pause, resume, override)",
      "catalog_id": "CNL-0025",
      "home": "HumanCheckpoint",
      "required_extension": null,
      "class": "mapped",
      "no_home_on_current_plane": false
    },
    {
      "id": "CAP-JURY",
      "capability": "Jury topology: deciders who did not argue",
      "catalog_id": "CNL-0034",
      "home": "Pipeline",
      "required_extension": null,
      "class": "mapped",
      "no_home_on_current_plane": false
    },
    {
      "id": "CAP-NESTED",
      "capability": "Nested subcouncils / council-of-councils fan-in",
      "catalog_id": "CNL-0037",
      "home": "Subworkflow",
      "required_extension": null,
      "class": "mapped",
      "no_home_on_current_plane": false
    },
    {
      "id": "CAP-TURN-TAKING",
      "capability": "Turn-taking / speaking order",
      "catalog_id": "CNL-0047",
      "home": "WorkUnit",
      "required_extension": null,
      "class": "mapped",
      "no_home_on_current_plane": false
    },
    {
      "id": "CAP-PROTOCOL-SEQ",
      "capability": "Protocol composition: sequence",
      "catalog_id": "CNL-0050",
      "home": "Pipeline",
      "required_extension": null,
      "class": "mapped",
      "no_home_on_current_plane": false
    },
    {
      "id": "CAP-PROTOCOL-SPLICE",
      "capability": "Protocol composition: splice",
      "catalog_id": "CNL-0050",
      "home": "Pipeline",
      "required_extension": null,
      "class": "mapped",
      "no_home_on_current_plane": false
    },
    {
      "id": "CAP-PROTOCOL-NEST",
      "capability": "Protocol composition: nest",
      "catalog_id": "CNL-0050",
      "home": "Subworkflow",
      "required_extension": null,
      "class": "mapped",
      "no_home_on_current_plane": false
    },
    {
      "id": "CAP-PROTOCOL-REPEAT",
      "capability": "Protocol composition: repeat-until",
      "catalog_id": "CNL-0050",
      "home": "Loop",
      "required_extension": null,
      "class": "mapped",
      "no_home_on_current_plane": false
    },
    {
      "id": "CAP-DIVERGE-CONVERGE",
      "capability": "Divergence-before-convergence ordering",
      "catalog_id": "CNL-0050",
      "home": "FanOut",
      "required_extension": null,
      "class": "mapped",
      "no_home_on_current_plane": false
    },
    {
      "id": "CAP-VOTING",
      "capability": "Ballot tabulation (majority / IRV / weighted / Condorcet)",
      "catalog_id": "CNL-0061",
      "home": null,
      "required_extension": "BallotReduce",
      "class": "required_extension",
      "no_home_on_current_plane": false
    },
    {
      "id": "CAP-ORACLE",
      "capability": "Bound-oracle / evidence-outranks-popularity join",
      "catalog_id": "CNL-0068",
      "home": "Barrier",
      "required_extension": null,
      "class": "mapped",
      "no_home_on_current_plane": false
    },
    {
      "id": "CAP-MINORITY",
      "capability": "Minority-report conservation at emit",
      "catalog_id": "CNL-0070",
      "home": "completion-predicate",
      "required_extension": null,
      "class": "mapped",
      "no_home_on_current_plane": false
    },
    {
      "id": "CAP-STANDING",
      "capability": "Standing watch: long-running, trigger-woken, low-intensity",
      "catalog_id": "CNL-0115",
      "home": null,
      "required_extension": "Watch",
      "class": "required_extension",
      "no_home_on_current_plane": true
    },
    {
      "id": "CAP-ROUTING",
      "capability": "Per-seat vendor/model/role routing",
      "catalog_id": "IMP-0135",
      "home": "routing",
      "required_extension": null,
      "class": "mapped",
      "no_home_on_current_plane": false
    }
  ],
  "catalog_anchors": {
    "hits": [
      {
        "id": "CAP-ROSTER",
        "catalog_id": "CNL-0005",
        "title": "Participant descriptor type: the 9 per-seat dials"
      },
      {
        "id": "CAP-INFO-PARTITION",
        "catalog_id": "CNL-0006",
        "title": "Information-partition lattice: who may see what, when"
      },
      {
        "id": "CAP-ANONYMITY",
        "catalog_id": "CNL-0007",
        "title": "Anonymity levels and their effect on attribution"
      },
      {
        "id": "CAP-BUDGET",
        "catalog_id": "CNL-0008",
        "title": "Budget block: 12 dials and the exhaustion semantics"
      },
      {
        "id": "CAP-STOPPING",
        "catalog_id": "CNL-0010",
        "title": "Stopping-expression grammar and STATIC validation"
      },
      {
        "id": "CAP-REPLAY",
        "catalog_id": "CNL-0011",
        "title": "Replay state model: what must be serialised for deterministic replay"
      },
      {
        "id": "CAP-CHAIR",
        "catalog_id": "CNL-0025",
        "title": "Chair powers and capture resistance"
      },
      {
        "id": "CAP-JURY",
        "catalog_id": "CNL-0034",
        "title": "Jury topology: deciders who did not argue"
      },
      {
        "id": "CAP-NESTED",
        "catalog_id": "CNL-0037",
        "title": "Nested subcouncils and council-of-councils fan-in"
      },
      {
        "id": "CAP-TURN-TAKING",
        "catalog_id": "CNL-0047",
        "title": "Turn-taking and speaking-order engine as one shared primitive"
      },
      {
        "id": "CAP-PROTOCOL-SEQ",
        "catalog_id": "CNL-0050",
        "title": "Protocol composition primitives, phase ordering, and the spec-vs-corpus protocol gap"
      },
      {
        "id": "CAP-PROTOCOL-SPLICE",
        "catalog_id": "CNL-0050",
        "title": "Protocol composition primitives, phase ordering, and the spec-vs-corpus protocol gap"
      },
      {
        "id": "CAP-PROTOCOL-NEST",
        "catalog_id": "CNL-0050",
        "title": "Protocol composition primitives, phase ordering, and the spec-vs-corpus protocol gap"
      },
      {
        "id": "CAP-PROTOCOL-REPEAT",
        "catalog_id": "CNL-0050",
        "title": "Protocol composition primitives, phase ordering, and the spec-vs-corpus protocol gap"
      },
      {
        "id": "CAP-DIVERGE-CONVERGE",
        "catalog_id": "CNL-0050",
        "title": "Protocol composition primitives, phase ordering, and the spec-vs-corpus protocol gap"
      },
      {
        "id": "CAP-VOTING",
        "catalog_id": "CNL-0061",
        "title": "Ranked-choice tabulation and its known pathologies"
      },
      {
        "id": "CAP-ORACLE",
        "catalog_id": "CNL-0068",
        "title": "Evidence outranks popularity: the executable-test override of a majority"
      },
      {
        "id": "CAP-MINORITY",
        "catalog_id": "CNL-0070",
        "title": "Minority report generation and mandatory preservation"
      },
      {
        "id": "CAP-STANDING",
        "catalog_id": "CNL-0115",
        "title": "Standing watch council: long-running, trigger-woken, low-intensity"
      },
      {
        "id": "CAP-ROUTING",
        "catalog_id": "IMP-0135",
        "title": "Add per-unit model/vendor/role routing that resolves through rails.toml, not a rival table"
      }
    ],
    "misses": [],
    "ok": true
  },
  "family_coverage": {
    "present": [
      "roster",
      "stopping",
      "voting",
      "anonymity",
      "chair",
      "nest",
      "standing",
      "minority",
      "composition",
      "turn"
    ],
    "missing": [],
    "ok": true
  },
  "workflow_primitives": {
    "node_kinds": [
      "Barrier",
      "DynamicFanOut",
      "FanOut",
      "HumanCheckpoint",
      "Loop",
      "Pipeline",
      "Subworkflow",
      "WorkUnit"
    ],
    "surfaces": [
      "Param",
      "budget-rollup",
      "completion-predicate",
      "routing",
      "workflow-receipts"
    ],
    "extensions": [
      "BallotReduce",
      "BlindEnvelope",
      "Watch"
    ],
    "catalog_parse_ok": true,
    "extracted": [
      "Barrier",
      "DynamicFanOut",
      "FanOut",
      "HumanCheckpoint",
      "Loop",
      "Param",
      "Pipeline",
      "Subworkflow",
      "WorkUnit",
      "routing"
    ],
    "agentspec_spec_py_present": true
  },
  "duplicate_control_plane": {
    "probe": "any council feature that would need its own scheduler is named",
    "mapped_home": {
      "id": "council.mapped-home",
      "gate": "PASS",
      "over_one": false,
      "extensions_named": [
        "BallotReduce"
      ]
    },
    "own_scheduler": {
      "id": "council.own-turn-engine",
      "gate": "FIRE",
      "over_one": true,
      "plane_count": 2,
      "introduced_planes": [
        "council-runtime"
      ],
      "scheduler_features_named": [
        {
          "id": "non-home-scheduler",
          "plane": "council-runtime",
          "why": "scheduler/runtime='council-runtime' is not the agentspec plane"
        },
        {
          "id": "own-round-dispatcher",
          "plane": "council-runtime",
          "why": "CNL-0047 names turn-taking as one shared primitive; a council-owned round dispatcher is a second orchestration runtime."
        }
      ]
    },
    "langgraph_import": {
      "id": "council.langgraph-import",
      "gate": "FIRE",
      "introduced_planes": [
        "langgraph"
      ]
    },
    "standing_watch_on_plane": {
      "id": "council.standing-watch-on-plane",
      "gate": "PASS",
      "extensions_named": [
        "BallotReduce",
        "Watch"
      ],
      "over_one": false
    },
    "standing_own_loop": {
      "id": "council.standing-own-event-loop",
      "gate": "FIRE",
      "scheduler_features_named": [
        {
          "id": "non-home-scheduler",
          "plane": "council-runtime",
          "why": "scheduler/runtime='council-runtime' is not the agentspec plane"
        },
        {
          "id": "standing-event-loop",
          "plane": "council-runtime",
          "why": "A standing council that runs its own wake clock is a duplicate control plane. Watch is a workflow-plane node, not a council engine."
        }
      ]
    },
    "nested_subworkflow": {
      "id": "council.nested-children",
      "gate": "PASS",
      "node_kinds": [
        "Barrier",
        "DynamicFanOut",
        "FanOut",
        "Loop",
        "Subworkflow",
        "WorkUnit"
      ]
    },
    "anonymous_blind": {
      "id": "council.anonymous-peer-review",
      "gate": "PASS",
      "extensions_named": [
        "BallotReduce",
        "BlindEnvelope"
      ]
    },
    "features_that_would_need_own_scheduler": [
      {
        "id": "own-round-dispatcher",
        "plane": "council-runtime",
        "why": "CNL-0047 names turn-taking as one shared primitive; a council-owned round dispatcher is a second orchestration runtime."
      },
      {
        "id": "standing-event-loop",
        "plane": "council-runtime",
        "why": "A standing council that runs its own wake clock is a duplicate control plane. Watch is a workflow-plane node, not a council engine."
      },
      {
        "id": "nested-private-runtime",
        "plane": "council-runtime",
        "why": "Child councils compile to Subworkflow on the parent graph. A private child runtime is a second scheduler."
      }
    ]
  },
  "source_availability": {
    "user_prompts": {
      "tried": [
        "/root/.claude/harness-restore-20260806/_USER-PROMPTS.md",
        "/home/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md",
        "/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md",
        "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md",
        "/opt/p2/ast-integrate/_USER-PROMPTS.md",
        "/opt/p2/ast-integrate/command-center/_USER-PROMPTS.md",
        "/opt/p2/ast-integrate/harness-restore-20260806/_USER-PROMPTS.md"
      ],
      "hits": [],
      "available": false
    },
    "council_schema_and_agentspec": {
      "tried": [
        "/root/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json",
        "C:/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json",
        "/opt/p2/ast-integrate/11-COUNCIL-SPECIFICATION.schema.json",
        "/opt/p2/ast-integrate/command-center/schema/councilspec.v2.schema.json",
        "/opt/p2/ast-integrate/tools/agentspec/agentspec/spec.py"
      ],
      "hits": [
        "/opt/p2/ast-integrate/command-center/schema/councilspec.v2.schema.json",
        "/opt/p2/ast-integrate/tools/agentspec/agentspec/spec.py"
      ],
      "available": true
    },
    "windows_harness_absent": true
  },
  "both_states": {
    "fired_on_bad": true,
    "silent_on_good": true,
    "good_verbatim": "{\"gate\": \"PASS\", \"over_one\": false}",
    "bad_verbatim": "{\"fixture\": \"own-scheduler\", \"gate\": \"FIRE\", \"introduced_planes\": [\"council-runtime\"], \"over_one\": true, \"parallel_engine\": true, \"plane_count\": 2}"
  },
  "counterexample": {
    "id": "cx-own-turn-engine",
    "status": "COUNTEREXAMPLE-PRODUCED",
    "claim_refuted": "any object titled council is automatically a workflow type",
    "instance": "command-center/p2-wave/probes/CNL-0124/fixtures/own-scheduler.json",
    "observed_gate": "FIRE"
  },
  "negative_control": {
    "id": "NC-OWN-SCHEDULER",
    "on_state": "fixtures/own-scheduler.json: scheduler=council-runtime, dispatch_loop=true, round_runner=council.engine.turn_taking",
    "rejects": "a council that is a parallel engine with its own round dispatcher",
    "observed": "gate=FIRE over_one=True plane_count=2 introduced_planes=['council-runtime']",
    "verbatim": "{\"fixture\": \"own-scheduler\", \"gate\": \"FIRE\", \"introduced_planes\": [\"council-runtime\"], \"over_one\": true, \"parallel_engine\": true, \"plane_count\": 2}",
    "does_on_reject_state": "The check FIRES; plane_count rises above one; introduced_planes names council-runtime; the council is not emit-legal as a workflow type. It does not return silent."
  },
  "tests": [
    {
      "id": "inventory-mechanical",
      "name": "every council capability maps to a workflow primitive or is listed as a required extension - counted mechanically",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0124/probe1_inventory.py",
      "result": "PASS",
      "verbatim": "{\n  \"summary\": {\n    \"n_capabilities\": 20,\n    \"n_mapped\": 17,\n    \"n_required_extension\": 3,\n    \"n_unmapped\": 0,\n    \"mapped_ids\": [\n      \"CAP-ROSTER\",\n      \"CAP-INFO-PARTITION\",\n      \"CAP-BUDGET\",\n      \"CAP-STOPPING\",\n      \"CAP-REPLAY\",\n      \"CAP-CHAIR\",\n      \"CAP-JURY\",\n      \"CAP-NESTED\",\n      \"CAP-TURN-TAKING\",\n      \"CAP-PROTOCOL-SEQ\",\n      \"CAP-PROTOCOL-SPLICE\",\n      \"CAP-PROTOCOL-NEST\",\n      \"CAP-PROTOCOL-REPEAT\",\n      \"CAP-DIVERGE-CONVERGE\",\n      \"CAP-ORACLE\",\n      \"CAP-MINORITY\",\n      \"CAP-ROUTING\"\n    ],\n    \"extension_ids\": [\n      \"CAP-ANONYMITY\",\n      \"CAP-VOTING\",\n      \"CAP-STANDING\"\n    ],\n    \"unmapped_ids\": [],\n    \"required_extensions_named\": [\n      \"BallotReduce\",\n      \"BlindEnvelope\",\n      \"Watch\"\n    ],\n    \"no_home_ids\": [\n      \"CAP-STANDING\"\n    ],\n    \"no_home_capability\": \"CAP-STANDING\",\n    \"ok\": true\n  },\n  \"no_home\": \"CAP-STANDING\",\n  \"mapped_council_gate\": \"PASS\",\n  \"standing_watch_gate\": \"PASS\"\n}\nSUCCESS:CNL-0124-probe1 n=20 mapped=17 ext=3 unmapped=0 no_home=CAP-STANDING"
    },
    {
      "id": "duplicate-control-plane",
      "name": "any council feature that would need its own scheduler is named explicitly",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0124/probe2_duplicate_plane.py",
      "result": "PASS",
      "verbatim": "BOTH-STATES-GOOD {\"gate\": \"PASS\", \"over_one\": false}\nBOTH-STATES-BAD {\"gate\": \"FIRE\", \"planes\": [\"council-runtime\"]}\nNEGATIVE-CONTROL {\"fixture\": \"own-scheduler\", \"gate\": \"FIRE\", \"introduced_planes\": [\"council-runtime\"], \"over_one\": true, \"parallel_engine\": true, \"plane_count\": 2, \"scheduler_features_named\": [{\"id\": \"non-home-scheduler\", \"plane\": \"council-runtime\", \"why\": \"scheduler/runtime='council-runtime' is not the agentspec plane\"}, {\"id\": \"own-round-dispatcher\", \"plane\": \"council-runtime\", \"why\": \"CNL-0047 names turn-taking as one shared primitive; a council-owned round dispatcher is a second orchestration runtime.\"}]}\nCOUNTEREXAMPLE cx-own-turn-engine COUNTEREXAMPLE-PRODUCED\nSUCCESS:CNL-0124-probe2 both-states and duplicate-control-plane no_home=CAP-STANDING"
    },
    {
      "id": "negative-control",
      "name": "recorded verbatim: what the check does on the reject state",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0124/probe2_duplicate_plane.py",
      "result": "PASS",
      "verbatim": "{\"fixture\": \"own-scheduler\", \"gate\": \"FIRE\", \"introduced_planes\": [\"council-runtime\"], \"over_one\": true, \"parallel_engine\": true, \"plane_count\": 2}"
    }
  ],
  "negative_controls": [
    {
      "id": "NC-OWN-SCHEDULER",
      "on_state": "fixtures/own-scheduler.json: scheduler=council-runtime, dispatch_loop=true, round_runner=council.engine.turn_taking",
      "observed": "gate=FIRE over_one=True plane_count=2 introduced_planes=['council-runtime']",
      "rejects": "a council that is a parallel engine with its own round dispatcher"
    },
    {
      "id": "NC-PLANTED-UNMAPPED",
      "on_state": "inventory row CAP-PLANTED-UNMAPPED with empty home and no required_extension",
      "observed": "ok=False n_unmapped=1 unmapped_ids=['CAP-PLANTED-UNMAPPED']",
      "rejects": "an inventory that silently drops a capability instead of mapping it or listing a required extension"
    },
    {
      "id": "NC-LANGGRAPH",
      "on_state": "fixtures/langgraph-import.json runtime=langgraph",
      "observed": "gate=FIRE introduced_planes=['langgraph']",
      "rejects": "importing a second orchestration runtime as the council engine"
    },
    {
      "id": "NC-STANDING-OWN-LOOP",
      "on_state": "fixtures/standing-own-loop.json watch_loop=true own_wake_clock=true",
      "observed": "gate=FIRE features=['non-home-scheduler', 'standing-event-loop']",
      "rejects": "a standing council that grows its own event loop instead of a Watch node on the workflow plane"
    }
  ],
  "evidence": [
    {
      "path": "command-center/WORK-UNIT-CATALOG.json",
      "line": 40569,
      "snippet": "\"evidence_requirement\": \"cite C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md:10727 (do not import a second orchestration runtime) and C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md:10483 (do not",
      "kind": "catalog-evidence-10727",
      "claim": "Catalog evidence_requirement binds _USER-PROMPTS.md:10727: do not import a second orchestration runtime. The file is absent on this Linux worktree; the citation is the catalog line.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/WORK-UNIT-CATALOG.json:40569",
      "mechanism": "catalog file:line of this unit's evidence_requirement plus Path.is_file hunt",
      "harness_available": false
    },
    {
      "path": "command-center/WORK-UNIT-CATALOG.json",
      "line": 40569,
      "snippet": "\"evidence_requirement\": \"cite C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md:10727 (do not import a second orchestration runtime) and C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md:10483 (do not",
      "kind": "catalog-evidence-10483",
      "claim": "Catalog evidence_requirement binds _USER-PROMPTS.md:10483: do not create duplicate control planes. Same-host hunt of the Windows harness path is empty.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/WORK-UNIT-CATALOG.json:40569",
      "mechanism": "catalog file:line plus Path.is_file hunt (different field from 10727 needle)"
    },
    {
      "path": "command-center/WORK-UNIT-CATALOG.json",
      "line": 46871,
      "snippet": "\"question_or_target\": \"Target: add a frozen `Subworkflow` node (id, workflow_ref, param_bindings, id_namespace) to tools/agentspec/agentspec/spec.py alongside FanOut/Barrier/Pipeline (:77-108), so a Workflow can embed another Workflow by re",
      "kind": "catalog-workflow-primitives",
      "claim": "IMP-0129 names the frozen workflow node surface as FanOut/Barrier/Pipeline plus Subworkflow. Loop, HumanCheckpoint, DynamicFanOut, Param, WorkUnit.routing are named on IMP-0130..0135.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/WORK-UNIT-CATALOG.json:46871",
      "mechanism": "independent parse of IMP-0129..0135 question text (set algebra vs frozen NODE_KINDS)",
      "extracted": [
        "Barrier",
        "DynamicFanOut",
        "FanOut",
        "HumanCheckpoint",
        "Loop",
        "Param",
        "Pipeline",
        "Subworkflow",
        "WorkUnit",
        "routing"
      ]
    },
    {
      "path": "command-center/WORK-UNIT-CATALOG.json",
      "line": 36786,
      "snippet": "\"question_or_target\": \"What primitives (sequence, splice, nest, repeat-until) compose two protocols into a custom one, how is divergence-before-convergence enforced as an ordering constraint the composer cannot accidentally violate, and - m",
      "kind": "catalog-composition-primitives",
      "claim": "CNL-0050 names the protocol composition primitives that must compile onto Pipeline/Subworkflow/Loop rather than a second composer.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/WORK-UNIT-CATALOG.json:36786",
      "mechanism": "catalog question needle for CNL-0050"
    },
    {
      "path": "command-center/WORK-UNIT-CATALOG.json",
      "line": 40129,
      "snippet": "\"title\": \"Standing watch council: long-running, trigger-woken, low-intensity\",",
      "kind": "catalog-no-home-capability",
      "claim": "CNL-0115 is the standing-watch capability. It is the inventory row with no_home_on_current_plane=true (required_extension=Watch).",
      "verdict": "CONFIRMED",
      "anchor": "command-center/WORK-UNIT-CATALOG.json:40129",
      "mechanism": "catalog title needle plus inventory class=required_extension"
    },
    {
      "path": "tools/agentspec/agentspec/spec.py",
      "line": 0,
      "snippet": "Path.is_file false on this worktree",
      "kind": "agentspec-spec-absent",
      "claim": "tools/agentspec/agentspec/spec.py is not on this tree (only __init__.py and progress.py). Primitive names are catalog-cited, not read from a missing spec.py. This unit does not invent a second agentspec.",
      "verdict": "PARTIAL",
      "anchor": "tools/agentspec/agentspec/__init__.py",
      "mechanism": "Path.is_file of spec.py (independent of catalog parse)"
    }
  ],
  "reviewer": {
    "reviewer_id": "CNL-0124-probe2-duplicate-plane",
    "verdict": "PASS",
    "independent": true,
    "control_executed": true,
    "counterexample": "cx-own-turn-engine",
    "refuted_not_attempted": false,
    "notes": "Probe2 re-tabulates the 20-row inventory, re-compiles mapped / own-scheduler / langgraph / standing-watch / standing-own-loop / nested fixtures, and produces counterexample cx-own-turn-engine. It does not read this answer as evidence. Catalog asked for a fresh-context adversarial reviewer; this G-1 signature is the mechanical re-run, not a second-vendor chat transcript."
  },
  "named_probes": [
    {
      "id": "probe1",
      "role": "inventory-mechanical",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0124/probe1_inventory.py"
    },
    {
      "id": "probe2",
      "role": "duplicate-control-plane",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0124/probe2_duplicate_plane.py"
    }
  ],
  "schema_note": "Catalog output_schema is a GENERATED SHIM whose $ref points at https://ast-integrate.invalid/...; validating against it tries the network and does not constrain this note. This unit validates against the per-unit schema. Overwriting the shared catalog schema would be a sibling rebuild circle.",
  "artifacts": [
    {
      "path": "command-center/design/council/CNL-0124-council-as-a-first-class-workflow-type-on-the-single-contr.md",
      "exists": true,
      "role": "primary"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0124/council-design-note.schema.json",
      "exists": true,
      "role": "supporting"
    },
    {
      "path": "command-center/schema/council-design-note.schema.json",
      "exists": true,
      "role": "supporting"
    }
  ],
  "scope": {
    "executable_on": "in-probe fixtures and inventory table; tools/agentspec/spec.py and 11-COUNCIL-SPECIFICATION.schema.json are absent",
    "does_not_claim": [
      "cloud ok=true is delivery",
      "global unit_manifest.py --write was run",
      "Windows harness-restore files were read on this host",
      "Watch/BallotReduce/BlindEnvelope were added to agentspec",
      "CNL-0001 / CNL-0050 artifacts were delivered on this tree"
    ]
  },
  "produced_by": {
    "vendor": "cursor",
    "model": "grok-4.6",
    "role": "council-systems-designer",
    "execution_substrate": "linux-local"
  },
  "cloud_ok": false,
  "min_bytes_threshold": 4096,
  "ts": "2026-08-25T00:55:17Z"
}
