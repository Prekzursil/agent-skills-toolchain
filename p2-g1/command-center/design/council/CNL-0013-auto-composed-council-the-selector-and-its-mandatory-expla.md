{
 "algorithm": {
  "id": "CNL-0013.v1-table-selector",
  "inputs": [
   "task_description:string",
   "risk_tier:T0|T1|T2|T3|T4"
  ],
  "outputs": [
   "protocol",
   "voting_method",
   "stopping_rule",
   "roles",
   "explanation.dials[]"
  ],
  "steps": [
   "Reject unknown risk_tier; do not coerce prose into a tier.",
   "Classify task_description by first matching TASK_CLASS_RULES keyword (case-insensitive substring); last rule is the general fallback.",
   "Copy RISK_BASE[risk_tier].dials as the working composition.",
   "If CLASS_OVERLAY[(risk_tier, task_class)] exists, replace named dials and append roles_add seats that are not already present.",
   "For each of protocol, voting_method, stopping_rule, roles, emit a dial record: value, default, differs_from_default, the last rule_id that set it, a reason string, and contest.override_key.",
   "Completeness: if differs_from_default and reason is empty, FAIL. Defaults may carry an 'equals default' note and do not require a deviation reason."
  ]
 },
 "answer": "The selector is a two-stage deterministic table. Stage 1 classifies the task description by first-match substring rules into a closed class (incident, safety, irreversible, judicial, design, adversarial, generative, forecast, tradecraft, general). Stage 2 loads RISK_BASE[T] for the owner-supplied risk tier T0..T4, then applies at most one CLASS_OVERLAY[(T, class)] that may replace protocol/voting/stop and append seats. Defaults are the four-voice P01 majority panel. Every chosen dial is emitted as {dial, value, default, differs_from_default, rule_id, reason, contest.override_key}. A reviewer reconstructs WHY by replaying the embedded rule_table on the same inputs; they do not need selector.select(). A dial that differs from default with an empty reason fails the completeness check. Owner contest is per-dial: override_key replaces that dial only. Protocol ids are the catalog names from CNL-0038..CNL-0046. The Windows source file cited as _USER-PROMPTS.md:10765 is ABSENT on this tree. On-tree stand-ins are command-center/WORK-UNIT-CATALOG.json:34931, platform/schema/councilspec.schema.json:245 (explain_choices), and command-center/PHASE-GRAPH.json:182. CNL-0003 and CNL-0022 artifacts are not on this worktree; this unit locally closes the T0..T4 enum and the role ids it actually branches on. SUCCESS:CNL-0013",
 "artifacts": [
  {
   "exists": true,
   "path": "command-center/design/council/CNL-0013-auto-composed-council-the-selector-and-its-mandatory-expla.md",
   "role": "primary"
  },
  {
   "exists": true,
   "path": "command-center/schema/council-design-note.schema.json",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0013/rules.py",
   "role": "supporting"
  }
 ],
 "completion_sentinel": "SUCCESS:CNL-0013",
 "defaults": {
  "protocol": "P01-free-form-moderated-panel",
  "roles": [
   "Architect",
   "Skeptic",
   "Pragmatist",
   "Critic"
  ],
  "stopping_rule": "stop_if(max_rounds>=3 OR majority_reached)",
  "voting_method": "majority"
 },
 "dependency_presence": {
  "CNL-0003": false,
  "CNL-0022": true
 },
 "evidence": [
  {
   "claim": "Catalog CNL-0013 requires citing _USER-PROMPTS.md:10765 for a general-purpose auto-composed council that explains every choice.",
   "kind": "catalog-paraphrase",
   "path": "command-center/WORK-UNIT-CATALOG.json:34931"
  },
  {
   "claim": "On-tree CouncilSpec marks explain_choices as Spec 10765: auto-composed council must explain every choice and allow owner override.",
   "kind": "live-tree",
   "path": "platform/schema/councilspec.schema.json:245"
  },
  {
   "claim": "Phase 2C deliverable names a general-purpose auto-composed council that selects roles and protocol from the task, explains every choice, and allows owner override.",
   "kind": "live-tree",
   "path": "command-center/PHASE-GRAPH.json:182"
  },
  {
   "claim": "The Windows source file named in that citation is not on this worktree; existence probe recorded per candidate path.",
   "kind": "path-existence",
   "path": "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md"
  },
  {
   "claim": "Default four voices match skill.council on this tree (Architect, Skeptic, Pragmatist, Critic).",
   "kind": "live-tree",
   "path": "command-center/p2-wave/probes/ARC-0010/registry.json:29"
  },
  {
   "claim": "Protocol ids P01,P10,P14,P18,P26,P33,P39,P46,P47,P58 are named in catalog CNL-0038..CNL-0046 questions.",
   "kind": "catalog-named-ids",
   "path": "command-center/WORK-UNIT-CATALOG.json"
  },
  {
   "claim": "CNL-0003 charter-enum artifact is absent; this unit locally closes T0..T4.",
   "kind": "dependency",
   "path": "command-center/design/council/CNL-0003-charter-block-the-typed-fields-a-compiler-actually-branche.md"
  },
  {
   "claim": "CNL-0022 role-mandate artifact is absent; this unit locally closes the role ids it branches on.",
   "kind": "dependency",
   "path": "command-center/design/council/CNL-0022-role-mandate-schema-obligations-vs-permissions-vs-rights.md"
  },
  {
   "claim": "Source-candidate existence probe recorded live: [{\"path\": \"C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md\", \"exists\": false, \"bytes\": 0}, {\"path\": \"_USER-PROMPTS.md\", \"exists\": false, \"bytes\": 0}, {\"path\": \"command-center/sources/_USER-PROMPTS.md\", \"exists\": false, \"bytes\": 0}, {\"path\": \"C:/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json\", \"exists\": false, \"bytes\": 0}, {\"path\": \"11-COUNCIL-SPECIFICATION.schema.json\", \"exists\": false, \"bytes\": 0}, {\"path\": \"command-center/sources/11-COUNCIL-SPECIFICATION.schema.json\", \"exists\": false, \"bytes\": 0}, {\"path\": \"C:/Users/Prekzursil/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json\", \"exists\": false, \"bytes\": 0}, {\"path\": \"12-COUNCIL-PROTOCOLS-AND-PRESETS.json\", \"exists\": false, \"bytes\": 0}, {\"path\": \"command-center/sources/12-COUNCIL-PROTOCOLS-AND-PRESETS.json\", \"exists\": false, \"bytes\": 0}]",
   "kind": "live-probe",
   "path": "command-center/p2-wave/probes/CNL-0013/emit_note.py"
  },
  {
   "claim": "skill.council registry present=True",
   "kind": "live-tree",
   "path": "command-center/p2-wave/probes/ARC-0010/registry.json"
  }
 ],
 "explanation_contract": {
  "dials": [
   "protocol",
   "voting_method",
   "stopping_rule",
   "roles"
  ],
  "missing_reason_fails": true,
  "owner_contest": "Each dial carries contest.override_key; the owner replaces that one field. Other auto-chosen dials stay unless also overridden. The override is a recorded contest, not a silent roster rewrite."
 },
 "fixtures": [
  {
   "explanation": {
    "dials": [
     {
      "contest": {
       "effect": "replaces this dial only; other auto-chosen dials stay unless also overridden",
       "override_key": "protocol"
      },
      "default": "P01-free-form-moderated-panel",
      "dial": "protocol",
      "differs_from_default": false,
      "reason": "protocol equals default P01-free-form-moderated-panel; owner may still override this dial",
      "rule_id": "RISK-T0",
      "value": "P01-free-form-moderated-panel"
     },
     {
      "contest": {
       "effect": "replaces this dial only; other auto-chosen dials stay unless also overridden",
       "override_key": "voting_method"
      },
      "default": "majority",
      "dial": "voting_method",
      "differs_from_default": false,
      "reason": "voting_method equals default majority; owner may still override this dial",
      "rule_id": "RISK-T0",
      "value": "majority"
     },
     {
      "contest": {
       "effect": "replaces this dial only; other auto-chosen dials stay unless also overridden",
       "override_key": "stopping_rule"
      },
      "default": "stop_if(max_rounds>=3 OR majority_reached)",
      "dial": "stopping_rule",
      "differs_from_default": true,
      "reason": "rule RISK-T0 set stopping_rule=stop_if(max_rounds>=2 OR majority_reached) (default=stop_if(max_rounds>=3 OR majority_reached)): T0 informational work uses a two-seat panel and a short majority stop",
      "rule_id": "RISK-T0",
      "value": "stop_if(max_rounds>=2 OR majority_reached)"
     },
     {
      "contest": {
       "effect": "replaces this dial only; other auto-chosen dials stay unless also overridden",
       "override_key": "roles"
      },
      "default": [
       "Architect",
       "Skeptic",
       "Pragmatist",
       "Critic"
      ],
      "dial": "roles",
      "differs_from_default": true,
      "reason": "rule RISK-T0 set roles=['Architect', 'Pragmatist'] (default=['Architect', 'Skeptic', 'Pragmatist', 'Critic']): T0 informational work uses a two-seat panel and a short majority stop",
      "rule_id": "RISK-T0",
      "value": [
       "Architect",
       "Pragmatist"
      ]
     }
    ],
    "inputs": {
     "risk_tier": "T0",
     "task_description": "Summarize yesterday's changelog for the internal notes wiki."
    },
    "protocol": "P01-free-form-moderated-panel",
    "roster": [
     "Architect",
     "Pragmatist"
    ],
    "rule_table": {
     "class_overlays": [
      {
       "dials": {
        "protocol": "P26-brainstorming-swarm",
        "voting_method": "approval"
       },
       "id": "CLASS-T1-generative",
       "prose": "T1 generative work uses the brainstorming swarm and an ideator seat",
       "risk_tier": "T1",
       "roles_add": [
        "Ideator"
       ],
       "task_class": "generative"
      },
      {
       "dials": {
        "protocol": "P46-architecture-review-board"
       },
       "id": "CLASS-T2-design",
       "prose": "T2 design work uses the architecture-review-board protocol",
       "risk_tier": "T2",
       "roles_add": [],
       "task_class": "design"
      },
      {
       "dials": {
        "protocol": "P10-mandated-devils-advocate"
       },
       "id": "CLASS-T2-adversarial",
       "prose": "T2 adversarial work uses mandated devil's advocate",
       "risk_tier": "T2",
       "roles_add": [
        "DevilsAdvocate"
       ],
       "task_class": "adversarial"
      },
      {
       "dials": {
        "protocol": "P33-prediction-tournament",
        "voting_method": "score-then-resolve"
       },
       "id": "CLASS-T2-forecast",
       "prose": "T2 forecast work uses a prediction tournament and score-then-resolve",
       "risk_tier": "T2",
       "roles_add": [],
       "task_class": "forecast"
      },
      {
       "dials": {
        "protocol": "P14-judge-and-jury"
       },
       "id": "CLASS-T3-judicial",
       "prose": "T3 judicial work uses judge-and-jury rather than a debate panel",
       "risk_tier": "T3",
       "roles_add": [],
       "task_class": "judicial"
      },
      {
       "dials": {
        "protocol": "P47-incident-war-room",
        "stopping_rule": "stop_if((containment_declared AND max_rounds>=6) OR owner_halt)"
       },
       "id": "CLASS-T3-incident",
       "prose": "T3 incident work uses the incident-war-room and a containment stop",
       "risk_tier": "T3",
       "roles_add": [],
       "task_class": "incident"
      },
      {
       "dials": {
        "protocol": "P39-key-assumptions-check"
       },
       "id": "CLASS-T3-tradecraft",
       "prose": "T3 tradecraft work uses the key-assumptions-check protocol",
       "risk_tier": "T3",
       "roles_add": [],
       "task_class": "tradecraft"
      },
      {
       "dials": {
        "protocol": "P18-two-key-dual-control"
       },
       "id": "CLASS-T4-safety",
       "prose": "T4 safety-interlock work adds two-key dual-control and a safety officer",
       "risk_tier": "T4",
       "roles_add": [
        "SafetyOfficer"
       ],
       "task_class": "safety"
      }
     ],
     "defaults": {
      "protocol": "P01-free-form-moderated-panel",
      "roles": [
       "Architect",
       "Skeptic",
       "Pragmatist",
       "Critic"
      ],
      "stopping_rule": "stop_if(max_rounds>=3 OR majority_reached)",
      "voting_method": "majority"
     },
     "dials": [
      "protocol",
      "voting_method",
      "stopping_rule",
      "roles"
     ],
     "risk_base": {
      "T0": {
       "dials": {
        "protocol": "P01-free-form-moderated-panel",
        "roles": [
         "Architect",
         "Pragmatist"
        ],
        "stopping_rule": "stop_if(max_rounds>=2 OR majority_reached)",
        "voting_method": "majority"
       },
       "id": "RISK-T0",
       "prose": "T0 informational work uses a two-seat panel and a short majority stop"
      },
      "T1": {
       "dials": {
        "protocol": "P01-free-form-moderated-panel",
        "roles": [
         "Architect",
         "Skeptic",
         "Pragmatist",
         "Critic"
        ],
        "stopping_rule": "stop_if(max_rounds>=3 OR majority_reached)",
        "voting_method": "majority"
       },
       "id": "RISK-T1",
       "prose": "T1 low-risk work keeps the four-voice default panel"
      },
      "T2": {
       "dials": {
        "protocol": "P45-scientific-peer-review",
        "roles": [
         "Architect",
         "Skeptic",
         "Pragmatist",
         "Critic",
         "Moderator"
        ],
        "stopping_rule": "stop_if((max_rounds>=5 AND unresolved_objections==0) OR max_rounds>=8)",
        "voting_method": "supermajority-2/3"
       },
       "id": "RISK-T2",
       "prose": "T2 material work adds a moderator, supermajority, and an objection-clear stop"
      },
      "T3": {
       "dials": {
        "protocol": "P10-mandated-devils-advocate",
        "roles": [
         "Architect",
         "Skeptic",
         "Pragmatist",
         "Critic",
         "Moderator",
         "DevilsAdvocate",
         "EvidenceClerk"
        ],
        "stopping_rule": "stop_if((max_rounds>=8 AND two_key_agree AND every_claim_has_citation) OR owner_halt)",
        "voting_method": "two-key"
       },
       "id": "RISK-T3",
       "prose": "T3 high-stakes work mandates a devil's advocate, two-key vote, and cited claims"
      },
      "T4": {
       "dials": {
        "protocol": "P58-owner-in-the-loop-stepwise",
        "roles": [
         "Architect",
         "Skeptic",
         "Pragmatist",
         "Critic",
         "Moderator",
         "DevilsAdvocate",
         "EvidenceClerk",
         "Owner"
        ],
        "stopping_rule": "stop_if(owner_explicit_accept); never auto-stop on consensus",
        "voting_method": "owner-ratify"
       },
       "id": "RISK-T4",
       "prose": "T4 irreversible work never auto-stops: the owner must ratify stepwise"
      }
     },
     "task_class_rules": [
      {
       "any_keywords": [
        "secret leak",
        "production",
        "ci logs",
        "contain the token",
        "outage",
        "sev-",
        "incident"
       ],
       "class": "incident",
       "id": "TC-incident",
       "prose": "incident-response language routes to the incident class"
      },
      {
       "any_keywords": [
        "safety interlock",
        "disable the safety",
        "two-key stop"
       ],
       "class": "safety",
       "id": "TC-safety",
       "prose": "safety-interlock language routes to the safety class"
      },
      {
       "any_keywords": [
        "budget ceiling",
        "irreversible",
        "unattended councils",
        "10x"
       ],
       "class": "irreversible",
       "id": "TC-irreversible",
       "prose": "irreversible-spend language routes to the irreversible class"
      },
      {
       "any_keywords": [
        "adjudicate",
        "silent-loss",
        "hand edit",
        "verdict"
       ],
       "class": "judicial",
       "id": "TC-judicial",
       "prose": "adjudication language routes to the judicial class"
      },
      {
       "any_keywords": [
        "control-plane",
        "load-order",
        "file set",
        "architecture",
        "before freeze"
       ],
       "class": "design",
       "id": "TC-design",
       "prose": "design-review language routes to the design class"
      },
      {
       "any_keywords": [
        "red-team",
        "silent default",
        "hide an override",
        "attack"
       ],
       "class": "adversarial",
       "id": "TC-adversarial",
       "prose": "red-team language routes to the adversarial class"
      },
      {
       "any_keywords": [
        "brainstorm",
        "names for",
        "idea count"
       ],
       "class": "generative",
       "id": "TC-generative",
       "prose": "brainstorm language routes to the generative class"
      },
      {
       "any_keywords": [
        "estimate hours",
        "forecast",
        "prediction"
       ],
       "class": "forecast",
       "id": "TC-forecast",
       "prose": "estimation language routes to the forecast class"
      },
      {
       "any_keywords": [
        "key assumption",
        "premortem",
        "competing hypothes"
       ],
       "class": "tradecraft",
       "id": "TC-tradecraft",
       "prose": "structured-analytic language routes to the tradecraft class"
      },
      {
       "any_keywords": [],
       "class": "general",
       "fallback": true,
       "id": "TC-general",
       "prose": "fallback class when no specialist keyword matched"
      }
     ]
    },
    "selector_version": "CNL-0013.v1",
    "stopping_rule": "stop_if(max_rounds>=2 OR majority_reached)",
    "task_class": "general",
    "task_class_rule_id": "TC-general",
    "trace": [
     {
      "dials": {
       "protocol": "P01-free-form-moderated-panel",
       "roles": [
        "Architect",
        "Pragmatist"
       ],
       "stopping_rule": "stop_if(max_rounds>=2 OR majority_reached)",
       "voting_method": "majority"
      },
      "prose": "T0 informational work uses a two-seat panel and a short majority stop",
      "rule_id": "RISK-T0"
     }
    ],
    "voting_method": "majority"
   },
   "id": "F01",
   "risk_tier": "T0",
   "task_class": "general",
   "task_description": "Summarize yesterday's changelog for the internal notes wiki."
  },
  {
   "explanation": {
    "dials": [
     {
      "contest": {
       "effect": "replaces this dial only; other auto-chosen dials stay unless also overridden",
       "override_key": "protocol"
      },
      "default": "P01-free-form-moderated-panel",
      "dial": "protocol",
      "differs_from_default": false,
      "reason": "protocol equals default P01-free-form-moderated-panel; owner may still override this dial",
      "rule_id": "RISK-T0",
      "value": "P01-free-form-moderated-panel"
     },
     {
      "contest": {
       "effect": "replaces this dial only; other auto-chosen dials stay unless also overridden",
       "override_key": "voting_method"
      },
      "default": "majority",
      "dial": "voting_method",
      "differs_from_default": false,
      "reason": "voting_method equals default majority; owner may still override this dial",
      "rule_id": "RISK-T0",
      "value": "majority"
     },
     {
      "contest": {
       "effect": "replaces this dial only; other auto-chosen dials stay unless also overridden",
       "override_key": "stopping_rule"
      },
      "default": "stop_if(max_rounds>=3 OR majority_reached)",
      "dial": "stopping_rule",
      "differs_from_default": true,
      "reason": "rule RISK-T0 set stopping_rule=stop_if(max_rounds>=2 OR majority_reached) (default=stop_if(max_rounds>=3 OR majority_reached)): T0 informational work uses a two-seat panel and a short majority stop",
      "rule_id": "RISK-T0",
      "value": "stop_if(max_rounds>=2 OR majority_reached)"
     },
     {
      "contest": {
       "effect": "replaces this dial only; other auto-chosen dials stay unless also overridden",
       "override_key": "roles"
      },
      "default": [
       "Architect",
       "Skeptic",
       "Pragmatist",
       "Critic"
      ],
      "dial": "roles",
      "differs_from_default": true,
      "reason": "rule RISK-T0 set roles=['Architect', 'Pragmatist'] (default=['Architect', 'Skeptic', 'Pragmatist', 'Critic']): T0 informational work uses a two-seat panel and a short majority stop",
      "rule_id": "RISK-T0",
      "value": [
       "Architect",
       "Pragmatist"
      ]
     }
    ],
    "inputs": {
     "risk_tier": "T0",
     "task_description": "Reformat this three-column table as Markdown for the weekly brief."
    },
    "protocol": "P01-free-form-moderated-panel",
    "roster": [
     "Architect",
     "Pragmatist"
    ],
    "rule_table": {
     "class_overlays": [
      {
       "dials": {
        "protocol": "P26-brainstorming-swarm",
        "voting_method": "approval"
       },
       "id": "CLASS-T1-generative",
       "prose": "T1 generative work uses the brainstorming swarm and an ideator seat",
       "risk_tier": "T1",
       "roles_add": [
        "Ideator"
       ],
       "task_class": "generative"
      },
      {
       "dials": {
        "protocol": "P46-architecture-review-board"
       },
       "id": "CLASS-T2-design",
       "prose": "T2 design work uses the architecture-review-board protocol",
       "risk_tier": "T2",
       "roles_add": [],
       "task_class": "design"
      },
      {
       "dials": {
        "protocol": "P10-mandated-devils-advocate"
       },
       "id": "CLASS-T2-adversarial",
       "prose": "T2 adversarial work uses mandated devil's advocate",
       "risk_tier": "T2",
       "roles_add": [
        "DevilsAdvocate"
       ],
       "task_class": "adversarial"
      },
      {
       "dials": {
        "protocol": "P33-prediction-tournament",
        "voting_method": "score-then-resolve"
       },
       "id": "CLASS-T2-forecast",
       "prose": "T2 forecast work uses a prediction tournament and score-then-resolve",
       "risk_tier": "T2",
       "roles_add": [],
       "task_class": "forecast"
      },
      {
       "dials": {
        "protocol": "P14-judge-and-jury"
       },
       "id": "CLASS-T3-judicial",
       "prose": "T3 judicial work uses judge-and-jury rather than a debate panel",
       "risk_tier": "T3",
       "roles_add": [],
       "task_class": "judicial"
      },
      {
       "dials": {
        "protocol": "P47-incident-war-room",
        "stopping_rule": "stop_if((containment_declared AND max_rounds>=6) OR owner_halt)"
       },
       "id": "CLASS-T3-incident",
       "prose": "T3 incident work uses the incident-war-room and a containment stop",
       "risk_tier": "T3",
       "roles_add": [],
       "task_class": "incident"
      },
      {
       "dials": {
        "protocol": "P39-key-assumptions-check"
       },
       "id": "CLASS-T3-tradecraft",
       "prose": "T3 tradecraft work uses the key-assumptions-check protocol",
       "risk_tier": "T3",
       "roles_add": [],
       "task_class": "tradecraft"
      },
      {
       "dials": {
        "protocol": "P18-two-key-dual-control"
       },
       "id": "CLASS-T4-safety",
       "prose": "T4 safety-interlock work adds two-key dual-control and a safety officer",
       "risk_tier": "T4",
       "roles_add": [
        "SafetyOfficer"
       ],
       "task_class": "safety"
      }
     ],
     "defaults": {
      "protocol": "P01-free-form-moderated-panel",
      "roles": [
       "Architect",
       "Skeptic",
       "Pragmatist",
       "Critic"
      ],
      "stopping_rule": "stop_if(max_rounds>=3 OR majority_reached)",
      "voting_method": "majority"
     },
     "dials": [
      "protocol",
      "voting_method",
      "stopping_rule",
      "roles"
     ],
     "risk_base": {
      "T0": {
       "dials": {
        "protocol": "P01-free-form-moderated-panel",
        "roles": [
         "Architect",
         "Pragmatist"
        ],
        "stopping_rule": "stop_if(max_rounds>=2 OR majority_reached)",
        "voting_method": "majority"
       },
       "id": "RISK-T0",
       "prose": "T0 informational work uses a two-seat panel and a short majority stop"
      },
      "T1": {
       "dials": {
        "protocol": "P01-free-form-moderated-panel",
        "roles": [
         "Architect",
         "Skeptic",
         "Pragmatist",
         "Critic"
        ],
        "stopping_rule": "stop_if(max_rounds>=3 OR majority_reached)",
        "voting_method": "majority"
       },
       "id": "RISK-T1",
       "prose": "T1 low-risk work keeps the four-voice default panel"
      },
      "T2": {
       "dials": {
        "protocol": "P45-scientific-peer-review",
        "roles": [
         "Architect",
         "Skeptic",
         "Pragmatist",
         "Critic",
         "Moderator"
        ],
        "stopping_rule": "stop_if((max_rounds>=5 AND unresolved_objections==0) OR max_rounds>=8)",
        "voting_method": "supermajority-2/3"
       },
       "id": "RISK-T2",
       "prose": "T2 material work adds a moderator, supermajority, and an objection-clear stop"
      },
      "T3": {
       "dials": {
        "protocol": "P10-mandated-devils-advocate",
        "roles": [
         "Architect",
         "Skeptic",
         "Pragmatist",
         "Critic",
         "Moderator",
         "DevilsAdvocate",
         "EvidenceClerk"
        ],
        "stopping_rule": "stop_if((max_rounds>=8 AND two_key_agree AND every_claim_has_citation) OR owner_halt)",
        "voting_method": "two-key"
       },
       "id": "RISK-T3",
       "prose": "T3 high-stakes work mandates a devil's advocate, two-key vote, and cited claims"
      },
      "T4": {
       "dials": {
        "protocol": "P58-owner-in-the-loop-stepwise",
        "roles": [
         "Architect",
         "Skeptic",
         "Pragmatist",
         "Critic",
         "Moderator",
         "DevilsAdvocate",
         "EvidenceClerk",
         "Owner"
        ],
        "stopping_rule": "stop_if(owner_explicit_accept); never auto-stop on consensus",
        "voting_method": "owner-ratify"
       },
       "id": "RISK-T4",
       "prose": "T4 irreversible work never auto-stops: the owner must ratify stepwise"
      }
     },
     "task_class_rules": [
      {
       "any_keywords": [
        "secret leak",
        "production",
        "ci logs",
        "contain the token",
        "outage",
        "sev-",
        "incident"
       ],
       "class": "incident",
       "id": "TC-incident",
       "prose": "incident-response language routes to the incident class"
      },
      {
       "any_keywords": [
        "safety interlock",
        "disable the safety",
        "two-key stop"
       ],
       "class": "safety",
       "id": "TC-safety",
       "prose": "safety-interlock language routes to the safety class"
      },
      {
       "any_keywords": [
        "budget ceiling",
        "irreversible",
        "unattended councils",
        "10x"
       ],
       "class": "irreversible",
       "id": "TC-irreversible",
       "prose": "irreversible-spend language routes to the irreversible class"
      },
      {
       "any_keywords": [
        "adjudicate",
        "silent-loss",
        "hand edit",
        "verdict"
       ],
       "class": "judicial",
       "id": "TC-judicial",
       "prose": "adjudication language routes to the judicial class"
      },
      {
       "any_keywords": [
        "control-plane",
        "load-order",
        "file set",
        "architecture",
        "before freeze"
       ],
       "class": "design",
       "id": "TC-design",
       "prose": "design-review language routes to the design class"
      },
      {
       "any_keywords": [
        "red-team",
        "silent default",
        "hide an override",
        "attack"
       ],
       "class": "adversarial",
       "id": "TC-adversarial",
       "prose": "red-team language routes to the adversarial class"
      },
      {
       "any_keywords": [
        "brainstorm",
        "names for",
        "idea count"
       ],
       "class": "generative",
       "id": "TC-generative",
       "prose": "brainstorm language routes to the generative class"
      },
      {
       "any_keywords": [
        "estimate hours",
        "forecast",
        "prediction"
       ],
       "class": "forecast",
       "id": "TC-forecast",
       "prose": "estimation language routes to the forecast class"
      },
      {
       "any_keywords": [
        "key assumption",
        "premortem",
        "competing hypothes"
       ],
       "class": "tradecraft",
       "id": "TC-tradecraft",
       "prose": "structured-analytic language routes to the tradecraft class"
      },
      {
       "any_keywords": [],
       "class": "general",
       "fallback": true,
       "id": "TC-general",
       "prose": "fallback class when no specialist keyword matched"
      }
     ]
    },
    "selector_version": "CNL-0013.v1",
    "stopping_rule": "stop_if(max_rounds>=2 OR majority_reached)",
    "task_class": "general",
    "task_class_rule_id": "TC-general",
    "trace": [
     {
      "dials": {
       "protocol": "P01-free-form-moderated-panel",
       "roles": [
        "Architect",
        "Pragmatist"
       ],
       "stopping_rule": "stop_if(max_rounds>=2 OR majority_reached)",
       "voting_method": "majority"
      },
      "prose": "T0 informational work uses a two-seat panel and a short majority stop",
      "rule_id": "RISK-T0"
     }
    ],
    "voting_method": "majority"
   },
   "id": "F02",
   "risk_tier": "T0",
   "task_class": "general",
   "task_description": "Reformat this three-column table as Markdown for the weekly brief."
  },
  {
   "explanation": {
    "dials": [
     {
      "contest": {
       "effect": "replaces this dial only; other auto-chosen dials stay unless also overridden",
       "override_key": "protocol"
      },
      "default": "P01-free-form-moderated-panel",
      "dial": "protocol",
      "differs_from_default": true,
      "reason": "rule CLASS-T1-generative set protocol=P26-brainstorming-swarm (default=P01-free-form-moderated-panel): T1 generative work uses the brainstorming swarm and an ideator seat",
      "rule_id": "CLASS-T1-generative",
      "value": "P26-brainstorming-swarm"
     },
     {
      "contest": {
       "effect": "replaces this dial only; other auto-chosen dials stay unless also overridden",
       "override_key": "voting_method"
      },
      "default": "majority",
      "dial": "voting_method",
      "differs_from_default": true,
      "reason": "rule CLASS-T1-generative set voting_method=approval (default=majority): T1 generative work uses the brainstorming swarm and an ideator seat",
      "rule_id": "CLASS-T1-generative",
      "value": "approval"
     },
     {
      "contest": {
       "effect": "replaces this dial only; other auto-chosen dials stay unless also overridden",
       "override_key": "stopping_rule"
      },
      "default": "stop_if(max_rounds>=3 OR majority_reached)",
      "dial": "stopping_rule",
      "differs_from_default": false,
      "reason": "stopping_rule equals default stop_if(max_rounds>=3 OR majority_reached); owner may still override this dial",
      "rule_id": "RISK-T1",
      "value": "stop_if(max_rounds>=3 OR majority_reached)"
     },
     {
      "contest": {
       "effect": "replaces this dial only; other auto-chosen dials stay unless also overridden",
       "override_key": "roles"
      },
      "default": [
       "Architect",
       "Skeptic",
       "Pragmatist",
       "Critic"
      ],
      "dial": "roles",
      "differs_from_default": true,
      "reason": "rule CLASS-T1-generative set roles=['Architect', 'Skeptic', 'Pragmatist', 'Critic', 'Ideator'] (default=['Architect', 'Skeptic', 'Pragmatist', 'Critic']): T1 generative work uses the brainstorming swarm and an ideator seat",
      "rule_id": "CLASS-T1-generative",
      "value": [
       "Architect",
       "Skeptic",
       "Pragmatist",
       "Critic",
       "Ideator"
      ]
     }
    ],
    "inputs": {
     "risk_tier": "T1",
     "task_description": "Brainstorm names for a new CLI flag that dumps the selector explanation."
    },
    "protocol": "P26-brainstorming-swarm",
    "roster": [
     "Architect",
     "Skeptic",
     "Pragmatist",
     "Critic",
     "Ideator"
    ],
    "rule_table": {
     "class_overlays": [
      {
       "dials": {
        "protocol": "P26-brainstorming-swarm",
        "voting_method": "approval"
       },
       "id": "CLASS-T1-generative",
       "prose": "T1 generative work uses the brainstorming swarm and an ideator seat",
       "risk_tier": "T1",
       "roles_add": [
        "Ideator"
       ],
       "task_class": "generative"
      },
      {
       "dials": {
        "protocol": "P46-architecture-review-board"
       },
       "id": "CLASS-T2-design",
       "prose": "T2 design work uses the architecture-review-board protocol",
       "risk_tier": "T2",
       "roles_add": [],
       "task_class": "design"
      },
      {
       "dials": {
        "protocol": "P10-mandated-devils-advocate"
       },
       "id": "CLASS-T2-adversarial",
       "prose": "T2 adversarial work uses mandated devil's advocate",
       "risk_tier": "T2",
       "roles_add": [
        "DevilsAdvocate"
       ],
       "task_class": "adversarial"
      },
      {
       "dials": {
        "protocol": "P33-prediction-tournament",
        "voting_method": "score-then-resolve"
       },
       "id": "CLASS-T2-forecast",
       "prose": "T2 forecast work uses a prediction tournament and score-then-resolve",
       "risk_tier": "T2",
       "roles_add": [],
       "task_class": "forecast"
      },
      {
       "dials": {
        "protocol": "P14-judge-and-jury"
       },
       "id": "CLASS-T3-judicial",
       "prose": "T3 judicial work uses judge-and-jury rather than a debate panel",
       "risk_tier": "T3",
       "roles_add": [],
       "task_class": "judicial"
      },
      {
       "dials": {
        "protocol": "P47-incident-war-room",
        "stopping_rule": "stop_if((containment_declared AND max_rounds>=6) OR owner_halt)"
       },
       "id": "CLASS-T3-incident",
       "prose": "T3 incident work uses the incident-war-room and a containment stop",
       "risk_tier": "T3",
       "roles_add": [],
       "task_class": "incident"
      },
      {
       "dials": {
        "protocol": "P39-key-assumptions-check"
       },
       "id": "CLASS-T3-tradecraft",
       "prose": "T3 tradecraft work uses the key-assumptions-check protocol",
       "risk_tier": "T3",
       "roles_add": [],
       "task_class": "tradecraft"
      },
      {
       "dials": {
        "protocol": "P18-two-key-dual-control"
       },
       "id": "CLASS-T4-safety",
       "prose": "T4 safety-interlock work adds two-key dual-control and a safety officer",
       "risk_tier": "T4",
       "roles_add": [
        "SafetyOfficer"
       ],
       "task_class": "safety"
      }
     ],
     "defaults": {
      "protocol": "P01-free-form-moderated-panel",
      "roles": [
       "Architect",
       "Skeptic",
       "Pragmatist",
       "Critic"
      ],
      "stopping_rule": "stop_if(max_rounds>=3 OR majority_reached)",
      "voting_method": "majority"
     },
     "dials": [
      "protocol",
      "voting_method",
      "stopping_rule",
      "roles"
     ],
     "risk_base": {
      "T0": {
       "dials": {
        "protocol": "P01-free-form-moderated-panel",
        "roles": [
         "Architect",
         "Pragmatist"
        ],
        "stopping_rule": "stop_if(max_rounds>=2 OR majority_reached)",
        "voting_method": "majority"
       },
       "id": "RISK-T0",
       "prose": "T0 informational work uses a two-seat panel and a short majority stop"
      },
      "T1": {
       "dials": {
        "protocol": "P01-free-form-moderated-panel",
        "roles": [
         "Architect",
         "Skeptic",
         "Pragmatist",
         "Critic"
        ],
        "stopping_rule": "stop_if(max_rounds>=3 OR majority_reached)",
        "voting_method": "majority"
       },
       "id": "RISK-T1",
       "prose": "T1 low-risk work keeps the four-voice default panel"
      },
      "T2": {
       "dials": {
        "protocol": "P45-scientific-peer-review",
        "roles": [
         "Architect",
         "Skeptic",
         "Pragmatist",
         "Critic",
         "Moderator"
        ],
        "stopping_rule": "stop_if((max_rounds>=5 AND unresolved_objections==0) OR max_rounds>=8)",
        "voting_method": "supermajority-2/3"
       },
       "id": "RISK-T2",
       "prose": "T2 material work adds a moderator, supermajority, and an objection-clear stop"
      },
      "T3": {
       "dials": {
        "protocol": "P10-mandated-devils-advocate",
        "roles": [
         "Architect",
         "Skeptic",
         "Pragmatist",
         "Critic",
         "Moderator",
         "DevilsAdvocate",
         "EvidenceClerk"
        ],
        "stopping_rule": "stop_if((max_rounds>=8 AND two_key_agree AND every_claim_has_citation) OR owner_halt)",
        "voting_method": "two-key"
       },
       "id": "RISK-T3",
       "prose": "T3 high-stakes work mandates a devil's advocate, two-key vote, and cited claims"
      },
      "T4": {
       "dials": {
        "protocol": "P58-owner-in-the-loop-stepwise",
        "roles": [
         "Architect",
         "Skeptic",
         "Pragmatist",
         "Critic",
         "Moderator",
         "DevilsAdvocate",
         "EvidenceClerk",
         "Owner"
        ],
        "stopping_rule": "stop_if(owner_explicit_accept); never auto-stop on consensus",
        "voting_method": "owner-ratify"
       },
       "id": "RISK-T4",
       "prose": "T4 irreversible work never auto-stops: the owner must ratify stepwise"
      }
     },
     "task_class_rules": [
      {
       "any_keywords": [
        "secret leak",
        "production",
        "ci logs",
        "contain the token",
        "outage",
        "sev-",
        "incident"
       ],
       "class": "incident",
       "id": "TC-incident",
       "prose": "incident-response language routes to the incident class"
      },
      {
       "any_keywords": [
        "safety interlock",
        "disable the safety",
        "two-key stop"
       ],
       "class": "safety",
       "id": "TC-safety",
       "prose": "safety-interlock language routes to the safety class"
      },
      {
       "any_keywords": [
        "budget ceiling",
        "irreversible",
        "unattended councils",
        "10x"
       ],
       "class": "irreversible",
       "id": "TC-irreversible",
       "prose": "irreversible-spend language routes to the irreversible class"
      },
      {
       "any_keywords": [
        "adjudicate",
        "silent-loss",
        "hand edit",
        "verdict"
       ],
       "class": "judicial",
       "id": "TC-judicial",
       "prose": "adjudication language routes to the judicial class"
      },
      {
       "any_keywords": [
        "control-plane",
        "load-order",
        "file set",
        "architecture",
        "before freeze"
       ],
       "class": "design",
       "id": "TC-design",
       "prose": "design-review language routes to the design class"
      },
      {
       "any_keywords": [
        "red-team",
        "silent default",
        "hide an override",
        "attack"
       ],
       "class": "adversarial",
       "id": "TC-adversarial",
       "prose": "red-team language routes to the adversarial class"
      },
      {
       "any_keywords": [
        "brainstorm",
        "names for",
        "idea count"
       ],
       "class": "generative",
       "id": "TC-generative",
       "prose": "brainstorm language routes to the generative class"
      },
      {
       "any_keywords": [
        "estimate hours",
        "forecast",
        "prediction"
       ],
       "class": "forecast",
       "id": "TC-forecast",
       "prose": "estimation language routes to the forecast class"
      },
      {
       "any_keywords": [
        "key assumption",
        "premortem",
        "competing hypothes"
       ],
       "class": "tradecraft",
       "id": "TC-tradecraft",
       "prose": "structured-analytic language routes to the tradecraft class"
      },
      {
       "any_keywords": [],
       "class": "general",
       "fallback": true,
       "id": "TC-general",
       "prose": "fallback class when no specialist keyword matched"
      }
     ]
    },
    "selector_version": "CNL-0013.v1",
    "stopping_rule": "stop_if(max_rounds>=3 OR majority_reached)",
    "task_class": "generative",
    "task_class_rule_id": "TC-generative",
    "trace": [
     {
      "dials": {
       "protocol": "P01-free-form-moderated-panel",
       "roles": [
        "Architect",
        "Skeptic",
        "Pragmatist",
        "Critic"
       ],
       "stopping_rule": "stop_if(max_rounds>=3 OR majority_reached)",
       "voting_method": "majority"
      },
      "prose": "T1 low-risk work keeps the four-voice default panel",
      "rule_id": "RISK-T1"
     },
     {
      "dials": {
       "protocol": "P26-brainstorming-swarm",
       "voting_method": "approval"
      },
      "prose": "T1 generative work uses the brainstorming swarm and an ideator seat",
      "roles_add": [
       "Ideator"
      ],
      "rule_id": "CLASS-T1-generative"
     }
    ],
    "voting_method": "approval"
   },
   "id": "F03",
   "risk_tier": "T1",
   "task_class": "generative",
   "task_description": "Brainstorm names for a new CLI flag that dumps the selector explanation."
  },
  {
   "explanation": {
    "dials": [
     {
      "contest": {
       "effect": "replaces this dial only; other auto-chosen dials stay unless also overridden",
       "override_key": "protocol"
      },
      "default": "P01-free-form-moderated-panel",
      "dial": "protocol",
      "differs_from_default": false,
      "reason": "protocol equals default P01-free-form-moderated-panel; owner may still override this dial",
      "rule_id": "RISK-T1",
      "value": "P01-free-form-moderated-panel"
     },
     {
      "contest": {
       "effect": "replaces this dial only; other auto-chosen dials stay unless also overridden",
       "override_key": "voting_method"
      },
      "default": "majority",
      "dial": "voting_method",
      "differs_from_default": false,
      "reason": "voting_method equals default majority; owner may still override this dial",
      "rule_id": "RISK-T1",
      "value": "majority"
     },
     {
      "contest": {
       "effect": "replaces this dial only; other auto-chosen dials stay unless also overridden",
       "override_key": "stopping_rule"
      },
      "default": "stop_if(max_rounds>=3 OR majority_reached)",
      "dial": "stopping_rule",
      "differs_from_default": false,
      "reason": "stopping_rule equals default stop_if(max_rounds>=3 OR majority_reached); owner may still override this dial",
      "rule_id": "RISK-T1",
      "value": "stop_if(max_rounds>=3 OR majority_reached)"
     },
     {
      "contest": {
       "effect": "replaces this dial only; other auto-chosen dials stay unless also overridden",
       "override_key": "roles"
      },
      "default": [
       "Architect",
       "Skeptic",
       "Pragmatist",
       "Critic"
      ],
      "dial": "roles",
      "differs_from_default": false,
      "reason": "roles equals default ['Architect', 'Skeptic', 'Pragmatist', 'Critic']; owner may still override this dial",
      "rule_id": "RISK-T1",
      "value": [
       "Architect",
       "Skeptic",
       "Pragmatist",
       "Critic"
      ]
     }
    ],
    "inputs": {
     "risk_tier": "T1",
     "task_description": "Review the README for typos and broken links only."
    },
    "protocol": "P01-free-form-moderated-panel",
    "roster": [
     "Architect",
     "Skeptic",
     "Pragmatist",
     "Critic"
    ],
    "rule_table": {
     "class_overlays": [
      {
       "dials": {
        "protocol": "P26-brainstorming-swarm",
        "voting_method": "approval"
       },
       "id": "CLASS-T1-generative",
       "prose": "T1 generative work uses the brainstorming swarm and an ideator seat",
       "risk_tier": "T1",
       "roles_add": [
        "Ideator"
       ],
       "task_class": "generative"
      },
      {
       "dials": {
        "protocol": "P46-architecture-review-board"
       },
       "id": "CLASS-T2-design",
       "prose": "T2 design work uses the architecture-review-board protocol",
       "risk_tier": "T2",
       "roles_add": [],
       "task_class": "design"
      },
      {
       "dials": {
        "protocol": "P10-mandated-devils-advocate"
       },
       "id": "CLASS-T2-adversarial",
       "prose": "T2 adversarial work uses mandated devil's advocate",
       "risk_tier": "T2",
       "roles_add": [
        "DevilsAdvocate"
       ],
       "task_class": "adversarial"
      },
      {
       "dials": {
        "protocol": "P33-prediction-tournament",
        "voting_method": "score-then-resolve"
       },
       "id": "CLASS-T2-forecast",
       "prose": "T2 forecast work uses a prediction tournament and score-then-resolve",
       "risk_tier": "T2",
       "roles_add": [],
       "task_class": "forecast"
      },
      {
       "dials": {
        "protocol": "P14-judge-and-jury"
       },
       "id": "CLASS-T3-judicial",
       "prose": "T3 judicial work uses judge-and-jury rather than a debate panel",
       "risk_tier": "T3",
       "roles_add": [],
       "task_class": "judicial"
      },
      {
       "dials": {
        "protocol": "P47-incident-war-room",
        "stopping_rule": "stop_if((containment_declared AND max_rounds>=6) OR owner_halt)"
       },
       "id": "CLASS-T3-incident",
       "prose": "T3 incident work uses the incident-war-room and a containment stop",
       "risk_tier": "T3",
       "roles_add": [],
       "task_class": "incident"
      },
      {
       "dials": {
        "protocol": "P39-key-assumptions-check"
       },
       "id": "CLASS-T3-tradecraft",
       "prose": "T3 tradecraft work uses the key-assumptions-check protocol",
       "risk_tier": "T3",
       "roles_add": [],
       "task_class": "tradecraft"
      },
      {
       "dials": {
        "protocol": "P18-two-key-dual-control"
       },
       "id": "CLASS-T4-safety",
       "prose": "T4 safety-interlock work adds two-key dual-control and a safety officer",
       "risk_tier": "T4",
       "roles_add": [
        "SafetyOfficer"
       ],
       "task_class": "safety"
      }
     ],
     "defaults": {
      "protocol": "P01-free-form-moderated-panel",
      "roles": [
       "Architect",
       "Skeptic",
       "Pragmatist",
       "Critic"
      ],
      "stopping_rule": "stop_if(max_rounds>=3 OR majority_reached)",
      "voting_method": "majority"
     },
     "dials": [
      "protocol",
      "voting_method",
      "stopping_rule",
      "roles"
     ],
     "risk_base": {
      "T0": {
       "dials": {
        "protocol": "P01-free-form-moderated-panel",
        "roles": [
         "Architect",
         "Pragmatist"
        ],
        "stopping_rule": "stop_if(max_rounds>=2 OR majority_reached)",
        "voting_method": "majority"
       },
       "id": "RISK-T0",
       "prose": "T0 informational work uses a two-seat panel and a short majority stop"
      },
      "T1": {
       "dials": {
        "protocol": "P01-free-form-moderated-panel",
        "roles": [
         "Architect",
         "Skeptic",
         "Pragmatist",
         "Critic"
        ],
        "stopping_rule": "stop_if(max_rounds>=3 OR majority_reached)",
        "voting_method": "majority"
       },
       "id": "RISK-T1",
       "prose": "T1 low-risk work keeps the four-voice default panel"
      },
      "T2": {
       "dials": {
        "protocol": "P45-scientific-peer-review",
        "roles": [
         "Architect",
         "Skeptic",
         "Pragmatist",
         "Critic",
         "Moderator"
        ],
        "stopping_rule": "stop_if((max_rounds>=5 AND unresolved_objections==0) OR max_rounds>=8)",
        "voting_method": "supermajority-2/3"
       },
       "id": "RISK-T2",
       "prose": "T2 material work adds a moderator, supermajority, and an objection-clear stop"
      },
      "T3": {
       "dials": {
        "protocol": "P10-mandated-devils-advocate",
        "roles": [
         "Architect",
         "Skeptic",
         "Pragmatist",
         "Critic",
         "Moderator",
         "DevilsAdvocate",
         "EvidenceClerk"
        ],
        "stopping_rule": "stop_if((max_rounds>=8 AND two_key_agree AND every_claim_has_citation) OR owner_halt)",
        "voting_method": "two-key"
       },
       "id": "RISK-T3",
       "prose": "T3 high-stakes work mandates a devil's advocate, two-key vote, and cited claims"
      },
      "T4": {
       "dials": {
        "protocol": "P58-owner-in-the-loop-stepwise",
        "roles": [
         "Architect",
         "Skeptic",
         "Pragmatist",
         "Critic",
         "Moderator",
         "DevilsAdvocate",
         "EvidenceClerk",
         "Owner"
        ],
        "stopping_rule": "stop_if(owner_explicit_accept); never auto-stop on consensus",
        "voting_method": "owner-ratify"
       },
       "id": "RISK-T4",
       "prose": "T4 irreversible work never auto-stops: the owner must ratify stepwise"
      }
     },
     "task_class_rules": [
      {
       "any_keywords": [
        "secret leak",
        "production",
        "ci logs",
        "contain the token",
        "outage",
        "sev-",
        "incident"
       ],
       "class": "incident",
       "id": "TC-incident",
       "prose": "incident-response language routes to the incident class"
      },
      {
       "any_keywords": [
        "safety interlock",
        "disable the safety",
        "two-key stop"
       ],
       "class": "safety",
       "id": "TC-safety",
       "prose": "safety-interlock language routes to the safety class"
      },
      {
       "any_keywords": [
        "budget ceiling",
        "irreversible",
        "unattended councils",
        "10x"
       ],
       "class": "irreversible",
       "id": "TC-irreversible",
       "prose": "irreversible-spend language routes to the irreversible class"
      },
      {
       "any_keywords": [
        "adjudicate",
        "silent-loss",
        "hand edit",
        "verdict"
       ],
       "class": "judicial",
       "id": "TC-judicial",
       "prose": "adjudication language routes to the judicial class"
      },
      {
       "any_keywords": [
        "control-plane",
        "load-order",
        "file set",
        "architecture",
        "before freeze"
       ],
       "class": "design",
       "id": "TC-design",
       "prose": "design-review language routes to the design class"
      },
      {
       "any_keywords": [
        "red-team",
        "silent default",
        "hide an override",
        "attack"
       ],
       "class": "adversarial",
       "id": "TC-adversarial",
       "prose": "red-team language routes to the adversarial class"
      },
      {
       "any_keywords": [
        "brainstorm",
        "names for",
        "idea count"
       ],
       "class": "generative",
       "id": "TC-generative",
       "prose": "brainstorm language routes to the generative class"
      },
      {
       "any_keywords": [
        "estimate hours",
        "forecast",
        "prediction"
       ],
       "class": "forecast",
       "id": "TC-forecast",
       "prose": "estimation language routes to the forecast class"
      },
      {
       "any_keywords": [
        "key assumption",
        "premortem",
        "competing hypothes"
       ],
       "class": "tradecraft",
       "id": "TC-tradecraft",
       "prose": "structured-analytic language routes to the tradecraft class"
      },
      {
       "any_keywords": [],
       "class": "general",
       "fallback": true,
       "id": "TC-general",
       "prose": "fallback class when no specialist keyword matched"
      }
     ]
    },
    "selector_version": "CNL-0013.v1",
    "stopping_rule": "stop_if(max_rounds>=3 OR majority_reached)",
    "task_class": "general",
    "task_class_rule_id": "TC-general",
    "trace": [
     {
      "dials": {
       "protocol": "P01-free-form-moderated-panel",
       "roles": [
        "Architect",
        "Skeptic",
        "Pragmatist",
        "Critic"
       ],
       "stopping_rule": "stop_if(max_rounds>=3 OR majority_reached)",
       "voting_method": "majority"
      },
      "prose": "T1 low-risk work keeps the four-voice default panel",
      "rule_id": "RISK-T1"
     }
    ],
    "voting_method": "majority"
   },
   "id": "F04",
   "risk_tier": "T1",
   "task_class": "general",
   "task_description": "Review the README for typos and broken links only."
  },
  {
   "explanation": {
    "dials": [
     {
      "contest": {
       "effect": "replaces this dial only; other auto-chosen dials stay unless also overridden",
       "override_key": "protocol"
      },
      "default": "P01-free-form-moderated-panel",
      "dial": "protocol",
      "differs_from_default": true,
      "reason": "rule CLASS-T2-design set protocol=P46-architecture-review-board (default=P01-free-form-moderated-panel): T2 design work uses the architecture-review-board protocol",
      "rule_id": "CLASS-T2-design",
      "value": "P46-architecture-review-board"
     },
     {
      "contest": {
       "effect": "replaces this dial only; other auto-chosen dials stay unless also overridden",
       "override_key": "voting_method"
      },
      "default": "majority",
      "dial": "voting_method",
      "differs_from_default": true,
      "reason": "rule RISK-T2 set voting_method=supermajority-2/3 (default=majority): T2 material work adds a moderator, supermajority, and an objection-clear stop",
      "rule_id": "RISK-T2",
      "value": "supermajority-2/3"
     },
     {
      "contest": {
       "effect": "replaces this dial only; other auto-chosen dials stay unless also overridden",
       "override_key": "stopping_rule"
      },
      "default": "stop_if(max_rounds>=3 OR majority_reached)",
      "dial": "stopping_rule",
      "differs_from_default": true,
      "reason": "rule RISK-T2 set stopping_rule=stop_if((max_rounds>=5 AND unresolved_objections==0) OR max_rounds>=8) (default=stop_if(max_rounds>=3 OR majority_reached)): T2 material work adds a moderator, supermajority, and an objection-clear stop",
      "rule_id": "RISK-T2",
      "value": "stop_if((max_rounds>=5 AND unresolved_objections==0) OR max_rounds>=8)"
     },
     {
      "contest": {
       "effect": "replaces this dial only; other auto-chosen dials stay unless also overridden",
       "override_key": "roles"
      },
      "default": [
       "Architect",
       "Skeptic",
       "Pragmatist",
       "Critic"
      ],
      "dial": "roles",
      "differs_from_default": true,
      "reason": "rule RISK-T2 set roles=['Architect', 'Skeptic', 'Pragmatist', 'Critic', 'Moderator'] (default=['Architect', 'Skeptic', 'Pragmatist', 'Critic']): T2 material work adds a moderator, supermajority, and an objection-clear stop",
      "rule_id": "RISK-T2",
      "value": [
       "Architect",
       "Skeptic",
       "Pragmatist",
       "Critic",
       "Moderator"
      ]
     }
    ],
    "inputs": {
     "risk_tier": "T2",
     "task_description": "Review the A1 control-plane file set for load-order bugs before freeze."
    },
    "protocol": "P46-architecture-review-board",
    "roster": [
     "Architect",
     "Skeptic",
     "Pragmatist",
     "Critic",
     "Moderator"
    ],
    "rule_table": {
     "class_overlays": [
      {
       "dials": {
        "protocol": "P26-brainstorming-swarm",
        "voting_method": "approval"
       },
       "id": "CLASS-T1-generative",
       "prose": "T1 generative work uses the brainstorming swarm and an ideator seat",
       "risk_tier": "T1",
       "roles_add": [
        "Ideator"
       ],
       "task_class": "generative"
      },
      {
       "dials": {
        "protocol": "P46-architecture-review-board"
       },
       "id": "CLASS-T2-design",
       "prose": "T2 design work uses the architecture-review-board protocol",
       "risk_tier": "T2",
       "roles_add": [],
       "task_class": "design"
      },
      {
       "dials": {
        "protocol": "P10-mandated-devils-advocate"
       },
       "id": "CLASS-T2-adversarial",
       "prose": "T2 adversarial work uses mandated devil's advocate",
       "risk_tier": "T2",
       "roles_add": [
        "DevilsAdvocate"
       ],
       "task_class": "adversarial"
      },
      {
       "dials": {
        "protocol": "P33-prediction-tournament",
        "voting_method": "score-then-resolve"
       },
       "id": "CLASS-T2-forecast",
       "prose": "T2 forecast work uses a prediction tournament and score-then-resolve",
       "risk_tier": "T2",
       "roles_add": [],
       "task_class": "forecast"
      },
      {
       "dials": {
        "protocol": "P14-judge-and-jury"
       },
       "id": "CLASS-T3-judicial",
       "prose": "T3 judicial work uses judge-and-jury rather than a debate panel",
       "risk_tier": "T3",
       "roles_add": [],
       "task_class": "judicial"
      },
      {
       "dials": {
        "protocol": "P47-incident-war-room",
        "stopping_rule": "stop_if((containment_declared AND max_rounds>=6) OR owner_halt)"
       },
       "id": "CLASS-T3-incident",
       "prose": "T3 incident work uses the incident-war-room and a containment stop",
       "risk_tier": "T3",
       "roles_add": [],
       "task_class": "incident"
      },
      {
       "dials": {
        "protocol": "P39-key-assumptions-check"
       },
       "id": "CLASS-T3-tradecraft",
       "prose": "T3 tradecraft work uses the key-assumptions-check protocol",
       "risk_tier": "T3",
       "roles_add": [],
       "task_class": "tradecraft"
      },
      {
       "dials": {
        "protocol": "P18-two-key-dual-control"
       },
       "id": "CLASS-T4-safety",
       "prose": "T4 safety-interlock work adds two-key dual-control and a safety officer",
       "risk_tier": "T4",
       "roles_add": [
        "SafetyOfficer"
       ],
       "task_class": "safety"
      }
     ],
     "defaults": {
      "protocol": "P01-free-form-moderated-panel",
      "roles": [
       "Architect",
       "Skeptic",
       "Pragmatist",
       "Critic"
      ],
      "stopping_rule": "stop_if(max_rounds>=3 OR majority_reached)",
      "voting_method": "majority"
     },
     "dials": [
      "protocol",
      "voting_method",
      "stopping_rule",
      "roles"
     ],
     "risk_base": {
      "T0": {
       "dials": {
        "protocol": "P01-free-form-moderated-panel",
        "roles": [
         "Architect",
         "Pragmatist"
        ],
        "stopping_rule": "stop_if(max_rounds>=2 OR majority_reached)",
        "voting_method": "majority"
       },
       "id": "RISK-T0",
       "prose": "T0 informational work uses a two-seat panel and a short majority stop"
      },
      "T1": {
       "dials": {
        "protocol": "P01-free-form-moderated-panel",
        "roles": [
         "Architect",
         "Skeptic",
         "Pragmatist",
         "Critic"
        ],
        "stopping_rule": "stop_if(max_rounds>=3 OR majority_reached)",
        "voting_method": "majority"
       },
       "id": "RISK-T1",
       "prose": "T1 low-risk work keeps the four-voice default panel"
      },
      "T2": {
       "dials": {
        "protocol": "P45-scientific-peer-review",
        "roles": [
         "Architect",
         "Skeptic",
         "Pragmatist",
         "Critic",
         "Moderator"
        ],
        "stopping_rule": "stop_if((max_rounds>=5 AND unresolved_objections==0) OR max_rounds>=8)",
        "voting_method": "supermajority-2/3"
       },
       "id": "RISK-T2",
       "prose": "T2 material work adds a moderator, supermajority, and an objection-clear stop"
      },
      "T3": {
       "dials": {
        "protocol": "P10-mandated-devils-advocate",
        "roles": [
         "Architect",
         "Skeptic",
         "Pragmatist",
         "Critic",
         "Moderator",
         "DevilsAdvocate",
         "EvidenceClerk"
        ],
        "stopping_rule": "stop_if((max_rounds>=8 AND two_key_agree AND every_claim_has_citation) OR owner_halt)",
        "voting_method": "two-key"
       },
       "id": "RISK-T3",
       "prose": "T3 high-stakes work mandates a devil's advocate, two-key vote, and cited claims"
      },
      "T4": {
       "dials": {
        "protocol": "P58-owner-in-the-loop-stepwise",
        "roles": [
         "Architect",
         "Skeptic",
         "Pragmatist",
         "Critic",
         "Moderator",
         "DevilsAdvocate",
         "EvidenceClerk",
         "Owner"
        ],
        "stopping_rule": "stop_if(owner_explicit_accept); never auto-stop on consensus",
        "voting_method": "owner-ratify"
       },
       "id": "RISK-T4",
       "prose": "T4 irreversible work never auto-stops: the owner must ratify stepwise"
      }
     },
     "task_class_rules": [
      {
       "any_keywords": [
        "secret leak",
        "production",
        "ci logs",
        "contain the token",
        "outage",
        "sev-",
        "incident"
       ],
       "class": "incident",
       "id": "TC-incident",
       "prose": "incident-response language routes to the incident class"
      },
      {
       "any_keywords": [
        "safety interlock",
        "disable the safety",
        "two-key stop"
       ],
       "class": "safety",
       "id": "TC-safety",
       "prose": "safety-interlock language routes to the safety class"
      },
      {
       "any_keywords": [
        "budget ceiling",
        "irreversible",
        "unattended councils",
        "10x"
       ],
       "class": "irreversible",
       "id": "TC-irreversible",
       "prose": "irreversible-spend language routes to the irreversible class"
      },
      {
       "any_keywords": [
        "adjudicate",
        "silent-loss",
        "hand edit",
        "verdict"
       ],
       "class": "judicial",
       "id": "TC-judicial",
       "prose": "adjudication language routes to the judicial class"
      },
      {
       "any_keywords": [
        "control-plane",
        "load-order",
        "file set",
        "architecture",
        "before freeze"
       ],
       "class": "design",
       "id": "TC-design",
       "prose": "design-review language routes to the design class"
      },
      {
       "any_keywords": [
        "red-team",
        "silent default",
        "hide an override",
        "attack"
       ],
       "class": "adversarial",
       "id": "TC-adversarial",
       "prose": "red-team language routes to the adversarial class"
      },
      {
       "any_keywords": [
        "brainstorm",
        "names for",
        "idea count"
       ],
       "class": "generative",
       "id": "TC-generative",
       "prose": "brainstorm language routes to the generative class"
      },
      {
       "any_keywords": [
        "estimate hours",
        "forecast",
        "prediction"
       ],
       "class": "forecast",
       "id": "TC-forecast",
       "prose": "estimation language routes to the forecast class"
      },
      {
       "any_keywords": [
        "key assumption",
        "premortem",
        "competing hypothes"
       ],
       "class": "tradecraft",
       "id": "TC-tradecraft",
       "prose": "structured-analytic language routes to the tradecraft class"
      },
      {
       "any_keywords": [],
       "class": "general",
       "fallback": true,
       "id": "TC-general",
       "prose": "fallback class when no specialist keyword matched"
      }
     ]
    },
    "selector_version": "CNL-0013.v1",
    "stopping_rule": "stop_if((max_rounds>=5 AND unresolved_objections==0) OR max_rounds>=8)",
    "task_class": "design",
    "task_class_rule_id": "TC-design",
    "trace": [
     {
      "dials": {
       "protocol": "P45-scientific-peer-review",
       "roles": [
        "Architect",
        "Skeptic",
        "Pragmatist",
        "Critic",
        "Moderator"
       ],
       "stopping_rule": "stop_if((max_rounds>=5 AND unresolved_objections==0) OR max_rounds>=8)",
       "voting_method": "supermajority-2/3"
      },
      "prose": "T2 material work adds a moderator, supermajority, and an objection-clear stop",
      "rule_id": "RISK-T2"
     },
     {
      "dials": {
       "protocol": "P46-architecture-review-board"
      },
      "prose": "T2 design work uses the architecture-review-board protocol",
      "roles_add": [],
      "rule_id": "CLASS-T2-design"
     }
    ],
    "voting_method": "supermajority-2/3"
   },
   "id": "F05",
   "risk_tier": "T2",
   "task_class": "design",
   "task_description": "Review the A1 control-plane file set for load-order bugs before freeze."
  },
  {
   "explanation": {
    "dials": [
     {
      "contest": {
       "effect": "replaces this dial only; other auto-chosen dials stay unless also overridden",
       "override_key": "protocol"
      },
      "default": "P01-free-form-moderated-panel",
      "dial": "protocol",
      "differs_from_default": true,
      "reason": "rule CLASS-T2-adversarial set protocol=P10-mandated-devils-advocate (default=P01-free-form-moderated-panel): T2 adversarial work uses mandated devil's advocate",
      "rule_id": "CLASS-T2-adversarial",
      "value": "P10-mandated-devils-advocate"
     },
     {
      "contest": {
       "effect": "replaces this dial only; other auto-chosen dials stay unless also overridden",
       "override_key": "voting_method"
      },
      "default": "majority",
      "dial": "voting_method",
      "differs_from_default": true,
      "reason": "rule RISK-T2 set voting_method=supermajority-2/3 (default=majority): T2 material work adds a moderator, supermajority, and an objection-clear stop",
      "rule_id": "RISK-T2",
      "value": "supermajority-2/3"
     },
     {
      "contest": {
       "effect": "replaces this dial only; other auto-chosen dials stay unless also overridden",
       "override_key": "stopping_rule"
      },
      "default": "stop_if(max_rounds>=3 OR majority_reached)",
      "dial": "stopping_rule",
      "differs_from_default": true,
      "reason": "rule RISK-T2 set stopping_rule=stop_if((max_rounds>=5 AND unresolved_objections==0) OR max_rounds>=8) (default=stop_if(max_rounds>=3 OR majority_reached)): T2 material work adds a moderator, supermajority, and an objection-clear stop",
      "rule_id": "RISK-T2",
      "value": "stop_if((max_rounds>=5 AND unresolved_objections==0) OR max_rounds>=8)"
     },
     {
      "contest": {
       "effect": "replaces this dial only; other auto-chosen dials stay unless also overridden",
       "override_key": "roles"
      },
      "default": [
       "Architect",
       "Skeptic",
       "Pragmatist",
       "Critic"
      ],
      "dial": "roles",
      "differs_from_default": true,
      "reason": "rule CLASS-T2-adversarial set roles=['Architect', 'Skeptic', 'Pragmatist', 'Critic', 'Moderator', 'DevilsAdvocate'] (default=['Architect', 'Skeptic', 'Pragmatist', 'Critic']): T2 adversarial work uses mandated devil's advocate",
      "rule_id": "CLASS-T2-adversarial",
      "value": [
       "Architect",
       "Skeptic",
       "Pragmatist",
       "Critic",
       "Moderator",
       "DevilsAdvocate"
      ]
     }
    ],
    "inputs": {
     "risk_tier": "T2",
     "task_description": "Red-team the auto-composer so a silent default cannot hide an override."
    },
    "protocol": "P10-mandated-devils-advocate",
    "roster": [
     "Architect",
     "Skeptic",
     "Pragmatist",
     "Critic",
     "Moderator",
     "DevilsAdvocate"
    ],
    "rule_table": {
     "class_overlays": [
      {
       "dials": {
        "protocol": "P26-brainstorming-swarm",
        "voting_method": "approval"
       },
       "id": "CLASS-T1-generative",
       "prose": "T1 generative work uses the brainstorming swarm and an ideator seat",
       "risk_tier": "T1",
       "roles_add": [
        "Ideator"
       ],
       "task_class": "generative"
      },
      {
       "dials": {
        "protocol": "P46-architecture-review-board"
       },
       "id": "CLASS-T2-design",
       "prose": "T2 design work uses the architecture-review-board protocol",
       "risk_tier": "T2",
       "roles_add": [],
       "task_class": "design"
      },
      {
       "dials": {
        "protocol": "P10-mandated-devils-advocate"
       },
       "id": "CLASS-T2-adversarial",
       "prose": "T2 adversarial work uses mandated devil's advocate",
       "risk_tier": "T2",
       "roles_add": [
        "DevilsAdvocate"
       ],
       "task_class": "adversarial"
      },
      {
       "dials": {
        "protocol": "P33-prediction-tournament",
        "voting_method": "score-then-resolve"
       },
       "id": "CLASS-T2-forecast",
       "prose": "T2 forecast work uses a prediction tournament and score-then-resolve",
       "risk_tier": "T2",
       "roles_add": [],
       "task_class": "forecast"
      },
      {
       "dials": {
        "protocol": "P14-judge-and-jury"
       },
       "id": "CLASS-T3-judicial",
       "prose": "T3 judicial work uses judge-and-jury rather than a debate panel",
       "risk_tier": "T3",
       "roles_add": [],
       "task_class": "judicial"
      },
      {
       "dials": {
        "protocol": "P47-incident-war-room",
        "stopping_rule": "stop_if((containment_declared AND max_rounds>=6) OR owner_halt)"
       },
       "id": "CLASS-T3-incident",
       "prose": "T3 incident work uses the incident-war-room and a containment stop",
       "risk_tier": "T3",
       "roles_add": [],
       "task_class": "incident"
      },
      {
       "dials": {
        "protocol": "P39-key-assumptions-check"
       },
       "id": "CLASS-T3-tradecraft",
       "prose": "T3 tradecraft work uses the key-assumptions-check protocol",
       "risk_tier": "T3",
       "roles_add": [],
       "task_class": "tradecraft"
      },
      {
       "dials": {
        "protocol": "P18-two-key-dual-control"
       },
       "id": "CLASS-T4-safety",
       "prose": "T4 safety-interlock work adds two-key dual-control and a safety officer",
       "risk_tier": "T4",
       "roles_add": [
        "SafetyOfficer"
       ],
       "task_class": "safety"
      }
     ],
     "defaults": {
      "protocol": "P01-free-form-moderated-panel",
      "roles": [
       "Architect",
       "Skeptic",
       "Pragmatist",
       "Critic"
      ],
      "stopping_rule": "stop_if(max_rounds>=3 OR majority_reached)",
      "voting_method": "majority"
     },
     "dials": [
      "protocol",
      "voting_method",
      "stopping_rule",
      "roles"
     ],
     "risk_base": {
      "T0": {
       "dials": {
        "protocol": "P01-free-form-moderated-panel",
        "roles": [
         "Architect",
         "Pragmatist"
        ],
        "stopping_rule": "stop_if(max_rounds>=2 OR majority_reached)",
        "voting_method": "majority"
       },
       "id": "RISK-T0",
       "prose": "T0 informational work uses a two-seat panel and a short majority stop"
      },
      "T1": {
       "dials": {
        "protocol": "P01-free-form-moderated-panel",
        "roles": [
         "Architect",
         "Skeptic",
         "Pragmatist",
         "Critic"
        ],
        "stopping_rule": "stop_if(max_rounds>=3 OR majority_reached)",
        "voting_method": "majority"
       },
       "id": "RISK-T1",
       "prose": "T1 low-risk work keeps the four-voice default panel"
      },
      "T2": {
       "dials": {
        "protocol": "P45-scientific-peer-review",
        "roles": [
         "Architect",
         "Skeptic",
         "Pragmatist",
         "Critic",
         "Moderator"
        ],
        "stopping_rule": "stop_if((max_rounds>=5 AND unresolved_objections==0) OR max_rounds>=8)",
        "voting_method": "supermajority-2/3"
       },
       "id": "RISK-T2",
       "prose": "T2 material work adds a moderator, supermajority, and an objection-clear stop"
      },
      "T3": {
       "dials": {
        "protocol": "P10-mandated-devils-advocate",
        "roles": [
         "Architect",
         "Skeptic",
         "Pragmatist",
         "Critic",
         "Moderator",
         "DevilsAdvocate",
         "EvidenceClerk"
        ],
        "stopping_rule": "stop_if((max_rounds>=8 AND two_key_agree AND every_claim_has_citation) OR owner_halt)",
        "voting_method": "two-key"
       },
       "id": "RISK-T3",
       "prose": "T3 high-stakes work mandates a devil's advocate, two-key vote, and cited claims"
      },
      "T4": {
       "dials": {
        "protocol": "P58-owner-in-the-loop-stepwise",
        "roles": [
         "Architect",
         "Skeptic",
         "Pragmatist",
         "Critic",
         "Moderator",
         "DevilsAdvocate",
         "EvidenceClerk",
         "Owner"
        ],
        "stopping_rule": "stop_if(owner_explicit_accept); never auto-stop on consensus",
        "voting_method": "owner-ratify"
       },
       "id": "RISK-T4",
       "prose": "T4 irreversible work never auto-stops: the owner must ratify stepwise"
      }
     },
     "task_class_rules": [
      {
       "any_keywords": [
        "secret leak",
        "production",
        "ci logs",
        "contain the token",
        "outage",
        "sev-",
        "incident"
       ],
       "class": "incident",
       "id": "TC-incident",
       "prose": "incident-response language routes to the incident class"
      },
      {
       "any_keywords": [
        "safety interlock",
        "disable the safety",
        "two-key stop"
       ],
       "class": "safety",
       "id": "TC-safety",
       "prose": "safety-interlock language routes to the safety class"
      },
      {
       "any_keywords": [
        "budget ceiling",
        "irreversible",
        "unattended councils",
        "10x"
       ],
       "class": "irreversible",
       "id": "TC-irreversible",
       "prose": "irreversible-spend language routes to the irreversible class"
      },
      {
       "any_keywords": [
        "adjudicate",
        "silent-loss",
        "hand edit",
        "verdict"
       ],
       "class": "judicial",
       "id": "TC-judicial",
       "prose": "adjudication language routes to the judicial class"
      },
      {
       "any_keywords": [
        "control-plane",
        "load-order",
        "file set",
        "architecture",
        "before freeze"
       ],
       "class": "design",
       "id": "TC-design",
       "prose": "design-review language routes to the design class"
      },
      {
       "any_keywords": [
        "red-team",
        "silent default",
        "hide an override",
        "attack"
       ],
       "class": "adversarial",
       "id": "TC-adversarial",
       "prose": "red-team language routes to the adversarial class"
      },
      {
       "any_keywords": [
        "brainstorm",
        "names for",
        "idea count"
       ],
       "class": "generative",
       "id": "TC-generative",
       "prose": "brainstorm language routes to the generative class"
      },
      {
       "any_keywords": [
        "estimate hours",
        "forecast",
        "prediction"
       ],
       "class": "forecast",
       "id": "TC-forecast",
       "prose": "estimation language routes to the forecast class"
      },
      {
       "any_keywords": [
        "key assumption",
        "premortem",
        "competing hypothes"
       ],
       "class": "tradecraft",
       "id": "TC-tradecraft",
       "prose": "structured-analytic language routes to the tradecraft class"
      },
      {
       "any_keywords": [],
       "class": "general",
       "fallback": true,
       "id": "TC-general",
       "prose": "fallback class when no specialist keyword matched"
      }
     ]
    },
    "selector_version": "CNL-0013.v1",
    "stopping_rule": "stop_if((max_rounds>=5 AND unresolved_objections==0) OR max_rounds>=8)",
    "task_class": "adversarial",
    "task_class_rule_id": "TC-adversarial",
    "trace": [
     {
      "dials": {
       "protocol": "P45-scientific-peer-review",
       "roles": [
        "Architect",
        "Skeptic",
        "Pragmatist",
        "Critic",
        "Moderator"
       ],
       "stopping_rule": "stop_if((max_rounds>=5 AND unresolved_objections==0) OR max_rounds>=8)",
       "voting_method": "supermajority-2/3"
      },
      "prose": "T2 material work adds a moderator, supermajority, and an objection-clear stop",
      "rule_id": "RISK-T2"
     },
     {
      "dials": {
       "protocol": "P10-mandated-devils-advocate"
      },
      "prose": "T2 adversarial work uses mandated devil's advocate",
      "roles_add": [
       "DevilsAdvocate"
      ],
      "rule_id": "CLASS-T2-adversarial"
     }
    ],
    "voting_method": "supermajority-2/3"
   },
   "id": "F06",
   "risk_tier": "T2",
   "task_class": "adversarial",
   "task_description": "Red-team the auto-composer so a silent default cannot hide an override."
  },
  {
   "explanation": {
    "dials": [
     {
      "contest": {
       "effect": "replaces this dial only; other auto-chosen dials stay unless also overridden",
       "override_key": "protocol"
      },
      "default": "P01-free-form-moderated-panel",
      "dial": "protocol",
      "differs_from_default": true,
      "reason": "rule CLASS-T3-judicial set protocol=P14-judge-and-jury (default=P01-free-form-moderated-panel): T3 judicial work uses judge-and-jury rather than a debate panel",
      "rule_id": "CLASS-T3-judicial",
      "value": "P14-judge-and-jury"
     },
     {
      "contest": {
       "effect": "replaces this dial only; other auto-chosen dials stay unless also overridden",
       "override_key": "voting_method"
      },
      "default": "majority",
      "dial": "voting_method",
      "differs_from_default": true,
      "reason": "rule RISK-T3 set voting_method=two-key (default=majority): T3 high-stakes work mandates a devil's advocate, two-key vote, and cited claims",
      "rule_id": "RISK-T3",
      "value": "two-key"
     },
     {
      "contest": {
       "effect": "replaces this dial only; other auto-chosen dials stay unless also overridden",
       "override_key": "stopping_rule"
      },
      "default": "stop_if(max_rounds>=3 OR majority_reached)",
      "dial": "stopping_rule",
      "differs_from_default": true,
      "reason": "rule RISK-T3 set stopping_rule=stop_if((max_rounds>=8 AND two_key_agree AND every_claim_has_citation) OR owner_halt) (default=stop_if(max_rounds>=3 OR majority_reached)): T3 high-stakes work mandates a devil's advocate, two-key vote, and cited claims",
      "rule_id": "RISK-T3",
      "value": "stop_if((max_rounds>=8 AND two_key_agree AND every_claim_has_citation) OR owner_halt)"
     },
     {
      "contest": {
       "effect": "replaces this dial only; other auto-chosen dials stay unless also overridden",
       "override_key": "roles"
      },
      "default": [
       "Architect",
       "Skeptic",
       "Pragmatist",
       "Critic"
      ],
      "dial": "roles",
      "differs_from_default": true,
      "reason": "rule RISK-T3 set roles=['Architect', 'Skeptic', 'Pragmatist', 'Critic', 'Moderator', 'DevilsAdvocate', 'EvidenceClerk'] (default=['Architect', 'Skeptic', 'Pragmatist', 'Critic']): T3 high-stakes work mandates a devil's advocate, two-key vote, and cited claims",
      "rule_id": "RISK-T3",
      "value": [
       "Architect",
       "Skeptic",
       "Pragmatist",
       "Critic",
       "Moderator",
       "DevilsAdvocate",
       "EvidenceClerk"
      ]
     }
    ],
    "inputs": {
     "risk_tier": "T3",
     "task_description": "Adjudicate whether hatch capture-back is a silent-loss of a hand edit."
    },
    "protocol": "P14-judge-and-jury",
    "roster": [
     "Architect",
     "Skeptic",
     "Pragmatist",
     "Critic",
     "Moderator",
     "DevilsAdvocate",
     "EvidenceClerk"
    ],
    "rule_table": {
     "class_overlays": [
      {
       "dials": {
        "protocol": "P26-brainstorming-swarm",
        "voting_method": "approval"
       },
       "id": "CLASS-T1-generative",
       "prose": "T1 generative work uses the brainstorming swarm and an ideator seat",
       "risk_tier": "T1",
       "roles_add": [
        "Ideator"
       ],
       "task_class": "generative"
      },
      {
       "dials": {
        "protocol": "P46-architecture-review-board"
       },
       "id": "CLASS-T2-design",
       "prose": "T2 design work uses the architecture-review-board protocol",
       "risk_tier": "T2",
       "roles_add": [],
       "task_class": "design"
      },
      {
       "dials": {
        "protocol": "P10-mandated-devils-advocate"
       },
       "id": "CLASS-T2-adversarial",
       "prose": "T2 adversarial work uses mandated devil's advocate",
       "risk_tier": "T2",
       "roles_add": [
        "DevilsAdvocate"
       ],
       "task_class": "adversarial"
      },
      {
       "dials": {
        "protocol": "P33-prediction-tournament",
        "voting_method": "score-then-resolve"
       },
       "id": "CLASS-T2-forecast",
       "prose": "T2 forecast work uses a prediction tournament and score-then-resolve",
       "risk_tier": "T2",
       "roles_add": [],
       "task_class": "forecast"
      },
      {
       "dials": {
        "protocol": "P14-judge-and-jury"
       },
       "id": "CLASS-T3-judicial",
       "prose": "T3 judicial work uses judge-and-jury rather than a debate panel",
       "risk_tier": "T3",
       "roles_add": [],
       "task_class": "judicial"
      },
      {
       "dials": {
        "protocol": "P47-incident-war-room",
        "stopping_rule": "stop_if((containment_declared AND max_rounds>=6) OR owner_halt)"
       },
       "id": "CLASS-T3-incident",
       "prose": "T3 incident work uses the incident-war-room and a containment stop",
       "risk_tier": "T3",
       "roles_add": [],
       "task_class": "incident"
      },
      {
       "dials": {
        "protocol": "P39-key-assumptions-check"
       },
       "id": "CLASS-T3-tradecraft",
       "prose": "T3 tradecraft work uses the key-assumptions-check protocol",
       "risk_tier": "T3",
       "roles_add": [],
       "task_class": "tradecraft"
      },
      {
       "dials": {
        "protocol": "P18-two-key-dual-control"
       },
       "id": "CLASS-T4-safety",
       "prose": "T4 safety-interlock work adds two-key dual-control and a safety officer",
       "risk_tier": "T4",
       "roles_add": [
        "SafetyOfficer"
       ],
       "task_class": "safety"
      }
     ],
     "defaults": {
      "protocol": "P01-free-form-moderated-panel",
      "roles": [
       "Architect",
       "Skeptic",
       "Pragmatist",
       "Critic"
      ],
      "stopping_rule": "stop_if(max_rounds>=3 OR majority_reached)",
      "voting_method": "majority"
     },
     "dials": [
      "protocol",
      "voting_method",
      "stopping_rule",
      "roles"
     ],
     "risk_base": {
      "T0": {
       "dials": {
        "protocol": "P01-free-form-moderated-panel",
        "roles": [
         "Architect",
         "Pragmatist"
        ],
        "stopping_rule": "stop_if(max_rounds>=2 OR majority_reached)",
        "voting_method": "majority"
       },
       "id": "RISK-T0",
       "prose": "T0 informational work uses a two-seat panel and a short majority stop"
      },
      "T1": {
       "dials": {
        "protocol": "P01-free-form-moderated-panel",
        "roles": [
         "Architect",
         "Skeptic",
         "Pragmatist",
         "Critic"
        ],
        "stopping_rule": "stop_if(max_rounds>=3 OR majority_reached)",
        "voting_method": "majority"
       },
       "id": "RISK-T1",
       "prose": "T1 low-risk work keeps the four-voice default panel"
      },
      "T2": {
       "dials": {
        "protocol": "P45-scientific-peer-review",
        "roles": [
         "Architect",
         "Skeptic",
         "Pragmatist",
         "Critic",
         "Moderator"
        ],
        "stopping_rule": "stop_if((max_rounds>=5 AND unresolved_objections==0) OR max_rounds>=8)",
        "voting_method": "supermajority-2/3"
       },
       "id": "RISK-T2",
       "prose": "T2 material work adds a moderator, supermajority, and an objection-clear stop"
      },
      "T3": {
       "dials": {
        "protocol": "P10-mandated-devils-advocate",
        "roles": [
         "Architect",
         "Skeptic",
         "Pragmatist",
         "Critic",
         "Moderator",
         "DevilsAdvocate",
         "EvidenceClerk"
        ],
        "stopping_rule": "stop_if((max_rounds>=8 AND two_key_agree AND every_claim_has_citation) OR owner_halt)",
        "voting_method": "two-key"
       },
       "id": "RISK-T3",
       "prose": "T3 high-stakes work mandates a devil's advocate, two-key vote, and cited claims"
      },
      "T4": {
       "dials": {
        "protocol": "P58-owner-in-the-loop-stepwise",
        "roles": [
         "Architect",
         "Skeptic",
         "Pragmatist",
         "Critic",
         "Moderator",
         "DevilsAdvocate",
         "EvidenceClerk",
         "Owner"
        ],
        "stopping_rule": "stop_if(owner_explicit_accept); never auto-stop on consensus",
        "voting_method": "owner-ratify"
       },
       "id": "RISK-T4",
       "prose": "T4 irreversible work never auto-stops: the owner must ratify stepwise"
      }
     },
     "task_class_rules": [
      {
       "any_keywords": [
        "secret leak",
        "production",
        "ci logs",
        "contain the token",
        "outage",
        "sev-",
        "incident"
       ],
       "class": "incident",
       "id": "TC-incident",
       "prose": "incident-response language routes to the incident class"
      },
      {
       "any_keywords": [
        "safety interlock",
        "disable the safety",
        "two-key stop"
       ],
       "class": "safety",
       "id": "TC-safety",
       "prose": "safety-interlock language routes to the safety class"
      },
      {
       "any_keywords": [
        "budget ceiling",
        "irreversible",
        "unattended councils",
        "10x"
       ],
       "class": "irreversible",
       "id": "TC-irreversible",
       "prose": "irreversible-spend language routes to the irreversible class"
      },
      {
       "any_keywords": [
        "adjudicate",
        "silent-loss",
        "hand edit",
        "verdict"
       ],
       "class": "judicial",
       "id": "TC-judicial",
       "prose": "adjudication language routes to the judicial class"
      },
      {
       "any_keywords": [
        "control-plane",
        "load-order",
        "file set",
        "architecture",
        "before freeze"
       ],
       "class": "design",
       "id": "TC-design",
       "prose": "design-review language routes to the design class"
      },
      {
       "any_keywords": [
        "red-team",
        "silent default",
        "hide an override",
        "attack"
       ],
       "class": "adversarial",
       "id": "TC-adversarial",
       "prose": "red-team language routes to the adversarial class"
      },
      {
       "any_keywords": [
        "brainstorm",
        "names for",
        "idea count"
       ],
       "class": "generative",
       "id": "TC-generative",
       "prose": "brainstorm language routes to the generative class"
      },
      {
       "any_keywords": [
        "estimate hours",
        "forecast",
        "prediction"
       ],
       "class": "forecast",
       "id": "TC-forecast",
       "prose": "estimation language routes to the forecast class"
      },
      {
       "any_keywords": [
        "key assumption",
        "premortem",
        "competing hypothes"
       ],
       "class": "tradecraft",
       "id": "TC-tradecraft",
       "prose": "structured-analytic language routes to the tradecraft class"
      },
      {
       "any_keywords": [],
       "class": "general",
       "fallback": true,
       "id": "TC-general",
       "prose": "fallback class when no specialist keyword matched"
      }
     ]
    },
    "selector_version": "CNL-0013.v1",
    "stopping_rule": "stop_if((max_rounds>=8 AND two_key_agree AND every_claim_has_citation) OR owner_halt)",
    "task_class": "judicial",
    "task_class_rule_id": "TC-judicial",
    "trace": [
     {
      "dials": {
       "protocol": "P10-mandated-devils-advocate",
       "roles": [
        "Architect",
        "Skeptic",
        "Pragmatist",
        "Critic",
        "Moderator",
        "DevilsAdvocate",
        "EvidenceClerk"
       ],
       "stopping_rule": "stop_if((max_rounds>=8 AND two_key_agree AND every_claim_has_citation) OR owner_halt)",
       "voting_method": "two-key"
      },
      "prose": "T3 high-stakes work mandates a devil's advocate, two-key vote, and cited claims",
      "rule_id": "RISK-T3"
     },
     {
      "dials": {
       "protocol": "P14-judge-and-jury"
      },
      "prose": "T3 judicial work uses judge-and-jury rather than a debate panel",
      "roles_add": [],
      "rule_id": "CLASS-T3-judicial"
     }
    ],
    "voting_method": "two-key"
   },
   "id": "F07",
   "risk_tier": "T3",
   "task_class": "judicial",
   "task_description": "Adjudicate whether hatch capture-back is a silent-loss of a hand edit."
  },
  {
   "explanation": {
    "dials": [
     {
      "contest": {
       "effect": "replaces this dial only; other auto-chosen dials stay unless also overridden",
       "override_key": "protocol"
      },
      "default": "P01-free-form-moderated-panel",
      "dial": "protocol",
      "differs_from_default": true,
      "reason": "rule CLASS-T3-incident set protocol=P47-incident-war-room (default=P01-free-form-moderated-panel): T3 incident work uses the incident-war-room and a containment stop",
      "rule_id": "CLASS-T3-incident",
      "value": "P47-incident-war-room"
     },
     {
      "contest": {
       "effect": "replaces this dial only; other auto-chosen dials stay unless also overridden",
       "override_key": "voting_method"
      },
      "default": "majority",
      "dial": "voting_method",
      "differs_from_default": true,
      "reason": "rule RISK-T3 set voting_method=two-key (default=majority): T3 high-stakes work mandates a devil's advocate, two-key vote, and cited claims",
      "rule_id": "RISK-T3",
      "value": "two-key"
     },
     {
      "contest": {
       "effect": "replaces this dial only; other auto-chosen dials stay unless also overridden",
       "override_key": "stopping_rule"
      },
      "default": "stop_if(max_rounds>=3 OR majority_reached)",
      "dial": "stopping_rule",
      "differs_from_default": true,
      "reason": "rule CLASS-T3-incident set stopping_rule=stop_if((containment_declared AND max_rounds>=6) OR owner_halt) (default=stop_if(max_rounds>=3 OR majority_reached)): T3 incident work uses the incident-war-room and a containment stop",
      "rule_id": "CLASS-T3-incident",
      "value": "stop_if((containment_declared AND max_rounds>=6) OR owner_halt)"
     },
     {
      "contest": {
       "effect": "replaces this dial only; other auto-chosen dials stay unless also overridden",
       "override_key": "roles"
      },
      "default": [
       "Architect",
       "Skeptic",
       "Pragmatist",
       "Critic"
      ],
      "dial": "roles",
      "differs_from_default": true,
      "reason": "rule RISK-T3 set roles=['Architect', 'Skeptic', 'Pragmatist', 'Critic', 'Moderator', 'DevilsAdvocate', 'EvidenceClerk'] (default=['Architect', 'Skeptic', 'Pragmatist', 'Critic']): T3 high-stakes work mandates a devil's advocate, two-key vote, and cited claims",
      "rule_id": "RISK-T3",
      "value": [
       "Architect",
       "Skeptic",
       "Pragmatist",
       "Critic",
       "Moderator",
       "DevilsAdvocate",
       "EvidenceClerk"
      ]
     }
    ],
    "inputs": {
     "risk_tier": "T3",
     "task_description": "Triage a production secret leak in CI logs and contain the token."
    },
    "protocol": "P47-incident-war-room",
    "roster": [
     "Architect",
     "Skeptic",
     "Pragmatist",
     "Critic",
     "Moderator",
     "DevilsAdvocate",
     "EvidenceClerk"
    ],
    "rule_table": {
     "class_overlays": [
      {
       "dials": {
        "protocol": "P26-brainstorming-swarm",
        "voting_method": "approval"
       },
       "id": "CLASS-T1-generative",
       "prose": "T1 generative work uses the brainstorming swarm and an ideator seat",
       "risk_tier": "T1",
       "roles_add": [
        "Ideator"
       ],
       "task_class": "generative"
      },
      {
       "dials": {
        "protocol": "P46-architecture-review-board"
       },
       "id": "CLASS-T2-design",
       "prose": "T2 design work uses the architecture-review-board protocol",
       "risk_tier": "T2",
       "roles_add": [],
       "task_class": "design"
      },
      {
       "dials": {
        "protocol": "P10-mandated-devils-advocate"
       },
       "id": "CLASS-T2-adversarial",
       "prose": "T2 adversarial work uses mandated devil's advocate",
       "risk_tier": "T2",
       "roles_add": [
        "DevilsAdvocate"
       ],
       "task_class": "adversarial"
      },
      {
       "dials": {
        "protocol": "P33-prediction-tournament",
        "voting_method": "score-then-resolve"
       },
       "id": "CLASS-T2-forecast",
       "prose": "T2 forecast work uses a prediction tournament and score-then-resolve",
       "risk_tier": "T2",
       "roles_add": [],
       "task_class": "forecast"
      },
      {
       "dials": {
        "protocol": "P14-judge-and-jury"
       },
       "id": "CLASS-T3-judicial",
       "prose": "T3 judicial work uses judge-and-jury rather than a debate panel",
       "risk_tier": "T3",
       "roles_add": [],
       "task_class": "judicial"
      },
      {
       "dials": {
        "protocol": "P47-incident-war-room",
        "stopping_rule": "stop_if((containment_declared AND max_rounds>=6) OR owner_halt)"
       },
       "id": "CLASS-T3-incident",
       "prose": "T3 incident work uses the incident-war-room and a containment stop",
       "risk_tier": "T3",
       "roles_add": [],
       "task_class": "incident"
      },
      {
       "dials": {
        "protocol": "P39-key-assumptions-check"
       },
       "id": "CLASS-T3-tradecraft",
       "prose": "T3 tradecraft work uses the key-assumptions-check protocol",
       "risk_tier": "T3",
       "roles_add": [],
       "task_class": "tradecraft"
      },
      {
       "dials": {
        "protocol": "P18-two-key-dual-control"
       },
       "id": "CLASS-T4-safety",
       "prose": "T4 safety-interlock work adds two-key dual-control and a safety officer",
       "risk_tier": "T4",
       "roles_add": [
        "SafetyOfficer"
       ],
       "task_class": "safety"
      }
     ],
     "defaults": {
      "protocol": "P01-free-form-moderated-panel",
      "roles": [
       "Architect",
       "Skeptic",
       "Pragmatist",
       "Critic"
      ],
      "stopping_rule": "stop_if(max_rounds>=3 OR majority_reached)",
      "voting_method": "majority"
     },
     "dials": [
      "protocol",
      "voting_method",
      "stopping_rule",
      "roles"
     ],
     "risk_base": {
      "T0": {
       "dials": {
        "protocol": "P01-free-form-moderated-panel",
        "roles": [
         "Architect",
         "Pragmatist"
        ],
        "stopping_rule": "stop_if(max_rounds>=2 OR majority_reached)",
        "voting_method": "majority"
       },
       "id": "RISK-T0",
       "prose": "T0 informational work uses a two-seat panel and a short majority stop"
      },
      "T1": {
       "dials": {
        "protocol": "P01-free-form-moderated-panel",
        "roles": [
         "Architect",
         "Skeptic",
         "Pragmatist",
         "Critic"
        ],
        "stopping_rule": "stop_if(max_rounds>=3 OR majority_reached)",
        "voting_method": "majority"
       },
       "id": "RISK-T1",
       "prose": "T1 low-risk work keeps the four-voice default panel"
      },
      "T2": {
       "dials": {
        "protocol": "P45-scientific-peer-review",
        "roles": [
         "Architect",
         "Skeptic",
         "Pragmatist",
         "Critic",
         "Moderator"
        ],
        "stopping_rule": "stop_if((max_rounds>=5 AND unresolved_objections==0) OR max_rounds>=8)",
        "voting_method": "supermajority-2/3"
       },
       "id": "RISK-T2",
       "prose": "T2 material work adds a moderator, supermajority, and an objection-clear stop"
      },
      "T3": {
       "dials": {
        "protocol": "P10-mandated-devils-advocate",
        "roles": [
         "Architect",
         "Skeptic",
         "Pragmatist",
         "Critic",
         "Moderator",
         "DevilsAdvocate",
         "EvidenceClerk"
        ],
        "stopping_rule": "stop_if((max_rounds>=8 AND two_key_agree AND every_claim_has_citation) OR owner_halt)",
        "voting_method": "two-key"
       },
       "id": "RISK-T3",
       "prose": "T3 high-stakes work mandates a devil's advocate, two-key vote, and cited claims"
      },
      "T4": {
       "dials": {
        "protocol": "P58-owner-in-the-loop-stepwise",
        "roles": [
         "Architect",
         "Skeptic",
         "Pragmatist",
         "Critic",
         "Moderator",
         "DevilsAdvocate",
         "EvidenceClerk",
         "Owner"
        ],
        "stopping_rule": "stop_if(owner_explicit_accept); never auto-stop on consensus",
        "voting_method": "owner-ratify"
       },
       "id": "RISK-T4",
       "prose": "T4 irreversible work never auto-stops: the owner must ratify stepwise"
      }
     },
     "task_class_rules": [
      {
       "any_keywords": [
        "secret leak",
        "production",
        "ci logs",
        "contain the token",
        "outage",
        "sev-",
        "incident"
       ],
       "class": "incident",
       "id": "TC-incident",
       "prose": "incident-response language routes to the incident class"
      },
      {
       "any_keywords": [
        "safety interlock",
        "disable the safety",
        "two-key stop"
       ],
       "class": "safety",
       "id": "TC-safety",
       "prose": "safety-interlock language routes to the safety class"
      },
      {
       "any_keywords": [
        "budget ceiling",
        "irreversible",
        "unattended councils",
        "10x"
       ],
       "class": "irreversible",
       "id": "TC-irreversible",
       "prose": "irreversible-spend language routes to the irreversible class"
      },
      {
       "any_keywords": [
        "adjudicate",
        "silent-loss",
        "hand edit",
        "verdict"
       ],
       "class": "judicial",
       "id": "TC-judicial",
       "prose": "adjudication language routes to the judicial class"
      },
      {
       "any_keywords": [
        "control-plane",
        "load-order",
        "file set",
        "architecture",
        "before freeze"
       ],
       "class": "design",
       "id": "TC-design",
       "prose": "design-review language routes to the design class"
      },
      {
       "any_keywords": [
        "red-team",
        "silent default",
        "hide an override",
        "attack"
       ],
       "class": "adversarial",
       "id": "TC-adversarial",
       "prose": "red-team language routes to the adversarial class"
      },
      {
       "any_keywords": [
        "brainstorm",
        "names for",
        "idea count"
       ],
       "class": "generative",
       "id": "TC-generative",
       "prose": "brainstorm language routes to the generative class"
      },
      {
       "any_keywords": [
        "estimate hours",
        "forecast",
        "prediction"
       ],
       "class": "forecast",
       "id": "TC-forecast",
       "prose": "estimation language routes to the forecast class"
      },
      {
       "any_keywords": [
        "key assumption",
        "premortem",
        "competing hypothes"
       ],
       "class": "tradecraft",
       "id": "TC-tradecraft",
       "prose": "structured-analytic language routes to the tradecraft class"
      },
      {
       "any_keywords": [],
       "class": "general",
       "fallback": true,
       "id": "TC-general",
       "prose": "fallback class when no specialist keyword matched"
      }
     ]
    },
    "selector_version": "CNL-0013.v1",
    "stopping_rule": "stop_if((containment_declared AND max_rounds>=6) OR owner_halt)",
    "task_class": "incident",
    "task_class_rule_id": "TC-incident",
    "trace": [
     {
      "dials": {
       "protocol": "P10-mandated-devils-advocate",
       "roles": [
        "Architect",
        "Skeptic",
        "Pragmatist",
        "Critic",
        "Moderator",
        "DevilsAdvocate",
        "EvidenceClerk"
       ],
       "stopping_rule": "stop_if((max_rounds>=8 AND two_key_agree AND every_claim_has_citation) OR owner_halt)",
       "voting_method": "two-key"
      },
      "prose": "T3 high-stakes work mandates a devil's advocate, two-key vote, and cited claims",
      "rule_id": "RISK-T3"
     },
     {
      "dials": {
       "protocol": "P47-incident-war-room",
       "stopping_rule": "stop_if((containment_declared AND max_rounds>=6) OR owner_halt)"
      },
      "prose": "T3 incident work uses the incident-war-room and a containment stop",
      "roles_add": [],
      "rule_id": "CLASS-T3-incident"
     }
    ],
    "voting_method": "two-key"
   },
   "id": "F08",
   "risk_tier": "T3",
   "task_class": "incident",
   "task_description": "Triage a production secret leak in CI logs and contain the token."
  },
  {
   "explanation": {
    "dials": [
     {
      "contest": {
       "effect": "replaces this dial only; other auto-chosen dials stay unless also overridden",
       "override_key": "protocol"
      },
      "default": "P01-free-form-moderated-panel",
      "dial": "protocol",
      "differs_from_default": true,
      "reason": "rule RISK-T4 set protocol=P58-owner-in-the-loop-stepwise (default=P01-free-form-moderated-panel): T4 irreversible work never auto-stops: the owner must ratify stepwise",
      "rule_id": "RISK-T4",
      "value": "P58-owner-in-the-loop-stepwise"
     },
     {
      "contest": {
       "effect": "replaces this dial only; other auto-chosen dials stay unless also overridden",
       "override_key": "voting_method"
      },
      "default": "majority",
      "dial": "voting_method",
      "differs_from_default": true,
      "reason": "rule RISK-T4 set voting_method=owner-ratify (default=majority): T4 irreversible work never auto-stops: the owner must ratify stepwise",
      "rule_id": "RISK-T4",
      "value": "owner-ratify"
     },
     {
      "contest": {
       "effect": "replaces this dial only; other auto-chosen dials stay unless also overridden",
       "override_key": "stopping_rule"
      },
      "default": "stop_if(max_rounds>=3 OR majority_reached)",
      "dial": "stopping_rule",
      "differs_from_default": true,
      "reason": "rule RISK-T4 set stopping_rule=stop_if(owner_explicit_accept); never auto-stop on consensus (default=stop_if(max_rounds>=3 OR majority_reached)): T4 irreversible work never auto-stops: the owner must ratify stepwise",
      "rule_id": "RISK-T4",
      "value": "stop_if(owner_explicit_accept); never auto-stop on consensus"
     },
     {
      "contest": {
       "effect": "replaces this dial only; other auto-chosen dials stay unless also overridden",
       "override_key": "roles"
      },
      "default": [
       "Architect",
       "Skeptic",
       "Pragmatist",
       "Critic"
      ],
      "dial": "roles",
      "differs_from_default": true,
      "reason": "rule RISK-T4 set roles=['Architect', 'Skeptic', 'Pragmatist', 'Critic', 'Moderator', 'DevilsAdvocate', 'EvidenceClerk', 'Owner'] (default=['Architect', 'Skeptic', 'Pragmatist', 'Critic']): T4 irreversible work never auto-stops: the owner must ratify stepwise",
      "rule_id": "RISK-T4",
      "value": [
       "Architect",
       "Skeptic",
       "Pragmatist",
       "Critic",
       "Moderator",
       "DevilsAdvocate",
       "EvidenceClerk",
       "Owner"
      ]
     }
    ],
    "inputs": {
     "risk_tier": "T4",
     "task_description": "Raise the owner token budget ceiling by 10x for unattended councils."
    },
    "protocol": "P58-owner-in-the-loop-stepwise",
    "roster": [
     "Architect",
     "Skeptic",
     "Pragmatist",
     "Critic",
     "Moderator",
     "DevilsAdvocate",
     "EvidenceClerk",
     "Owner"
    ],
    "rule_table": {
     "class_overlays": [
      {
       "dials": {
        "protocol": "P26-brainstorming-swarm",
        "voting_method": "approval"
       },
       "id": "CLASS-T1-generative",
       "prose": "T1 generative work uses the brainstorming swarm and an ideator seat",
       "risk_tier": "T1",
       "roles_add": [
        "Ideator"
       ],
       "task_class": "generative"
      },
      {
       "dials": {
        "protocol": "P46-architecture-review-board"
       },
       "id": "CLASS-T2-design",
       "prose": "T2 design work uses the architecture-review-board protocol",
       "risk_tier": "T2",
       "roles_add": [],
       "task_class": "design"
      },
      {
       "dials": {
        "protocol": "P10-mandated-devils-advocate"
       },
       "id": "CLASS-T2-adversarial",
       "prose": "T2 adversarial work uses mandated devil's advocate",
       "risk_tier": "T2",
       "roles_add": [
        "DevilsAdvocate"
       ],
       "task_class": "adversarial"
      },
      {
       "dials": {
        "protocol": "P33-prediction-tournament",
        "voting_method": "score-then-resolve"
       },
       "id": "CLASS-T2-forecast",
       "prose": "T2 forecast work uses a prediction tournament and score-then-resolve",
       "risk_tier": "T2",
       "roles_add": [],
       "task_class": "forecast"
      },
      {
       "dials": {
        "protocol": "P14-judge-and-jury"
       },
       "id": "CLASS-T3-judicial",
       "prose": "T3 judicial work uses judge-and-jury rather than a debate panel",
       "risk_tier": "T3",
       "roles_add": [],
       "task_class": "judicial"
      },
      {
       "dials": {
        "protocol": "P47-incident-war-room",
        "stopping_rule": "stop_if((containment_declared AND max_rounds>=6) OR owner_halt)"
       },
       "id": "CLASS-T3-incident",
       "prose": "T3 incident work uses the incident-war-room and a containment stop",
       "risk_tier": "T3",
       "roles_add": [],
       "task_class": "incident"
      },
      {
       "dials": {
        "protocol": "P39-key-assumptions-check"
       },
       "id": "CLASS-T3-tradecraft",
       "prose": "T3 tradecraft work uses the key-assumptions-check protocol",
       "risk_tier": "T3",
       "roles_add": [],
       "task_class": "tradecraft"
      },
      {
       "dials": {
        "protocol": "P18-two-key-dual-control"
       },
       "id": "CLASS-T4-safety",
       "prose": "T4 safety-interlock work adds two-key dual-control and a safety officer",
       "risk_tier": "T4",
       "roles_add": [
        "SafetyOfficer"
       ],
       "task_class": "safety"
      }
     ],
     "defaults": {
      "protocol": "P01-free-form-moderated-panel",
      "roles": [
       "Architect",
       "Skeptic",
       "Pragmatist",
       "Critic"
      ],
      "stopping_rule": "stop_if(max_rounds>=3 OR majority_reached)",
      "voting_method": "majority"
     },
     "dials": [
      "protocol",
      "voting_method",
      "stopping_rule",
      "roles"
     ],
     "risk_base": {
      "T0": {
       "dials": {
        "protocol": "P01-free-form-moderated-panel",
        "roles": [
         "Architect",
         "Pragmatist"
        ],
        "stopping_rule": "stop_if(max_rounds>=2 OR majority_reached)",
        "voting_method": "majority"
       },
       "id": "RISK-T0",
       "prose": "T0 informational work uses a two-seat panel and a short majority stop"
      },
      "T1": {
       "dials": {
        "protocol": "P01-free-form-moderated-panel",
        "roles": [
         "Architect",
         "Skeptic",
         "Pragmatist",
         "Critic"
        ],
        "stopping_rule": "stop_if(max_rounds>=3 OR majority_reached)",
        "voting_method": "majority"
       },
       "id": "RISK-T1",
       "prose": "T1 low-risk work keeps the four-voice default panel"
      },
      "T2": {
       "dials": {
        "protocol": "P45-scientific-peer-review",
        "roles": [
         "Architect",
         "Skeptic",
         "Pragmatist",
         "Critic",
         "Moderator"
        ],
        "stopping_rule": "stop_if((max_rounds>=5 AND unresolved_objections==0) OR max_rounds>=8)",
        "voting_method": "supermajority-2/3"
       },
       "id": "RISK-T2",
       "prose": "T2 material work adds a moderator, supermajority, and an objection-clear stop"
      },
      "T3": {
       "dials": {
        "protocol": "P10-mandated-devils-advocate",
        "roles": [
         "Architect",
         "Skeptic",
         "Pragmatist",
         "Critic",
         "Moderator",
         "DevilsAdvocate",
         "EvidenceClerk"
        ],
        "stopping_rule": "stop_if((max_rounds>=8 AND two_key_agree AND every_claim_has_citation) OR owner_halt)",
        "voting_method": "two-key"
       },
       "id": "RISK-T3",
       "prose": "T3 high-stakes work mandates a devil's advocate, two-key vote, and cited claims"
      },
      "T4": {
       "dials": {
        "protocol": "P58-owner-in-the-loop-stepwise",
        "roles": [
         "Architect",
         "Skeptic",
         "Pragmatist",
         "Critic",
         "Moderator",
         "DevilsAdvocate",
         "EvidenceClerk",
         "Owner"
        ],
        "stopping_rule": "stop_if(owner_explicit_accept); never auto-stop on consensus",
        "voting_method": "owner-ratify"
       },
       "id": "RISK-T4",
       "prose": "T4 irreversible work never auto-stops: the owner must ratify stepwise"
      }
     },
     "task_class_rules": [
      {
       "any_keywords": [
        "secret leak",
        "production",
        "ci logs",
        "contain the token",
        "outage",
        "sev-",
        "incident"
       ],
       "class": "incident",
       "id": "TC-incident",
       "prose": "incident-response language routes to the incident class"
      },
      {
       "any_keywords": [
        "safety interlock",
        "disable the safety",
        "two-key stop"
       ],
       "class": "safety",
       "id": "TC-safety",
       "prose": "safety-interlock language routes to the safety class"
      },
      {
       "any_keywords": [
        "budget ceiling",
        "irreversible",
        "unattended councils",
        "10x"
       ],
       "class": "irreversible",
       "id": "TC-irreversible",
       "prose": "irreversible-spend language routes to the irreversible class"
      },
      {
       "any_keywords": [
        "adjudicate",
        "silent-loss",
        "hand edit",
        "verdict"
       ],
       "class": "judicial",
       "id": "TC-judicial",
       "prose": "adjudication language routes to the judicial class"
      },
      {
       "any_keywords": [
        "control-plane",
        "load-order",
        "file set",
        "architecture",
        "before freeze"
       ],
       "class": "design",
       "id": "TC-design",
       "prose": "design-review language routes to the design class"
      },
      {
       "any_keywords": [
        "red-team",
        "silent default",
        "hide an override",
        "attack"
       ],
       "class": "adversarial",
       "id": "TC-adversarial",
       "prose": "red-team language routes to the adversarial class"
      },
      {
       "any_keywords": [
        "brainstorm",
        "names for",
        "idea count"
       ],
       "class": "generative",
       "id": "TC-generative",
       "prose": "brainstorm language routes to the generative class"
      },
      {
       "any_keywords": [
        "estimate hours",
        "forecast",
        "prediction"
       ],
       "class": "forecast",
       "id": "TC-forecast",
       "prose": "estimation language routes to the forecast class"
      },
      {
       "any_keywords": [
        "key assumption",
        "premortem",
        "competing hypothes"
       ],
       "class": "tradecraft",
       "id": "TC-tradecraft",
       "prose": "structured-analytic language routes to the tradecraft class"
      },
      {
       "any_keywords": [],
       "class": "general",
       "fallback": true,
       "id": "TC-general",
       "prose": "fallback class when no specialist keyword matched"
      }
     ]
    },
    "selector_version": "CNL-0013.v1",
    "stopping_rule": "stop_if(owner_explicit_accept); never auto-stop on consensus",
    "task_class": "irreversible",
    "task_class_rule_id": "TC-irreversible",
    "trace": [
     {
      "dials": {
       "protocol": "P58-owner-in-the-loop-stepwise",
       "roles": [
        "Architect",
        "Skeptic",
        "Pragmatist",
        "Critic",
        "Moderator",
        "DevilsAdvocate",
        "EvidenceClerk",
        "Owner"
       ],
       "stopping_rule": "stop_if(owner_explicit_accept); never auto-stop on consensus",
       "voting_method": "owner-ratify"
      },
      "prose": "T4 irreversible work never auto-stops: the owner must ratify stepwise",
      "rule_id": "RISK-T4"
     }
    ],
    "voting_method": "owner-ratify"
   },
   "id": "F09",
   "risk_tier": "T4",
   "task_class": "irreversible",
   "task_description": "Raise the owner token budget ceiling by 10x for unattended councils."
  },
  {
   "explanation": {
    "dials": [
     {
      "contest": {
       "effect": "replaces this dial only; other auto-chosen dials stay unless also overridden",
       "override_key": "protocol"
      },
      "default": "P01-free-form-moderated-panel",
      "dial": "protocol",
      "differs_from_default": true,
      "reason": "rule CLASS-T4-safety set protocol=P18-two-key-dual-control (default=P01-free-form-moderated-panel): T4 safety-interlock work adds two-key dual-control and a safety officer",
      "rule_id": "CLASS-T4-safety",
      "value": "P18-two-key-dual-control"
     },
     {
      "contest": {
       "effect": "replaces this dial only; other auto-chosen dials stay unless also overridden",
       "override_key": "voting_method"
      },
      "default": "majority",
      "dial": "voting_method",
      "differs_from_default": true,
      "reason": "rule RISK-T4 set voting_method=owner-ratify (default=majority): T4 irreversible work never auto-stops: the owner must ratify stepwise",
      "rule_id": "RISK-T4",
      "value": "owner-ratify"
     },
     {
      "contest": {
       "effect": "replaces this dial only; other auto-chosen dials stay unless also overridden",
       "override_key": "stopping_rule"
      },
      "default": "stop_if(max_rounds>=3 OR majority_reached)",
      "dial": "stopping_rule",
      "differs_from_default": true,
      "reason": "rule RISK-T4 set stopping_rule=stop_if(owner_explicit_accept); never auto-stop on consensus (default=stop_if(max_rounds>=3 OR majority_reached)): T4 irreversible work never auto-stops: the owner must ratify stepwise",
      "rule_id": "RISK-T4",
      "value": "stop_if(owner_explicit_accept); never auto-stop on consensus"
     },
     {
      "contest": {
       "effect": "replaces this dial only; other auto-chosen dials stay unless also overridden",
       "override_key": "roles"
      },
      "default": [
       "Architect",
       "Skeptic",
       "Pragmatist",
       "Critic"
      ],
      "dial": "roles",
      "differs_from_default": true,
      "reason": "rule CLASS-T4-safety set roles=['Architect', 'Skeptic', 'Pragmatist', 'Critic', 'Moderator', 'DevilsAdvocate', 'EvidenceClerk', 'Owner', 'SafetyOfficer'] (default=['Architect', 'Skeptic', 'Pragmatist', 'Critic']): T4 safety-interlock work adds two-key dual-control and a safety officer",
      "rule_id": "CLASS-T4-safety",
      "value": [
       "Architect",
       "Skeptic",
       "Pragmatist",
       "Critic",
       "Moderator",
       "DevilsAdvocate",
       "EvidenceClerk",
       "Owner",
       "SafetyOfficer"
      ]
     }
    ],
    "inputs": {
     "risk_tier": "T4",
     "task_description": "Disable the safety interlock that blocks owner-override of two-key stop."
    },
    "protocol": "P18-two-key-dual-control",
    "roster": [
     "Architect",
     "Skeptic",
     "Pragmatist",
     "Critic",
     "Moderator",
     "DevilsAdvocate",
     "EvidenceClerk",
     "Owner",
     "SafetyOfficer"
    ],
    "rule_table": {
     "class_overlays": [
      {
       "dials": {
        "protocol": "P26-brainstorming-swarm",
        "voting_method": "approval"
       },
       "id": "CLASS-T1-generative",
       "prose": "T1 generative work uses the brainstorming swarm and an ideator seat",
       "risk_tier": "T1",
       "roles_add": [
        "Ideator"
       ],
       "task_class": "generative"
      },
      {
       "dials": {
        "protocol": "P46-architecture-review-board"
       },
       "id": "CLASS-T2-design",
       "prose": "T2 design work uses the architecture-review-board protocol",
       "risk_tier": "T2",
       "roles_add": [],
       "task_class": "design"
      },
      {
       "dials": {
        "protocol": "P10-mandated-devils-advocate"
       },
       "id": "CLASS-T2-adversarial",
       "prose": "T2 adversarial work uses mandated devil's advocate",
       "risk_tier": "T2",
       "roles_add": [
        "DevilsAdvocate"
       ],
       "task_class": "adversarial"
      },
      {
       "dials": {
        "protocol": "P33-prediction-tournament",
        "voting_method": "score-then-resolve"
       },
       "id": "CLASS-T2-forecast",
       "prose": "T2 forecast work uses a prediction tournament and score-then-resolve",
       "risk_tier": "T2",
       "roles_add": [],
       "task_class": "forecast"
      },
      {
       "dials": {
        "protocol": "P14-judge-and-jury"
       },
       "id": "CLASS-T3-judicial",
       "prose": "T3 judicial work uses judge-and-jury rather than a debate panel",
       "risk_tier": "T3",
       "roles_add": [],
       "task_class": "judicial"
      },
      {
       "dials": {
        "protocol": "P47-incident-war-room",
        "stopping_rule": "stop_if((containment_declared AND max_rounds>=6) OR owner_halt)"
       },
       "id": "CLASS-T3-incident",
       "prose": "T3 incident work uses the incident-war-room and a containment stop",
       "risk_tier": "T3",
       "roles_add": [],
       "task_class": "incident"
      },
      {
       "dials": {
        "protocol": "P39-key-assumptions-check"
       },
       "id": "CLASS-T3-tradecraft",
       "prose": "T3 tradecraft work uses the key-assumptions-check protocol",
       "risk_tier": "T3",
       "roles_add": [],
       "task_class": "tradecraft"
      },
      {
       "dials": {
        "protocol": "P18-two-key-dual-control"
       },
       "id": "CLASS-T4-safety",
       "prose": "T4 safety-interlock work adds two-key dual-control and a safety officer",
       "risk_tier": "T4",
       "roles_add": [
        "SafetyOfficer"
       ],
       "task_class": "safety"
      }
     ],
     "defaults": {
      "protocol": "P01-free-form-moderated-panel",
      "roles": [
       "Architect",
       "Skeptic",
       "Pragmatist",
       "Critic"
      ],
      "stopping_rule": "stop_if(max_rounds>=3 OR majority_reached)",
      "voting_method": "majority"
     },
     "dials": [
      "protocol",
      "voting_method",
      "stopping_rule",
      "roles"
     ],
     "risk_base": {
      "T0": {
       "dials": {
        "protocol": "P01-free-form-moderated-panel",
        "roles": [
         "Architect",
         "Pragmatist"
        ],
        "stopping_rule": "stop_if(max_rounds>=2 OR majority_reached)",
        "voting_method": "majority"
       },
       "id": "RISK-T0",
       "prose": "T0 informational work uses a two-seat panel and a short majority stop"
      },
      "T1": {
       "dials": {
        "protocol": "P01-free-form-moderated-panel",
        "roles": [
         "Architect",
         "Skeptic",
         "Pragmatist",
         "Critic"
        ],
        "stopping_rule": "stop_if(max_rounds>=3 OR majority_reached)",
        "voting_method": "majority"
       },
       "id": "RISK-T1",
       "prose": "T1 low-risk work keeps the four-voice default panel"
      },
      "T2": {
       "dials": {
        "protocol": "P45-scientific-peer-review",
        "roles": [
         "Architect",
         "Skeptic",
         "Pragmatist",
         "Critic",
         "Moderator"
        ],
        "stopping_rule": "stop_if((max_rounds>=5 AND unresolved_objections==0) OR max_rounds>=8)",
        "voting_method": "supermajority-2/3"
       },
       "id": "RISK-T2",
       "prose": "T2 material work adds a moderator, supermajority, and an objection-clear stop"
      },
      "T3": {
       "dials": {
        "protocol": "P10-mandated-devils-advocate",
        "roles": [
         "Architect",
         "Skeptic",
         "Pragmatist",
         "Critic",
         "Moderator",
         "DevilsAdvocate",
         "EvidenceClerk"
        ],
        "stopping_rule": "stop_if((max_rounds>=8 AND two_key_agree AND every_claim_has_citation) OR owner_halt)",
        "voting_method": "two-key"
       },
       "id": "RISK-T3",
       "prose": "T3 high-stakes work mandates a devil's advocate, two-key vote, and cited claims"
      },
      "T4": {
       "dials": {
        "protocol": "P58-owner-in-the-loop-stepwise",
        "roles": [
         "Architect",
         "Skeptic",
         "Pragmatist",
         "Critic",
         "Moderator",
         "DevilsAdvocate",
         "EvidenceClerk",
         "Owner"
        ],
        "stopping_rule": "stop_if(owner_explicit_accept); never auto-stop on consensus",
        "voting_method": "owner-ratify"
       },
       "id": "RISK-T4",
       "prose": "T4 irreversible work never auto-stops: the owner must ratify stepwise"
      }
     },
     "task_class_rules": [
      {
       "any_keywords": [
        "secret leak",
        "production",
        "ci logs",
        "contain the token",
        "outage",
        "sev-",
        "incident"
       ],
       "class": "incident",
       "id": "TC-incident",
       "prose": "incident-response language routes to the incident class"
      },
      {
       "any_keywords": [
        "safety interlock",
        "disable the safety",
        "two-key stop"
       ],
       "class": "safety",
       "id": "TC-safety",
       "prose": "safety-interlock language routes to the safety class"
      },
      {
       "any_keywords": [
        "budget ceiling",
        "irreversible",
        "unattended councils",
        "10x"
       ],
       "class": "irreversible",
       "id": "TC-irreversible",
       "prose": "irreversible-spend language routes to the irreversible class"
      },
      {
       "any_keywords": [
        "adjudicate",
        "silent-loss",
        "hand edit",
        "verdict"
       ],
       "class": "judicial",
       "id": "TC-judicial",
       "prose": "adjudication language routes to the judicial class"
      },
      {
       "any_keywords": [
        "control-plane",
        "load-order",
        "file set",
        "architecture",
        "before freeze"
       ],
       "class": "design",
       "id": "TC-design",
       "prose": "design-review language routes to the design class"
      },
      {
       "any_keywords": [
        "red-team",
        "silent default",
        "hide an override",
        "attack"
       ],
       "class": "adversarial",
       "id": "TC-adversarial",
       "prose": "red-team language routes to the adversarial class"
      },
      {
       "any_keywords": [
        "brainstorm",
        "names for",
        "idea count"
       ],
       "class": "generative",
       "id": "TC-generative",
       "prose": "brainstorm language routes to the generative class"
      },
      {
       "any_keywords": [
        "estimate hours",
        "forecast",
        "prediction"
       ],
       "class": "forecast",
       "id": "TC-forecast",
       "prose": "estimation language routes to the forecast class"
      },
      {
       "any_keywords": [
        "key assumption",
        "premortem",
        "competing hypothes"
       ],
       "class": "tradecraft",
       "id": "TC-tradecraft",
       "prose": "structured-analytic language routes to the tradecraft class"
      },
      {
       "any_keywords": [],
       "class": "general",
       "fallback": true,
       "id": "TC-general",
       "prose": "fallback class when no specialist keyword matched"
      }
     ]
    },
    "selector_version": "CNL-0013.v1",
    "stopping_rule": "stop_if(owner_explicit_accept); never auto-stop on consensus",
    "task_class": "safety",
    "task_class_rule_id": "TC-safety",
    "trace": [
     {
      "dials": {
       "protocol": "P58-owner-in-the-loop-stepwise",
       "roles": [
        "Architect",
        "Skeptic",
        "Pragmatist",
        "Critic",
        "Moderator",
        "DevilsAdvocate",
        "EvidenceClerk",
        "Owner"
       ],
       "stopping_rule": "stop_if(owner_explicit_accept); never auto-stop on consensus",
       "voting_method": "owner-ratify"
      },
      "prose": "T4 irreversible work never auto-stops: the owner must ratify stepwise",
      "rule_id": "RISK-T4"
     },
     {
      "dials": {
       "protocol": "P18-two-key-dual-control"
      },
      "prose": "T4 safety-interlock work adds two-key dual-control and a safety officer",
      "roles_add": [
       "SafetyOfficer"
      ],
      "rule_id": "CLASS-T4-safety"
     }
    ],
    "voting_method": "owner-ratify"
   },
   "id": "F10",
   "risk_tier": "T4",
   "task_class": "safety",
   "task_description": "Disable the safety interlock that blocks owner-override of two-key stop."
  }
 ],
 "min_bytes_threshold": 2048,
 "named_probes": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0013/probe1_ten_fixtures.py",
   "id": "probe1"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0013/probe2_completeness_negative.py",
   "id": "probe2"
  }
 ],
 "negative_controls": [
  {
   "fires_on_bad": true,
   "id": "CNL0013-C1",
   "rejects": "A composition whose protocol differs from default and whose reason is empty. Verbatim live errors: [\"missing-reason:protocol\"]",
   "silent_on_good": true
  }
 ],
 "produced_by": {
  "execution_substrate": "headless-linux",
  "model": "grok-4.6",
  "role": "council-systems-designer",
  "vendor": "xai"
 },
 "question": "Given only a task description and a risk tier, what algorithm selects roles, protocol, voting method and stopping rule - and what is the explanation record that makes every auto-chosen dial individually contestable by the owner rather than a black-box roster?",
 "report": {
  "control_ids": [
   "CNL0013-C1"
  ],
  "kind": "council-design-note",
  "observations": [
   {
    "anchor": "command-center/p2-wave/probes/CNL-0013/reconstruct.py",
    "measured": true,
    "method": "reconstruct.matches on selector.select for FIXTURES F01-F10 without calling select during reconstruct",
    "name": "ten-fixture-reconstruct"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0013/completeness.py",
    "measured": true,
    "method": "missing_reasons(plant_missing_reason(F05))",
    "name": "completeness-fires-on-planted-empty-reason"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0013/completeness.py",
    "measured": true,
    "method": "missing_reasons(F05 explanation)",
    "name": "completeness-silent-on-known-good-F05"
   }
  ]
 },
 "residual_unknowns": [
  {
   "claim": "Verbatim bytes of _USER-PROMPTS.md:10765 and the 58 protocol bodies in 12-COUNCIL-PROTOCOLS-AND-PRESETS.json.",
   "verdict": "NOT-CHECKED"
  }
 ],
 "reviewer": {
  "independent": true,
  "reviewer_id": "CNL-0013-probe1-reconstruct",
  "verdict": "PASS"
 },
 "rule_table": {
  "class_overlays": [
   {
    "dials": {
     "protocol": "P26-brainstorming-swarm",
     "voting_method": "approval"
    },
    "id": "CLASS-T1-generative",
    "prose": "T1 generative work uses the brainstorming swarm and an ideator seat",
    "risk_tier": "T1",
    "roles_add": [
     "Ideator"
    ],
    "task_class": "generative"
   },
   {
    "dials": {
     "protocol": "P46-architecture-review-board"
    },
    "id": "CLASS-T2-design",
    "prose": "T2 design work uses the architecture-review-board protocol",
    "risk_tier": "T2",
    "roles_add": [],
    "task_class": "design"
   },
   {
    "dials": {
     "protocol": "P10-mandated-devils-advocate"
    },
    "id": "CLASS-T2-adversarial",
    "prose": "T2 adversarial work uses mandated devil's advocate",
    "risk_tier": "T2",
    "roles_add": [
     "DevilsAdvocate"
    ],
    "task_class": "adversarial"
   },
   {
    "dials": {
     "protocol": "P33-prediction-tournament",
     "voting_method": "score-then-resolve"
    },
    "id": "CLASS-T2-forecast",
    "prose": "T2 forecast work uses a prediction tournament and score-then-resolve",
    "risk_tier": "T2",
    "roles_add": [],
    "task_class": "forecast"
   },
   {
    "dials": {
     "protocol": "P14-judge-and-jury"
    },
    "id": "CLASS-T3-judicial",
    "prose": "T3 judicial work uses judge-and-jury rather than a debate panel",
    "risk_tier": "T3",
    "roles_add": [],
    "task_class": "judicial"
   },
   {
    "dials": {
     "protocol": "P47-incident-war-room",
     "stopping_rule": "stop_if((containment_declared AND max_rounds>=6) OR owner_halt)"
    },
    "id": "CLASS-T3-incident",
    "prose": "T3 incident work uses the incident-war-room and a containment stop",
    "risk_tier": "T3",
    "roles_add": [],
    "task_class": "incident"
   },
   {
    "dials": {
     "protocol": "P39-key-assumptions-check"
    },
    "id": "CLASS-T3-tradecraft",
    "prose": "T3 tradecraft work uses the key-assumptions-check protocol",
    "risk_tier": "T3",
    "roles_add": [],
    "task_class": "tradecraft"
   },
   {
    "dials": {
     "protocol": "P18-two-key-dual-control"
    },
    "id": "CLASS-T4-safety",
    "prose": "T4 safety-interlock work adds two-key dual-control and a safety officer",
    "risk_tier": "T4",
    "roles_add": [
     "SafetyOfficer"
    ],
    "task_class": "safety"
   }
  ],
  "defaults": {
   "protocol": "P01-free-form-moderated-panel",
   "roles": [
    "Architect",
    "Skeptic",
    "Pragmatist",
    "Critic"
   ],
   "stopping_rule": "stop_if(max_rounds>=3 OR majority_reached)",
   "voting_method": "majority"
  },
  "dials": [
   "protocol",
   "voting_method",
   "stopping_rule",
   "roles"
  ],
  "risk_base": {
   "T0": {
    "dials": {
     "protocol": "P01-free-form-moderated-panel",
     "roles": [
      "Architect",
      "Pragmatist"
     ],
     "stopping_rule": "stop_if(max_rounds>=2 OR majority_reached)",
     "voting_method": "majority"
    },
    "id": "RISK-T0",
    "prose": "T0 informational work uses a two-seat panel and a short majority stop"
   },
   "T1": {
    "dials": {
     "protocol": "P01-free-form-moderated-panel",
     "roles": [
      "Architect",
      "Skeptic",
      "Pragmatist",
      "Critic"
     ],
     "stopping_rule": "stop_if(max_rounds>=3 OR majority_reached)",
     "voting_method": "majority"
    },
    "id": "RISK-T1",
    "prose": "T1 low-risk work keeps the four-voice default panel"
   },
   "T2": {
    "dials": {
     "protocol": "P45-scientific-peer-review",
     "roles": [
      "Architect",
      "Skeptic",
      "Pragmatist",
      "Critic",
      "Moderator"
     ],
     "stopping_rule": "stop_if((max_rounds>=5 AND unresolved_objections==0) OR max_rounds>=8)",
     "voting_method": "supermajority-2/3"
    },
    "id": "RISK-T2",
    "prose": "T2 material work adds a moderator, supermajority, and an objection-clear stop"
   },
   "T3": {
    "dials": {
     "protocol": "P10-mandated-devils-advocate",
     "roles": [
      "Architect",
      "Skeptic",
      "Pragmatist",
      "Critic",
      "Moderator",
      "DevilsAdvocate",
      "EvidenceClerk"
     ],
     "stopping_rule": "stop_if((max_rounds>=8 AND two_key_agree AND every_claim_has_citation) OR owner_halt)",
     "voting_method": "two-key"
    },
    "id": "RISK-T3",
    "prose": "T3 high-stakes work mandates a devil's advocate, two-key vote, and cited claims"
   },
   "T4": {
    "dials": {
     "protocol": "P58-owner-in-the-loop-stepwise",
     "roles": [
      "Architect",
      "Skeptic",
      "Pragmatist",
      "Critic",
      "Moderator",
      "DevilsAdvocate",
      "EvidenceClerk",
      "Owner"
     ],
     "stopping_rule": "stop_if(owner_explicit_accept); never auto-stop on consensus",
     "voting_method": "owner-ratify"
    },
    "id": "RISK-T4",
    "prose": "T4 irreversible work never auto-stops: the owner must ratify stepwise"
   }
  },
  "task_class_rules": [
   {
    "any_keywords": [
     "secret leak",
     "production",
     "ci logs",
     "contain the token",
     "outage",
     "sev-",
     "incident"
    ],
    "class": "incident",
    "id": "TC-incident",
    "prose": "incident-response language routes to the incident class"
   },
   {
    "any_keywords": [
     "safety interlock",
     "disable the safety",
     "two-key stop"
    ],
    "class": "safety",
    "id": "TC-safety",
    "prose": "safety-interlock language routes to the safety class"
   },
   {
    "any_keywords": [
     "budget ceiling",
     "irreversible",
     "unattended councils",
     "10x"
    ],
    "class": "irreversible",
    "id": "TC-irreversible",
    "prose": "irreversible-spend language routes to the irreversible class"
   },
   {
    "any_keywords": [
     "adjudicate",
     "silent-loss",
     "hand edit",
     "verdict"
    ],
    "class": "judicial",
    "id": "TC-judicial",
    "prose": "adjudication language routes to the judicial class"
   },
   {
    "any_keywords": [
     "control-plane",
     "load-order",
     "file set",
     "architecture",
     "before freeze"
    ],
    "class": "design",
    "id": "TC-design",
    "prose": "design-review language routes to the design class"
   },
   {
    "any_keywords": [
     "red-team",
     "silent default",
     "hide an override",
     "attack"
    ],
    "class": "adversarial",
    "id": "TC-adversarial",
    "prose": "red-team language routes to the adversarial class"
   },
   {
    "any_keywords": [
     "brainstorm",
     "names for",
     "idea count"
    ],
    "class": "generative",
    "id": "TC-generative",
    "prose": "brainstorm language routes to the generative class"
   },
   {
    "any_keywords": [
     "estimate hours",
     "forecast",
     "prediction"
    ],
    "class": "forecast",
    "id": "TC-forecast",
    "prose": "estimation language routes to the forecast class"
   },
   {
    "any_keywords": [
     "key assumption",
     "premortem",
     "competing hypothes"
    ],
    "class": "tradecraft",
    "id": "TC-tradecraft",
    "prose": "structured-analytic language routes to the tradecraft class"
   },
   {
    "any_keywords": [],
    "class": "general",
    "fallback": true,
    "id": "TC-general",
    "prose": "fallback class when no specialist keyword matched"
   }
  ]
 },
 "schema_version": 1,
 "sentinel": "SUCCESS:CNL-0013",
 "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:34931",
 "state": "SUCCESS",
 "tests": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0013/probe1_ten_fixtures.py",
   "id": "T1-ten-fixtures-reconstruct",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0013/probe2_completeness_negative.py",
   "id": "T2-completeness-negative",
   "result": "PASS"
  }
 ],
 "timestamps": {
  "ended_at": "2026-08-25T00:56:37Z"
 },
 "title": "Auto-composed council: the selector and its mandatory explanation record",
 "unit_id": "CNL-0013"
}
