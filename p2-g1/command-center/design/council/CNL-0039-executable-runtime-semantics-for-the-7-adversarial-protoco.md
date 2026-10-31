{
 "answer": "For each of P07-P13 the attack is real only when the attacking role emits a protocol-specific artifact a cooperative participant cannot fake: P07 clash_ledger bound to proposition speech hashes; P08 exploit_repro whose needle makes the Blue-artifact oracle fail; P09 contradiction_witness as syntactic NOT(claim); P10 steelman_opposite whose bytes differ from the majority draft; P11 discrepancy_table with at least one unequal key_judgment matching both estimates; P12 preregistered_falsifier with incompatible signed predictions; P13 pin_exhibit pairing two witness hashes in syntactic negation. All 7 records have executable turn schedules. The seven artifact kinds are distinct (no mechanism-duplicate).",
 "artifacts": [
  {
   "exists": true,
   "path": "command-center/design/council/CNL-0039-executable-runtime-semantics-for-the-7-adversarial-protoco.md",
   "role": "primary"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0039/fixtures/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/schema/council-design-note.schema.json",
   "role": "supporting"
  }
 ],
 "completion_sentinel": "SUCCESS:CNL-0039",
 "dependencies_on_this_tree": {
  "CNL-0001": false,
  "CNL-0010": false,
  "CNL-0022": false,
  "note": "CouncilSpec v2 / stopping grammar / role-mandate artifacts are absent. This unit's ranging set and attack-real checker do not wait on those files (no ADV rebuild circle)."
 },
 "enumeration": {
  "expected_n": 7,
  "fixture_count": 7,
  "fixture_protocol_total": 58,
  "ids": [
   "P07",
   "P08",
   "P09",
   "P10",
   "P11",
   "P12",
   "P13"
  ],
  "independent_count": 7,
  "slugs": [
   "oxford-debate",
   "red-blue-team",
   "dialectical-inquiry",
   "mandated-devils-advocate",
   "team-b-competitive-estimate",
   "adversarial-collaboration",
   "hostile-cross-examination"
  ],
  "source": "command-center/p2-wave/probes/CNL-0039/fixtures/12-COUNCIL-PROTOCOLS-AND-PRESETS.json filter family=ADVERSARIAL; cross-checked by regex parse of CNL-0039 question_or_target",
  "windows_library_path": "C:/Users/Prekzursil/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
  "windows_library_present": false
 },
 "evidence": [
  {
   "anchor": "command-center/p2-wave/probes/CNL-0039/fixtures/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
   "claim": "ADVERSARIAL family membership is 7 records P07-P13 when the stand-in catalogue is filtered on family=ADVERSARIAL.",
   "signal": {
    "anchor": "command-center/p2-wave/probes/CNL-0039/fixtures/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    "kind": "file_line"
   },
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=CNL-0039]",
   "claim": "The same 7 P-ids are independently recoverable from the CNL-0039 question_or_target ranging list in WORK-UNIT-CATALOG.json.",
   "signal": {
    "anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=CNL-0039]",
    "kind": "file_line"
   },
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0039/runtime.py",
   "claim": "Each of the 7 records has an executable turn schedule in runtime.SCHEDULES; none is NOT-EXECUTABLE.",
   "signal": {
    "anchor": "command-center/p2-wave/probes/CNL-0039/runtime.py",
    "kind": "file_line"
   },
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0039/probe2_both_states.py",
   "claim": "The attack-real check is SILENT on known-good transcripts and FIRES on planted cooperative-fake transcripts for all 7 ids.",
   "signal": {
    "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0039/probe2_both_states.py",
    "kind": "command_output",
    "output": "fired_on_bad=True silent_on_good=True"
   },
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "enumeration.windows_library_present",
   "claim": "The original 12-COUNCIL-PROTOCOLS-AND-PRESETS.json was read from the Windows harness-restore path on this worktree.",
   "signal": {
    "anchor": "enumeration.windows_library_present=false",
    "kind": "file_line"
   },
   "verdict": "REFUTED"
  }
 ],
 "family": "ADVERSARIAL",
 "family_count": 7,
 "format": "council-design-note+json",
 "manifest_registration": {
  "global_catalog_write": false,
  "manifest_path": "command-center/p2-wave/probes/CNL-0039/UNIT-ARTIFACT-MANIFEST.json",
  "registered": true
 },
 "min_bytes_threshold": 2048,
 "named_probes": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0039/probe1_family_schedule.py",
   "id": "probe1",
   "role": "independent-family-recount"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0039/probe2_both_states.py",
   "id": "probe2",
   "role": "both-states-attack-real"
  }
 ],
 "negative_controls": [
  {
   "bad_state_output": "PERFORMED-ATTACK fired=true violations=[\"unbound-quote\",\"no-bound-clash\"]",
   "check_does_on_reject_state": "Emits fired=true verdict=PERFORMED-ATTACK violations=[\"unbound-quote\",\"no-bound-clash\"]",
   "description": "Planted-bad oxford-debate clash_ledger cites sha256 of text that was never a proposition speech. The check must FIRE PERFORMED-ATTACK, not stay silent.",
   "fired_on_bad_state": true,
   "good_state_output": "REAL-ATTACK silent=true violations=[]",
   "id": "CNL0039-C1",
   "kind": "known-broken-fixture",
   "protocol_id": "P07",
   "rejects": "Planted-bad oxford-debate clash_ledger whose quoted_sha256 does not bind to any proposition speech",
   "silent_on_good_state": true
  }
 ],
 "produced_by": {
  "execution_substrate": "headless-linux",
  "model": "grok-4.6",
  "role": "council-systems-designer",
  "vendor": "cursor"
 },
 "question": "Ranging over exactly these 7 records, named so no member can fall through a family mis-assignment (P07 oxford-debate, P08 red-blue-team, P09 dialectical-inquiry, P10 mandated-devils-advocate, P11 team-b-competitive-estimate, P12 adversarial-collaboration, P13 hostile-cross-examination): For each of the 7 ADVERSARIAL protocol records, what enforcement makes the attack real rather than performed - specifically, what artifact must the attacking role produce that a cooperative participant could not fake?",
 "records": [
  {
   "attacking_role": "opposition",
   "both_states": {
    "known_good": {
     "fired": false,
     "silent": true,
     "verdict": "REAL-ATTACK",
     "violations": []
    },
    "planted_bad": {
     "fired": true,
     "silent": false,
     "verdict": "PERFORMED-ATTACK",
     "violations": [
      "unbound-quote",
      "no-bound-clash"
     ]
    }
   },
   "family": "ADVERSARIAL",
   "id": "P07",
   "missing_element": null,
   "slug": "oxford-debate",
   "source_unit": "CNL-0039",
   "turn_schedule": [
    "proposition",
    "opposition",
    "proposition",
    "opposition"
   ],
   "unfakeable_artifact": {
    "cooperative_fake": "Saying 'I disagree' or posting ledger hashes that do not bind to proposition utterances. A cooperative partner can perform dissent without ever quoting the other side.",
    "enforcement": "runtime._p07 requires at least one bound clash; unbound-quote and defeater-restates-prop fire PERFORMED-ATTACK.",
    "kind": "clash_ledger",
    "must_produce": "Opposition must emit clash_ledger rows whose quoted_sha256 equals sha256 of an actual proposition speech and whose defeater text is not a restatement of that speech."
   },
   "verdict": "EXECUTABLE"
  },
  {
   "attacking_role": "red",
   "both_states": {
    "known_good": {
     "fired": false,
     "silent": true,
     "verdict": "REAL-ATTACK",
     "violations": []
    },
    "planted_bad": {
     "fired": true,
     "silent": false,
     "verdict": "PERFORMED-ATTACK",
     "violations": [
      "oracle-did-not-fail"
     ]
    }
   },
   "family": "ADVERSARIAL",
   "id": "P08",
   "missing_element": null,
   "slug": "red-blue-team",
   "source_unit": "CNL-0039",
   "turn_schedule": [
    "blue",
    "red",
    "referee"
   ],
   "unfakeable_artifact": {
    "cooperative_fake": "Narrating a vulnerability whose needle is absent from the artifact. Theater does not make the oracle fail.",
    "enforcement": "runtime._p08 fires oracle-did-not-fail when needle not in blue_artifact.",
    "kind": "exploit_repro",
    "must_produce": "Red must emit exploit_repro.needle that occurs inside Blue's current artifact body (oracle FAIL on the live bytes)."
   },
   "verdict": "EXECUTABLE"
  },
  {
   "attacking_role": "antithesis",
   "both_states": {
    "known_good": {
     "fired": false,
     "silent": true,
     "verdict": "REAL-ATTACK",
     "violations": []
    },
    "planted_bad": {
     "fired": true,
     "silent": false,
     "verdict": "PERFORMED-ATTACK",
     "violations": [
      "witness-not-negation"
     ]
    }
   },
   "family": "ADVERSARIAL",
   "id": "P09",
   "missing_element": null,
   "slug": "dialectical-inquiry",
   "source_unit": "CNL-0039",
   "turn_schedule": [
    "thesis",
    "antithesis",
    "thesis"
   ],
   "unfakeable_artifact": {
    "cooperative_fake": "Offering a compatible 'another view' (form=also) that does not negate any thesis claim.",
    "enforcement": "runtime._p09 fires witness-not-negation / antithesis-text-not-negation.",
    "kind": "contradiction_witness",
    "must_produce": "Antithesis must emit a witness {negates, form:not, of} bound to a named thesis claim, and the antithesis turn text must be NOT(claim)."
   },
   "verdict": "EXECUTABLE"
  },
  {
   "attacking_role": "devil",
   "both_states": {
    "known_good": {
     "fired": false,
     "silent": true,
     "verdict": "REAL-ATTACK",
     "violations": []
    },
    "planted_bad": {
     "fired": true,
     "silent": false,
     "verdict": "PERFORMED-ATTACK",
     "violations": [
      "devil-restates-majority"
     ]
    }
   },
   "family": "ADVERSARIAL",
   "id": "P10",
   "missing_element": null,
   "slug": "mandated-devils-advocate",
   "source_unit": "CNL-0039",
   "turn_schedule": [
    "majority",
    "devil",
    "majority"
   ],
   "unfakeable_artifact": {
    "cooperative_fake": "Token dissent that restates the majority draft (same bytes / same hash).",
    "enforcement": "runtime._p10 fires devil-restates-majority.",
    "kind": "steelman_opposite",
    "must_produce": "Devil must emit steelman_opposite bound to the majority draft hash and to devil-turn bytes that are not the majority text."
   },
   "verdict": "EXECUTABLE"
  },
  {
   "attacking_role": "team_b",
   "both_states": {
    "known_good": {
     "fired": false,
     "silent": true,
     "verdict": "REAL-ATTACK",
     "violations": []
    },
    "planted_bad": {
     "fired": true,
     "silent": false,
     "verdict": "PERFORMED-ATTACK",
     "violations": [
      "no-actual-discrepancy"
     ]
    }
   },
   "family": "ADVERSARIAL",
   "id": "P11",
   "missing_element": null,
   "slug": "team-b-competitive-estimate",
   "source_unit": "CNL-0039",
   "turn_schedule": [
    "team_a",
    "team_b",
    "comparator"
   ],
   "unfakeable_artifact": {
    "cooperative_fake": "A same-estimate paraphrase with an empty or all-equal table, or a forged table that does not match the estimate maps.",
    "enforcement": "runtime._p11 fires no-actual-discrepancy or discrepancy-does-not-match-estimates.",
    "kind": "discrepancy_table",
    "must_produce": "Team B must emit a discrepancy_table whose cells match both estimates and contain at least one key_judgment where team_a != team_b."
   },
   "verdict": "EXECUTABLE"
  },
  {
   "attacking_role": "side_no",
   "both_states": {
    "known_good": {
     "fired": false,
     "silent": true,
     "verdict": "REAL-ATTACK",
     "violations": []
    },
    "planted_bad": {
     "fired": true,
     "silent": false,
     "verdict": "PERFORMED-ATTACK",
     "violations": [
      "compatible-predictions"
     ]
    }
   },
   "family": "ADVERSARIAL",
   "id": "P12",
   "missing_element": null,
   "slug": "adversarial-collaboration",
   "source_unit": "CNL-0039",
   "turn_schedule": [
    "side_yes",
    "side_no",
    "registrar"
   ],
   "unfakeable_artifact": {
    "cooperative_fake": "A 'test' both sides win because the predictions are identical.",
    "enforcement": "runtime._p12 fires compatible-predictions.",
    "kind": "preregistered_falsifier",
    "must_produce": "The attacking side (side_no) jointly seals a preregistered_falsifier with incompatible signed predictions (yes_prediction != no_prediction) and recomputable role signatures."
   },
   "verdict": "EXECUTABLE"
  },
  {
   "attacking_role": "examiner",
   "both_states": {
    "known_good": {
     "fired": false,
     "silent": true,
     "verdict": "REAL-ATTACK",
     "violations": []
    },
    "planted_bad": {
     "fired": true,
     "silent": false,
     "verdict": "PERFORMED-ATTACK",
     "violations": [
      "pin-same-statement",
      "pin-relation-not-contradicts",
      "pin-not-syntactic-negation"
     ]
    }
   },
   "family": "ADVERSARIAL",
   "id": "P13",
   "missing_element": null,
   "slug": "hostile-cross-examination",
   "source_unit": "CNL-0039",
   "turn_schedule": [
    "witness",
    "examiner",
    "witness",
    "examiner"
   ],
   "unfakeable_artifact": {
    "cooperative_fake": "Hostile tone, loaded questions, or a pin that cites the same statement twice / relation=clarifies.",
    "enforcement": "runtime._p13 fires pin-same-statement / pin-not-syntactic-negation.",
    "kind": "pin_exhibit",
    "must_produce": "Examiner must emit pin_exhibit pairing two distinct witness utterance hashes whose texts are syntactic negations (NOT(x) vs x)."
   },
   "verdict": "EXECUTABLE"
  }
 ],
 "report": {
  "control_ids": [
   "CNL0039-C1"
  ],
  "kind": "council-design-note",
  "observations": [
   {
    "anchor": "command-center/p2-wave/probes/CNL-0039/fixtures/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    "measured": 7,
    "method": "filter fixture protocols where family=ADVERSARIAL",
    "name": "adversarial-family-count"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0039/runtime.py",
    "measured": 7,
    "method": "runtime.verdict_for for each P07-P13",
    "name": "executable-schedules"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0039/probe2_both_states.py",
    "measured": "fired_on_bad=True silent_on_good=True",
    "method": "runtime.check_transcript on transcripts.all_good/all_bad",
    "name": "attack-real-both-states"
   }
  ]
 },
 "residual_unknowns": [
  {
   "claim": "Byte-identity of this 58-record stand-in against the missing harness-restore 12-COUNCIL-PROTOCOLS-AND-PRESETS.json bodies (roles, stopping prose, original field names).",
   "settling_experiment": "Place the harness-restore library on disk and re-run family filter family=ADVERSARIAL; disagreement in n or ids blocks.",
   "verdict": "NOT-CHECKED"
  }
 ],
 "retry": {
  "count": 0,
  "policy": "two strikes then pivot: after two failed attempts on the same framing, enumerate at least two alternative decompositions before a third attempt (AGENTS.md 4b)"
 },
 "reviewer": {
  "counterexample": {
   "attempted": true,
   "id": "P07-unbound-clash-ledger",
   "note": "The cooperative-fake clash_ledger was submitted as a counterexample to 'attack theater still passes'. The checker rejected it (PERFORMED-ATTACK). That does not refute the design; it is the required negative control.",
   "refutes": false
  },
  "fresh_context": true,
  "independent": true,
  "method": "probe1 re-filters the frozen 58-protocol fixture on family=ADVERSARIAL and re-parses CNL-0039 question_or_target; a disagreement in the id set or in family_count blocks the unit. It does not read this answer paragraph as evidence.",
  "reviewer_id": "CNL-0039-probe1-independent-recount",
  "scope_not_agreement": true,
  "verdict": "PASS"
 },
 "schema_version": 1,
 "sentinel": "SUCCESS:CNL-0039",
 "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=CNL-0039]",
 "state": "SUCCESS",
 "tests": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0039/probe1_family_schedule.py",
   "id": "T1-family-count-and-schedules",
   "name": "Independent recount of family=ADVERSARIAL against the fixture and the catalog ranging list; every record has an executable turn schedule",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0039/probe2_both_states.py",
   "id": "T2-both-states-attack-real",
   "name": "Both-states: check FIRES on planted-bad cooperative fakes and is SILENT on known-good transcripts; family-count plant drops n",
   "result": "PASS"
  }
 ],
 "timestamps": {
  "ended_at": "2026-08-25T00:53:48Z",
  "started_at": "2026-08-24T18:33:00Z"
 },
 "title": "Executable runtime semantics for the 7 ADVERSARIAL protocols",
 "unit_id": "CNL-0039"
}
