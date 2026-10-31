{
 "algorithm": {
  "id": "judicial-admissibility-gate",
  "inputs": [
   "protocol record_id in {P14..P19}",
   "run fixture: exhibits, rulings, officers, deciders, ballots"
  ],
  "outputs": [
   "admitted exhibit ids",
   "excluded exhibit ids plus invariant violations"
  ],
  "steps": [
   "Enumerate JUDICIAL members from catalog named ranging set and ranging_set.json (n=6).",
   "Apply the protocol's admissibility standard to each exhibit (content predicates).",
   "Admit only when the officer set, disjoint from deciders, issues the required ruling(s).",
   "Seal the admitted packet; decider ballots may cite admitted ids only.",
   "FIRE on GATEKEEPER_IS_DECIDER, OFFICER_CAST_VERDICT, SINGLE_KEY_ADMIT, HUNG_BROKEN_BY_OFFICER, or CHAIR_DECLARED_CONSENSUS."
  ]
 },
 "answer": "For the 6 JUDICIAL records P14-P19 the admissibility officer is never a decider. P14/P17: judge applies RELEVANCE_AND_RELIABILITY; jury decides (P17 may terminate HUNG). P15: claims-clerk applies ATOMIC_CITABLE_CLAIM; panel decides per admitted claim. P16: threshold-clerk applies PROBABLE_CAUSE_PACKET; grand jury true-bills. P18: two officers must both admit (DUAL_CONCURRENCE); dual-key deciders authorize. P19: last-call-chair applies IN_WINDOW_SPECIFIC_CITATION; participants count consensus. All 6 are EXECUTABLE. Family n=6 was re-derived from the catalog named ranging set and fixtures/ranging_set.json; 12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent on this worktree. SUCCESS:CNL-0040",
 "artifacts": [
  {
   "exists": true,
   "path": "command-center/design/council/CNL-0040-executable-runtime-semantics-for-the-6-judicial-protocols.md",
   "role": "primary"
  },
  {
   "exists": true,
   "path": "command-center/schema/council-design-note.schema.json",
   "role": "schema"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0040/council-design-note.schema.json",
   "role": "schema"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0040/fixtures/ranging_set.json",
   "role": "ranging-set"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0040/fixtures/runs.json",
   "role": "fixtures"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0040/runtime.py",
   "role": "runtime"
  }
 ],
 "both_states": {
  "bad": {
   "admitted": [
    "E-record"
   ],
   "excluded": [
    "E-hearsay"
   ],
   "fires": true,
   "ok": false,
   "verdict": "liable",
   "violations": [
    {
     "code": "GATEKEEPER_IS_DECIDER",
     "detail": [
      "judge-1"
     ]
    },
    {
     "code": "OFFICER_CAST_VERDICT",
     "detail": "judge-1"
    }
   ]
  },
  "extra_planted": {
   "all_fired": true,
   "cases": {
    "P17-judge-breaks-hung": {
     "codes": [
      "OFFICER_CAST_VERDICT",
      "HUNG_BROKEN_BY_OFFICER"
     ],
     "expected_code": "HUNG_BROKEN_BY_OFFICER",
     "fired": true
    },
    "P18-single-key-admit": {
     "codes": [
      "SINGLE_KEY_ADMIT",
      "DECIDER_SAW_EXCLUDED",
      "DECIDER_SAW_EXCLUDED"
     ],
     "expected_code": "SINGLE_KEY_ADMIT",
     "fired": true
    },
    "P19-chair-declares-consensus": {
     "codes": [
      "CHAIR_DECLARED_CONSENSUS"
     ],
     "expected_code": "CHAIR_DECLARED_CONSENSUS",
     "fired": true
    }
   }
  },
  "family_count": {
   "bad_n": 7,
   "fires_on_bad": true,
   "good_n": 6,
   "silent_on_good": true
  },
  "fires_on_bad": true,
  "good": {
   "admitted": [
    "E-record"
   ],
   "excluded": [
    "E-hearsay"
   ],
   "fires": false,
   "ok": true,
   "verdict": "liable",
   "violations": []
  },
  "id": "gatekeeper-vs-decider",
  "silent_on_good": true
 },
 "defaults": {
  "protocol": "P14-judge-and-jury",
  "roles": [
   "judge",
   "jury",
   "clerk",
   "advocate",
   "opponent"
  ],
  "stopping_rule": "ALL(decider_ballots_cast) AND NOT ANY(pending_objections)",
  "voting_method": "jury-ballot-on-admitted-only"
 },
 "dependencies_used": {
  "CNL-0001": "Records are addressable by P-id inside a CouncilSpec-shaped envelope.",
  "CNL-0010": "Stopping conditions are AND/OR/NOT/ALL/ANY expressions, not prose.",
  "CNL-0022": "Officer obligation/permission/right are distinct from decider mandate."
 },
 "enumeration": {
  "catalog_ids": [
   "P14",
   "P15",
   "P16",
   "P17",
   "P18",
   "P19"
  ],
  "expected_n": 6,
  "fixture_ids": [
   "P14",
   "P15",
   "P16",
   "P17",
   "P18",
   "P19"
  ],
  "library": {
   "ids": [],
   "mechanism": "library-file",
   "n": null,
   "path": null,
   "present": false
  },
  "match": true,
  "note": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent on this worktree. Family membership is the catalog named ranging set plus the independent ranging_set.json fixture. If the library appears, family.ranging_from_library requires family=JUDICIAL count==6."
 },
 "evidence": [
  {
   "anchor": "command-center/WORK-UNIT-CATALOG.json:36261",
   "claim": "Catalog evidence_requirement names JUDICIAL expected n=6.",
   "kind": "dossier",
   "line": 36261,
   "path": "command-center/WORK-UNIT-CATALOG.json",
   "snippet": "family=JUDICIAL, expected n=6",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/WORK-UNIT-CATALOG.json:36280",
   "claim": "Catalog question names the 6 JUDICIAL P-ids so none can fall through.",
   "kind": "dossier",
   "line": 36280,
   "path": "command-center/WORK-UNIT-CATALOG.json",
   "snippet": "P14 judge-and-jury, P15 claim-by-claim-adjudication, P16 grand-jury-threshold, P17 jury-with-allowed-hung, P18 two-key-dual-control, P19 rfc-last-call",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0040/fixtures/ranging_set.json:5",
   "claim": "Ranging-set fixture lists P14 as the first JUDICIAL member.",
   "kind": "live-tree",
   "line": 5,
   "path": "command-center/p2-wave/probes/CNL-0040/fixtures/ranging_set.json",
   "snippet": "\"id\": \"P14\"",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0040/runtime.py:272",
   "claim": "Runtime fires GATEKEEPER_IS_DECIDER when officer and decider sets intersect.",
   "kind": "live-tree",
   "line": 272,
   "path": "command-center/p2-wave/probes/CNL-0040/runtime.py",
   "snippet": "GATEKEEPER_IS_DECIDER",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0040/fixtures/runs.json:3",
   "claim": "Planted-bad fixture puts judge-1 in officers and deciders.",
   "kind": "live-tree",
   "line": 3,
   "path": "command-center/p2-wave/probes/CNL-0040/fixtures/runs.json",
   "snippet": "P14-gatekeeper-decides",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0040/runtime.py:93",
   "claim": "P17 records hung as a terminal state the judge must not break.",
   "kind": "live-tree",
   "line": 93,
   "path": "command-center/p2-wave/probes/CNL-0040/runtime.py",
   "snippet": "hung_is_terminal",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0040/fixtures/ranging_set.json:16",
   "claim": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json was read from this worktree.",
   "kind": "live-tree",
   "line": 16,
   "path": "command-center/p2-wave/probes/CNL-0040/fixtures/ranging_set.json",
   "snippet": "\"library_on_this_tree\": false",
   "verdict": "REFUTED"
  }
 ],
 "explanation_contract": {
  "dials": [
   "admissibility_standard_id",
   "officer_role",
   "decider_role",
   "stopping_expression"
  ],
  "missing_reason_fails": true,
  "owner_contest": "Owner may contest an exclude only by naming the failed predicate (relevance, reliability, atomicity, dual-key, or last-call window); a contest without a predicate fails closed."
 },
 "family": "JUDICIAL",
 "family_count": 6,
 "fixtures": [
  {
   "explanation": {
    "deciders": [
     "juror-a",
     "juror-b",
     "juror-c"
    ],
    "expected": "SILENT",
    "kind": "good",
    "officers": [
     "judge-1"
    ],
    "protocol_id": "P14"
   },
   "id": "P14-good",
   "risk_tier": "T1",
   "task_description": "Known-good P14 run: officer gates exhibits; deciders ballot admitted ids only; invariants silent."
  },
  {
   "explanation": {
    "deciders": [
     "panel-1",
     "panel-2"
    ],
    "expected": "SILENT",
    "kind": "good",
    "officers": [
     "claims-clerk"
    ],
    "protocol_id": "P15"
   },
   "id": "P15-good",
   "risk_tier": "T1",
   "task_description": "Known-good P15 run: officer gates exhibits; deciders ballot admitted ids only; invariants silent."
  },
  {
   "explanation": {
    "deciders": [
     "gj-1",
     "gj-2",
     "gj-3"
    ],
    "expected": "SILENT",
    "kind": "good",
    "officers": [
     "threshold-clerk"
    ],
    "protocol_id": "P16"
   },
   "id": "P16-good",
   "risk_tier": "T1",
   "task_description": "Known-good P16 run: officer gates exhibits; deciders ballot admitted ids only; invariants silent."
  },
  {
   "explanation": {
    "deciders": [
     "juror-a",
     "juror-b",
     "juror-c"
    ],
    "expected": "SILENT",
    "kind": "good",
    "officers": [
     "judge-1"
    ],
    "protocol_id": "P17"
   },
   "id": "P17-good-hung",
   "risk_tier": "T1",
   "task_description": "Known-good P17 run: officer gates exhibits; deciders ballot admitted ids only; invariants silent."
  },
  {
   "explanation": {
    "deciders": [
     "key-1",
     "key-2"
    ],
    "expected": "SILENT",
    "kind": "good",
    "officers": [
     "officer-a",
     "officer-b"
    ],
    "protocol_id": "P18"
   },
   "id": "P18-good",
   "risk_tier": "T1",
   "task_description": "Known-good P18 run: officer gates exhibits; deciders ballot admitted ids only; invariants silent."
  },
  {
   "explanation": {
    "deciders": [
     "p1",
     "p2"
    ],
    "expected": "SILENT",
    "kind": "good",
    "officers": [
     "chair-1"
    ],
    "protocol_id": "P19"
   },
   "id": "P19-good",
   "risk_tier": "T1",
   "task_description": "Known-good P19 run: officer gates exhibits; deciders ballot admitted ids only; invariants silent."
  },
  {
   "explanation": {
    "expected": "FIRE",
    "kind": "bad",
    "planted_defect": "GATEKEEPER_IS_DECIDER",
    "protocol_id": "P14"
   },
   "id": "P14-gatekeeper-decides",
   "risk_tier": "T3",
   "task_description": "Planted-bad P14-gatekeeper-decides: expect FIRE GATEKEEPER_IS_DECIDER."
  },
  {
   "explanation": {
    "expected": "FIRE",
    "kind": "bad",
    "planted_defect": "HUNG_BROKEN_BY_OFFICER",
    "protocol_id": "P17"
   },
   "id": "P17-judge-breaks-hung",
   "risk_tier": "T3",
   "task_description": "Planted-bad P17-judge-breaks-hung: expect FIRE HUNG_BROKEN_BY_OFFICER."
  },
  {
   "explanation": {
    "expected": "FIRE",
    "kind": "bad",
    "planted_defect": "SINGLE_KEY_ADMIT",
    "protocol_id": "P18"
   },
   "id": "P18-single-key-admit",
   "risk_tier": "T3",
   "task_description": "Planted-bad P18-single-key-admit: expect FIRE SINGLE_KEY_ADMIT."
  },
  {
   "explanation": {
    "expected": "FIRE",
    "kind": "bad",
    "planted_defect": "CHAIR_DECLARED_CONSENSUS",
    "protocol_id": "P19"
   },
   "id": "P19-chair-declares-consensus",
   "risk_tier": "T3",
   "task_description": "Planted-bad P19-chair-declares-consensus: expect FIRE CHAIR_DECLARED_CONSENSUS."
  }
 ],
 "format": "council-design-note+json",
 "negative_control": {
  "codes": [
   "GATEKEEPER_IS_DECIDER",
   "OFFICER_CAST_VERDICT"
  ],
  "fires": true,
  "fixture": "P14-gatekeeper-decides",
  "statement": "On planted-bad fixture P14-gatekeeper-decides the judge is in both officers and deciders and casts a verdict ballot. admissibility_invariants FIRES with GATEKEEPER_IS_DECIDER (and OFFICER_CAST_VERDICT). That is the state the check is meant to reject: an admissibility officer who becomes the decider.",
  "verbatim": "[{\"code\": \"GATEKEEPER_IS_DECIDER\", \"detail\": [\"judge-1\"]}, {\"code\": \"OFFICER_CAST_VERDICT\", \"detail\": \"judge-1\"}]",
  "violations": [
   {
    "code": "GATEKEEPER_IS_DECIDER",
    "detail": [
     "judge-1"
    ]
   },
   {
    "code": "OFFICER_CAST_VERDICT",
    "detail": "judge-1"
   }
  ]
 },
 "negative_controls": [
  {
   "fires_on_bad": true,
   "id": "P14-gatekeeper-decides",
   "rejects": "Judge in both officers and deciders who casts a verdict ballot; GATEKEEPER_IS_DECIDER.",
   "silent_on_good": true,
   "verbatim": "[{\"code\": \"GATEKEEPER_IS_DECIDER\", \"detail\": [\"judge-1\"]}, {\"code\": \"OFFICER_CAST_VERDICT\", \"detail\": \"judge-1\"}]"
  }
 ],
 "notes": "JSON stored at the catalog .md path because G-1 measure requires json.loads of output_path. Catalog output_schema is a $ref shim to ast-integrate.invalid and is not fetched. Live compile uses probes/CNL-0040/council-design-note.schema.json. Did not run unit_manifest.py --write.",
 "protocols": [
  {
   "admissibility_standard": "RELEVANCE_AND_RELIABILITY: an exhibit is admissible iff its claim_id is on the charged docket, source_kind is record|measurement|sworn-statement, and provenance_hash is present. Hearsay and argument fail the standard.",
   "admissibility_standard_id": "RELEVANCE_AND_RELIABILITY",
   "decider_role": "jury",
   "executable": true,
   "family": "JUDICIAL",
   "live_good_run": {
    "admitted": [
     "E-record"
    ],
    "excluded": [
     "E-hearsay"
    ],
    "fires": false,
    "ok": true,
    "record_id": "P14",
    "verdict": "liable",
    "violations": []
   },
   "missing_element": null,
   "officer_role": "judge",
   "record_id": "P14",
   "role_mandate": {
    "decider_obligation": "ballot only on admitted exhibits",
    "decider_permission": "none to admit or exclude",
    "officer_obligation": "must rule admit|exclude on every offered exhibit",
    "officer_permission": "may exclude exhibits that fail the standard",
    "officer_right": "must not be conscripted as a decider"
   },
   "separation": "The judge issues admit|exclude rulings and is forbidden from the decider set and from casting a verdict ballot. The jury sees only admitted exhibits.",
   "slug": "judge-and-jury",
   "stopping": {
    "expr": {
     "args": [
      {
       "op": "ALL",
       "var": "jury_ballots_cast"
      },
      {
       "args": [
        {
         "op": "ANY",
         "var": "pending_objections"
        }
       ],
       "op": "NOT"
      }
     ],
     "op": "AND"
    },
    "kind": "expression"
   },
   "turn_schedule": [
    {
     "action": "publish_charged_claims",
     "actor": "clerk",
     "id": "open-docket"
    },
    {
     "action": "offer_exhibits",
     "actor": "advocate",
     "id": "offer"
    },
    {
     "action": "optional_object",
     "actor": "opponent",
     "id": "object"
    },
    {
     "action": "rule_admissibility",
     "actor": "judge",
     "id": "rule"
    },
    {
     "action": "publish_admitted_only",
     "actor": "clerk",
     "id": "seal"
    },
    {
     "action": "cast_ballots_on_admitted",
     "actor": "jury",
     "id": "ballot"
    },
    {
     "action": "tally_excluding_judge",
     "actor": "clerk",
     "id": "tally"
    }
   ],
   "verdict": "P14 EXECUTABLE: standard=RELEVANCE_AND_RELIABILITY officer=judge decider=jury live_good_silent admitted=['E-record'] excluded=['E-hearsay']",
   "who_decides": "jury",
   "who_rules_on_admissibility": "judge"
  },
  {
   "admissibility_standard": "ATOMIC_CITABLE_CLAIM: a claim-exhibit is admissible iff it is atomic (atomic:true), cites a record_id, sits on the docket, and is not an argument.",
   "admissibility_standard_id": "ATOMIC_CITABLE_CLAIM",
   "decider_role": "panel",
   "executable": true,
   "family": "JUDICIAL",
   "live_good_run": {
    "admitted": [
     "E-atomic"
    ],
    "excluded": [
     "E-compound"
    ],
    "fires": false,
    "ok": true,
    "record_id": "P15",
    "verdict": "sustained",
    "violations": []
   },
   "missing_element": null,
   "officer_role": "claims-clerk",
   "record_id": "P15",
   "role_mandate": {
    "decider_obligation": "ballot only on admitted exhibits",
    "decider_permission": "none to admit or exclude",
    "officer_obligation": "must rule admit|exclude on every offered exhibit",
    "officer_permission": "may exclude exhibits that fail the standard",
    "officer_right": "must not be conscripted as a decider"
   },
   "separation": "The claims-clerk gates each claim. The panel ballots only admitted claims. The clerk is not a panel member and casts no claim ballot.",
   "slug": "claim-by-claim-adjudication",
   "stopping": {
    "expr": {
     "op": "ALL",
     "var": "admitted_claims_balloted_or_unresolved"
    },
    "kind": "expression"
   },
   "turn_schedule": [
    {
     "action": "list_atomic_claims",
     "actor": "clerk",
     "id": "docket-claims"
    },
    {
     "action": "admit_or_exclude_per_claim",
     "actor": "claims-clerk",
     "id": "gate"
    },
    {
     "action": "vote_admitted_claims_only",
     "actor": "panel",
     "id": "adjudicate"
    }
   ],
   "verdict": "P15 EXECUTABLE: standard=ATOMIC_CITABLE_CLAIM officer=claims-clerk decider=panel live_good_silent admitted=['E-atomic'] excluded=['E-compound']",
   "who_decides": "panel",
   "who_rules_on_admissibility": "claims-clerk"
  },
  {
   "admissibility_standard": "PROBABLE_CAUSE_PACKET: threshold evidence only \u2014 reliable kind plus provenance, threshold_only:true. Argument and full-proof advocacy are excluded from the true-bill packet.",
   "admissibility_standard_id": "PROBABLE_CAUSE_PACKET",
   "decider_role": "grand-jury",
   "executable": true,
   "family": "JUDICIAL",
   "live_good_run": {
    "admitted": [
     "E-threshold"
    ],
    "excluded": [
     "E-argument"
    ],
    "fires": false,
    "ok": true,
    "record_id": "P16",
    "verdict": "true-bill",
    "violations": []
   },
   "missing_element": null,
   "officer_role": "threshold-clerk",
   "record_id": "P16",
   "role_mandate": {
    "decider_obligation": "ballot only on admitted exhibits",
    "decider_permission": "none to admit or exclude",
    "officer_obligation": "must rule admit|exclude on every offered exhibit",
    "officer_permission": "may exclude exhibits that fail the standard",
    "officer_right": "must not be conscripted as a decider"
   },
   "separation": "The threshold-clerk seals the packet. The grand jury votes true-bill|no-bill on that packet. The clerk has no grand-jury ballot.",
   "slug": "grand-jury-threshold",
   "stopping": {
    "expr": {
     "op": "ALL",
     "var": "grand_jury_ballots_cast"
    },
    "kind": "expression"
   },
   "turn_schedule": [
    {
     "action": "offer_threshold_exhibits",
     "actor": "presenter",
     "id": "present"
    },
    {
     "action": "seal_probable_cause_packet",
     "actor": "threshold-clerk",
     "id": "pack"
    },
    {
     "action": "true_bill_or_no_bill",
     "actor": "grand-jury",
     "id": "bill"
    }
   ],
   "verdict": "P16 EXECUTABLE: standard=PROBABLE_CAUSE_PACKET officer=threshold-clerk decider=grand-jury live_good_silent admitted=['E-threshold'] excluded=['E-argument']",
   "who_decides": "grand-jury",
   "who_rules_on_admissibility": "threshold-clerk"
  },
  {
   "admissibility_standard": "Same RELEVANCE_AND_RELIABILITY as P14. Hung is a terminal protocol state, not a failure to decide.",
   "admissibility_standard_id": "RELEVANCE_AND_RELIABILITY",
   "decider_role": "jury",
   "executable": true,
   "family": "JUDICIAL",
   "live_good_run": {
    "admitted": [
     "E-record"
    ],
    "excluded": [],
    "fires": false,
    "ok": true,
    "record_id": "P17",
    "verdict": "HUNG",
    "violations": []
   },
   "missing_element": null,
   "officer_role": "judge",
   "record_id": "P17",
   "role_mandate": {
    "decider_obligation": "ballot only on admitted exhibits",
    "decider_permission": "none to admit or exclude",
    "officer_obligation": "must rule admit|exclude on every offered exhibit",
    "officer_permission": "may exclude exhibits that fail the standard",
    "officer_right": "must not be conscripted as a decider"
   },
   "separation": "After rounds_exhausted without unanimity the clerk records HUNG. The judge must not cast a tie-break ballot or substitute a verdict.",
   "slug": "jury-with-allowed-hung",
   "stopping": {
    "expr": {
     "args": [
      {
       "op": "ALL",
       "var": "jury_ballots_cast"
      },
      {
       "args": [
        {
         "op": "UNANIMOUS",
         "var": "jury_votes"
        },
        {
         "args": [
          {
           "var": "rounds_exhausted"
          }
         ],
         "op": "AND"
        }
       ],
       "op": "OR"
      }
     ],
     "op": "AND"
    },
    "kind": "expression"
   },
   "turn_schedule": [
    {
     "action": "publish_charged_claims",
     "actor": "clerk",
     "id": "open-docket"
    },
    {
     "action": "rule_admissibility",
     "actor": "judge",
     "id": "rule"
    },
    {
     "action": "cast_ballots_on_admitted",
     "actor": "jury",
     "id": "ballot"
    },
    {
     "action": "record_hung_if_not_unanimous",
     "actor": "clerk",
     "id": "hung-or-verdict"
    }
   ],
   "verdict": "P17 EXECUTABLE: standard=RELEVANCE_AND_RELIABILITY officer=judge decider=jury live_good_silent admitted=['E-record'] excluded=[]",
   "who_decides": "jury",
   "who_rules_on_admissibility": "judge"
  },
  {
   "admissibility_standard": "DUAL_CONCURRENCE: content must pass RELEVANCE_AND_RELIABILITY AND two distinct officers must both admit. A single-key admit fail-closes to exclude.",
   "admissibility_standard_id": "DUAL_CONCURRENCE",
   "decider_role": "dual-key-deciders",
   "executable": true,
   "family": "JUDICIAL",
   "live_good_run": {
    "admitted": [
     "E-record"
    ],
    "excluded": [
     "E-hearsay"
    ],
    "fires": false,
    "ok": true,
    "record_id": "P18",
    "verdict": "authorize",
    "violations": []
   },
   "missing_element": null,
   "officer_role": "officer-pair",
   "record_id": "P18",
   "role_mandate": {
    "decider_obligation": "ballot only on admitted exhibits",
    "decider_permission": "none to admit or exclude",
    "officer_obligation": "must rule admit|exclude on every offered exhibit",
    "officer_permission": "may exclude exhibits that fail the standard",
    "officer_right": "must not be conscripted as a decider"
   },
   "separation": "Neither officer is a decider. Verdict keys are a disjoint pair. Dual control applies to admission and to authorization.",
   "slug": "two-key-dual-control",
   "stopping": {
    "expr": {
     "args": [
      {
       "op": "ALL",
       "var": "dual_key_ballots_cast"
      },
      {
       "op": "ALL",
       "var": "exhibits_have_two_officer_rulings"
      }
     ],
     "op": "AND"
    },
    "kind": "expression"
   },
   "turn_schedule": [
    {
     "action": "offer_exhibits",
     "actor": "requestor",
     "id": "offer"
    },
    {
     "action": "independent_admit_or_exclude",
     "actor": "officer-a",
     "id": "key-a"
    },
    {
     "action": "independent_admit_or_exclude",
     "actor": "officer-b",
     "id": "key-b"
    },
    {
     "action": "admit_iff_both_admit",
     "actor": "runtime",
     "id": "concur"
    },
    {
     "action": "two_key_verdict",
     "actor": "dual-deciders",
     "id": "authorize"
    }
   ],
   "verdict": "P18 EXECUTABLE: standard=DUAL_CONCURRENCE officer=officer-pair decider=dual-key-deciders live_good_silent admitted=['E-record'] excluded=['E-hearsay']",
   "who_decides": "dual-key deciders",
   "who_rules_on_admissibility": "officer-a and officer-b (pair)"
  },
  {
   "admissibility_standard": "IN_WINDOW_SPECIFIC_CITATION: an objection is in-scope iff timestamp is inside the last-call window, section_id is present, and claim_id is specific.",
   "admissibility_standard_id": "IN_WINDOW_SPECIFIC_CITATION",
   "decider_role": "participants",
   "executable": true,
   "family": "JUDICIAL",
   "live_good_run": {
    "admitted": [
     "O-inwindow"
    ],
    "excluded": [
     "O-bare"
    ],
    "fires": false,
    "ok": true,
    "record_id": "P19",
    "verdict": "consensus",
    "violations": []
   },
   "missing_element": null,
   "officer_role": "last-call-chair",
   "record_id": "P19",
   "role_mandate": {
    "decider_obligation": "ballot only on admitted exhibits",
    "decider_permission": "none to admit or exclude",
    "officer_obligation": "must rule admit|exclude on every offered exhibit",
    "officer_permission": "may exclude exhibits that fail the standard",
    "officer_right": "must not be conscripted as a decider"
   },
   "separation": "The chair rules in-scope|out-of-scope only. Consensus is counted among participants. A chair consensus_call is CHAIR_DECLARED_CONSENSUS.",
   "slug": "rfc-last-call",
   "stopping": {
    "expr": {
     "args": [
      {
       "var": "window_closed"
      },
      {
       "op": "ALL",
       "var": "in_scope_objections_addressed_or_recorded"
      }
     ],
     "op": "AND"
    },
    "kind": "expression"
   },
   "turn_schedule": [
    {
     "action": "publish_last_call_window",
     "actor": "editor",
     "id": "open-window"
    },
    {
     "action": "file_objections",
     "actor": "participants",
     "id": "object"
    },
    {
     "action": "rule_objection_in_or_out_of_scope",
     "actor": "chair",
     "id": "scope"
    },
    {
     "action": "close_window",
     "actor": "editor",
     "id": "close"
    },
    {
     "action": "count_consensus_without_chair_vote",
     "actor": "participants",
     "id": "consensus"
    }
   ],
   "verdict": "P19 EXECUTABLE: standard=IN_WINDOW_SPECIFIC_CITATION officer=last-call-chair decider=participants live_good_silent admitted=['O-inwindow'] excluded=['O-bare']",
   "who_decides": "participants",
   "who_rules_on_admissibility": "last-call-chair"
  }
 ],
 "question": "Ranging over exactly these 6 records, named so no member can fall through a family mis-assignment (P14 judge-and-jury, P15 claim-by-claim-adjudication, P16 grand-jury-threshold, P17 jury-with-allowed-hung, P18 two-key-dual-control, P19 rfc-last-call): For each of the 6 JUDICIAL protocol records, what is the admissibility standard for evidence and who rules on admissibility without becoming the decider?",
 "report": {
  "control_ids": [
   "gatekeeper-vs-decider",
   "family-count-n6",
   "P14-gatekeeper-decides",
   "P17-judge-breaks-hung",
   "P18-single-key-admit",
   "P19-chair-declares-consensus"
  ],
  "kind": "council-design-note",
  "observations": [
   {
    "anchor": "command-center/p2-wave/probes/CNL-0040/fixtures/ranging_set.json:1",
    "measured": 6,
    "method": "catalog-question-regex plus ranging_set.json",
    "name": "judicial_family_n"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0040/runtime.py:GATEKEEPER_IS_DECIDER",
    "measured": true,
    "method": "runtime.execute_named good/P14",
    "name": "gatekeeper_silent_on_good"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0040/fixtures/runs.json:P14-gatekeeper-decides",
    "measured": true,
    "method": "runtime.execute_named bad/P14-gatekeeper-decides",
    "name": "gatekeeper_fires_on_bad"
   }
  ]
 },
 "reviewer": {
  "ids": {
   "catalog": [
    "P14",
    "P15",
    "P16",
    "P17",
    "P18",
    "P19"
   ],
   "fixture": [
    "P14",
    "P15",
    "P16",
    "P17",
    "P18",
    "P19"
   ],
   "semantics": [
    "P14",
    "P15",
    "P16",
    "P17",
    "P18",
    "P19"
   ]
  },
  "independent": true,
  "method": "Regex-parse CNL-0040 question_or_target P-ids; JSON-load ranging_set.json members; list runtime.PROTOCOLS keys; list artifact.protocols[].record_id. Compare sets and counts. Does not read answer prose.",
  "numbers": {
   "artifact_family_count": 6,
   "artifact_n": 6,
   "catalog_n": 6,
   "expected_n": 6,
   "fixture_n": 6,
   "semantics_n": 6
  },
  "reviewer_id": "CNL-0040-independent-recount",
  "scope_not_agreement": true,
  "verdict": "PASS"
 },
 "schema_version": 1,
 "sentinel": "SUCCESS:CNL-0040",
 "state": "SUCCESS",
 "strongest_surviving_counterargument": "The original 12-COUNCIL library might assign a seventh record to JUDICIAL or might have encoded a different officer for P18. That counterargument survives as a library-absent residual. It does not change the catalog named ranging set of six P-ids this unit is required to range over, and the library probe is live if the file appears.",
 "tests": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0040/probe1_family_schedules.py",
   "id": "T1-family-schedules",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0040/probe2_both_states.py",
   "id": "T2-both-states-negative-recount",
   "result": "PASS"
  }
 ],
 "title": "Executable runtime semantics for the 6 JUDICIAL protocols",
 "ts": "2026-08-25T00:57:53Z",
 "unit_id": "CNL-0040"
}
