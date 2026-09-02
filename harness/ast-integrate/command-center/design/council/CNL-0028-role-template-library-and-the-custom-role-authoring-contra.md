{
 "artifacts": [
  {
   "bytes": 1,
   "eol": "LF",
   "exists": true,
   "path": "command-center/design/council/CNL-0028-role-template-library-and-the-custom-role-authoring-contra.md",
   "role": "primary",
   "sha256": "f8f60cad943a9fedd5c546ca020e2f0920f0a6075d10f6e7a4299e9ea93288eb"
  },
  {
   "bytes": 1118,
   "eol": "LF",
   "exists": true,
   "path": "command-center/schema/council-design-note.schema.json",
   "role": "supporting",
   "sha256": "e66edc40156c6abcad6b2e27d5e6ebc32a37e72559967fa1fc3ce53e5b245755"
  },
  {
   "bytes": 7327,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0028/protocols.json",
   "role": "fixture",
   "sha256": "af648b47f3968fa1666956c93592827f4fabbb5e458206dbdfb419e8f8fb115c"
  },
  {
   "bytes": 5314,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0028/templates.json",
   "role": "fixture",
   "sha256": "3b49ee7b89b34a15ccdd0bba355c64ee921ec07ac9c6e7fde293dd9a0c5a1b6e"
  },
  {
   "bytes": 2621,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0028/coverage.py",
   "role": "supporting",
   "sha256": "916acc73c730b948b4b52fed397f73ab1dc0c45ac94a6d3279fb7a1272035d85"
  },
  {
   "bytes": 4748,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0028/authoring.py",
   "role": "supporting",
   "sha256": "5a314c0bf03c0bf347554842da1f47db06ca5b34e19a7aa7aba0df82c43c793a"
  },
  {
   "bytes": 1074,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0028/catalog_pids.py",
   "role": "supporting",
   "sha256": "7de106e8cc8ba503ab163f1f7d544caeb289b18e5fe234f72a1891e85980d429"
  },
  {
   "bytes": 2486,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0028/probe1_coverage.py",
   "role": "control",
   "sha256": "dc6b38f2195c69f167b8d911ffa36510e911464ab25ae7affd55d704e86b038b"
  },
  {
   "bytes": 4390,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0028/probe2_reviewer.py",
   "role": "control",
   "sha256": "fee6cf1e3826031670984b62cede79d15ac9fa0721ab5e1e0d92e263d8e9d352"
  }
 ],
 "downstream_consumers": [
  {
   "artifact_path": "command-center/design/council/CNL-0028-role-template-library-and-the-custom-role-authoring-contra.md",
   "consumer": "jsonschema.Draft7Validator council-design-note (disk $ref)",
   "executed": true,
   "exit_code": 0,
   "probe": {
    "command": "python3 -B command-center/p2-wave/probes/CNL-0028/emit_note.py",
    "exit_code": 0,
    "fingerprint": "fdb542db4ae21ebfa3ad1c6804bacb12",
    "method": "schema-validate",
    "raw_output": "schema_errors=0 validator_vacuous=false",
    "role": "verifier"
   },
   "read_ok": true
  }
 ],
 "evidence": [
  {
   "anchor": "command-center/p2-wave/probes/CNL-0028/coverage.py:31",
   "claim": "Every role named across the 58 catalog-cited protocol records maps to one of 11 templates; ablating any template leaves a named role unmapped.",
   "confidence": "almost-certain",
   "probes": [
    {
     "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0028/probe1_coverage.py",
     "exit_code": 0,
     "fingerprint": "4f6e78898186db090d077e68d2da124b",
     "method": "test-run",
     "raw_output": "protocol_n=58 unique_ids=58 template_n=11 unmapped=[] minimum_holds=True library_on_tree=False planted_wizard_unmapped=[\"wizard\"]",
     "role": "source"
    },
    {
     "command": "python3 -B command-center/p2-wave/probes/CNL-0028/catalog_pids.py",
     "exit_code": 0,
     "fingerprint": "81ff38c6a055076ceeec9312f4d390fb",
     "method": "file-read",
     "raw_output": "catalog_n=58 ids=[\"P01\", \"P02\", \"P03\", \"P04\", \"P05\", \"P06\", \"P07\", \"P08\", \"P09\", \"P10\", \"P11\", \"P12\", \"P13\", \"P14\", \"P15\", \"P16\", \"P17\", \"P18\", \"P19\", \"P20\", \"P21\", \"P22\", \"P23\", \"P24\", \"P25\", \"P26\", \"P27\", \"P28\", \"P29\", \"P30\", \"P31\", \"P32\", \"P33\", \"P34\", \"P35\", \"P36\", \"P37\", \"P38\", \"P39\", \"P40\", \"P41\", \"P42\", \"P43\", \"P44\", \"P45\", \"P46\", \"P47\", \"P48\", \"P49\", \"P50\", \"P51\", \"P52\", \"P53\", \"P54\", \"P55\", \"P56\", \"P57\", \"P58\"]",
     "role": "verifier"
    }
   ],
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0028/authoring.py:44",
   "claim": "check_custom_role rejects authors\u2229judges (SELF_JUDGE), missing capabilities, and rights outside the template union, and accepts a critic-extending custom role.",
   "confidence": "almost-certain",
   "probes": [
    {
     "command": "python3 -c import authoring; authoring.check_custom_role",
     "exit_code": 0,
     "fingerprint": "94f4c5d1a3df19a2f7e60cda0c653a84",
     "method": "static-analysis",
     "raw_output": "good_accepted=True self_judge=[\"SELF_JUDGE\"] missing=[\"MISSING_CAPABILITIES\", \"MISSING_CAPABILITIES\"] escalate=[\"RIGHTS_ESCALATION\"]",
     "role": "source"
    },
    {
     "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0028/probe2_reviewer.py",
     "exit_code": 0,
     "fingerprint": "399cc95f8896cb156f07ef1b8bd3713a",
     "method": "command",
     "raw_output": "good_accepted=True self_judge=[\"SELF_JUDGE\"] missing=[\"MISSING_CAPABILITIES\", \"MISSING_CAPABILITIES\"] escalate=[\"RIGHTS_ESCALATION\"]",
     "role": "verifier"
    }
   ],
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0028/protocols.json",
   "claim": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json was read from disk on this worktree and supplied the 58 role lists.",
   "confidence": "almost-certain",
   "probes": [
    {
     "command": "test -f 12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
     "exit_code": 0,
     "fingerprint": "4675f9a4083d443d30e5966961f2f254",
     "method": "file-read",
     "raw_output": "present=False",
     "role": "source"
    },
    {
     "command": "python3 -c Path('12-COUNCIL-PROTOCOLS-AND-PRESETS.json').is_file()",
     "exit_code": 0,
     "fingerprint": "d3395b0df98c86e48bcfbc02d59d897d",
     "method": "other",
     "raw_output": "library_file_on_this_tree=False",
     "role": "verifier"
    }
   ],
   "verdict": "REFUTED"
  }
 ],
 "manifest_registration": {
  "manifest_path": "command-center/p2-wave/probes/CNL-0028/UNIT-ARTIFACT-MANIFEST.json",
  "registered": true
 },
 "min_bytes_threshold": 4096,
 "negative_controls": [
  {
   "bad_state_output": "covered=False unmapped=[\"wizard\"]",
   "description": "Protocol role 'wizard' with no template and no explicit gap must be unmapped; the known-good 58-record census must have unmapped=[]",
   "fired_on_bad_state": true,
   "good_state_output": "covered=True unmapped=[]",
   "id": "unmapped-wizard",
   "kind": "known-broken-fixture",
   "silent_on_good_state": true
  },
  {
   "bad_state_output": "accepted=False codes=[\"SELF_JUDGE\"]",
   "description": "Custom role with authors=['proposal'] and judges=['proposal'] must be rejected; a critic-extending custom role must be accepted",
   "fired_on_bad_state": true,
   "good_state_output": "accepted=True codes=[]",
   "id": "self-judge-custom",
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
  "aliases": {
   "architect": "proposer",
   "blue": "proposer",
   "devils-advocate": "critic",
   "editor": "chair",
   "facilitator": "chair",
   "foreperson": "chair",
   "moderator": "chair",
   "opposition": "critic",
   "pragmatist": "synthesiser",
   "proposition": "proposer",
   "questioner": "critic",
   "red": "critic",
   "respondent": "proposer",
   "scribe": "clerk",
   "skeptic": "critic",
   "timekeeper": "chair"
  },
  "answer": "Minimum covering set is 11 templates: chair, clerk, critic, estimator, judge, juror, observer, owner, proposer, scorer, synthesiser. Ablation of any one template leaves at least one named protocol role unmapped, so the set is minimal under this census. 12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent on this worktree; the 58 records are the catalog-cited P01-P58 identities from CNL-0038..CNL-0046, with roles assigned from the CNL-0022/0025/0026/0027 vocabulary plus protocol-forced seats (observer, estimator, clerk, scorer, owner). A custom role is reasoner-visible iff it supplies id, nonempty obligations, permissions, rights, and the eight capability fields (authors, judges, votes_on, may_speak, may_vote, may_veto, may_chair, may_synthesise). The checker rejects self-judging (authors \u2229 judges), synthesiser-drift (may_synthesise and authors contains proposal), chair substance votes without a casting_vote right, and rights not in the template-right union. SUCCESS:CNL-0028",
  "claims": [
   {
    "anchor": "command-center/p2-wave/probes/CNL-0028/protocols.json",
    "claim": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json was read from disk on this worktree and supplied the 58 role lists.",
    "id": "C1",
    "verdict": "REFUTED"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0028/coverage.py:31",
    "claim": "Every role named across the 58 catalog-cited protocol records maps to one of 11 templates; the set is minimal by ablation.",
    "id": "C2",
    "verdict": "CONFIRMED"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0028/catalog_pids.py:14",
    "claim": "The 58 fixture ids are the same 58 P-ids named in CNL-0038..CNL-0046 catalog questions.",
    "id": "C3",
    "verdict": "CONFIRMED"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0028/authoring.py:44",
    "claim": "A custom role that authors and judges the same artifact kind is accepted by the authoring checker.",
    "id": "C4",
    "verdict": "REFUTED"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0028/authoring.py:good_custom_role",
    "claim": "A custom role that supplies the required capability vector and does not self-judge is accepted.",
    "id": "C5",
    "verdict": "CONFIRMED"
   }
  ],
  "control_ids": [
   "unmapped-wizard",
   "self-judge-custom"
  ],
  "custom_role_authoring_contract": {
   "good_role_accepted": true,
   "missing_capabilities_rejected": true,
   "rejection_codes": [
    "SELF_JUDGE",
    "MISSING_CAPABILITIES",
    "RIGHTS_ESCALATION",
    "SYNTHESISER_DRIFT",
    "CHAIR_SUBSTANCE_VOTE",
    "EMPTY_OBLIGATIONS"
   ],
   "required_capabilities": [
    "authors",
    "judges",
    "votes_on",
    "may_speak",
    "may_vote",
    "may_veto",
    "may_chair",
    "may_synthesise"
   ],
   "required_fields": [
    "id",
    "obligations",
    "permissions",
    "rights",
    "capabilities"
   ],
   "rights_escalation_rejected": true,
   "self_judge_rejected": true
  },
  "kind": "council-design-note",
  "library_honesty": {
   "census_basis": "Catalog CNL-0038..CNL-0046 question_or_target P-ids. Role lists are assigned from sibling CNL role vocabulary (CNL-0022/0025/0026/0027) plus protocol-forced seats. This is not a byte copy of 12-COUNCIL-PROTOCOLS-AND-PRESETS.json, which is absent.",
   "path": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
   "present_on_this_tree": false
  },
  "minimum_templates": {
   "ablation_unmapped": {
    "chair": [
     "chair"
    ],
    "clerk": [
     "clerk"
    ],
    "critic": [
     "critic"
    ],
    "estimator": [
     "estimator"
    ],
    "judge": [
     "judge"
    ],
    "juror": [
     "juror"
    ],
    "observer": [
     "observer"
    ],
    "owner": [
     "owner"
    ],
    "proposer": [
     "proposer"
    ],
    "scorer": [
     "scorer"
    ],
    "synthesiser": [
     "synthesiser"
    ]
   },
   "explicit_gaps": [],
   "ids": [
    "chair",
    "clerk",
    "critic",
    "estimator",
    "judge",
    "juror",
    "observer",
    "owner",
    "proposer",
    "scorer",
    "synthesiser"
   ],
   "minimum_holds": true,
   "n": 11,
   "named_roles": [
    "chair",
    "clerk",
    "critic",
    "estimator",
    "judge",
    "juror",
    "observer",
    "owner",
    "proposer",
    "scorer",
    "synthesiser"
   ]
  },
  "observations": [
   {
    "anchor": "command-center/p2-wave/probes/CNL-0028/protocols.json",
    "measured": 58,
    "method": "len(protocols.json records)",
    "name": "protocol_n"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0028/coverage.py:31",
    "measured": 11,
    "method": "ablation of each template against named roles",
    "name": "template_n_minimum"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0028/catalog_pids.py:14",
    "measured": 58,
    "method": "regex P(\\d{2}) over CNL-0038..CNL-0046 questions",
    "name": "catalog_pid_n"
   },
   {
    "anchor": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    "measured": false,
    "method": "Path.is_file",
    "name": "library_file_on_this_tree"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0028/authoring.py:44",
    "measured": true,
    "method": "check_custom_role authors\u2229judges",
    "name": "self_judge_rejected"
   }
  ],
  "protocol_coverage": {
   "catalog_ids": [
    "P01",
    "P02",
    "P03",
    "P04",
    "P05",
    "P06",
    "P07",
    "P08",
    "P09",
    "P10",
    "P11",
    "P12",
    "P13",
    "P14",
    "P15",
    "P16",
    "P17",
    "P18",
    "P19",
    "P20",
    "P21",
    "P22",
    "P23",
    "P24",
    "P25",
    "P26",
    "P27",
    "P28",
    "P29",
    "P30",
    "P31",
    "P32",
    "P33",
    "P34",
    "P35",
    "P36",
    "P37",
    "P38",
    "P39",
    "P40",
    "P41",
    "P42",
    "P43",
    "P44",
    "P45",
    "P46",
    "P47",
    "P48",
    "P49",
    "P50",
    "P51",
    "P52",
    "P53",
    "P54",
    "P55",
    "P56",
    "P57",
    "P58"
   ],
   "catalog_n": 58,
   "covered": true,
   "family_counts": {
    "ADVERSARIAL": 7,
    "ANONYMOUS": 6,
    "DELIBERATIVE": 6,
    "ENGINEERING-REVIEW": 7,
    "FORECASTING": 5,
    "GENERATIVE": 7,
    "JUDICIAL": 6,
    "META-COMPOSITION": 7,
    "TRADECRAFT": 7
   },
   "protocol_n": 58,
   "unmapped": []
  },
  "question": "What is the minimum set of role templates that covers the 58 catalogued protocols, and what must a user supply to author a custom role that the incompatible-role checker can still reason about?",
  "templates": {
   "chair": {
    "capabilities": {
     "authors": [
      "agenda"
     ],
     "judges": [
      "procedure"
     ],
     "may_chair": true,
     "may_speak": true,
     "may_synthesise": false,
     "may_veto": false,
     "may_vote": false,
     "votes_on": []
    },
    "obligations": [
     "allocate_turns",
     "keep_agenda"
    ],
    "permissions": [
     "recognise_speaker",
     "extend_round"
    ],
    "rights": [
     "procedure_voice_cannot_be_stripped"
    ]
   },
   "clerk": {
    "capabilities": {
     "authors": [
      "evidence_record"
     ],
     "judges": [],
     "may_chair": false,
     "may_speak": true,
     "may_synthesise": false,
     "may_veto": false,
     "may_vote": false,
     "votes_on": []
    },
    "obligations": [
     "custody_of_evidence_record"
    ],
    "permissions": [
     "flag_missing_exhibit"
    ],
    "rights": [
     "cannot_be_asked_to_rule"
    ]
   },
   "critic": {
    "capabilities": {
     "authors": [
      "objection"
     ],
     "judges": [],
     "may_chair": false,
     "may_speak": true,
     "may_synthesise": false,
     "may_veto": false,
     "may_vote": true,
     "votes_on": [
      "proposal",
      "objection"
     ]
    },
    "obligations": [
     "produce_objection"
    ],
    "permissions": [
     "demand_evidence",
     "cross_examine"
    ],
    "rights": [
     "objection_must_be_recorded"
    ]
   },
   "estimator": {
    "capabilities": {
     "authors": [
      "estimate"
     ],
     "judges": [],
     "may_chair": false,
     "may_speak": false,
     "may_synthesise": false,
     "may_veto": false,
     "may_vote": false,
     "votes_on": []
    },
    "obligations": [
     "produce_estimate_or_forecast"
    ],
    "permissions": [
     "revise_after_feedback_round"
    ],
    "rights": [
     "anonymity_until_declared_lift_point"
    ]
   },
   "judge": {
    "capabilities": {
     "authors": [
      "ruling"
     ],
     "judges": [
      "proposal",
      "evidence"
     ],
     "may_chair": false,
     "may_speak": true,
     "may_synthesise": false,
     "may_veto": false,
     "may_vote": false,
     "votes_on": []
    },
    "obligations": [
     "rule_admissibility",
     "issue_ruling"
    ],
    "permissions": [
     "exclude_evidence"
    ],
    "rights": [
     "ruling_must_cite_a_critique_or_standard"
    ]
   },
   "juror": {
    "capabilities": {
     "authors": [],
     "judges": [
      "proposal"
     ],
     "may_chair": false,
     "may_speak": true,
     "may_synthesise": false,
     "may_veto": false,
     "may_vote": true,
     "votes_on": [
      "proposal"
     ]
    },
    "obligations": [
     "decide_merits"
    ],
    "permissions": [
     "ask_clarifying_question"
    ],
    "rights": [
     "hung_verdict_is_representable"
    ]
   },
   "observer": {
    "capabilities": {
     "authors": [],
     "judges": [],
     "may_chair": false,
     "may_speak": false,
     "may_synthesise": false,
     "may_veto": false,
     "may_vote": false,
     "votes_on": []
    },
    "obligations": [
     "remain_silent_until_invited"
    ],
    "permissions": [
     "take_notes"
    ],
    "rights": [
     "cannot_be_counted_as_a_vote"
    ]
   },
   "owner": {
    "capabilities": {
     "authors": [],
     "judges": [
      "step"
     ],
     "may_chair": false,
     "may_speak": true,
     "may_synthesise": false,
     "may_veto": true,
     "may_vote": true,
     "votes_on": [
      "step"
     ]
    },
    "obligations": [
     "approve_or_reject_each_step"
    ],
    "permissions": [
     "pause_resume"
    ],
    "rights": [
     "stepwise_approval_cannot_be_stripped"
    ]
   },
   "proposer": {
    "capabilities": {
     "authors": [
      "proposal"
     ],
     "judges": [],
     "may_chair": false,
     "may_speak": true,
     "may_synthesise": false,
     "may_veto": false,
     "may_vote": true,
     "votes_on": [
      "proposal",
      "objection"
     ]
    },
    "obligations": [
     "produce_proposal"
    ],
    "permissions": [
     "cite_evidence",
     "revise_proposal"
    ],
    "rights": [
     "must_be_heard_once"
    ]
   },
   "scorer": {
    "capabilities": {
     "authors": [
      "score"
     ],
     "judges": [],
     "may_chair": false,
     "may_speak": true,
     "may_synthesise": false,
     "may_veto": false,
     "may_vote": false,
     "votes_on": []
    },
    "obligations": [
     "apply_declared_scoring_rule"
    ],
    "permissions": [
     "publish_leaderboard"
    ],
    "rights": [
     "cannot_author_the_scored_forecast"
    ]
   },
   "synthesiser": {
    "capabilities": {
     "authors": [
      "synthesis"
     ],
     "judges": [],
     "may_chair": false,
     "may_speak": true,
     "may_synthesise": true,
     "may_veto": false,
     "may_vote": false,
     "votes_on": []
    },
    "obligations": [
     "produce_synthesis_covering_dissent"
    ],
    "permissions": [
     "compress_record"
    ],
    "rights": [
     "may_not_be_required_to_propose"
    ]
   }
  },
  "title": "Role-template library and the custom-role authoring contract"
 },
 "residual_unknowns": [
  {
   "claim": "Verbatim role lists inside 12-COUNCIL-PROTOCOLS-AND-PRESETS.json on the Windows harness-restore path.",
   "settling_experiment": "Place that library file on this tree and re-run coverage.py against its records instead of the catalog-cited census.",
   "verdict": "NOT-CHECKED"
  },
  {
   "claim": "CNL-0022 role-mandate schema and CNL-0029 incompatible-role solver artifacts on this worktree.",
   "settling_experiment": "Deliver those catalog output_path files and re-bind template capability fields to the mandate schema.",
   "verdict": "NOT-CHECKED"
  }
 ],
 "retry": {
  "count": 0,
  "policy": "two strikes then pivot: after the 2nd failure on the same hypothesis, enumerate >=2 alternative mechanisms before a 3rd attempt (AGENTS.md 4b)"
 },
 "reviewer": {
  "fresh_context": true,
  "independent": true,
  "notes": "Regex-extract P-ids from catalog questions; re-run authoring checks; jsonschema over the note with a disk $ref store. Does not read the author's answer field as the source of the counts.",
  "reviewer_id": "CNL-0028-probe2-catalog-regex-and-authoring",
  "verdict": "PASS"
 },
 "schema_version": 1,
 "sentinel": "SUCCESS:CNL-0028",
 "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:35679",
 "state": "SUCCESS",
 "tests": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0028/probe1_coverage.py",
   "id": "coverage",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0028/probe2_reviewer.py",
   "id": "authoring-negative",
   "result": "PASS"
  }
 ],
 "timestamps": {
  "ended_at": "2026-08-25T00:57:27Z",
  "started_at": "2026-08-25T00:57:27Z"
 },
 "unit_id": "CNL-0028"
}
